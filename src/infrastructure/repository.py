import json
import random
from typing import List, Dict
from domain.models import Depot, DeliveryOrder, Address, TimeWindow

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
        """
        clients = self.data.get("CLIENTS", [])
        selected = random.sample(clients, min(count, len(clients)))
        
        orders = []
        for i, c in enumerate(selected):
            # 50% chance of strict morning delivery
            is_morning = random.choice([True, False])
            tw = TimeWindow(start_minute=480, end_minute=720) if is_morning else TimeWindow(start_minute=480, end_minute=1080)
            
            addr = Address(name=c["name"], latitude=c["latitude"], longitude=c["longitude"])
            order = DeliveryOrder(
                order_id=f"ORD-{random.randint(1000, 9999)}",
                address=addr,
                weight_kg=random.choice([50, 200, 400, 800, 1000]),
                time_window=tw,
                service_time_minutes=15, # 15 mins to unload
                priority=1 if not is_morning else 2
            )
            orders.append(order)
            
        return orders
