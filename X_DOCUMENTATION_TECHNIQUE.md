# Documentation Technique — Système UCTP
## Solveur d'Emplois du Temps Universitaires

**Université de Ngaoundéré**  
**Version :** 2.0  
**Date :** 01 Avril 2026  
**Document de référence :** `Planification_cours_v2.md`

---

## Table des Matières

1. [Vue d'Ensemble du Système](#1-vue-densemble-du-système)
2. [Architecture Modulaire](#2-architecture-modulaire)
3. [Module 1 — DataLoader : Chargement et Validation des Données](#3-module-1--dataloader--chargement-et-validation-des-données)
4. [Module 2 — UCTPSolver : Le Moteur d'Optimisation](#4-module-2--uctpsolver--le-moteur-doptimisation)
5. [Module 3 — TimetableExporter : Génération des Rapports](#5-module-3--timetableexporter--génération-des-rapports)
6. [Correspondance Théorie ↔ Implémentation](#6-correspondance-théorie--implémentation)
7. [Flux d'Exécution Complet](#7-flux-dexécution-complet)
8. [Glossaire](#8-glossaire)

---

## 1. Vue d'Ensemble du Système

Le système UCTP est un **outil de génération automatique d'emplois du temps universitaires** basé sur la Programmation Linéaire en Nombres Entiers (PLNE). Il prend en entrée des fichiers CSV décrivant les ressources de l'université (enseignants, cours, salles, groupes) et produit en sortie un ensemble de fichiers Excel représentant les emplois du temps optimisés.

Le système répond à l'enjeu suivant : trouver, parmi des milliards de combinaisons possibles, la meilleure affectation de la forme **"Qui enseigne Quoi, Où et Quand"**, en respectant toutes les règles institutionnelles.

### Principes Fondamentaux

- **Aucun conflit** : Un enseignant, une salle ou un groupe ne peut jamais se retrouver à deux endroits en même temps.
- **Adéquation des ressources** : La salle attribuée doit avoir le bon type d'équipement et une capacité suffisante pour accueillir tous les étudiants du cours.
- **Respect des vœux** : Le plus possible, chaque enseignant est affecté aux cours pour lesquels il a exprimé une préférence.
- **Équité des charges** : La charge horaire est distribuée équitablement entre tous les enseignants.
- **Durées variables** : Les cours peuvent durer 2h (1 créneau) ou 4h (2 créneaux consécutifs).

---

## 2. Architecture Modulaire

Le système est découpé en trois modules indépendants, orchestrés par un script principal.

```
main.py         ←──── Chef d'orchestre (point d'entrée unique)
    │
    ├── src/io/loader.py          ← Module 1 : DataLoader
    │       Lit, valide et structure les données CSV
    │
    ├── src/core/solver.py        ← Module 2 : UCTPSolver
    │       Construit et résout le problème PLNE
    │
    └── src/reporting/exporter.py ← Module 3 : TimetableExporter
            Génère les fichiers Excel multi-vues
```

### Fichiers de Données en Entrée (dans `donnees_problemes/`)

| Fichier | Contenu | Équivalent Mathématique |
|---|---|---|
| `enseignants.csv` | Liste des profs, charge max hebdomadaire | Ensemble $I$, paramètre $MaxH_i$ |
| `cours.csv` | Liste des cours, durée, type requis, effectif | Ensemble $C$, paramètres $Duration_c$, $Size_c$ |
| `salles.csv` | Liste des salles, type, capacité | Ensemble $S$, paramètre $Cap_s$ |
| `groupes.csv` | Liste des groupes, filière, niveau, effectif | Ensemble $G$ |
| `creneaux.txt` | Liste des créneaux horaires (ex: Lundi_8h-10h) | Ensemble $T$ |
| `preferences_enseignants.csv` | Habilitations + préférences (prof, cours, score) | Paramètre $P_{i,c}$ |
| `inscriptions.csv` | Table de jonction Cours ↔ Groupes | Paramètre $A_{c,g}$ |

---

## 3. Module 1 — DataLoader : Chargement et Validation des Données

**Fichier source :** `src/io/loader.py`  
**Rôle :** Ce module est le "gardien des données". Il est la toute première barrière de qualité : si les données sont incohérentes, il le signale avant même que le solveur n'entre en jeu.

### 3.1 Chargement des Fichiers CSV

Le DataLoader lit séquentiellement les sept fichiers CSV et les charge en mémoire sous forme de tableaux structurés (DataFrames Pandas). Pour chaque fichier, il vérifie que les colonnes obligatoires sont présentes et que les identifiants sont conformes au format attendu.

Si un fichier est manquant ou corrompu, le DataLoader lève une erreur immédiatement avec un message explicatif, évitant ainsi une erreur cryptique lors de la résolution.

### 3.2 Garde-fous de Faisabilité (Pre-Solving)

Avant de remettre les données au solveur, le DataLoader effectue deux vérifications critiques de **faisabilité globale**. Ces vérifications permettent d'identifier des problèmes structurels évidents sans passer par le calcul long et coûteux du PLNE.

**Garde-fou 1 — Capacité Physique :**  
Ce garde-fou vérifie qu'il existe au moins une salle dans l'université capable d'accueillir le cours avec le plus grand effectif. Si le cours le plus chargé (ex: 200 étudiants) ne trouve aucune salle assez grande, le planning est mathématiquement impossible et le système s'arrête avec un message clair. Ce test correspond à vérifier que $\max(Size_c) \leq \max(Cap_s)$.

**Garde-fou 2 — Volume Horaire :**  
Ce garde-fou compare la demande horaire totale (somme des durées de tous les cours) à la capacité horaire totale disponible (nombre de créneaux × nombre de salles × durée d'un créneau). Si la demande dépasse l'offre, aucune solution complète ne peut exister. Ce test est un filtre rapide bien avant la résolution.

### 3.3 Construction des Structures d'Accélération

Une fois les données brutes chargées, le DataLoader construit plusieurs **structures d'index** qui accélèrent considérablement le travail du solveur :

**La Matrice Creuse des Habilitations (`preferences_index`) :**  
Au lieu de stocker une grille de 50 enseignants × 300 cours (soit 15 000 cellules, dont la majorité à zéro), le DataLoader stocke uniquement les paires (enseignant, cours) qui existent réellement dans le fichier de préférences. Cette structure est un dictionnaire compact qui permet au solveur de connaître en une seule opération si une affectation est autorisée ou non.

**L'Index Cours → Groupes (`cours_groupes`) :**  
Cette structure est construite à partir du fichier `inscriptions.csv`. Pour chaque cours, elle donne instantanément la liste de tous les groupes d'étudiants qui le suivent. Elle est indispensable pour appliquer les contraintes d'unicité des groupes sans avoir à parcourir toute la table à chaque fois.

**Le Dictionnaire de Disponibilités (`disponibilites`) :**  
Ce dictionnaire permet de répondre instantanément à la question "L'enseignant E est-il disponible au créneau T ?", en s'appuyant sur les données de la colonne `disponibilites` du fichier des enseignants.

### 3.4 Calcul de l'Effectif des Cours

L'effectif d'un cours n'est pas une donnée directe. Il est **calculé** comme la somme des effectifs de tous les groupes inscrits à ce cours (via la table `inscriptions.csv`). C'est ce chiffre calculé qui est ensuite utilisé pour le filtrage des salles.

---

## 4. Module 2 — UCTPSolver : Le Moteur d'Optimisation

**Fichier source :** `src/core/solver.py`  
**Rôle :** C'est le "cerveau mathématique" du système. Il traduit le problème UCTP en un modèle PLNE que le solveur CBC (un algorithme Branch and Bound) peut résoudre.

### 4.1 La Variable de Décision : Concept de "Créneau de Début"

La variable centrale du modèle est $x_{i,c,s,t}$. Elle vaut 1 si l'enseignant $i$ donne le cours $c$ dans la salle $s$ en **commençant** au créneau $t$. C'est un choix de conception important.

Pour un cours de **2h**, si $t = $ "Lundi_8h", il occupe uniquement ce créneau.  
Pour un cours de **4h**, si $t = $ "Lundi_8h", il occupe "Lundi_8h" **et** "Lundi_10h" — deux créneaux consécutifs.

Le solveur raisonne donc toujours en termes de **créneau de début**, et les contraintes sont conçues pour protéger automatiquement tous les créneaux couverts par la durée du cours.

### 4.2 Création des Variables — Le Filtrage Avancé (Sparse Variables)

C'est l'optimisation la plus importante du système. Au lieu de créer une variable pour chaque combinaison (enseignant × cours × salle × créneau) — ce qui représenterait plus de **30 millions de variables** pour notre instance — le solveur n'instancie une variable que si **toutes** les conditions suivantes sont simultanément satisfaites :

1. **Habilitation vérifiée** : La paire (enseignant, cours) doit exister dans le fichier de préférences. Si l'enseignant n'est pas habilité pour ce cours, aucune variable n'est créée, quelle que soit la salle ou le créneau.

2. **Compatibilité de la salle** : La salle doit correspondre au type de cours (ex: un TP nécessite un Labo, un cours magistral nécessite un Amphi) **et** avoir une capacité suffisante pour accueillir tous les étudiants inscrits.

3. **Disponibilité temporelle de l'enseignant** : La variable n'est créée que si l'enseignant est disponible sur **tous les créneaux** que le cours va occuper (pour un cours de 4h, les deux créneaux sont vérifiés).

4. **Non-débordement sur la nuit ou le lendemain** : Pour les cours de 4h, le solveur vérifie que le dernier créneau occupé appartient bien au **même jour** que le créneau de début. Un cours de 4h qui "débuterait" à 17h un lundi ne serait pas créé, car il se terminerait à 21h ou déborderait sur le mardi.

Grâce à ce filtrage combiné, le nombre de variables passe de **30 millions à environ 40 000**, soit une réduction de 99.9%. Cela rend la résolution possible en quelques minutes au lieu de plusieurs heures.

### 4.3 La Fonction Objectif — Ce que le Solveur Cherche à Maximiser

La fonction objectif est composée de **trois termes** qui guident la direction de recherche du solveur. Elle est structurée par ordre de priorité décroissante :

**Terme 1 — Bonus de Couverture (Priorité absolue) :**  
Chaque cours planifié ajoute un bonus de 100 points à l'objectif. Ce terme est délibérément bien plus grand que les scores de préférence (maximum 5 points). Cela garantit que le solveur cherchera toujours en priorité à planifier le **plus grand nombre de cours possible**, avant même de s'intéresser aux préférences. Sans ce terme, le solveur pourrait théoriquement trouver "optimal" de planifier seulement quelques cours avec de très bonnes préférences.

**Terme 2 — Satisfaction des Vœux :**  
Pour chaque cours planifié, on ajoute au score le niveau de préférence déclaré par l'enseignant (de 1 à 5). Ce terme maximise l'adéquation entre les vœux pédagogiques et les affectations réelles. Un enseignant affecté à un cours qu'il aime (préférence 5) contribue plus au score qu'un enseignant affecté à un cours qui lui est indifférent (préférence 1).

**Terme 3 — Pénalité d'Inéquité (à minimiser) :**  
Pour chaque enseignant, on calcule l'écart entre sa charge horaire réelle et la charge horaire moyenne cible du département ($\bar{H}$). La somme de ces écarts est pondérée par un coefficient $\beta$ (par défaut 0.5) et **soustraite** de l'objectif. Ainsi, plus les charges sont inégalement réparties, moins l'objectif est bon, et le solveur est naturellement incité à équilibrer les affectations.

La valeur absolue de l'écart est mathématiquement non-linéaire. Pour la rendre compatible avec la PLNE, on utilise une **linéarisation classique** : on introduit une variable auxiliaire $e_i \geq 0$ par enseignant, et on la contraint à être supérieure ou égale à l'écart dans les deux sens (positif et négatif). Le solveur sera alors forcé d'attribuer à $e_i$ la valeur minimale possible, qui est exactement l'écart absolu.

### 4.4 Les Contraintes — Les Règles Non Négociables

#### Contrainte de Couverture (Soft Constraint)

Chaque cours peut être planifié **au plus une fois** dans la semaine. On dit "au plus" (et non "exactement") car certains cours pourraient ne pas trouver de créneau compatible (enseignant indisponible, salle pleine) : forcer une solution exacte rendrait le problème mathématiquement infaisable. Le terme de bonus de couverture dans la fonction objectif compense cette souplesse en incitant le solveur à toujours chercher à planifier.

#### Contrainte d'Unicité de l'Enseignant

Un enseignant ne peut être dans deux salles différentes en même temps. En pratique, pour chaque couple (enseignant, créneau), le solveur additionne toutes les variables qui placeraient cet enseignant à ce créneau. La somme doit rester inférieure ou égale à 1.

Pour les cours de 4h, un seul cours planifié "bloque" l'enseignant sur **deux** créneaux. La contrainte est donc évaluée non seulement pour le créneau de début, mais pour chaque créneau couvert par le cours.

#### Contrainte d'Unicité de la Salle

Le raisonnement est strictement identique à celui de l'enseignant. Pour chaque couple (salle, créneau), au maximum un cours peut s'y dérouler. Là encore, les cours de 4h bloquent la salle sur l'ensemble de leur intervalle.

#### Contrainte d'Unicité des Groupes

Un groupe d'étudiants ne peut pas assister à deux cours simultanément. Pour identifier quels groupes sont concernés par un cours, le solveur consulte l'index `cours_groupes` (construit par le DataLoader à partir de `inscriptions.csv`). Pour chaque couple (groupe, créneau), la somme de toutes les variables de cours auxquels ce groupe est inscrit doit rester inférieure à 1. Cette contrainte peut générer un très grand nombre d'inégalités, car un groupe peut être inscrit à de nombreux cours.

#### Contrainte de Charge Maximale (Hard Constraint)

Pour chaque enseignant, la somme des durées de tous les cours qui lui sont attribués doit rester inférieure ou égale à sa charge maximale hebdomadaire autorisée ($MaxH_i$). Cette contrainte est une **barrière absolue** : elle ne peut jamais être violée, contrairement à l'objectif d'équité qui opère en dessous de ce plafond.

### 4.5 La Résolution — Branch and Bound avec CBC

Une fois le modèle construit (variables, objectif, contraintes), il est transmis au solveur **CBC** (COIN-BC), un moteur de Branch and Bound open-source intégré dans PuLP. Le processus se déroule en trois phases :

1. **Relaxation Linéaire :** Le solveur ignore temporairement la contrainte d'intégralité (il autorise des valeurs comme $x = 0.3$ ou $x = 0.7$). Il résout ce problème simplifié très rapidement et obtient une borne supérieure de l'objectif atteignable.

2. **Branchement :** Si une variable n'est pas entière dans la solution relaxée (ex: $x = 0.6$), le solveur crée deux sous-problèmes : l'un en forçant $x = 0$ et l'autre en forçant $x = 1$. Il explore ces branches de manière intelligente.

3. **Élagage :** Dès qu'une branche ne peut mathématiquement pas améliorer la meilleure solution déjà trouvée, elle est abandonnée. C'est grâce à cet élagage que l'algorithme reste tractable malgré l'immensité de l'espace de recherche.

Un **timeout de 120 secondes** est configuré. Si le solveur n'a pas prouvé l'optimalité absolue dans ce délai, il retourne la meilleure solution trouvée jusqu'à présent (solution "Faisable").

---

## 5. Module 3 — TimetableExporter : Génération des Rapports

**Fichier source :** `src/reporting/exporter.py`  
**Rôle :** Transformer la solution brute (une liste de tuples) en documents Excel lisibles et exploitables par l'administration, les enseignants et les étudiants.

### 5.1 Reconstruction du Tableau Central

La solution brute retournée par le solveur est un dictionnaire de clés `(enseignant_id, cours_id, salle_id, créneau_debut)`. L'exporter parcourt ce dictionnaire et enrichit chaque entrée avec toutes les informations textuelles provenant du DataLoader :
- Nom complet de l'enseignant
- Intitulé du cours et son type (CM, TD, TP)
- Nom de la salle
- Label horaire **calculé** : pour un cours de 4h débutant à 8h, le label affiché sera "8h-12h" et non "8h-10h". L'exporter reconstitue l'heure de fin en cherchant le label du dernier créneau couvert.
- Noms lisibles des groupes (ex: `INFO-M2` au lieu de `G0045`), obtenus via l'index du DataLoader.

Ce tableau central est le pivot de tous les exports suivants.

### 5.2 Vues Générées

À partir du tableau central, l'exporter produit plusieurs "vues" filtrées et formatées :

**Vue Globale :** Un seul fichier Excel contenant toutes les affectations de la semaine, trié par créneau puis par salle. C'est la vue "administrative" complète.

**Vues par Filière/Niveau :** Pour chaque combinaison unique (filière, niveau) détectée dans la solution (ex: INFO-L1, MATH-M2), un fichier Excel personnalisé est généré. Ne contient que les cours concernant ce groupe. C'est la vue "étudiant".

**Vues par Enseignant :** Pour chaque enseignant ayant au moins un cours planifié, un fichier Excel personnel est généré. C'est la vue "carnet de l'enseignant".

**Vues par Salle :** Pour chaque salle utilisée, un fichier Excel est généré, montrant son occupation semaine. C'est la vue "logistique" pour le gestionnaire des salles.

### 5.3 Rapport d'Audit RH

Ce fichier contient deux indicateurs de qualité de la solution :

**Taux de Satisfaction :** Calculé comme le ratio entre la somme des préférences obtenues par les enseignants et la somme des préférences maximales qu'ils auraient pu obtenir. Un taux de 95% signifie que les enseignants ont globalement été affectés à des cours qu'ils appréciaient.

**Équité (Écart Moyen) :** Calculé comme la moyenne des écarts absolus entre la charge horaire de chaque enseignant et la charge moyenne cible du département. Un écart de 2h signifie qu'en moyenne, les enseignants s'écartent de 2h de la cible. Plus cette valeur est faible, plus la répartition est équitable.

---

## 6. Correspondance Théorie ↔ Implémentation

Ce tableau de synthèse établit le lien direct entre chaque élément du modèle mathématique et sa traduction dans le code.

| Élément Mathématique | Description | Implémentation |
|---|---|---|
| Ensemble $I$ | Enseignants | Liste extraite de `enseignants.csv` par le DataLoader |
| Ensemble $C$ | Cours | Liste extraite de `cours.csv` |
| Ensemble $S$ | Salles | Liste extraite de `salles.csv` |
| Ensemble $T$ | Créneaux | Liste extraite de `creneaux.txt` |
| Ensemble $G$ | Groupes | Liste extraite de `groupes.csv` |
| Paramètre $P_{i,c}$ | Préférence/Habilitation | Dictionnaire `preferences_index` dans le DataLoader. Si absent, la variable $x$ n'est **jamais créée**. |
| Paramètre $D_{i,t}$ | Disponibilité | Dictionnaire `disponibilites`. Vérifié lors du filtrage, **avant** la création de la variable. |
| Paramètre $Cap_s$ / $Size_c$ | Capacité salle / Effectif cours | Filtre de salle lors de la création des variables (`capacite >= effectif`). |
| Paramètre $A_{c,g}$ | Appartenance Cours-Groupe | Index `cours_groupes` construit depuis `inscriptions.csv`. Utilisé dans la contrainte d'unicité des groupes. |
| Paramètre $Duration_c$ | Durée du cours | Colonne `duree` dans `cours.csv`. Convertie en $K_c = duree / 2$ créneaux. |
| Paramètre $MaxH_i$ | Charge max de l'enseignant | Colonne `charge_max` dans `enseignants.csv`. Contrainte dure dans le solveur. |
| Paramètre $\bar{H}$ | Charge horaire moyenne cible | Calculé dynamiquement : somme des durées de tous les cours divisée par le nombre d'enseignants. |
| Variable $x_{i,c,s,t}$ | Affectation (Qui, Quoi, Où, Quand) | Variables binaires PuLP. Créées **uniquement** pour les combinaisons viables (filtrage avancé). |
| Variable $e_i$ | Écart de charge de l'enseignant $i$ | Variable auxiliaire PuLP (`LpVariable`, `lowBound=0`). Linéarise la valeur absolue. |
| $Z_{couverture}$ | Bonus de planification | Constante 100 × nombre de variables actives dans l'objectif PuLP. |
| $Z_{sat}$ | Satisfaction des vœux | Somme pondérée par $P_{i,c}$ dans la fonction objectif PuLP. |
| $Z_{equite}$ | Pénalité d'inéquité | Somme des $e_i$ × $\beta$ soustraite dans l'objectif PuLP. |
| Contrainte Couverture ($\leq 1$) | Au plus 1 affectation par cours | Boucle sur chaque cours, regroupement de ses variables, inégalité PuLP. |
| Contrainte Unicité Enseignant | 1 cours par prof par créneau | Pour chaque (enseignant, créneau_global), somme de **toutes** les variables qui l'occupent ≤ 1. Inclut les créneaux "intermédiaires" des cours de 4h. |
| Contrainte Unicité Salle | 1 cours par salle par créneau | Même principe que l'unicité enseignant, appliqué par salle. |
| Contrainte Unicité Groupe | 1 cours par groupe par créneau | Pour chaque (groupe, créneau_global), somme des variables des cours auxquels ce groupe est inscrit ≤ 1. |
| Contrainte Charge Max | $Charge_i \leq MaxH_i$ | Inégalité PuLP par enseignant sur la somme pondérée des durées. |

---

## 7. Flux d'Exécution Complet

Schéma de l'ordre d'appel et du flux de données lors d'une exécution de `main.py` :

```
main.py
  │
  ├─ 1. DataLoader("donnees_problemes/")
  │       ├─ Lit les 7 fichiers CSV
  │       ├─ Vérifie les colonnes et formats
  │       ├─ Garde-fous de faisabilité (Capacité, Volume horaire)
  │       ├─ Construit preferences_index, cours_groupes, disponibilites
  │       └─ Calcule les effectifs des cours depuis inscriptions.csv
  │
  ├─ 2. UCTPSolver(loader)
  │       ├─ _creer_variables()
  │       │   └─ Pour chaque (prof, cours) habilité :
  │       │       ├─ Calcule k_slots = duree / 2
  │       │       ├─ Filtre les salles compatibles (type + capacité)
  │       │       └─ Pour chaque créneau t valide (dispo, pas de débordement jour) :
  │       │           └─ Crée x_{prof,cours,salle,t}
  │       │
  │       ├─ _ajouter_objectif()
  │       │   └─ Z = z_couverture + z_satisfaction - β * z_equite
  │       │       (avec linéarisation de l'équité via variables e_i)
  │       │
  │       ├─ _contrainte_couverture()
  │       │   └─ Pour chaque cours : Σ x ≤ 1
  │       │
  │       ├─ _contrainte_unicite_ressources()
  │       │   └─ Pour chaque créneau t_global occupé par x (pas seulement t_debut) :
  │       │       ├─ Unicité enseignant : Σ x ≤ 1
  │       │       ├─ Unicité salle      : Σ x ≤ 1
  │       │       └─ Unicité groupe     : Σ x ≤ 1
  │       │
  │       ├─ _contrainte_charge_max()
  │       │   └─ Pour chaque enseignant : Σ(duree * x) ≤ MaxH
  │       │
  │       └─ .solve(CBC, timeout=120s) → solution = {(i,c,s,t): 1, ...}
  │
  └─ 3. TimetableExporter(loader, solution)
          ├─ Construit le tableau central (enrichissement des clés)
          ├─ Calcule les labels horaires dynamiques (2h et 4h)
          ├─ Génère emploi_du_temps_global.xlsx
          ├─ Génère un fichier Excel par filière/niveau
          ├─ Génère un fichier Excel par enseignant
          ├─ Génère un fichier Excel par salle
          └─ Génère rapport_audit_RH.xlsx (satisfaction + équité)
```

---

## 8. Glossaire

| Terme | Définition |
|---|---|
| **PLNE** | Programmation Linéaire en Nombres Entiers. Méthode d'optimisation où les variables de décision sont contraintes à être des entiers (0 ou 1 pour les variables binaires). |
| **Variable de Décision** | La brique de base du modèle mathématique. Ici, $x_{i,c,s,t} \in \{0, 1\}$ représente le choix d'affecter un enseignant à un cours. |
| **Contrainte Dure (Hard)** | Règle qui ne peut jamais être violée sous peine d'invalider la solution. Ex: un prof ne peut pas être dans deux salles en même temps. |
| **Contrainte Souple (Soft)** | Préférence que le solveur cherche à respecter, mais qu'il peut violer si c'est la seule façon de trouver une solution. Traduite en terme dans la fonction objectif. |
| **Branch and Bound** | Algorithme de résolution de la PLNE. Il explore l'arbre des solutions de manière intelligente en élaguant les branches qui ne peuvent pas améliorer la meilleure solution trouvée. |
| **Matrice Creuse (Sparse)** | Structure de données qui ne stocke que les éléments non nuls d'une matrice. Ici, on ne stocke que les paires (prof, cours) habilitées au lieu de toutes les combinaisons possibles. |
| **Habilitation** | Autorisation explicite d'un enseignant à dispensement d'un cours, formalisée par la présence d'une entrée dans `preferences_enseignants.csv`. |
| **CBC (COIN-BC)** | Solveur open-source de Branch and Bound utilisé par PuLP pour résoudre le modèle PLNE. |
| **PuLP** | Bibliothèque Python qui permet de définir et résoudre des problèmes de PLNE de manière déclarative. |
| **Créneau de Début** | Concept clé pour les cours de durée variable. Le solveur affecte un créneau de début $t$, et le cours occupe automatiquement tous les créneaux jusqu'à $t + K_c - 1$. |
| **$K_c$** | Nombre de créneaux occupés par le cours $c$. Calculé comme $Duration_c / 2$. Vaut 1 pour un cours de 2h et 2 pour un cours de 4h. |

---

*Ce document est la référence d'implémentation du projet UCTP. Il doit être lu conjointement avec `Planification_cours_v2.md` qui contient le modèle mathématique formel.*
