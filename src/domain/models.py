from pydantic import BaseModel, Field
from typing import Optional

class TimeWindow(BaseModel):
    start_minute: int = Field(..., description="Minutes from midnight (e.g. 480 = 08:00)")
    end_minute: int = Field(..., description="Minutes from midnight (e.g. 720 = 12:00)")

class Address(BaseModel):
    name: str
    latitude: float
    longitude: float

class DeliveryOrder(BaseModel):
    order_id: str
    address: Address
    weight_kg: float = Field(..., gt=0)
    time_window: Optional[TimeWindow] = None
    service_time_minutes: int = Field(default=15, description="Temps de déchargement")
    priority: int = Field(default=1)

class Depot(BaseModel):
    depot_id: str
    name: str
    latitude: float
    longitude: float
    is_active: bool = True

class Truck(BaseModel):
    truck_id: str
    type_name: str
    capacity_kg: float
    start_depot_id: str
    end_depot_id: str
    co2_emission_rate_g_per_km: float
    wage_per_hour_euro: float = Field(default=25.0)
    maintenance_per_km_euro: float = Field(default=0.8)
    fixed_cost_euro: float = Field(default=0.0, description="Coût fixe d'activation du véhicule (assurance, amortissement)")
