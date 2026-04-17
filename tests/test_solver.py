import pytest
from src.solver.route_optimizer import EnterpriseRouteOptimizer
from src.domain.models import Depot, Truck, Address

def test_optimizer_initialization():
    depot1 = Depot(depot_id="D1", name="Depot1", latitude=47.1, longitude=1.1)
    truck1 = Truck(truck_id="T1", type_name="3.5t", capacity_kg=1500, start_depot_id="D1", end_depot_id="D1", co2_emission_rate_g_per_km=100)
    
    # Needs matching matrix sizes to total nodes = 1
    dist_matrix = [[0]]
    time_matrix = [[0]]
    
    optimizer = EnterpriseRouteOptimizer(all_nodes=[depot1], trucks=[truck1], dist_matrix=dist_matrix, time_matrix=time_matrix)
    
    assert optimizer.num_vehicles == 1
    assert optimizer.num_nodes == 1
    assert optimizer.starts == [0] # truck 1 starts at array index 0
    assert optimizer.ends == [0]
