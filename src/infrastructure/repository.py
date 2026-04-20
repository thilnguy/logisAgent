import json
import random
import math
import pandas as pd
from typing import List, Dict
from domain.models import Depot, DeliveryOrder, Address, TimeWindow

# Orléans city center reference point
ORLEANS_CENTER_LAT = 47.902
ORLEANS_CENTER_LON = 1.904

def auto_zone(lat: float, lon: float) -> str:
    """
    Auto-calculate territory zone from GPS coordinates.
    """
    dlat_km = (lat - ORLEANS_CENTER_LAT) * 111.0
    dlon_km = (lon - ORLEANS_CENTER_LON) * 73.0
    dist_km = math.sqrt(dlat_km**2 + dlon_km**2)
    
    if dist_km < 3.0:
        return "CENTRE-VILLE"
    elif lat >= 47.91:
        return "NORD"
    else:
        return "SUD"

class LogisticsRepository:
    def __init__(self, db_path: str = "data/mock_db.json"):
        with open(db_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
            
    def get_active_depots(self) -> List[Depot]:
        return [Depot(**d) for d in self.data.get("DEPOTS", []) if d.get("is_active")]
    
    def fetch_daily_orders(self, count: int = 6) -> List[DeliveryOrder]:
        clients = self.data.get("CLIENTS", [])
        
        if count > len(clients):
            biz_names = [
                "Boulangerie du Centre", "Pharmacie de Saran", "Supermarché E.Leclerc", 
                "Clinique d'Orléans", "Magasin Fnac", "Zara Place d'Arc", 
                "Garage Renault", "Entrepôt Amazon", "Laboratoire Médical", 
                "Hôtel Kyriad", "Boutique Nespresso", "Auchan Saint-Jean",
                "Decathlon Saran", "Castorama Ingré", "Leroy Merlin"
            ]
            
            selected = []
            for i in range(count):
                lat = ORLEANS_CENTER_LAT + random.uniform(-0.15, 0.15)
                lon = ORLEANS_CENTER_LON + random.uniform(-0.15, 0.15)
                biz = random.choice(biz_names)
                selected.append({"name": f"{biz} #{i+1}", "latitude": lat, "longitude": lon})
            
            return [self._create_order(f"ORD-SIM-{i:03d}", s["name"], s["latitude"], s["longitude"]) for i, s in enumerate(selected)]
        else:
            selected = random.sample(clients, count)
        
        return [self._create_order(f"ORD-DB-{i:03d}", c["name"], c["latitude"], c["longitude"]) for i, c in enumerate(selected)]

    def parse_dataframe(self, df: pd.DataFrame) -> List[DeliveryOrder]:
        orders = []
        for i, row in df.iterrows():
            try:
                name = str(row.get("Client", f"Client {i+1}"))
                lat = float(row.get("Latitude", 47.9))
                lon = float(row.get("Longitude", 1.9))
                weight = float(row.get("Weight", 100))
                priority = int(row.get("Priority", 1))
                service_mins = int(row.get("Unloading_mins", 15))
                
                start_str = str(row.get("Start", "08:00"))
                end_str = str(row.get("End", "18:00"))
                
                def to_mins(time_str):
                    h, m = map(int, time_str.split(':'))
                    return h * 60 + m
                
                tw = TimeWindow(start_minute=to_mins(start_str), end_minute=to_mins(end_str))
                
                orders.append(DeliveryOrder(
                    order_id=f"ORD-IMP-{i:03d}",
                    address={"name": name, "latitude": lat, "longitude": lon},
                    weight_kg=weight,
                    time_window=tw,
                    service_time_minutes=service_mins,
                    priority=priority,
                    zone=auto_zone(lat, lon)
                ))
            except:
                continue
        return orders

    def _create_order(self, order_id: str, name: str, lat: float, lon: float) -> DeliveryOrder:
        tw_type = random.choice(["morning", "afternoon", "allday"])
        if tw_type == "morning":
            tw = TimeWindow(start_minute=480, end_minute=720)
        elif tw_type == "afternoon":
            tw = TimeWindow(start_minute=840, end_minute=1080)
        else:
            tw = TimeWindow(start_minute=480, end_minute=1140)
        
        addr = Address(name=name, latitude=lat, longitude=lon)
        
        weight_service_map = {50:10, 200:15, 400:20, 800:30, 1000:45}
        weight = random.choice(list(weight_service_map.keys()))
        service_time = weight_service_map[weight]
        
        return DeliveryOrder(
            order_id=order_id,
            address=addr,
            weight_kg=weight,
            time_window=tw,
            service_time_minutes=service_time,
            priority=1 if tw_type == "morning" else 2,
            zone=auto_zone(lat, lon)
        )
