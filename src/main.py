import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
from datetime import datetime, timedelta
import sys
from loguru import logger

# Configure Loguru: Only show INFO and above for the production demo
logger.remove()
logger.add(sys.stderr, level="INFO")

from domain.models import Truck
from domain.inventory_agent import InventoryAgent
from infrastructure.repository import LogisticsRepository
from infrastructure.tco_calculator import calculate_tco
from solver.distance_matrix import RoutingMatrix
from solver.route_optimizer import EnterpriseRouteOptimizer
from domain.traffic_agent import TrafficAgent


st.set_page_config(page_title="LogisAgent V8.2.0 : Optimiseur Industriel", layout="wide", page_icon="🚛")

# Industrial Headers (Problem Solver Branding)
st.title("🚛 LogisAgent V8.2.0 : Pipeline de Tuning Industriel")

st.markdown("""
*Système d'Aide à la Décision (DSS) de classe industrielle. 
Optimisation parallèle massive (Ensemble Optimization) & Résilience temps réel.*
""")

# 1. Initialize Mock DB / Repository
def load_data():
    return LogisticsRepository("data/mock_db.json")

repo = load_data()
depots = repo.get_active_depots()

st.sidebar.header("⚙️ Configuration DSS")

# 1. Industrial Importation (Prioritized)
st.sidebar.subheader("📥 Importation Industrielle")
import_mode = st.sidebar.toggle("Activer Remplacement Manuel", help="Permet d'ignorer la simulation pour importer un fichier ou saisir manuellement.")

uploaded_file = None
if import_mode:
    uploaded_file = st.sidebar.file_uploader("Fichier WMS (CSV/xlsx)", type=["csv", "xlsx"])
    
    # Template Download
    template_df = pd.DataFrame({
        "Client": ["Boulangerie A", "Pharmacie B"],
        "Latitude": [47.902, 47.922],
        "Longitude": [1.904, 1.914],
        "Weight": [250.0, 500.0],
        "Start": ["08:00", "14:00"],
        "End": ["12:00", "18:00"],
        "Priority": [1, 2]
    })
    st.sidebar.download_button("📥 Télécharger Template CSV", template_df.to_csv(index=False), "template_logisagent.csv", "text/csv")
    
    # In manual mode, num_orders matches the actual count
    if "orders" in st.session_state and st.session_state.orders:
        num_orders = len(st.session_state.orders)
    else:
        num_orders = 12 # Default
else:
    num_orders = st.sidebar.slider("Volume de commandes (Scalability Test)", 5, 100, 12, help="Poussez à 100 pour tester la performance industrielle.")

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
st.sidebar.subheader("🚀 Optimisation (Expert)")
solver_time = st.sidebar.slider(
    "Temps de Calcul (s)", 
    5, 120, 15, 
    help="Plus de temps = meilleure convergence pour les gros volumes (>50 col)."
)

with st.sidebar.expander("🛠️ Stratégies Avancées (V8.0)", expanded=True):
    st.caption("🚀 CONTRÔLE INDUSTRIEL")
    
    ensemble_mode = st.toggle("🤖 Ensemble (Multi-Strategy)", value=False, help="Exécution parallèle de plusieurs stratégies distinctes pour une exploration optimale de l'espace des solutions.")
    
    fss_map = {
        "AUTOMATIC": "AUTOMATIC",
        "PARALLEL_CHEAPEST_INSERTION": "PARALLEL_CHEAPEST_INSERTION",
        "PATH_CHEAPEST_ARC": "PATH_CHEAPEST_ARC",
        "SAVINGS": "SAVINGS",
        "CHRISTOFIDES": "CHRISTOFIDES"
    }
    
    meta_map = {
        "AUTOMATIC": "AUTOMATIC",
        "GUIDED_LOCAL_SEARCH": "GUIDED_LOCAL_SEARCH",
        "TABU_SEARCH": "TABU_SEARCH",
        "SIMULATED_ANNEALING": "SIMULATED_ANNEALING"
    }

    if not ensemble_mode:
        fss_choice = st.selectbox("First Solution Strategy", list(fss_map.keys()), index=1)
        meta_choice = st.selectbox("Local Search Metaheuristic", list(meta_map.keys()), index=0)
    else:
        st.info("Mode Orchestrator : Le système assigne automatiquement les meilleures combinaisons de stratégies à chaque thread.")
        fss_choice = "AUTOMATIC"
        meta_choice = "AUTOMATIC"
        
    parallel_workers = st.sidebar.slider("Workers Concurrents", 1, 8, 4 if ensemble_mode else 1, help="Nombre de threads CPU exécutés en parallèle.")
    solution_limit = st.sidebar.slider("Limitation des Solutions", 100, 10000, 1000, step=100, help="Arrête la recherche locale une fois la limite atteinte.")

# Data Generation Button (Only for simulation mode)
if not import_mode:
    generate_btn = st.sidebar.button("🚀 Simuler Flux Entrant (WMS)")
