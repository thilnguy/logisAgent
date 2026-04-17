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
from domain.traffic_agent import TrafficAgent

st.set_page_config(page_title="DSS Digital Twin | LogisAgent", layout="wide", page_icon="🏢")

st.title("🏢 LogisAgent V2.0: Logistics Digital Twin (DSS)")
st.caption("Pôle 45 / Saran Hub | Amélioration Continue & CVRPTW OR-Tools Engine")

# 1. Initialize Mock DB / Repository
@st.cache_data
def load_data():
    return LogisticsRepository("data/mock_db.json")

repo = load_data()
depots = repo.get_active_depots()

# Provide simulated Inventory (all items in stock)
stock_mock = {f"ORD-{i}": 100 for i in range(1000, 9999)}

st.sidebar.header("⚙️ Configuration DSS")
num_orders = st.sidebar.slider("Volume de commandes (Scalability Test)", 5, 15, 12)

# Live API Integration instead of Manual Checkbox
st.sidebar.markdown("---")
st.sidebar.subheader("📡 Live API (Bison Futé)")
traffic_agent = TrafficAgent()
traffic_data = traffic_agent.check_a10_north()
is_congested = (traffic_data["status"] == "CRITICAL")

if is_congested:
    st.sidebar.error(f"🔴 **{traffic_data['status']}**\n\n{traffic_data['message']}")
else:
    st.sidebar.success(f"🟢 **{traffic_data['status']}**\n\n{traffic_data['message']}")
st.sidebar.markdown("---")

generate_btn = st.sidebar.button("📦 Simuler Flux Entrant (WMS)")

if "orders" not in st.session_state:
    st.session_state.orders = []
    
if generate_btn:
    orders = repo.fetch_daily_orders(num_orders)
    st.session_state.orders = orders

if not st.session_state.orders:
    st.info("Veuillez générer des commandes pour lancer le profilage.")
    st.stop()

st.markdown("---")
st.subheader("📋 WMS Data Feed (Audit)")
st.caption("Dữ liệu thô từ hệ thống kho (Randomized). Người dùng có thể kiểm tra ở đây.")
# Render WMS Orders as a visually clear Dataframe
order_data = [{"Order ID": o.order_id, "Client": o.address.name, "Zone": o.zone or "N/A", "Weight (kg)": o.weight_kg, "Time Window": f"{o.time_window.start_minute//60:02d}:00 - {o.time_window.end_minute//60:02d}:00", "Unloading (mins)": o.service_time_minutes} for o in st.session_state.orders]
df_audit = pd.DataFrame(order_data)
st.dataframe(df_audit, use_container_width=True)

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
        
        # Build Enterprise Fleet (Multi-Depot & Territory Zones)
        trucks = [
            Truck(truck_id="T1-VUL-1", type_name="3.5t Downtown A", capacity_kg=1500, start_depot_id="D1", end_depot_id="D1", co2_emission_rate_g_per_km=280.0, wage_per_hour_euro=20.0, fixed_cost_euro=35.0, allowed_zones=["CITY", "SOUTH"]),
            Truck(truck_id="T1-VUL-2", type_name="3.5t Downtown B", capacity_kg=1500, start_depot_id="D1", end_depot_id="D1", co2_emission_rate_g_per_km=280.0, wage_per_hour_euro=20.0, fixed_cost_euro=35.0, allowed_zones=["CITY", "NORTH"]),
            Truck(truck_id="T2-PL-1", type_name="12t Ext A", capacity_kg=5000, start_depot_id="D1", end_depot_id="D2", co2_emission_rate_g_per_km=650.0, wage_per_hour_euro=25.0, fixed_cost_euro=65.0, allowed_zones=["NORTH"]),
            Truck(truck_id="T2-PL-2", type_name="12t Ext B", capacity_kg=5000, start_depot_id="D2", end_depot_id="D1", co2_emission_rate_g_per_km=650.0, wage_per_hour_euro=27.0, fixed_cost_euro=65.0, allowed_zones=["SOUTH"]),
            Truck(truck_id="T3-HGV", type_name="44t Artenay", capacity_kg=25000, start_depot_id="D2", end_depot_id="D2", co2_emission_rate_g_per_km=950.0, wage_per_hour_euro=30.0, fixed_cost_euro=120.0, allowed_zones=["NORTH"])
        ]
        
        # Calculate matrices via dynamic Webhook trigger
        router = RoutingMatrix([o.address if hasattr(o, 'address') else o for o in all_nodes])
        dist_matrix, time_matrix = router.get_matrices(apply_congestion_scenario=is_congested)
        
        # Optimize with an extended 8-sec search for larger graphs
        optimizer = EnterpriseRouteOptimizer(all_nodes, trucks, dist_matrix, time_matrix)
        solution = optimizer.solve(time_limit_sec=8)
        
        if solution is None:
            st.error("Aucune solution trouvée respectant les fenêtres de temps (Time Windows) ou capacités.")
        else:
            st.session_state.solution = solution['routes']
            st.session_state.dropped_orders = solution.get('dropped_orders', [])
            st.session_state.dist_matrix = dist_matrix
            st.session_state.time_matrix = time_matrix
            st.session_state.all_nodes = all_nodes

