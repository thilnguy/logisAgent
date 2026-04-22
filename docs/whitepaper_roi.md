# LogisAgent: Industrial Solver: Business Case & ROI

## Overview
This **Decision Support System (DSS)** transforms a complex Operations Research problem into an accessible management dashboard. Moving beyond a standard "CVRP script", LogisAgent: Industrial Solver integrates constraints fundamental to urban logistics: **Time Windows**, **Multi-Depots**, and **Heterogeneous fleets**.

## 1. The Value Proposition (ROI)
LogisAgent doesn't just cut kilometers; it computes the **Total Cost of Ownership (TCO)** per route. By calculating:
- Driver Wages (Hourly)
- Carrier Maintenance (€/km)
- Carbon Taxes (€/kg)

Management is provided with pure financial metrics to compare against current Excel-based or legacy SAP routing.

## 2. Advanced CVRPTW Implementation
Using Google's OR-Tools, the AI enforces:
- `Time Dimension`: Constraints ensure town deliveries (08:00 to 12:00) strictly occur before constraints expire. If a route cannot mathematically accommodate the stop, it is pruned.
- `What-If Scenarios`: The matrix seamlessly injects simulated traffic data to compute real-time impact.

## 3. DevOps Stack
- Data Flow: `Inventory Agent -> VRP Solver -> Plotly Gantt / Pydeck 3D Maps`
- Deployed via `Docker`
- Fully tested using `Pytest`

This represents an Enterprise Standard architecture built specifically to wow Supply Chain directors and demonstrate mature technical leadership.
