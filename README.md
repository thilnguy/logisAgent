# PoC: Agentic Logistics Optimizer

**LogisAgent** est un outil de démonstration "Proof of Concept" conçu pour un centre logistique à **Orléans (Pôle 45/Saran)**, ciblant spécifiquement la chaîne d'approvisionnement (exemple : *Sephora*). L'objectif est d'illustrer la transition d'une planification manuelle (type Excel) vers un outil AI optimisé.

## Le principe de *"L'Amélioration Continue"* (Lean)
Ce PoC s'inscrit au cœur du Lean Management et du Six Sigma :
- **Optimisation des Processus :** Réduction de la redondance des trajets, diminuant le coût final (Euro / Km).
- **Réduction des Déchets (Muda) :** La planification "Agentic" réduit directement les émissions inutiles de gaz à effet de serre. 
- **Time to Value :** Ce que prenait 2 heures sous Excel est instantané avec Google OR-Tools.

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Démarrage rapide

```bash
streamlit run app.py
```

Découvrez en temps réel les tournées générées sur la carte interactive et analysez les métriques Avant/Après.
