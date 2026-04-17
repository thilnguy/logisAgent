from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import math
from geopy.distance import geodesic

class RouteOptimizer:
    def __init__(self, depot, locations, trucks):
        self.depot = depot
        self.locations = locations
        self.trucks = trucks
        # Index 0 is the depot, indices 1..N are the locations
        self.all_nodes = [self.depot] + self.locations
        self.num_vehicles = len(trucks)
        self.depot_index = 0
        
    def _create_data_model(self):
        data = {}
        data['distance_matrix'] = self._compute_distance_matrix()
        data['vehicle_capacities'] = [t['capacity_kg'] for t in self.trucks]
        data['num_vehicles'] = self.num_vehicles
        data['depot'] = self.depot_index
        data['demands'] = [0] + [loc.get('weight_kg', 0) for loc in self.locations]
        return data

    def _compute_distance_matrix(self):
        matrix = []
        for i in range(len(self.all_nodes)):
            row = []
            for j in range(len(self.all_nodes)):
                if i == j:
                    row.append(0)
                else:
                    dist = geodesic(
                        (self.all_nodes[i]['latitude'], self.all_nodes[i]['longitude']),
                        (self.all_nodes[j]['latitude'], self.all_nodes[j]['longitude'])
                    ).kilometers
                    row.append(int(dist * 1000)) # OR-tools requiert des entiers (mètres)
            matrix.append(row)
        return matrix
        
    def solve(self):
        data = self._create_data_model()
        manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']),
                                               data['num_vehicles'], data['depot'])
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return data['distance_matrix'][from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return data['demands'][from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # null capacity slack
            data['vehicle_capacities'],  # véhicules maximum capacités
            True,  # start cumul to zero
            'Capacity')

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
        search_parameters.time_limit.FromSeconds(3) # Time limit for the PoC

        solution = routing.SolveWithParameters(search_parameters)
        
        if solution:
            return self._format_solution(data, manager, routing, solution)
        else:
            return None

    def _format_solution(self, data, manager, routing, solution):
        routes = []
        total_distance_m = 0
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            route = []
            route_distance_m = 0
            route_load = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += data['demands'][node_index]
                route.append(node_index)
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_distance_m += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id)
            
            # Ajouter le retour au dépôt
            route.append(manager.IndexToNode(index))
            
            if len(route) > 2: # Le véhicule a fait au moins une livraison
                routes.append({
                    "vehicle_id": vehicle_id,
                    "route": route, # Index based tracking
                    "distance_km": route_distance_m / 1000.0,
                    "load_kg": route_load,
                    "truck_type": self.trucks[vehicle_id]['type_name']
                })
                total_distance_m += route_distance_m

        return {
            "routes": routes,
            "total_distance_km": total_distance_m / 1000.0,
        }
