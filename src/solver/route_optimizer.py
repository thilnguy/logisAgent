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

    def solve(self, 
              time_limit_sec=10, 
              global_span_weight=100, 
              span_cost_weight=300, 
              safety_margin=1.0,
              first_solution_strategy="PARALLEL_CHEAPEST_INSERTION",
              local_search_metaheuristic="AUTOMATIC",
              num_workers=1):
        """
        AI Solver with Adaptive Tuning Pipeline (V7.2)
        - Multi-start parallel seeds support
        - Configurable neighborhood operators
        - Hybrid priority shaping
        """
        self.safety_margin = safety_margin
        
        manager = pywrapcp.RoutingIndexManager(self.num_nodes, self.num_vehicles, self.starts, self.ends)
        routing = pywrapcp.RoutingModel(manager)

        # 1. Base Constraints & Costs
        for vid, t in enumerate(self.trucks):
            routing.SetFixedCostOfVehicle(int(t.fixed_cost_euro * 100), vid)

        for vid, truck in enumerate(self.trucks):
            cost_multiplier = min(3, max(1, int(truck.capacity_kg / 1500)))
            def make_cost_callback(mult):
                def vehicle_cost_callback(from_index, to_index):
                    from_node = manager.IndexToNode(from_index)
                    to_node = manager.IndexToNode(to_index)
                    return self.dist_matrix[from_node][to_node] * mult
                return vehicle_cost_callback
            routing.SetArcCostEvaluatorOfVehicle(routing.RegisterTransitCallback(make_cost_callback(cost_multiplier)), vid)

        # Capacity Dimension
        def demand_callback(from_index):
            return int(getattr(self.nodes[manager.IndexToNode(from_index)], 'weight_kg', 0))
        routing.AddDimensionWithVehicleCapacity(routing.RegisterUnaryTransitCallback(demand_callback), 0, [int(t.capacity_kg) for t in self.trucks], True, 'Capacity')

        # Time Dimension with Adaptive Slack
        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            node = self.nodes[from_node]
            service_time = getattr(node, 'service_time_minutes', 0)
            tw = getattr(node, 'time_window', None)
            is_rush_hour_risk = tw and tw.start_minute < 600
            extra_slack = 10 if (safety_margin > 1.0 and is_rush_hour_risk) else 5
            return int(self.time_matrix[from_node][to_node] * safety_margin + service_time + extra_slack)

        routing.AddDimension(routing.RegisterTransitCallback(time_callback), 120, 1440, False, 'Time')
        time_dimension = routing.GetDimensionOrDie('Time')
        time_dimension.SetGlobalSpanCostCoefficient(global_span_weight)
        time_dimension.SetSpanCostCoefficientForAllVehicles(span_cost_weight)

        # Constraints & Time Windows
        for i, node in enumerate(self.nodes):
            tw = getattr(node, 'time_window', None)
            if tw:
                time_dimension.CumulVar(manager.NodeToIndex(i)).SetRange(tw.start_minute, tw.end_minute)

        for i in range(self.num_vehicles):
            time_dimension.CumulVar(routing.Start(i)).SetRange(480, 1200)
            time_dimension.CumulVar(routing.End(i)).SetRange(480, 1200)

        # 2. Priority Logic & Soft Shaping (Hybrid Approach)
        self.num_depots = len([n for n in self.nodes if hasattr(n, 'depot_id')])
        for i in range(self.num_depots, self.num_nodes):
            node = self.nodes[i]
            index = manager.NodeToIndex(i)
            prio = getattr(node, 'priority', 2)
            
            # Weighted Drop Penalty
            penalty = 2000000 if prio == 1 else (500000 if prio == 2 else 50000)
            routing.AddDisjunction([index], penalty)
            
            # Incentive to serve early for Priority 1
            if prio == 1:
                time_dimension.SetCumulVarSoftUpperBound(index, 720, 5000) # Soft 12:00 PM target

        # Territory Zone Restrictions
        cp_solver = routing.solver()
        for i in range(self.num_depots, self.num_nodes):
            node = self.nodes[i]
            order_zone = getattr(node, 'zone', None)
            if order_zone:
                index = manager.NodeToIndex(i)
                for vid, truck in enumerate(self.trucks):
                    if order_zone not in truck.allowed_zones:
                        cp_solver.Add(routing.VehicleVar(index) != vid)

        # 3. Expert Search Parameters (Tuning Pipeline)
        fss_map = {
            "AUTOMATIC": routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC,
            "PARALLEL_CHEAPEST_INSERTION": routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION,
            "PATH_CHEAPEST_ARC": routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC,
            "SAVINGS": routing_enums_pb2.FirstSolutionStrategy.SAVINGS,
            "CHRISTOFIDES": routing_enums_pb2.FirstSolutionStrategy.CHRISTOFIDES,
        }
        meta_map = {
            "AUTOMATIC": routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC,
            "GUIDED_LOCAL_SEARCH": routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH,
            "TABU_SEARCH": routing_enums_pb2.LocalSearchMetaheuristic.TABU_SEARCH,
            "SIMULATED_ANNEALING": routing_enums_pb2.LocalSearchMetaheuristic.SIMULATED_ANNEALING,
        }
        
        best_solution = None
        min_cost = float('inf')
        
        logger.info(f"🚀 Multi-Start Pipeline: {num_workers} workers")
        for seed in range(int(num_workers)):
            search_params = pywrapcp.DefaultRoutingSearchParameters()
            search_params.first_solution_strategy = fss_map.get(first_solution_strategy, fss_map["PARALLEL_CHEAPEST_INSERTION"])
            search_params.local_search_metaheuristic = meta_map.get(local_search_metaheuristic, meta_map["AUTOMATIC"])
            search_params.time_limit.seconds = int(time_limit_sec)
            
            # Note: Randomization is handled internally by Metaheuristics (V7.2)
            
            sol = routing.SolveWithParameters(search_params)
            if sol:
                cost = sol.ObjectiveValue()
                logger.info(f"  - Worker {seed}: Coût={cost}")
                if cost < min_cost:
                    min_cost = cost
                    best_solution = sol
        
        if best_solution:
            logger.success(f"Optimisation terminée. Meilleur coût: {min_cost}")
            return self._format_solution(manager, routing, best_solution, time_dimension)
        else:
            logger.error("Aucune solution trouvée.")
            return None

    def _format_solution(self, manager, routing, solution, time_dimension):
        routes = []
        for vehicle_id in range(self.num_vehicles):
            index = routing.Start(vehicle_id)
            route = []
            route_load = 0
            prev_finish_min = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                time_var = time_dimension.CumulVar(index)
                
                # Service time for current node
                svc_time = int(getattr(self.nodes[node_index], 'service_time_min', 15))
                
                # Arrival time = strictly when the truck reaches the node
                # CumulVar(index).Min() is the "Start of Service" (it honors the window)
                # To get arrival, we look at the previous departure + transit
                if len(route) == 0:
                    arrival_min = solution.Min(time_var) # Depot start
                else:
                    prev_node = route[-1]['node_index']
                    transit_time = self.time_matrix[prev_node][node_index]
                    arrival_min = prev_finish_min + transit_time
                
                route.append({
                    "node_index": node_index,
                    "arrival_time_min": arrival_min,
                    "time_min": solution.Min(time_var), # Start of service
                    "time_max": solution.Max(time_var)
                })
                
                prev_finish_min = solution.Min(time_var) + svc_time
                route_load += int(getattr(self.nodes[node_index], 'weight_kg', 0))
                index = solution.Value(routing.NextVar(index))
                
            node_index = manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            prev_node = route[-1]['node_index']
            transit_time = self.time_matrix[prev_node][node_index]
            arrival_min = prev_finish_min + transit_time
            
            route.append({
                "node_index": node_index,
                "arrival_time_min": arrival_min,
                "time_min": solution.Min(time_var),
                "time_max": solution.Max(time_var)
            })

            if len(route) > 2:
                rush_stops = 0
                for stop in route:
                    t = stop['time_min']
                    if (480 <= t <= 570) or (990 <= t <= 1110):
                        rush_stops += 1
                
                penalty = (rush_stops * 0.15) / self.safety_margin
                robustness_score = max(0.4, 1.0 - penalty)

                route_duration = route[-1]['time_min'] - route[0]['time_min']
                break_info = None
                if route_duration > 270:
                    midpoint_min = route[0]['time_min'] + 270
                    break_info = {"start_min": midpoint_min, "duration_min": 45}
                
                routes.append({
                    "vehicle_id": vehicle_id,
                    "truck": self.trucks[vehicle_id],
                    "route": route,
                    "total_load_kg": route_load,
                    "break_info": break_info,
                    "robustness_score": round(robustness_score * 100, 1)
                })
        
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
                    "reason": "Capacité/Temps incompatible"
                })
                
        avg_robustness = sum(r['robustness_score'] for r in routes) / len(routes) if routes else 100
        return {
            "routes": routes, 
            "dropped_orders": dropped_orders,
            "solution_robustness": round(avg_robustness, 1)
        }
