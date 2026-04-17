import random
from typing import Dict
from loguru import logger

class TrafficAgent:
    """
    V3 Production Architecture:
    Replaces purely manual 'What-If' scenarios with simulated Live Webhooks.
    In a real environment, this pings TomTom API or Bison Futé to retrieve GeoJSON congestion heatmaps.
    """
    
    def __init__(self):
        self.endpoint = "https://bison-fute.api.mock/orleans-nord"

    def check_a10_north(self) -> Dict:
        """
        Polls the API for the A10/D2020 northern axis status.
        Currently returns a randomized mock response to demonstrate dynamic System ingestion.
        """
        logger.info(f"📡 [TrafficAgent] Interrogation du webhook en temps réel: {self.endpoint}")
        
        # Simulate a 30% chance of massive congestion on the A10 highway
        is_congested = random.random() < 0.30
        
        if is_congested:
            logger.warning("🚨 [TrafficAgent] Alerte reçue: Congestion critique détectée (A10 / D2020)!")
            return {
                "status": "CRITICAL",
                "speed_limit_kmh": 8.0,
                "message": "Congestion majeure Axe Nord (A10 / Pôle 45). Reroutage conseillé."
            }
        else:
            logger.success("🟢 [TrafficAgent] Trafic fluide sur l'Axe Nord.")
            return {
                "status": "FLUID",
                "speed_limit_kmh": 45.0,
                "message": "Conditions de circulation nominales (A10)."
            }
