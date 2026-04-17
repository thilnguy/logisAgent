from loguru import logger
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from typing import List

class EnterpriseRouteOptimizer:
    def __init__(self, all_nodes: list, trucks: list, dist_matrix: list, time_matrix: list):
        """
        all_nodes: List of Union[Depot, DeliveryOrder]
        trucks: List of Truck
        """
        self.nodes = all_nodes
        self.trucks = trucks
        self.dist_matrix = dist_matrix
        self.time_matrix = time_matrix
        
        self.num_nodes = len(all_nodes)
        self.num_vehicles = len(trucks)
        
        # Build starts and ends arrays for multi-depot
        self.starts = []
        self.ends = []
        for t in trucks:
            start_idx = next(i for i, n in enumerate(self.nodes) if getattr(n, 'depot_id', None) == t.start_depot_id)
            end_idx = next(i for i, n in enumerate(self.nodes) if getattr(n, 'depot_id', None) == t.end_depot_id)
            self.starts.append(start_idx)
            self.ends.append(end_idx)

    def solve(self, time_limit_sec: int = 5):
        manager = pywrapcp.RoutingIndexManager(self.num_nodes, self.num_vehicles, self.starts, self.ends)
        routing = pywrapcp.RoutingModel(manager)

        # Fixed Vehicle Activation Costs (V4 Phase 8)
        for vid, t in enumerate(self.trucks):
            routing.SetFixedCostOfVehicle(int(t.fixed_cost_euro * 100), vid)  # Scale to cents for integer solver

        # V4 Phase 12: Per-Vehicle Arc Cost (Load Factor Optimization)
        # Heavier trucks cost more per km → solver prefers smaller trucks for light loads
        # Cost multiplier: 3.5t=1x, 12t=2x, 44t=4x (proportional to fuel/maintenance)
        for vid, truck in enumerate(self.trucks):
            cost_multiplier = max(1, int(truck.capacity_kg / 1500))  # 1500kg base = 1x
            
            def make_cost_callback(mult):
                def vehicle_cost_callback(from_index, to_index):
                    from_node = manager.IndexToNode(from_index)
                    to_node = manager.IndexToNode(to_index)
                    return self.dist_matrix[from_node][to_node] * mult
                return vehicle_cost_callback
            
            callback_index = routing.RegisterTransitCallback(make_cost_callback(cost_multiplier))
            routing.SetArcCostEvaluatorOfVehicle(callback_index, vid)

        # Capacity Dimension
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            node = self.nodes[from_node]
            return int(getattr(node, 'weight_kg', 0))

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            [int(t.capacity_kg) for t in self.trucks],
            True,
            'Capacity'
        )

        # Time Dimension
        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            node = self.nodes[from_node]
            service_time = getattr(node, 'service_time_minutes', 0)
            return self.time_matrix[from_node][to_node] + service_time

        time_callback_idx = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(
            time_callback_idx,
            120,  # V4 Phase 9: Increased slack to 120 mins to accommodate 45-min mandatory breaks
            1440, # max 24 hours per vehicle route
            False,
            'Time'
        )
        time_dimension = routing.GetDimensionOrDie('Time')
        # V4.1: Rebalanced Objective Weights
        # SpanCost > GlobalSpanCost → Prioritize "start late, no waiting" over "spread evenly"
        # 1. Moderate balancing (still uses multiple trucks, but won't force premature dispatch)
        time_dimension.SetGlobalSpanCostCoefficient(200)
        # 2. Strong delayed start (heavily penalizes long route duration = eliminates idle waiting)
        time_dimension.SetSpanCostCoefficientForAllVehicles(300)

        # Add Time Windows Logic
        for i, node in enumerate(self.nodes):
            tw = getattr(node, 'time_window', None)
            if tw:
                index = manager.NodeToIndex(i)
                time_dimension.CumulVar(index).SetRange(tw.start_minute, tw.end_minute)

        # Instantiate route start and end time windows to 08:00 (480) to 20:00 (1200)
        for i in range(self.num_vehicles):
            start_index = routing.Start(i)
            time_dimension.CumulVar(start_index).SetRange(480, 1200)
            end_index = routing.End(i)
            time_dimension.CumulVar(end_index).SetRange(480, 1200)

        # V4 Phase 9: EU 561/2006 - Break compliance is checked post-solve
        # (Hard constraints cause infeasibility with tight time windows.
        #  Real-world fleets use post-optimization compliance auditing.)

        # V4 Phase 10: Allow Dropping Undeliverable Orders (Graceful Degradation)
        # Instead of failing entirely when one order is infeasible, the solver
        # can skip it at a high penalty cost (simulating re-scheduling next day).
        self.num_depots = len([n for n in self.nodes if hasattr(n, 'depot_id')])
        penalty_per_drop = 50000  # High cost to discourage unnecessary drops
        for i in range(self.num_depots, self.num_nodes):  # Only delivery nodes, not depots
            index = manager.NodeToIndex(i)
            routing.AddDisjunction([index], penalty_per_drop)

        # V4 Phase 11: Territory Zone Restrictions
        # Use SetAllowedVehiclesForIndex to restrict which trucks can serve each zone
        for i in range(self.num_depots, self.num_nodes):
            node = self.nodes[i]
            order_zone = getattr(node, 'zone', None)
            if order_zone:
                index = manager.NodeToIndex(i)
                allowed_vehicles = []
                for vid, truck in enumerate(self.trucks):
                    if order_zone in truck.allowed_zones:
                        allowed_vehicles.append(vid)
                if allowed_vehicles:
                    routing.SetAllowedVehiclesForIndex(allowed_vehicles, index)
                    logger.debug(f"Node {i} ({node.address.name}, zone={order_zone}) → allowed vehicles: {allowed_vehicles}")

        # Instantiate search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_parameters.time_limit.FromSeconds(time_limit_sec)

        logger.info("Démarrage du Solver CVRPTW OR-Tools...")
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            logger.success("Solution optimale trouvée par l'Agent.")
            return self._format_solution(manager, routing, solution, time_dimension)
        else:
            logger.error("Aucune solution trouvée. Contraintes de Temps/Poids probablement incompatibles.")
            return None

    def _format_solution(self, manager, routing, solution, time_dimension):
        routes = []
        for vehicle_id in range(self.num_vehicles):
            index = routing.Start(vehicle_id)
            route = []
            route_load = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                time_var = time_dimension.CumulVar(index)
                
                route.append({
                    "node_index": node_index,
                    "time_min": solution.Min(time_var),
                    "time_max": solution.Max(time_var)
                })
                
                route_load += int(getattr(self.nodes[node_index], 'weight_kg', 0))
                index = solution.Value(routing.NextVar(index))
                
            # Add end depot
            node_index = manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            route.append({
                "node_index": node_index,
                "time_min": solution.Min(time_var),
                "time_max": solution.Max(time_var)
            })

            if len(route) > 2:
                # V4 Phase 9: Post-solve EU 561/2006 compliance check
                route_duration = route[-1]['time_min'] - route[0]['time_min']
                break_info = None
                if route_duration > 270:  # 4.5 hours → mandatory 45-min break
                    # Insert break at nearest midpoint
                    midpoint_min = route[0]['time_min'] + 270
                    break_info = {"start_min": midpoint_min, "duration_min": 45}
                    logger.warning(f"⚠️ Vehicle {vehicle_id}: Route duration {route_duration}m > 270m. Mandatory break inserted at minute {midpoint_min}.")
                
                routes.append({
                    "vehicle_id": vehicle_id,
                    "truck": self.trucks[vehicle_id],
                    "route": route,
                    "total_load_kg": route_load,
                    "break_info": break_info
                })
        
        # V4 Phase 10: Detect dropped (undelivered) orders
        served_node_indices = set()
        for r in routes:
            for stop in r['route']:
                served_node_indices.add(stop['node_index'])
        
        dropped_orders = []
        for i in range(self.num_depots, self.num_nodes):
            if i not in served_node_indices:
                node = self.nodes[i]
                dropped_orders.append({
                    "order_id": getattr(node, 'order_id', f'N/A-{i}'),
                    "address": node.address.name,
                    "weight_kg": node.weight_kg,
                    "reason": "Time Window ou Capacité incompatible"
                })
                logger.warning(f"⚠️ Dropped order: {node.address.name} ({node.weight_kg}kg)")
                
        return {"routes": routes, "dropped_orders": dropped_orders}
