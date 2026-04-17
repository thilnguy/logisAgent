import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
from loguru import logger
from datetime import datetime, timedelta

from domain.models import Truck
from domain.inventory_agent import InventoryAgent
from infrastructure.repository import LogisticsRepository
from infrastructure.tco_calculator import calculate_tco
from solver.distance_matrix import RoutingMatrix
from solver.route_optimizer import EnterpriseRouteOptimizer

st.set_page_config(page_title="DSS Digital Twin | LogisAgent", layout="wide", page_icon="🏢")

st.title("🏢 LogisAgent V2.0: Logistics Digital Twin (DSS)")
st.caption("Pôle 45 / Saran Hub | Amélioration Continue & CVRPTW OR-Tools Engine")

# 1. Initialize Mock DB / Repository
@st.cache_data
def load_data():
    return LogisticsRepository("data/mock_db.json")

repo = load_data()
depots = repo.get_active_depots()

# Provide simulated Inventory
stock_mock = {f"ORD-{i}": 100 for i in range(1000, 9999)}
# Randomly make 1 order out of stock to show the agent working
stock_mock["ORD-5555"] = 0 

st.sidebar.header("⚙️ Configuration DSS")
num_orders = st.sidebar.slider("Volume de commandes", 3, 7, 5)

scenario = st.sidebar.checkbox("🚨 Simuler: A10 Bloquée (Orléans Nord)")
if scenario:
    st.sidebar.warning("La congestion routière augmentera drastiquement les temps de trajets au Nord.")

generate_btn = st.sidebar.button("📦 Simuler Flux Entrant (WMS)")

if "orders" not in st.session_state:
    st.session_state.orders = []
    
if generate_btn:
    orders = repo.fetch_daily_orders(num_orders)
    # inject the fake 5555 order sometimes to trigger inventory issue
    if len(orders) > 0 and num_orders % 2 == 0:
        orders[0].order_id = "ORD-5555"
    st.session_state.orders = orders

if not st.session_state.orders:
    st.info("Veuillez générer des commandes pour lancer le profilage.")
    st.stop()

# 2. Inventory Agent Validation
agent = InventoryAgent(stock_mock)
valid_orders, invalid_orders = agent.validate_orders(st.session_state.orders)

if invalid_orders:
    st.error(f"⚠️ {len(invalid_orders)} commande(s) mise(s) en attente (Rupture Stock Saran détectée par l'Inventory Agent).")
    for o in invalid_orders:
        st.write(f"- {o.order_id} ({o.address.name})")

st.markdown("---")
st.subheader("🚛 Planification (Routing & Time Windows)")

if st.button("🚀 Exécuter Solveur CVRPTW", type="primary"):
    with st.spinner("Modélisation des matrices Temps/Distance et recherche d'optimal (OR-Tools)..."):
        # Combine valid nodes: Depots first, then valid_orders
        all_nodes = depots + valid_orders
        
        # Build fleet (Multi-Depot)
        trucks = [
            Truck(truck_id="T1-VUL", type_name="3.5t Downtown", capacity_kg=1500, start_depot_id="D1", end_depot_id="D1", co2_emission_rate_g_per_km=280.0, wage_per_hour_euro=20.0),
            Truck(truck_id="T2-PL", type_name="12t Ext", capacity_kg=5000, start_depot_id="D1", end_depot_id="D2", co2_emission_rate_g_per_km=650.0, wage_per_hour_euro=25.0),
            Truck(truck_id="T3-HGV", type_name="44t Artenay", capacity_kg=25000, start_depot_id="D2", end_depot_id="D2", co2_emission_rate_g_per_km=950.0, wage_per_hour_euro=30.0)
        ]
        
        # Calculate matrices
        router = RoutingMatrix([o.address if hasattr(o, 'address') else o for o in all_nodes])
        dist_matrix, time_matrix = router.get_matrices(apply_congestion_scenario=scenario)
        
        # Optimize
        optimizer = EnterpriseRouteOptimizer(all_nodes, trucks, dist_matrix, time_matrix)
        solution = optimizer.solve(time_limit_sec=4)
        
        if solution is None:
            st.error("Aucune solution trouvée respectant les fenêtres de temps (Time Windows) ou capacités.")
        else:
            st.session_state.solution = solution
            st.session_state.dist_matrix = dist_matrix
            st.session_state.time_matrix = time_matrix
            st.session_state.all_nodes = all_nodes

