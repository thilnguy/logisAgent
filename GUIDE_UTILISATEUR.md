# 🇫🇷 Guide Utilisateur LogisAgent V7

Bienvenue dans le Système d'Aide à la Décision (DSS) de LogisAgent pour le hub d'Orléans. Ce système vous permet d'optimiser vos tournées, de gérer votre flotte et de contrôler vos coûts opérationnels (TCO).

---

## 🚀 Processus en 4 étapes

### Étape 1 : Configuration (Thanh bên trái)
Avant de lancer l'optimisation, configurez vos paramètres :
1. **Volume de commandes** : Choisissez le nombre de commandes à simuler (5 - 15).
2. **Live API (Bison Futé)** : Surveillez le trafic en temps réel. Le système ajuste les temps de trajet si l'axe A10 Nord est congestionné.
3. **Stratégie Décisionnelle (🎯 Stratégie)** :
   - **Économique** : Maximise le groupage, utilise le moins de véhicules possibles.
   - **Équilibré** : Configuration par défaut, compromis coût/charge.
   - **Social** : Répartit équitablement le travail entre les chauffeurs.
   - *Astuce : Ouvrez "Cấu hình Trade-offs" pour un réglage manuel des poids.*

### Étape 2 : Chargement des données (Simulation ou Import)
1. **Choix du mode** : En haut de la barre latérale, la section **"Importation Industrielle"** vous permet de choisir :
   - **Mode Simulation** : Désactivez "Activer Remplacement Manuel" et utilisez le curseur pour définir le volume.
   - **Mode Manuel/Import** : Activez "Activer Remplacement Manuel" pour télécharger un fichier CSV/Excel.
2. **Template** : Utilisez le bouton **"Télécharger Template CSV"** pour obtenir un fichier au format correct.
3. **Éditeur Interactif** : Une fois les données chargées, vous pouvez modifier les coordonnées, le poids, les fenêtres horaires et la **Priorité** directement dans le tableau **"📋 WMS Data Feed & Éditeur Interactif"**.

### Étape 3 : Optimisation
Cliquez sur **"🚀 Exécuter Solveur CVRPTW"**. 
- L'IA (Google OR-Tools) calcule la meilleure solution respectant toutes les contraintes opérationnelles.

### Étape 4 : Analyse des résultats
Les résultats sont répartis en 3 onglets :

#### 1. 🌐 Digital Twin (Carte)
- Visualisez les tournées avec des arcs directionnels.
- **Code couleur des points (Zones) :**
  - 🔴 Rouge : Entrepôt (Depot).
  - 🔵 Bleu : Zone NORD.
  - 🟢 Vert : Zone SUD.
  - 🟠 Orange : Centre-ville (CITY).
- Permet de vérifier que chaque véhicule respecte son territoire.

#### 2. 📊 Timeline Gantt (Planning)
- Planning détaillé par chauffeur.
- **Bleu** : Conduite.
- **Vert** : Déchargement chez le client.
- **Gris** : Attente (arrivée avant l'ouverture).
- **Jaune (Pause)** : Pause légale de 45 min obligatoire après 4h30 de conduite (EU 561/2006).

#### 3. 💶 Financial Audit (Audit TCO)
- Coûts détaillés par véhicule : Carburant, Salaire, Maintenance, CO2 et **Frais d'activation**.
- Colonne **Taux Chargement (%)** : Indique l'optimisation du remplissage. Si trop bas (< 50%), passez en stratégie "Économique".

---

## ⚠️ Notes Importantes

- **Commandes Non-Livrées** : Si un avertissement apparaît, certaines commandes n'ont pu être planifiées (fenêtre horaire trop courte ou poids excessif). Ajoutez des camions ou élargissez les fenêtres.
- **Zones Géographiques** : Les camions de 12t et 44t sont restreints par zone pour maximiser l'efficacité opérationnelle chuyên môn hóa.

---
