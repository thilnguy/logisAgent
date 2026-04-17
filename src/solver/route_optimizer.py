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

        # Distance Callback
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return self.dist_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

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
            60,  # allow waiting up to 60 mins
            1440, # max 24 hours per vehicle route
            False,
            'Time'
        )
        time_dimension = routing.GetDimensionOrDie('Time')
        # V3.2: Hybrid Time Optimization
        # 1. Force Balancing: Penalize the single latest arrival across all trucks
        time_dimension.SetGlobalSpanCostCoefficient(500)
        # 2. Delayed Start: Minimize duration (End - Start) for each truck to save wages
        time_dimension.SetSpanCostCoefficientForAllVehicles(100)

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
                routes.append({
                    "vehicle_id": vehicle_id,
                    "truck": self.trucks[vehicle_id],
                    "route": route,
                    "total_load_kg": route_load
                })
                
        return routes
