from geopy.distance import geodesic
from typing import List
from domain.models import Address

class RoutingMatrix:
    """
    Computes Distances (meters) and Travel Times (minutes)
    for the OR-Tools Dimensions.
    """
    def __init__(self, nodes: List[Address]):
        self.nodes = nodes
        # Base speed 45 km/h for urban logistics
        self.base_speed_kmh = 45.0
        
    def get_matrices(self, apply_congestion_scenario: bool = False):
        dist_matrix = []
        time_matrix = []
        for i, node_a in enumerate(self.nodes):
            dist_row = []
            time_row = []
            for j, node_b in enumerate(self.nodes):
                if i == j:
                    dist_row.append(0)
                    time_row.append(0)
                else:
                    dist_km = geodesic(
                        (node_a.latitude, node_a.longitude),
                        (node_b.latitude, node_b.longitude)
                    ).kilometers
                    
                    dist_row.append(int(dist_km * 1000))
                    
                    # Scenario: Orléans North congestion (A10)
                    speed_kmh = self.base_speed_kmh
                    if apply_congestion_scenario:
                        # Anything strictly North of downtown (approx lat > 47.91)
                        if node_a.latitude > 47.91 or node_b.latitude > 47.91:
                            speed_kmh = 8.0  # Massive gridlock: 8 km/h
                            
                    time_h = dist_km / speed_kmh
                    # add base loading/unloading delays via matrix if needed, but handled by solver ServiceTime
                    import math
                    time_mins = math.ceil(time_h * 60)
                    # Force minimum 1 minute to ensure Gantt transit isn't mathematically zero
                    time_row.append(max(1, time_mins))
                    
            dist_matrix.append(dist_row)
            time_matrix.append(time_row)
            
        return dist_matrix, time_matrix
