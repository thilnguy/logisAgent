import json
import random
import math
from typing import List, Dict
from domain.models import Depot, DeliveryOrder, Address, TimeWindow

# Orléans city center reference point
ORLEANS_CENTER_LAT = 47.902
ORLEANS_CENTER_LON = 1.904

def auto_zone(lat: float, lon: float) -> str:
    """
    Auto-calculate territory zone from GPS coordinates.
    - CITY: Within ~3km of Orléans center
    - NORTH: North of Orléans (lat >= 47.91) and outside city core
    - SOUTH: South/East/West of Orléans and outside city core
    """
    dlat_km = (lat - ORLEANS_CENTER_LAT) * 111.0   # ~111km per degree latitude
    dlon_km = (lon - ORLEANS_CENTER_LON) * 73.0     # ~73km per degree longitude at 47.9°N
    dist_km = math.sqrt(dlat_km**2 + dlon_km**2)
    
    if dist_km < 3.0:
        return "CENTRE-VILLE"
    elif lat >= 47.91:
        return "NORD"
    else:
        return "SUD"

class LogisticsRepository:
    """
    Simulates a repository layer talking to a Database/WMS.
    Loads raw JSON data and instantiates pure Domain Entities.
    """
    
    def __init__(self, db_path: str = "data/mock_db.json"):
        with open(db_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
            
    def get_active_depots(self) -> List[Depot]:
        return [Depot(**d) for d in self.data.get("DEPOTS", []) if d.get("is_active")]
    
    def fetch_daily_orders(self, count: int = 6) -> List[DeliveryOrder]:
        """
        Mocks today's orders.
        Randomly assigns priority and time windows (morning vs afternoon).
        Zone is auto-calculated from GPS coordinates.
        """
        clients = self.data.get("CLIENTS", [])
        selected = random.sample(clients, min(count, len(clients)))
        
        orders = []
        for i, c in enumerate(selected):
            tw_type = random.choice(["morning", "afternoon", "allday"])
            if tw_type == "morning":
                tw = TimeWindow(start_minute=480, end_minute=720)
            elif tw_type == "afternoon":
                tw = TimeWindow(start_minute=840, end_minute=1080)
            else:
                tw = TimeWindow(start_minute=480, end_minute=1140)
            
            addr = Address(name=c["name"], latitude=c["latitude"], longitude=c["longitude"])
            
            # Weight and Service Time are correlated (heavier = longer unloading)
            weight_service_map = {
                50: 10,    # Colis léger → 10 min
                200: 15,   # Palette légère → 15 min
                400: 20,   # Palette standard → 20 min
                800: 30,   # Demi-camion → 30 min
                1000: 45,  # Chargement complet → 45 min
            }
            weight = random.choice(list(weight_service_map.keys()))
            service_time = weight_service_map[weight]
            
            # Auto-calculate zone from GPS coordinates
            calculated_zone = auto_zone(c["latitude"], c["longitude"])
            
            order = DeliveryOrder(
                order_id=f"ORD-{random.randint(1000, 9999)}",
                address=addr,
                weight_kg=weight,
                time_window=tw,
                service_time_minutes=service_time,
                priority=1 if tw_type == "morning" else 2,
                zone=calculated_zone
            )
            orders.append(order)
            
        return orders
