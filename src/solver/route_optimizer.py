from loguru import logger
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from typing import List
import concurrent.futures
import time
import json
import os

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
        
        # Load Solver Parameters
        self.config = self._load_config()
        
        # Build starts and ends arrays for multi-depot
        self.starts = []
        self.ends = []
        for t in trucks:
            start_idx = next(i for i, n in enumerate(self.nodes) if getattr(n, 'depot_id', None) == t.start_depot_id)
            end_idx = next(i for i, n in enumerate(self.nodes) if getattr(n, 'depot_id', None) == t.end_depot_id)
            self.starts.append(start_idx)
            self.ends.append(end_idx)
        
        self.num_depots = len([n for n in self.nodes if hasattr(n, 'depot_id')])

    def _load_config(self):
        config_path = "config/solver_params.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)
        return {
            "penalties": {"priority_1_dropped": 2000000, "priority_2_dropped": 500000},
            "coefficients": {"distance_meter_mult": 1, "fixed_cost_multiplier": 100, "global_span_default": 100, "span_cost_default": 300}
        }

    def solve(self, 
              time_limit_sec=10, 
              global_span_weight=100, 
              span_cost_weight=300, 
              safety_margin=1.0,
              first_solution_strategy="PARALLEL_CHEAPEST_INSERTION",
              local_search_metaheuristic="AUTOMATIC",
              num_workers=1,
              ensemble_mode=False,
              solution_limit=1000):
        """
        AI Solver with Architecture V8.0
        - Parallel Ensemble Orchestrator (Concurrent Futures)
        - Adaptive Priority Scaling
        - Robust Neighborhood Operators
        """
        self.safety_margin = safety_margin
        
        # Strategy Ensemble Configuration
        if ensemble_mode:
            # Distributed strategies across workers
            strategies = [
                ("PARALLEL_CHEAPEST_INSERTION", "GUIDED_LOCAL_SEARCH"),
                ("PATH_CHEAPEST_ARC", "TABU_SEARCH"),
                ("SAVINGS", "SIMULATED_ANNEALING"),
                ("CHRISTOFIDES", "AUTOMATIC"),
                ("AUTOMATIC", "GUIDED_LOCAL_SEARCH"),
                ("PARALLEL_CHEAPEST_INSERTION", "TABU_SEARCH"),
                ("SAVINGS", "GUIDED_LOCAL_SEARCH"),
                ("PATH_CHEAPEST_ARC", "AUTOMATIC")
            ]
            worker_configs = strategies[:num_workers]
        else:
            # Single strategy multi-seed
            worker_configs = [(first_solution_strategy, local_search_metaheuristic)] * num_workers

        best_result = None
        min_cost = float('inf')

        import concurrent.futures
        from functools import partial

        logger.info(f"🚀 Launching Parallel Ensemble: {len(worker_configs)} workers")
        
        worker_results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # We must build the model inside each thread for safety
            futures = []
            for i, (fss, meta) in enumerate(worker_configs):
                futures.append(executor.submit(
                    self._solve_worker, 
                    time_limit_sec=time_limit_sec,
                    global_span_weight=global_span_weight,
                    span_cost_weight=span_cost_weight,
                    fss_name=fss,
                    meta_name=meta,
                    solution_limit=solution_limit,
                    seed=i
                ))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        worker_results.append({
                            "strategy": f"{result['fss']} + {result['meta']}",
                            "cost": result['cost'],
                            "dist_cost": result['breakdown']['distance'],
                            "fixed_cost": result['breakdown']['fixed'],
                            "penalty_cost": result['breakdown']['penalty'],
                            "span_cost": result['breakdown']['span']
                        })
                        if result['cost'] < min_cost:
                            min_cost = result['cost']
                            best_result = result['data']
                            logger.info(f"  - Worker found better solution: Coût={min_cost}")
                except Exception as e:
                    logger.error(f"❌ Worker failed: {e}")

        if best_result:
            logger.success(f"Optimisation terminée. Meilleur coût: {min_cost}")
            best_result['worker_results'] = sorted(worker_results, key=lambda x: x['cost'])
            return best_result
        else:
            logger.error("Aucune solution trouvée.")
            return None

    def _solve_worker(self, time_limit_sec, global_span_weight, span_cost_weight, fss_name, meta_name, solution_limit, seed):
        """Isolated solver run for parallel execution."""
        manager = pywrapcp.RoutingIndexManager(self.num_nodes, self.num_vehicles, self.starts, self.ends)
        routing = pywrapcp.RoutingModel(manager)

        # 1. Base Constraints & Costs
        for vid, t in enumerate(self.trucks):
            routing.SetFixedCostOfVehicle(int(t.fixed_cost_euro * 100), vid)

        for vid, truck in enumerate(self.trucks):
            cost_multiplier = min(3, max(1, int(truck.capacity_kg / 1500)))
            def make_cost_callback(mult):
                def vehicle_cost_callback(from_index, to_index):
                    fn = manager.IndexToNode(from_index)
                    tn = manager.IndexToNode(to_index)
                    return self.dist_matrix[fn][tn] * mult
                return vehicle_cost_callback
            routing.SetArcCostEvaluatorOfVehicle(routing.RegisterTransitCallback(make_cost_callback(cost_multiplier)), vid)

        # Dimension: Capacity
        def demand_callback(from_index):
            return int(getattr(self.nodes[manager.IndexToNode(from_index)], 'weight_kg', 0))
        routing.AddDimensionWithVehicleCapacity(routing.RegisterUnaryTransitCallback(demand_callback), 0, [int(t.capacity_kg) for t in self.trucks], True, 'Capacity')

        # Dimension: Time with Adaptive Slack
        def time_callback(from_index, to_index):
            fn = manager.IndexToNode(from_index)
            node = self.nodes[fn]
            svc = getattr(node, 'service_time_minutes', 0)
            tw = getattr(node, 'time_window', None)
            risk = tw and tw.start_minute < 600
            slack = 10 if (self.safety_margin > 1.0 and risk) else 5
            return int(self.time_matrix[fn][manager.IndexToNode(to_index)] * self.safety_margin + svc + slack)

        routing.AddDimension(routing.RegisterTransitCallback(time_callback), 1440, 1440, False, 'Time')
        time_dim = routing.GetDimensionOrDie('Time')
        time_dim.SetGlobalSpanCostCoefficient(global_span_weight)
        time_dim.SetSpanCostCoefficientForAllVehicles(span_cost_weight)

        # Constraints
        for i, node in enumerate(self.nodes):
            tw = getattr(node, 'time_window', None)
            if tw:
                time_dim.CumulVar(manager.NodeToIndex(i)).SetRange(tw.start_minute, tw.end_minute)
        
        for i in range(self.num_vehicles):
            time_dim.CumulVar(routing.Start(i)).SetRange(360, 1320) # 06:00 to 22:00
            time_dim.CumulVar(routing.End(i)).SetRange(360, 1320)

        # Adaptive Priority Scaling
        for i in range(self.num_depots, self.num_nodes):
            node = self.nodes[i]
            idx = manager.NodeToIndex(i)
            prio = getattr(node, 'priority', 2)
            weight = getattr(node, 'weight_kg', 0)
            
            # Dynamic penalty from config
            p1_penalty = self.config["penalties"]["priority_1_dropped"]
            p2_penalty = self.config["penalties"]["priority_2_dropped"]
            base_p = p1_penalty if prio == 1 else p2_penalty
            adj_p = int(base_p * (1 + (weight / 5000))) 
            routing.AddDisjunction([idx], adj_p)
            
            if prio == 1:
                time_dim.SetCumulVarSoftUpperBound(idx, 720, 10000) # Strong 12:00 PM target

        # Zone logic
        cp_solver = routing.solver()
        for i in range(self.num_depots, self.num_nodes):
            node = self.nodes[i]
            zone = getattr(node, 'zone', None)
            if zone:
                idx = manager.NodeToIndex(i)
                for vid, truck in enumerate(self.trucks):
                    if zone not in truck.allowed_zones:
                        cp_solver.Add(routing.VehicleVar(idx) != vid)

        # Search Parameters
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

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = fss_map.get(fss_name, fss_map["AUTOMATIC"])
        search_params.local_search_metaheuristic = meta_map.get(meta_name, meta_map["AUTOMATIC"])
        search_params.time_limit.seconds = int(time_limit_sec)
        search_params.solution_limit = int(solution_limit)
        
        # B: Enable Robust Neighborhood Operators
        search_params.local_search_operators.use_relocate = pywrapcp.BOOL_TRUE
        search_params.local_search_operators.use_exchange = pywrapcp.BOOL_TRUE
        search_params.local_search_operators.use_cross = pywrapcp.BOOL_TRUE
        search_params.local_search_operators.use_two_opt = pywrapcp.BOOL_TRUE
        
        sol = routing.SolveWithParameters(search_params)
        if sol:
            formatted = self._format_solution(manager, routing, sol, time_dim)
            
            # Calculate breakdown
            # Note: This is an estimation based on the solver state
            dist_cost = 0
            fixed_cost = 0
            for vid in range(self.num_vehicles):
                if routing.IsVehicleUsed(sol, vid):
                    fixed_cost += int(self.trucks[vid].fixed_cost_euro * self.config["coefficients"]["fixed_cost_multiplier"])
            
            # Distance is the Arc costs part
            # We subtract fixed and penalties from total objective to get distance + span
            total_obj = sol.ObjectiveValue()
            
            penalty_cost = 0
            for i in range(self.num_depots, self.num_nodes):
                if sol.Value(routing.NextVar(manager.NodeToIndex(i))) == manager.NodeToIndex(i):
                    # Dropped
                    node = self.nodes[i]
                    prio = getattr(node, 'priority', 2)
                    penalty_cost += self.config["penalties"]["priority_1_dropped"] if prio == 1 else self.config["penalties"]["priority_2_dropped"]

            # Estimation of span cost part (very rough)
            span_cost_est = total_obj - fixed_cost - penalty_cost - sum(r.get('dist_meters', 0) for r in formatted['routes']) # problematic
            
            # Actually, let's just calculate distance manually
            total_dist_score = 0
            for r in formatted['routes']:
                truck = r['truck']
                mult = min(3, max(1, int(truck.capacity_kg / self.config["scaling"].get("truck_capacity_threshold", 1500))))
                # Calculate meters from route segments
                route_nodes = r['route']
                d_m = 0
                for k in range(len(route_nodes)-1):
                    d_m += self.dist_matrix[route_nodes[k]['node_index']][route_nodes[k+1]['node_index']]
                total_dist_score += d_m * mult
            
            span_cost = total_obj - fixed_cost - penalty_cost - total_dist_score

            breakdown = {
                "distance": total_dist_score,
                "fixed": fixed_cost,
                "penalty": penalty_cost,
                "span": max(0, span_cost)
            }
            
            return {'cost': total_obj, 'data': formatted, 'fss': fss_name, 'meta': meta_name, 'breakdown': breakdown}
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
                svc_time = int(getattr(self.nodes[node_index], 'service_time_minutes', 0))
                
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
