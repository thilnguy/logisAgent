def calculate_emissions(distance_km: float, truck_type: str) -> float:
    """
    Calcule les émissions de gaz à effet de serre (gCO2e) d'un trajet en fonction du type de camion.
    Basé sur des moyennes simplifiées de l'ADEME (Base Carbone).
    """
    # Emission averages in gCO2e/km
    rates = {
        "3.5t": 280.0,
        "12t": 650.0,
        "44t": 950.0
    }
    
    # Default to 12t rate if unknown
    rate = rates.get(truck_type, 650.0)
    
    return distance_km * rate

def format_emissions_kg(emissions_g: float) -> float:
    """Converts grams of CO2 to kilograms and returns rounded value."""
    return round(emissions_g / 1000, 2)
