## 🛠️ Installation et Prérequis

### 1. Créer un Environnement Virtuel (Recommandé)

Afin d'éviter les conflits entre les différentes versions de python et les bibliothèques installées, il est recommandé de créer un environnement virtuel.

```bash
# Créer l'environnement
python3 -m venv mon_env

# L'activer (sous Linux/Mac)
source mon_env/bin/activate

# L'activer (sous Windows)
 mon_env\Scripts\activate
```

### 2. Installer les Dépendances

Taper cette commande pour télécharger automatiquement toutes les bibliothèques nécessaires :

- pulp
- pandas
- numpy
- openpyxl

```bash
pip install -r requirements.txt
```

---

## 🚀 Utilisation du Projet

Le flux de travail se décompose en 3 étapes simples :

### Étape A : Générer les données de test (Optionnel)

Si vous n'avez pas encore vos propres fichiers CSV, vous pouvez générer un jeu de données réaliste :

- Via le notebook interactif : `Probleme 2.ipynb` (à ouvrir avec Jupyter)
- OU via le script Python direct :

```bash
python3 "Probleme 2.py"
```

Cela créera les fichiers dans le dossier `donnees_problemes/`.

### Étape B : Lancer la Résolution et l'Export

C'est ici que le moteur mathématique calcule le planning :

```bash
# Sous Linux/Mac
PYTHONPATH=. python3 main.py

# Sous Windows
set PYTHONPATH=.
python3 main.py
```

Le solveur va construire plus de 40 000 variables de décision et trouver l'équilibre entre les vœux des profs et les contraintes de salles.

### Étape C : Consulter les Résultats

Tous les plannings sont générés dans le dossier **/output/** sous format Excel (.xlsx) :

- `emploi_du_temps_global.xlsx` : Vue d'ensemble administrative.
- `par_filiere_niveau/` : Planning pour chaque classe d'étudiants (ex: INFO-M2).
- `par_enseignant/` : Emploi du temps personnel de chaque professeur.
- `par_salle/` : Taux d'occupation de chaque salle de l'université.

---

## 🏗️ Architecture du Projet

```
gestion_emploie_temps/
├── main.py                # Point d'entrée principal
├── src/
│   ├── io/loader.py       # Lecteur et validateur de données CSV
│   ├── core/solver.py     # Cœur mathématique (PuLP/CBC)
│   └── reporting/exporter.py # Moteur de génération Excel
├── donnees_problemes/     # Vos fichiers d'entrée (CSV)
├── output/                # Résultats générés (Excel)
└── DOCUMENTATION_TECHNIQUE.md # Explications détaillées du modèle
```

---

## 💡 Notes Importantes

- **Support Durées Variables** : Le système gère les cours de 2h et de 4h (2 créneaux successifs).
- **Habilitations** : Un enseignant ne peut pas donner un cours pour lequel il n'a pas mis de vœu dans `preferences_enseignants.csv`.
