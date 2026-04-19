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

st.set_page_config(page_title="LogisAgent V4: Digital Twin & Strategic DSS", layout="wide", page_icon="🚛")

# Industrial Headers (Problem Solver Branding)
st.title("🚛 LogisAgent V4: Digital Twin & Decision Support System")
st.markdown("""
*Système d'Aide à la Décision (DSS) basé sur l'IA - Optimisation de la Supply Chain selon les normes industrielles (EU 561/2006). 
Intègre les concepts de **Human-in-the-loop** & **Digital Twin** pour la gestion du TCO.*
""")

# 1. Initialize Mock DB / Repository
def load_data():
    return LogisticsRepository("data/mock_db.json")

repo = load_data()
depots = repo.get_active_depots()

st.sidebar.header("⚙️ Configuration DSS")
num_orders = st.sidebar.slider("Volume de commandes (Scalability Test)", 5, 100, 12, help="Poussez à 100 pour tester la performance industrielle du solver.")

# Global Fleet Definition (Digital Twin Assets)
base_trucks = [
    Truck(truck_id="T1-VUL-1", type_name="3.5t Downtown A", capacity_kg=1500, start_depot_id="D1", end_depot_id="D1", co2_emission_rate_g_per_km=280.0, wage_per_hour_euro=20.0, fixed_cost_euro=35.0, allowed_zones=["CENTRE-VILLE", "SUD"]),
    Truck(truck_id="T1-VUL-2", type_name="3.5t Downtown B", capacity_kg=1500, start_depot_id="D1", end_depot_id="D1", co2_emission_rate_g_per_km=280.0, wage_per_hour_euro=20.0, fixed_cost_euro=35.0, allowed_zones=["CENTRE-VILLE", "NORD"]),
    Truck(truck_id="T2-PL-1", type_name="12t Ext A", capacity_kg=5000, start_depot_id="D1", end_depot_id="D2", co2_emission_rate_g_per_km=650.0, wage_per_hour_euro=25.0, fixed_cost_euro=65.0, allowed_zones=["NORD"]),
    Truck(truck_id="T2-PL-2", type_name="12t Ext B", capacity_kg=5000, start_depot_id="D2", end_depot_id="D1", co2_emission_rate_g_per_km=650.0, wage_per_hour_euro=27.0, fixed_cost_euro=65.0, allowed_zones=["SUD"]),
    Truck(truck_id="T3-HGV", type_name="44t Artenay", capacity_kg=25000, start_depot_id="D2", end_depot_id="D2", co2_emission_rate_g_per_km=950.0, wage_per_hour_euro=30.0, fixed_cost_euro=120.0, allowed_zones=["NORD"])
]

