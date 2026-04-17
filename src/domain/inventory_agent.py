from loguru import logger
from typing import List
from domain.models import DeliveryOrder

class InventoryAgent:
    """
    Simulate checking a WMS (Warehouse Management System).
    Filters out orders if stock is missing at the primary depot.
    """
    
    def __init__(self, stock_levels_mock: dict):
        self.stock_levels = stock_levels_mock
        
    def validate_orders(self, orders: List[DeliveryOrder]) -> tuple[List[DeliveryOrder], List[DeliveryOrder]]:
        valid_orders = []
        invalid_orders = []
        
        for order in orders:
            # Using random/mock logic for PoC missing stock
            if order.order_id in self.stock_levels and self.stock_levels[order.order_id] == 0:
                logger.warning(f"InventoryAgent: OOS (Out of Stock) détecté pour {order.order_id} - Ne sera pas planifié.")
                invalid_orders.append(order)
            else:
                logger.info(f"InventoryAgent: Stock OK pour {order.order_id}")
                valid_orders.append(order)
                
        return valid_orders, invalid_orders
