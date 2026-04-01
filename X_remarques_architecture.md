# Remarques d'Architecture et Décisions Techniques (UCTP)

Ce document compile les découvertes majeures et les décisions techniques prises lors de nos sessions de brainstorming, afin de guider l'implémentation du solveur Python.

## 1. La Création de Variables par Matrice Creuse (Sparse Variables)

**Le Problème :**
Générer naïvement toutes les variables de décision possibles impliquerait de créer une boucle immense : `50 profs * 200 cours * 100 salles * 30 creneaux` = **30 millions de variables binaires**. Cela saturerait la mémoire RAM et rendrait le temps de résolution par PuLP (Branch and Bound) irréaliste.

**La Solution :**
Le `DataLoader` ne demandera à PuLP de créer la variable `x_{i,c,s,t}` **que si** la paire `(enseignant, cours)` figure explicitement dans le fichier `preferences_enseignants.csv`.

**Avantage décisif :**
Si un enseignant n'a pas mis un cours dans ses préférences, la variable mathématique correspondante *n'existera littéralement pas dans la mémoire*. Cela a deux conséquences majeures :
1. L'affectation d'un prof de biologie à un cours de mathématiques devient techniquement impossible au niveau logiciel.
2. L'espace de recherche (la complexité du problème NP-Difficile) est considérablement réduit, accélérant drastiquement la résolution.

## 2. Le "Data Ingestion Layer" (Le Gardien)

Le module de chargement des données (ex: `loader.py`) ne doit pas être un simple lecteur de CSV. Il doit agir comme un **Validateur strict** :
- Il s'assure que les données sont conformes avant de les envoyer au solveur mathématique.
- Il détecte les "fails silencieux" (ex: un cours obligatoire qui n'a été sélectionné par aucun enseignant dans ses préférences). Si cela arrive, le système doit lever une erreur claire *"Insoluble : Aucun prof pour le cours X"* plutôt que de laisser le solveur tourner dans le vide.

## 3. Le "Multi-Perspective Exporter" (Le Rapporteur Analytique)

La résolution brute produit des milliers de `1` et de `0`. L'architecture exige un module d'exportation dédié (ex: `exporter.py`) dont la responsabilité unique est la **traduction humaine et administrative** :
- **Génération Excel multi-vues :** Production de classeurs Excel spécifiques filtrables à la demande (Par filière+niveau, par Identifiant Enseignant, par Identifiant Salle, et un Planning Maître global).
- **L'Audit Statistique :** Le module lira les résultats et générera un rapport documenté de la qualité de la solution (taux de satisfaction atteint, écarts à la moyenne d'équité).
- **Transparence RH :** Le rapport statistique s'accompagnera obligatoirement d'une documentation explicative des calculs, pour que l'administration (RH, Doyen) comprenne et valide la pertinence du planning généré.

## 4. La Relation Cours-Groupes (Table de Jonction)

Le modèle mathématique V2 exige de savoir quel groupe assiste à quel cours via le paramètre $A_{c,g}$ (pour éviter qu'un étudiant ait Analyse Mathématique et Chimie au même instant). Étant donné que `cours.csv` et `groupes.csv` n'ont aucun lien direct, nous allons normaliser les données selon les standards des **bases de données relationnelles (Many-To-Many)** :
- **Création du fichier** `inscriptions.csv` dans le dossier des données.
- **Structure stricte :** Deux colonnes uniques `(cours_id, groupe_id)`.
- **Avantage logiciel :** C'est le design pattern le plus robuste. Un cours magistral (C0001) en amphithéâtre pourra être mappé à 3 groupes (G01, G02, G03) via 3 lignes dans ce fichier, sans jamais altérer la structure des fichiers de base.

---
*Ces règles fondamentales (First Principles) devront être respectées scrupuleusement lors de l'écriture du code Python.*