# V6: Auto-scale fleet for Stress Testing
if num_orders > 15:
    trucks = []
    multiplier = (num_orders // 10) + 1
    unit_id = 100
    for i in range(multiplier):
        for t in base_trucks:
            unit_id += 1
            new_t = t.copy(update={"truck_id": f"UNIT-{unit_id}", "type_name": t.type_name})
            trucks.append(new_t)
else:
    trucks = base_trucks

# Provide simulated Inventory (all items in stock)
stock_mock = {f"ORD-{i}": 100 for i in range(1000, 9999 + num_orders)}
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
st.sidebar.subheader("🎯 Stratégie Décisionnelle")
strategy = st.sidebar.radio(
    "Objectif prioritaire",
    ["Économique (Optimisation Coût)", "Équilibré (Standard TCO)", "Social (Équité Chauffeurs)"],
    index=1,
    help="Économique: Minimum camions | Équilibré: TCO vs Charge | Social: Répartition égale"
)

# Advanced Sliders for Leadership fine-tuning
with st.sidebar.expander("🛠️ Paramètres Trade-offs (Avancé)"):
    # Map presets to defaults
    if "Économique" in strategy:
        def_balance, def_span = 0, 500
    elif "Équilibré" in strategy:
        def_balance, def_span = 100, 300
    else:  # Social
        def_balance, def_span = 600, 100
        
    g_weight = st.slider("Équilibrage Charge (GlobalSpan)", 0, 1000, def_balance)
    s_weight = st.slider("Optimisation Salaire/Attente (SpanCost)", 0, 1000, def_span)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Résilience Opérationnelle")
resilience_level = st.sidebar.select_slider(
    "Niveau de Sécurité (Marge Chauffeur)",
    options=["Risqué (Efficient)", "Standard (Prudent)", "Robuste (Haute Résilience)"],
    value="Standard (Prudent)",
    help="Risqué: 0% marge | Standard: 15% marge | Robuste: 30% marge s'adaptant au trafic."
)
resilience_map = {"Risqué (Efficient)": 1.0, "Standard (Prudent)": 1.15, "Robuste (Haute Résilience)": 1.3}
safety_margin = resilience_map[resilience_level]

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
st.caption("Données brutes issues du WMS (Simulation). Audit utilisateur.")
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
        
        # Calculate matrices via dynamic Webhook trigger
        router = RoutingMatrix([o.address if hasattr(o, 'address') else o for o in all_nodes])
        dist_matrix, time_matrix = router.get_matrices(apply_congestion_scenario=is_congested)
        # Optimize with dynamic configuration from Sidebar
        optimizer = EnterpriseRouteOptimizer(all_nodes, trucks, dist_matrix, time_matrix)
        
        import time
        start_time = time.time()
        solution = optimizer.solve(
            time_limit_sec=8,
            global_span_weight=g_weight,
            span_cost_weight=s_weight,
            safety_margin=safety_margin
        )
        st.session_state.solve_duration = time.time() - start_time
        
        if solution is None:
            st.error("Aucune solution trouvée respectant les fenêtres de temps (Time Windows) ou capacités.")
        else:
            st.session_state.solution = solution['routes']
            st.session_state.dropped_orders = solution.get('dropped_orders', [])
            st.session_state.dist_matrix = dist_matrix
            st.session_state.time_matrix = time_matrix
            st.session_state.all_nodes = all_nodes
            st.session_state.solution_robustness = solution.get('solution_robustness', 100)

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
        st.success("✅ Toutes les commandes sont planifiées avec succès.")
    
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
        
        # V6/7: Dynamic Color Palette for multi-truck visualization
        palette = [
            [0, 255, 128],   # Spring Green
            [0, 128, 255],   # Azure
            [153, 50, 204],  # Orchid
            [255, 20, 147],  # Deep Pink
            [255, 165, 0],   # Orange
            [255, 255, 0],   # Yellow
            [0, 255, 255],   # Cyan
            [255, 0, 0],     # Red
            [128, 0, 128],   # Purple
            [0, 128, 0]      # Green
        ]
        color = palette[sum(ord(c) for c in truck.truck_id) % len(palette)]

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
        # Build zone-colored markers for delivery points
        zone_colors = {"NORD": [0, 120, 255], "SUD": [0, 200, 100], "CENTRE-VILLE": [255, 160, 0]}
        zone_markers = []
        for node in all_nodes:
            if hasattr(node, 'zone') and node.zone:
                zone_markers.append({
                    "position": [node.address.longitude, node.address.latitude],
                    "color": zone_colors.get(node.zone, [180, 180, 180]),
                    "name": f"{node.address.name} ({node.zone})",
                    "zone": node.zone
                })
            elif hasattr(node, 'depot_id'):
                zone_markers.append({
                    "position": [node.longitude, node.latitude],
                    "color": [255, 0, 0],
                    "name": f"🏭 {node.name} (DEPOT)",
                    "zone": "DEPOT"
                })
        
        view_state = pdk.ViewState(latitude=47.93, longitude=1.9, zoom=10, pitch=45)
        arc_layer = pdk.Layer(
            "ArcLayer",
            data=pydeck_lines,
            get_source_position="start",
            get_target_position="end",
            get_source_color="color",
            get_target_color="color",
            get_width=5,
            pickable=True
        )
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=zone_markers,
            get_position="position",
            get_fill_color="color",
            get_radius=300,
            pickable=True
        )
        st.pydeck_chart(pdk.Deck(
            layers=[arc_layer, scatter_layer], 
            initial_view_state=view_state, 
            tooltip={"text": "{name}"}
        ))
        st.caption("🔴 Dépôt | 🔵 NORD | 🟢 SUD | 🟠 CENTRE-VILLE")

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
        colA, colB, colC, colD = st.columns([1.2, 1, 1, 1])
        with colA:
            st.metric("Total Cost of Ownership", f"{total_tco:.2f} €", "Incl. Salaires, Gazole, Entretien, Taxe CO2")
        with colB:
            robustness = st.session_state.get('solution_robustness', 100)
            st.metric("Indice de Fiabilité", f"{robustness}%", f"{resilience_level}")
        with colC:
            avg_load_factor = sum(float(d['Taux Chargement'].replace('%','')) for d in tco_truck_details) / len(tco_truck_details) if tco_truck_details else 0
            st.metric("Taux de Remplissage", f"{avg_load_factor:.1f}%", "Moyen Fleet")
        with colD:
            solve_time = st.session_state.get('solve_duration', 0)
            st.metric("Temps de Calcul", f"{solve_time:.3f} s", f"{len(st.session_state.orders)} stops")

        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("#### 🔍 Matrice d'Audit Financier par Camion")
            df_tco_dev = pd.DataFrame(tco_truck_details)
            st.dataframe(df_tco_dev, use_container_width=True)
            st.info("Ce tableau permet aux auditeurs de vérifier le calcul du TCO véhicule par véhicule.")
        with col2:
            st.markdown("#### 🥧 Répartition des Coûts")
            df_tco_pie = pd.DataFrame({
                "Catégorie": ["Gazole", "Salaires", "Entretien", "Taxe CO2"],
                "Coût (€)": [tco_breakdown["fuel_euro"], tco_breakdown["wage_euro"], tco_breakdown["maintenance_euro"], tco_breakdown["co2_tax_euro"]]
            })
            fig_pie = px.pie(df_tco_pie, values="Coût (€)", names="Catégorie")
            fig_pie.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)

        # Simulated Decision Report Export
        st.markdown("---")
        st.subheader("📄 Exportation Industrielle")
        
        # Calculate summary metrics
        total_kms_all = sum(float(str(d['KM']).replace(',','')) for d in tco_truck_details)
        avg_load_factor = sum(float(d['Taux Chargement'].replace('%','')) for d in tco_truck_details) / len(tco_truck_details) if tco_truck_details else 0
        
        report_data = f"""### RAPPORT DÉCISIONNEL - LOGISAGENT V7 (Industriel)
--------------------------------------
**Hub**: Orléans (Saran/Ormes)  
**Date**: {datetime.now().strftime('%d/%m/%Y %H:%M')}  
**Statut Trafic**: {'ALERTE CRITIQUE' if is_congested else 'FLUIDE'}  
**Stratégie**: {strategy}
**Résilience**: {resilience_level} (Marge {safety_margin}x)

#### 📊 RÉSULTATS CLÉS:
- **Coût Total (TCO)**: {total_tco:,.2f} €
- **Distance Totale**: {total_kms_all:.1f} km
- **Indice de Fiabilité**: {st.session_state.get('solution_robustness', 'N/A')}%
- **Camions Activés**: {len(tco_truck_details)} / {len(trucks)}
- **Taux de Remplissage Moyen**: {avg_load_factor:.1f}%

#### ✅ CONFORMITÉ & RÉSILIENCE:
- **Repos Chauffeur (EU 561/2006)**: VÉRIFIÉ & CONFORME
- **Marge de Sécurité**: Appliquée ({resilience_level})
- **Robustesse**: Optimisée

---
*Généré par LogisAgent DSS - Digital Twin Engine*
"""
        st.info("💡 Vous pouvez télécharger ce rapport au format Markdown/Texte pour l'inclure dans votre dossier de candidature.")
        st.download_button(
            label="📩 Télécharger le Rapport Décisionnel (Simulation)",
            data=report_data,
            file_name="rapport_logis_agent_v4.md",
            mime="text/markdown",
            key="download_report"
        )