if "solution" in st.session_state:
    solution = st.session_state.solution
    dist_matrix = st.session_state.dist_matrix
    all_nodes = st.session_state.all_nodes
    st.success("Logistique optimisée ! Temps de service & Fenêtres respectés.")
    
    # 3. Process TCO and metrics
    total_tco = 0.0
    tco_breakdown = {
        "fuel_euro": 0.0,
        "wage_euro": 0.0,
        "maintenance_euro": 0.0,
        "co2_tax_euro": 0.0
    }
    gantt_data = []
    pydeck_lines = []
    
    base_time = datetime.strptime("00:00", "%H:%M")
    
    for route in solution:
        truck = route['truck']
        distance_m = 0
        node_seq = route['route']
        
        color = [128, 0, 128] if truck.type_name == "12t Ext" else [0, 128, 255]
        if truck.type_name == "44t Artenay":
            color = [255, 165, 0]

        for i in range(len(node_seq)-1):
            n_curr = node_seq[i]
            n_next = node_seq[i+1]
            dist_seg = dist_matrix[n_curr['node_index']][n_next['node_index']]
            distance_m += dist_seg
            
            # Draw line for Pydeck
            curr_coords = all_nodes[n_curr['node_index']]
            next_coords = all_nodes[n_next['node_index']]
            
            lat1, lon1 = (curr_coords.address.latitude, curr_coords.address.longitude) if hasattr(curr_coords, 'address') else (curr_coords.latitude, curr_coords.longitude)
            lat2, lon2 = (next_coords.address.latitude, next_coords.address.longitude) if hasattr(next_coords, 'address') else (next_coords.latitude, next_coords.longitude)
            
            pydeck_lines.append({
                "start": [lon1, lat1],
                "end":   [lon2, lat2],
                "color": color,
                "truck": truck.truck_id
            })
            
            # Logic to split Service Time (Unloading) and Transit Time (Driving)
            is_depot = n_curr['node_index'] < len(depots)
            node_obj = all_nodes[n_curr['node_index']]
            service_mins = getattr(node_obj, 'service_time_minutes', 0) if not is_depot else 0
            
            start_dt = base_time + timedelta(minutes=n_curr['time_min'])
            finish_service_dt = start_dt + timedelta(minutes=service_mins)
            end_dt = base_time + timedelta(minutes=n_next['time_min'])
            
            name = all_nodes[n_curr['node_index']].address.name if hasattr(all_nodes[n_curr['node_index']], 'address') else all_nodes[n_curr['node_index']].name
            
            # Service Block
            if service_mins > 0:
                gantt_data.append(dict(
                    Task=truck.truck_id, Start=start_dt.strftime("2026-04-17 %H:%M"), End=finish_service_dt.strftime("2026-04-17 %H:%M"), 
                    Phase=f"Manutention ({service_mins}m)", Location=name
                ))
            
            # Transit Block
            if finish_service_dt < end_dt:
                next_name = all_nodes[n_next['node_index']].address.name if hasattr(all_nodes[n_next['node_index']], 'address') else all_nodes[n_next['node_index']].name
                gantt_data.append(dict(
                    Task=truck.truck_id, Start=finish_service_dt.strftime("2026-04-17 %H:%M"), End=end_dt.strftime("2026-04-17 %H:%M"), 
                    Phase="Trajet routier", Location=f"Vers: {next_name}"
                ))

        total_kms = distance_m / 1000.0
        route_time_hours = (node_seq[-1]['time_min'] - node_seq[0]['time_min']) / 60.0
        
        tco = calculate_tco(total_kms, route_time_hours, truck.wage_per_hour_euro, truck.maintenance_per_km_euro, truck.co2_emission_rate_g_per_km)
        total_tco += tco['total_tco_euro']
        tco_breakdown['fuel_euro'] += tco['fuel_euro']
        tco_breakdown['wage_euro'] += tco['wage_euro']
        tco_breakdown['maintenance_euro'] += tco['maintenance_euro']
        tco_breakdown['co2_tax_euro'] += tco['co2_tax_euro']
        
    # --- UI RENDERING ---
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("💶 Financial Dashboard (TCO)")
        st.metric("Total Cost of Ownership", f"{total_tco:.2f} €", "Incl. Wages, Fuel, Maintenance, CO2 Tax")
        
        # Audit View: Breakdown pie chart
        df_tco = pd.DataFrame({
            "Cost Category": ["Fuel", "Wages", "Maintenance", "CO2 Tax"],
            "Cost (€)": [tco_breakdown["fuel_euro"], tco_breakdown["wage_euro"], tco_breakdown["maintenance_euro"], tco_breakdown["co2_tax_euro"]]
        })
        fig_pie = px.pie(df_tco, values="Cost (€)", names="Cost Category", title="TCO Breakdown (Audit view)")
        fig_pie.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)
        
        df_gantt = pd.DataFrame(gantt_data)
        fig = px.timeline(df_gantt, x_start="Start", x_end="End", y="Task", color="Phase", text="Location", hover_name="Location", title="Dispatch Timeline (Driving vs Unloading)")
        fig.update_traces(textposition='inside', insidetextanchor='middle')
        fig.update_yaxes(autorange="reversed")
        # Optimization of visual thickness AND keeping legend
        fig.update_layout(
            height=350, 
            margin=dict(t=30, b=0, l=0, r=0), 
            legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5, title="")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🌐 Digital Twin GPS (Pydeck)")
        # Plot Pydeck
        view_state = pdk.ViewState(latitude=47.93, longitude=1.9, zoom=10, pitch=45)
        layer = pdk.Layer(
            "ArcLayer",
            data=pydeck_lines,
            get_source_position="start",
            get_target_position="end",
            get_source_color="color",
            get_target_color="color",
            get_width=5,
            pickable=True
        )
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{truck}"}))
