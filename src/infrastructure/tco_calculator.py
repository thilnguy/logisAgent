def calculate_tco(distance_km: float, time_hours: float, wage_per_hour: float, maint_per_km: float, co2_g_per_km: float) -> dict:
    """
    Calculate Total Cost of Ownership (TCO) for a route.
    Returns breakdown: Fuel/Toll, Wage, Maintenance, CO2 Cost.
    """
    # Assuming avg fuel cost per km + toll is ~0.40 EUR for standard logistics
    fuel_cost = distance_km * 0.40
    
    wage_cost = time_hours * wage_per_hour
    maint_cost = distance_km * maint_per_km
    
    co2_kg = (distance_km * co2_g_per_km) / 1000
    # European carbon tax is approx 0.08 EUR per kg
    co2_cost = co2_kg * 0.08
    
    total = fuel_cost + wage_cost + maint_cost + co2_cost
    
    return {
        "fuel_euro": round(fuel_cost, 2),
        "wage_euro": round(wage_cost, 2),
        "maintenance_euro": round(maint_cost, 2),
        "co2_tax_euro": round(co2_cost, 2),
        "total_tco_euro": round(total, 2),
        "co2_kg": round(co2_kg, 2)
    }
