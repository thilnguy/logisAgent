from pydantic import BaseModel, Field
from typing import Optional

class Address(BaseModel):
    name: str = Field(..., description="Nom de l'entreprise hoặc địa chỉ")
    latitude: float
    longitude: float

class DeliveryOrder(BaseModel):
    order_id: str
    address: Address
    weight_kg: float = Field(..., gt=0, description="Poids de la commande en kg")
    volume_m3: float = Field(default=0.0, ge=0, description="Volume en mètres cubes")
    priority: int = Field(default=1, description="1: Normal, 2: Express")

class Truck(BaseModel):
    truck_id: str
    type_name: str = Field(..., description="E.g., '3.5t', '12t', '44t'")
    capacity_kg: float = Field(..., gt=0)
    capacity_volume_m3: float = Field(default=0.0, ge=0)
    co2_emission_rate_g_per_km: float = Field(..., description="Taux d'émission CO2 (g/km) selon l'ADEME")
