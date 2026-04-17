import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import random
import logging
from geopy.distance import geodesic

from depot_locations import DEPOT, CLIENT_LOCATIONS
from route_optimizer import RouteOptimizer
from emissions_calculator import calculate_emissions, format_emissions_kg

# Configuration du logging (Phase 4: Resilience)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LogisAgent")

st.set_page_config(page_title="Agentic Logistics Optimizer", layout="wide", page_icon="🚚")

st.title("🚚 LogisAgent: Optimiseur de Tournées (PoC)")
st.markdown("**Localisation:** Pôle 45 / Saran - Hub Sephora")

# Feature 1: Zone de saisie
st.sidebar.header("📋 Zone de saisie")
num_orders = st.sidebar.slider("Nombre de commandes (Simulation)", min_value=2, max_value=len(CLIENT_LOCATIONS), value=5)

# Flotte de camions (Hardcoded pour le PoC)
FLEET = [
    {"truck_id": "T1", "type_name": "3.5t", "capacity_kg": 1500},
    {"truck_id": "T2", "type_name": "12t", "capacity_kg": 5000},
    {"truck_id": "T3", "type_name": "12t", "capacity_kg": 5000}
]

# Generate orders
if 'orders' not in st.session_state:
    st.session_state.orders = []

if st.sidebar.button("Générer Simulation"):
    selected_clients = random.sample(CLIENT_LOCATIONS, num_orders)
    orders = []
    for client in selected_clients:
        orders.append({
            "name": client["name"],
            "latitude": client["latitude"],
            "longitude": client["longitude"],
            "weight_kg": random.choice([50, 150, 300, 500, 800])
        })
    st.session_state.orders = orders
    logger.info(f"Generated {num_orders} orders.")

if not st.session_state.orders:
    st.info("👈 Veuillez générer des commandes via la Zone de saisie dans le menu latéral.")
    st.stop()

# Display current orders
st.subheader("📦 Commandes à livrer")
df_orders = pd.DataFrame(st.session_state.orders)
st.dataframe(df_orders, use_container_width=True)

# Lancer l'optimisation
st.markdown("---")
if st.button("🚀 Lancer l'Optimisation par l'Agent AI", type="primary"):
    with st.spinner("L'agent analyse les itinéraires optimisés (CVRP OR-Tools)..."):
        optimizer = RouteOptimizer(depot=DEPOT, locations=st.session_state.orders, trucks=FLEET)
        solution = optimizer.solve()
        st.session_state.solution = solution

if 'solution' in st.session_state:
    solution = st.session_state.solution
    if solution:
        st.success("Tournées optimisées avec succès !")
        
        # Calculate a transparent Baseline (Naive Route)
        # Assuming the driver just goes chronologically in the order the orders were entered
        def calc_naive_distance(orders):
            nodes = [DEPOT] + orders + [DEPOT]
            dist = 0
            for i in range(len(nodes)-1):
                dist += geodesic((nodes[i]['latitude'], nodes[i]['longitude']),
                                 (nodes[i+1]['latitude'], nodes[i+1]['longitude'])).kilometers
            return dist
            
        manual_distance_km = calc_naive_distance(st.session_state.orders)
        optimized_distance_km = solution['total_distance_km']
        
        # Calculate Emissions
        manual_emissions_g = calculate_emissions(manual_distance_km, "12t")
        optimized_emissions_g = sum([calculate_emissions(r['distance_km'], r['truck_type']) for r in solution['routes']])

        # Feature 3: Comparatif Avant/Après
        st.subheader("📊 Comparatif Avant/Après (Amélioration Continue ROI)")
        
        with st.expander("🔍 Pourquoi ces chiffres sont-ils fiables ? (Transparence des calculs)"):
            st.markdown(f"""
            - **Point de départ/arrivée (Dépôt) :** Tous les camions partent et reviennent à **{DEPOT['name']}**.
            - **Distance Non-Optimisée (Excel) :** Estimée mathématiquement si un chauffeur livrait les points chronologiquement dans l'ordre de saisie (Dépôt ➔ Client 1 ➔ Client 2 ➔ ... ➔ Dépôt).
            - **Distance Optimisée (AI) :** Résultat du solveur *Google OR-Tools* qui explore les milliers de permutations possibles pour trouver la boucle (ou les boucles) la plus courte respectant le poids du camion.
            """)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Distance Totale", f"{optimized_distance_km:.1f} km", f"{(optimized_distance_km - manual_distance_km):.1f} km (ordre chronologique)")
        with col2:
            cost_per_km = 1.40
            savings_euro = (manual_distance_km - optimized_distance_km) * cost_per_km
            st.metric("Économie (Carburant + Usure)", f"€ {savings_euro:.2f}", "+ Marge Brillante")
        with col3:
            saved_co2 = format_emissions_kg(manual_emissions_g - optimized_emissions_g)
            st.metric("Bilan Carbone (ADEME)", f"{format_emissions_kg(optimized_emissions_g)} kg CO2", f"- {saved_co2} kg CO2e")

        # Feature 2: Carte Interactive
        st.subheader("🗺️ Carte Interactive des Tournées")
        m = folium.Map(location=[DEPOT["latitude"], DEPOT["longitude"]], zoom_start=11)
        
        folium.Marker(
            [DEPOT["latitude"], DEPOT["longitude"]],
            popup="Dépôt (Sephora Saran)",
            icon=folium.Icon(color="red", icon="home")
        ).add_to(m)

        colors = ['blue', 'green', 'purple', 'orange', 'darkred']
        all_nodes = [DEPOT] + st.session_state.orders

        for route_info in solution["routes"]:
            color = colors[route_info["vehicle_id"] % len(colors)]
            route_coords = []
            
            for idx in route_info['route']:
                node = all_nodes[idx]
                route_coords.append((node["latitude"], node["longitude"]))
                
                if idx != 0:
                    folium.Marker(
                        [node["latitude"], node["longitude"]],
                        popup=f"Camion {route_info['vehicle_id']} - {node['name']} ({node['weight_kg']}kg)",
                        icon=folium.Icon(color=color, icon="info-sign")
                    ).add_to(m)

            folium.PolyLine(route_coords, color=color, weight=4, opacity=0.7).add_to(m)

            itinerary = " ➔ ".join([all_nodes[idx]["name"] for idx in route_info['route']])
            st.markdown(f"**Camion {route_info['vehicle_id']} ({route_info['truck_type']})** : "
                        f"{route_info['distance_km']:.1f} km — Charge: {route_info['load_kg']:.0f} kg")
            st.caption(f"📍 **Itinéraire:** {itinerary}")

        # Rendre the map without causing infinite reruns if the user interacts
        st_folium(m, width=900, height=500, returned_objects=[])
    else:
        st.error("Aucune solution trouvée. Veuillez vérifier les poids des commandes et les capacités des camions.")
        logger.error("Failed to find a route solution.")