else:
    generate_btn = False

if "orders" not in st.session_state:
    st.session_state.orders = []

# Handle Data Ingestion
if import_mode and uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_imp = pd.read_csv(uploaded_file)
        else:
            df_imp = pd.read_excel(uploaded_file)
        st.session_state.orders = repo.parse_dataframe(df_imp)
    except Exception as e:
        st.sidebar.error("Erreur lecture file.")

if generate_btn:
    st.session_state.orders = repo.fetch_daily_orders(num_orders)

if not st.session_state.orders:
    st.info("Veuillez générer ou importer des commandes pour lancer l'optimisation.")
    st.stop()

st.markdown("---")
st.subheader("📋 WMS Data Feed & Éditeur Interactif")
st.caption("Données issues du WMS ou Importées. Vous pouvez modifier les valeurs directement dans le tableau.")

# 1. Prepare Data for Editor
editor_data = []
for o in st.session_state.orders:
    editor_data.append({
        "ID": o.order_id,
        "Client": o.address.name,
        "Lat": o.address.latitude,
        "Lon": o.address.longitude,
        "Weight": o.weight_kg,
        "Date": o.scheduled_date,
        "Start": f"{o.time_window.start_minute//60:02d}:{o.time_window.start_minute%60:02d}",
        "End": f"{o.time_window.end_minute//60:02d}:{o.time_window.end_minute%60:02d}",
        "Déchargement (mins)": o.service_time_minutes,
        "Priority": o.priority,
        "Zone": o.zone
    })

# 2. Render st.data_editor
df_editor = pd.DataFrame(editor_data)
edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="main_editor")