if "solution" in st.session_state:
    solution = st.session_state.solution
    dist_matrix = st.session_state.dist_matrix
    all_nodes = st.session_state.all_nodes
    
    # V4 Phase 10: Display dropped orders warning
    dropped = st.session_state.get('dropped_orders', [])
    if dropped:
        st.warning(f"⚠️ **{len(dropped)} commande(s) non-livrée(s)** (reportée(s) au lendemain)")
        with st.expander("📋 Détails des commandes reportées"):
            df_dropped = pd.DataFrame(dropped)
            st.dataframe(df_dropped, use_container_width=True)
    else:
        st.success("✅ Toutes les commandes livrées avec succès.")
    
    # 3. Process TCO and metrics
    total_tco = 0.0
    tco_breakdown = {
        "fuel_euro": 0.0,
        "wage_euro": 0.0,
        "maintenance_euro": 0.0,
        "co2_tax_euro": 0.0
    }
    tco_truck_details = []
    gantt_data = []
    pydeck_lines = []
    
    base_time = datetime.strptime("00:00", "%H:%M")
    
    for route in solution:
        truck = route['truck']
        distance_m = 0
        node_seq = route['route']
        
        truck_colors = {
            "T1-VUL-1": [0, 255, 128],   # Green
            "T1-VUL-2": [0, 128, 255],   # Blue
            "T2-PL-1": [153, 50, 204],   # Deep Purple
            "T2-PL-2": [255, 20, 147],   # Deep Pink
            "T3-HGV": [255, 165, 0]      # Orange
        }
        color = truck_colors.get(truck.truck_id, [255, 255, 255])

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
            
            # Precise V3.1 Logic: Distinguish between Driving and Waiting
            is_depot = n_curr['node_index'] < len(depots)
            node_obj = all_nodes[n_curr['node_index']]
            service_mins = getattr(node_obj, 'service_time_minutes', 0) if not is_depot else 0
            
            travel_mins = st.session_state.time_matrix[n_curr['node_index']][n_next['node_index']]
            
            start_dt = base_time + timedelta(minutes=n_curr['time_min'])
            finish_service_dt = start_dt + timedelta(minutes=service_mins)
            
            # arrival_dt = Time the truck physically pulls up at the customer
            arrival_dt = finish_service_dt + timedelta(minutes=travel_mins)
            
            # end_dt = Time the service ACTUALLY starts (OR-Tools node start time)
            end_dt = base_time + timedelta(minutes=n_next['time_min'])
            
            name = all_nodes[n_curr['node_index']].address.name if hasattr(all_nodes[n_curr['node_index']], 'address') else all_nodes[n_curr['node_index']].name
            
            # 1. Service Block (Unloading)
            if service_mins > 0:
                gantt_data.append(dict(
                    Task=truck.truck_id, Start=start_dt.strftime("2026-04-17 %H:%M"), End=finish_service_dt.strftime("2026-04-17 %H:%M"), 
                    Phase=f"Manutention ({service_mins}m)", Location=name
                ))
            
            # 2. Transit Block (Physically Driving)
            next_name = all_nodes[n_next['node_index']].address.name if hasattr(all_nodes[n_next['node_index']], 'address') else all_nodes[n_next['node_index']].name
            gantt_data.append(dict(
                Task=truck.truck_id, Start=finish_service_dt.strftime("2026-04-17 %H:%M"), End=arrival_dt.strftime("2026-04-17 %H:%M"), 
                Phase="Trajet routier", Location=f"Vers: {next_name}"
            ))
            
            # 3. Waiting Block (If arrived before Window opens)
            if arrival_dt < end_dt:
                gantt_data.append(dict(
                    Task=truck.truck_id, Start=arrival_dt.strftime("2026-04-17 %H:%M"), End=end_dt.strftime("2026-04-17 %H:%M"), 
                    Phase="Attente (Time Window)", Location=f"Patienter à: {next_name}"
                ))

        # V4 Phase 9: Render mandatory driver break on Gantt
        break_info = route.get('break_info')
        if break_info:
            break_start = base_time + timedelta(minutes=break_info['start_min'])
            break_end = break_start + timedelta(minutes=break_info['duration_min'])
            gantt_data.append(dict(
                Task=truck.truck_id, 
                Start=break_start.strftime("2026-04-17 %H:%M"), 
                End=break_end.strftime("2026-04-17 %H:%M"),
                Phase="Pause réglementaire (45m)", 
                Location="EU 561/2006"
            ))

        total_kms = distance_m / 1000.0
        route_time_hours = (node_seq[-1]['time_min'] - node_seq[0]['time_min']) / 60.0
        
        tco = calculate_tco(total_kms, route_time_hours, truck.wage_per_hour_euro, truck.maintenance_per_km_euro, truck.co2_emission_rate_g_per_km)
        total_tco += tco['total_tco_euro'] + truck.fixed_cost_euro
        tco_breakdown['fuel_euro'] += tco['fuel_euro']
        tco_breakdown['wage_euro'] += tco['wage_euro']
        tco_breakdown['maintenance_euro'] += tco['maintenance_euro']
        tco_breakdown['co2_tax_euro'] += tco['co2_tax_euro']
        
        load_kg = route['total_load_kg']
        load_factor = round((load_kg / truck.capacity_kg) * 100, 1) if truck.capacity_kg > 0 else 0
        
        tco_truck_details.append({
            "Camion": truck.truck_id,
            "Type": truck.type_name,
            "Zones": ", ".join(truck.allowed_zones),
            "Charge (kg)": f"{load_kg}/{int(truck.capacity_kg)}",
            "Taux Chargement": f"{load_factor}%",
            "KM": round(total_kms, 1),
            "Heures": round(route_time_hours, 2),
            "Activation (€)": round(truck.fixed_cost_euro, 2),
            "Gazole (€)": round(tco['fuel_euro'], 2),
            "Salaire (€)": round(tco['wage_euro'], 2),
            "Entretien (€)": round(tco['maintenance_euro'], 2),
            "Taxe CO2 (€)": round(tco['co2_tax_euro'], 2),
            "Total (€)": round(tco['total_tco_euro'] + truck.fixed_cost_euro, 2)
        })
        
    # --- UI RENDERING (GRID & TABS) ---
    st.markdown("---")
    st.subheader("📈 Operation Dashboard")
    
    # Using Tabs for modularity and preventing clutter
    tab1, tab2, tab3 = st.tabs(["🌐 Digital Twin (Map)", "📊 Timeline Gantt", "💶 Financial Audit (TCO)"])

    with tab1:
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

    with tab2:
        df_gantt = pd.DataFrame(gantt_data)
        fig = px.timeline(df_gantt, x_start="Start", x_end="End", y="Task", color="Phase", text="Location", hover_name="Location", title="Dispatch Timeline (Driving vs Unloading)")
        fig.update_traces(textposition='inside', insidetextanchor='middle')
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            height=350, 
            margin=dict(t=30, b=0, l=0, r=0), 
            legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5, title="")
        )
        st.plotly_chart(fig, use_container_width=True)
        
    with tab3:
        # Nested Grid for Finances
        colA, colB = st.columns([1, 1])
        with colA:
            st.metric("Total Cost of Ownership", f"{total_tco:.2f} €", "Incl. Wages, Fuel, Maintenance, CO2 Tax")
            st.markdown("#### 🔍 Matrice d'Audit Financier par Camion")
            df_tco_dev = pd.DataFrame(tco_truck_details)
            st.dataframe(df_tco_dev, use_container_width=True)
            st.info("Cette table permet aux auditeurs de vérifier le calcul TCO véhicule par véhicule.")
        with colB:
            # Audit View: Breakdown pie chart
            df_tco = pd.DataFrame({
                "Cost Category": ["Fuel", "Wages", "Maintenance", "CO2 Tax"],
                "Cost (€)": [tco_breakdown["fuel_euro"], tco_breakdown["wage_euro"], tco_breakdown["maintenance_euro"], tco_breakdown["co2_tax_euro"]]
            })
            fig_pie = px.pie(df_tco, values="Cost (€)", names="Cost Category")
            fig_pie.update_layout(height=280, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
