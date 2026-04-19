# LogisAgent V4: Logistics Digital Twin & Strategic DSS

**Enterprise-grade Decision Support System (DSS) for Orléans Hub Optimization.**

LogisAgent V4 is not just a routing solver; it is a **Digital Twin** designed to bridge the gap between complex optimization algorithms (AI) and operational business value (ROI). Built specifically for the **Pôle 45 / Orléans** industrial landscape, it solves the Capacitated Vehicle Routing Problem with Time Windows (CVRPTW) while strictly adhering to French/EU logistics regulations.

## 🚀 Strategic Value Proposition

- **Local Relevance**: Tailored for the Orléans geography (A10 Nord/Sud, Saran, Artenay, Chécy).
- **Industrial Compliance**: Built-in audit for **EU Regulation 561/2006** (mandatory 45-min driver breaks after 4.5h driving).
- **Financial Intelligence**: Granular **TCO (Total Cost of Ownership)** calculation including fixed activation costs, maintenance, wages, and CO2 taxes.
- **Human-in-the-loop**: Allows decision-makers to choose between **Economic**, **Balanced**, or **Social** (fair workload) strategies.

## 🛠️ Tech Stack & Philosophy

- **Solver Engine**: Google OR-Tools (Parallel Cheapest Insertion + Guided Local Search).
- **Digital Twin Visualization**: Pydeck (High-resolution GPS mapping).
- **Operations Audit**: Plotly-powered Gantt charts for precise timeline tracking (Driving vs. Waiting).
- **Data Engineering**: Modular clean architecture with Repository and Inventory patterns.

## 📊 Business KPIs Optimized

1. **Load Factor (%)**: Objective-driven fleet selection to minimize empty runs.
2. **Wage Optimization**: Strategic delayed-start logic (`SpanCost`) to eliminate idle waiting time.
3. **Territory Specialization**: Hard CP constraints to enforce zone-based fleet management (NORTH/SOUTH/CITY).

---
*Created for the CESI Alternance Portfolio - Showcasing Industrial Problem Solving through AI.*