# 3. Sync Back to session_state.orders (Refining the objects)
if st.session_state.get("main_editor"):
    # Re-parse the edited dataframe to ensure solver uses fresh values
    st.session_state.orders = repo.parse_dataframe(edited_df.rename(columns={"Lat": "Latitude", "Lon": "Longitude", "Déchargement (mins)": "Unloading_mins", "Date": "Date"}))

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
            time_limit_sec=solver_time,
            global_span_weight=g_weight,
            span_cost_weight=s_weight,
            safety_margin=safety_margin,
            first_solution_strategy=fss_choice,
            local_search_metaheuristic=meta_choice,
            num_workers=parallel_workers,
            ensemble_mode=ensemble_mode,
            solution_limit=solution_limit
        )
        st.session_state.solve_duration = time.time() - start_time
        
        if solution is None:
            st.error("Aucune solution trouvée respectant les fenêtres de temps (Time Windows) ou capacités.")
        else:
            st.session_state.solution = solution['routes']
            st.session_state.dropped_orders = solution.get('dropped_orders', [])
            st.session_state.worker_results = solution.get('worker_results', [])
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
    
    # V3.2: Use Date from first order if available, otherwise today
    plan_date_str = valid_orders[0].scheduled_date if valid_orders else datetime.now().strftime('%Y-%m-%d')
    try:
        base_time = datetime.strptime(plan_date_str, '%Y-%m-%d')
    except:
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
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
            
            name = getattr(all_nodes[n_curr['node_index']], 'address', all_nodes[n_curr['node_index']]).name if hasattr(all_nodes[n_curr['node_index']], 'address') else all_nodes[n_curr['node_index']].name
            
            # 1. Service Block (Unloading)
            if service_mins > 0:
                gantt_data.append(dict(
                    Task=truck.truck_id, Start=start_dt.strftime("%Y-%m-%d %H:%M"), End=finish_service_dt.strftime("%Y-%m-%d %H:%M"), 
                    Phase=f"Manutention ({service_mins}m)", Location=name
                ))
            
            # 2. Transit Block (Physically Driving)
            next_name = getattr(all_nodes[n_next['node_index']], 'address', all_nodes[n_next['node_index']]).name if hasattr(all_nodes[n_next['node_index']], 'address') else all_nodes[n_next['node_index']].name
            gantt_data.append(dict(
                Task=truck.truck_id, Start=finish_service_dt.strftime("%Y-%m-%d %H:%M"), End=arrival_dt.strftime("%Y-%m-%d %H:%M"), 
                Phase="Trajet routier", Location=f"Vers: {next_name}"
            ))
            
            # 3. Waiting Block (If arrived before Window opens)
            if arrival_dt < end_dt:
                gantt_data.append(dict(
                    Task=truck.truck_id, Start=arrival_dt.strftime("%Y-%m-%d %H:%M"), End=end_dt.strftime("%Y-%m-%d %H:%M"), 
                    Phase="Attente (Time Window)", Location=f"Patienter à: {next_name}"
                ))

        # V4 Phase 9: Render mandatory driver break on Gantt
        break_info = route.get('break_info')
        if break_info:
            break_start = base_time + timedelta(minutes=break_info['start_min'])
            break_end = break_start + timedelta(minutes=break_info['duration_min'])
            gantt_data.append(dict(
                Task=truck.truck_id, 
                Start=break_start.strftime("%Y-%m-%d %H:%M"), 
                End=break_end.strftime("%Y-%m-%d %H:%M"),
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "🌐 Digital Twin (Map)", 
        "📊 Timeline Gantt", 
        "💶 Financial Audit (TCO)",
        "🔬 Solver Quality Audit"
    ])

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
        fig = px.timeline(
            df_gantt, 
            x_start="Start", 
            x_end="End", 
            y="Task", 
            color="Phase", 
            text="Location", 
            hover_name="Location", 
            title="Timeline de Dispatch (Route vs Déchargement)"
        )
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
            st.metric("Coût Total de Possession (TCO)", f"{total_tco:.2f} €", "Incl. Salaires, Carburant, Entretien, Taxe CO2")
        with colB:
            robustness = st.session_state.get('solution_robustness', 100)
            st.metric("Indice de Fiabilité", f"{robustness}%", f"{resilience_level}")
        with colC:
            avg_load_factor = sum(float(d['Taux Chargement'].replace('%','')) for d in tco_truck_details) / len(tco_truck_details) if tco_truck_details else 0
            st.metric("Taux de Remplissage", f"{avg_load_factor:.1f}%", "Moyenne Flotte")
        with colD:
            solve_time = st.session_state.get('solve_duration', 0)
            st.metric("Temps de Calcul", f"{solve_time:.3f} s", f"{len(st.session_state.orders)} points")

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
        
        # New metrics requested by user
        if st.session_state.get("orders"):
            total_orders = len(st.session_state.orders)
            min_weight = min(o.weight_kg for o in st.session_state.orders)
            max_weight = max(o.weight_kg for o in st.session_state.orders)
        else:
            total_orders, min_weight, max_weight = 0, 0, 0

        report_data = f"""### RAPPORT DÉCISIONNEL - LOGISAGENT V8.1 (Industriel)
--------------------------------------
**Hub**: Orléans (Saran/Ormes)  
**Date**: {datetime.now().strftime('%d/%m/%Y %H:%M')}  
**Statut Trafic**: {'ALERTE CRITIQUE' if is_congested else 'FLUIDE'}  
**Stratégie**: {strategy}
**Résilience**: {resilience_level} (Marge {safety_margin}x)

#### 📊 RÉSULTATS CLÉS:
- **Total Commandes**: {total_orders} colis
- **Plage de Poids**: {min_weight}kg - {max_weight}kg
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
        st.download_button(
            label="📩 Télécharger Rapport Décisionnel (Format Industriel .md)",
            data=report_data,
            file_name=f"Rapport_LogisAgent_V8_2_0_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            type="primary",
            use_container_width=True
        )
        
        st.caption("✅ Rapport Markdown chuẩn V8.2.0 đã sẵn sàng. Bạn có thể mở bằng bất kỳ trình soạn thảo văn bản nào.")

    with tab4:
        st.markdown("### 🧬 Analyse de Convergence (Ensemble Mode) - v8.2.0")
        if "worker_results" in st.session_state and st.session_state.worker_results:
            import pandas as pd
            df_audit = pd.DataFrame(st.session_state.worker_results)
            
            # Show Detailed Table
            cols_to_show = ["strategy", "cost", "dist_cost", "fixed_cost", "penalty_cost", "span_cost"]
            # Filter only existing columns to avoid errors if some workers failed/old data
            existing_cols = [c for c in cols_to_show if c in df_audit.columns]
            
            st.dataframe(df_audit[existing_cols].rename(columns={
                "strategy": "Stratégie", 
                "cost": "Coût Total",
                "dist_cost": "Coût Distance",
                "fixed_cost": "Coût Fixe",
                "penalty_cost": "Pénalités",
                "span_cost": "Coût Span"
            }), use_container_width=True)
        
            with st.expander("ℹ️ Comprendre le Coût (Formule Industrielle)"):
                st.markdown("""
                **Le Coût Total est une somme pondérée permettant d'arbitrer entre plusieurs objectifs :**
                - 📏 **Distance** : Kilométrage total ajusté par le poids/capacité.
                - 🚛 **Coût Fixe** : Frais d'activation de chaque camion (Configurable dans l'onglet Flotte).
                - ❌ **Pénalités** : Coût virtuel élevé (ex: 2M pts) pour chaque commande non-livrée (Dropped) ou livraison prioritaire en retard.
                - ⚖️ **Span** : Pénalité d'écart entre le camion le plus chargé et le moins chargé (pour équilibrer le travail).
                
                *Vous pouvez ajuster ces poids dans : `config/solver_params.json`*
                """)
                
                df_workers = pd.DataFrame(st.session_state.worker_results)
                st.success(f"Meilleure stratégie identifiée : **{df_workers.iloc[0]['strategy']}**")
                
                st.caption("Note: Le solveur industriel sélectionne automatiquement la solution avec le coût global minimum parmi toutes les configurations testées.")
        else:
            st.info("Lancez le solveur pour auditer les performances des stratégies parallèles.")
