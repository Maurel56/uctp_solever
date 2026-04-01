# Planification des Horaires Universitaires (UCTP) — Version 2

**Université de Ngaoundéré**
**Date de révision :** 01 Avril 2026

> Ce document est la version révisée et enrichie du modèle mathématique initial. Il conserve
> l'intégralité du contenu original et y intègre les améliorations issues de la session de
> travail collaborative. Les ajouts sont clairement signalés par la mention **(Nouveau V2)**.

---

## 1. Introduction

La planification des horaires dans un établissement d'enseignement supérieur est l'un des
problèmes combinatoires les plus complexes de la recherche opérationnelle. Connue sous
l'acronyme UCTP (*University Course Timetabling Problem*), cette problématique consiste à
organiser de manière cohérente et satisfaisante l'ensemble des activités pédagogiques sur
une période définie (ici, une semaine).

Dans notre contexte, le défi est particulièrement exigeant : il s'agit de coordonner
50 enseignants, 200 groupes d'étudiants, 100 salles et 30 créneaux horaires hebdomadaires.
L'enjeu dépasse la simple logistique ; il s'agit de respecter les vœux pédagogiques des
enseignants, d'assurer l'équité de leur charge de travail, de garantir la cohérence des
parcours étudiants et de construire un système suffisamment robuste pour gérer les
imprévus (absences, permissionnaires) sans provoquer de conflits en cascade.

Ce projet s'inscrit dans la lignée des défis d'optimisation rencontrés à l'Université de
Ngaoundéré, où la gestion des flux d'étudiants et la rareté des ressources imposent le
recours à des algorithmes de pointe pour garantir une rentrée académique sereine et
performante.

---

## 2. Modélisation Mathématique

La modélisation consiste à traduire les exigences métier en un langage mathématique
formel. Nous utilisons ici le formalisme de la Programmation Linéaire en Nombres Entiers
(PLNE).

### 2.1 Définition des Indices et des Ensembles

Pour structurer notre espace de décision, nous définissons les ensembles suivants :

- $I$ : Ensemble des enseignants, $|I| = 50$, indexé par $i$.
- $C$ : Ensemble des cours (sessions), $|C| = 300$, indexé par $c$.
- $S$ : Ensemble des salles, $|S| = 100$, indexé par $s$.
- $T$ : Ensemble des créneaux horaires, $|T| = 20$ (5 jours × 4 plages de 2h), indexé par $t$.
- $G$ : Ensemble des groupes d'étudiants, $|G| = 200$, indexé par $g$.
- $R$ : Ensemble des ressources matérielles (projecteurs, laboratoires, etc.), indexé par $r$.

### 2.2 Paramètres du Modèle (Données d'Entrée)

Les paramètres sont les valeurs fixes fournies par l'université.

**Paramètres originaux :**

- $P_{i,c}$ : Score de préférence de l'enseignant $i$ pour le cours $c$ (ex : de $0$ à $10$). **(Mise à jour V2 : Ce paramètre gère désormais l'habilitation. Si un enseignant n'a pas exprimé de préférence pour un cours, il n'est pas autorisé à l'enseigner.)**
- $D_{i,t}$ : Matrice binaire de disponibilité ($1$ si $i$ est disponible au créneau $t$, $0$ sinon).
- $Cap_s$ : Capacité physique (nombre de places) de la salle $s$.
- $Size_c$ : Nombre d'étudiants inscrits au cours $c$.
- $MaxH_i$ : Charge horaire **maximale absolue** hebdomadaire autorisée pour l'enseignant $i$.
- $Duration_c$ : Durée en heures du cours $c$. **(Harmonisation V2 : fixée à 2h pour tous les cours, correspondant exactement à un créneau horaire.)**
- $Req_{c,r}$ : Paramètre binaire ($1$ si le cours $c$ nécessite la ressource $r$, $0$ sinon).
- $Has_{s,r}$ : Paramètre binaire ($1$ si la salle $s$ possède la ressource $r$, $0$ sinon).

**Nouveaux paramètres (V2) :**

- $A_{c,g}$ **(Nouveau V2)** : Paramètre binaire d'**appartenance cours-groupe**. $A_{c,g} = 1$ si le cours $c$ fait partie du programme du groupe $g$, $0$ sinon. Ce paramètre remplace la notation informelle $C_g$ du modèle original et permet de formaliser rigoureusement la contrainte d'unicité des groupes.

$$A_{c,g} = \begin{cases} 1 & \text{si le cours } c \text{ appartient au parcours du groupe } g \\ 0 & \text{sinon} \end{cases}$$

- $\bar{H}$ **(Nouveau V2)** : Charge horaire **moyenne cible** du département, calculée comme la charge totale divisée par le nombre d'enseignants. Ce paramètre sert de référence pour l'objectif d'équité.

- $x^{init}_{i,c,s,t}$ **(Nouveau V2)** : Valeur de la variable de décision dans le **planning déjà publié**, utilisée uniquement en mode "ré-optimisation" après une absence imprévisible.

- $\alpha, \beta$ **(Nouveau V2)** : Coefficients de pondération permettant d'arbitrer entre satisfaction, équité et stabilité dans la fonction objectif globale.

### 2.3 Variables de Décision

Nous introduisons une variable binaire quadri-dimensionnelle qui représente le choix
élémentaire de planification :

$$x_{i,c,s,t} = \begin{cases} 1 & \text{si l'enseignant } i \text{ est affecté au cours } c \text{ dans la salle } s \text{ au créneau } t \\ 0 & \text{sinon} \end{cases}$$

### 2.4 Fonction Objectif

#### A. Mode Normal — Planification Initiale

L'objectif principal est de maximiser la satisfaction globale des enseignants en agrégeant
les poids de préférence pour chaque affectation réalisée :

$$Z_{sat} = \sum_{i \in I} \sum_{c \in C} \sum_{s \in S} \sum_{t \in T} P_{i,c} \cdot x_{i,c,s,t}$$

#### B. Objectif d'Équité des Charges **(Nouveau V2)**

Pour éviter qu'un enseignant soit disproportionnellement surchargé par rapport à ses
collègues, nous ajoutons un objectif de **lissage des charges** autour de la moyenne.
Soit $Charge_i$ la charge horaire effective de l'enseignant $i$ :

$$Charge_i = \sum_{c \in C} \sum_{s \in S} \sum_{t \in T} x_{i,c,s,t} \cdot Duration_c$$

L'objectif d'équité est de **minimiser la somme des écarts absolus** à la charge moyenne :

$$Z_{equite} = \sum_{i \in I} \left| Charge_i - \bar{H} \right|$$

> **Note :** La valeur absolue étant non linéaire, on la linéarise en PLNE par l'introduction
> d'une variable auxiliaire $e_i \geq 0$ représentant l'écart positif, avec les contraintes :
> $e_i \geq Charge_i - \bar{H}$ et $e_i \geq \bar{H} - Charge_i$.
> On minimise alors $\sum_{i} e_i$ en lieu et place.

#### C. Fonction Objectif Globale — Mode Normal **(Mise à jour V2)**

La fonction globale comporte **trois termes** hiérarchisés par priorité :

$$\text{Maximiser} \quad Z = Z_{couverture} + Z_{sat} - \beta \cdot Z_{equite}$$

Avec :
- $Z_{couverture} = 100 \cdot \sum_{i,c,s,t} x_{i,c,s,t}$ : **Bonus de couverture** (priorité absolue). Chaque cours planifié rapporte 100 points, ce qui dépasse largement le score de préférence max (5 points), garantissant que le solveur cherche toujours à planifier le maximum de cours avant d'optimiser les préférences.
- $Z_{sat} = \sum P_{i,c} \cdot x_{i,c,s,t}$ : satisfaction des vœux des enseignants.
- $Z_{equite} = \sum e_i$ : somme des écarts à la charge moyenne (à minimiser).

Un $\beta$ élevé accorde plus d'importance à l'équité ; un $\beta$ proche de $0$ revient
au modèle original centré sur les vœux pédagogiques. La valeur par défaut est $\beta = 0.5$.

#### D. Mode Robuste — Ré-optimisation après Absence **(Nouveau V2)**

Lorsqu'un enseignant est permissionnaire de manière imprévue, il est impensable de
recalculer entièrement l'emploi du temps (cela perturberait l'ensemble des 200 groupes
d'étudiants). En mode "réparation", la fonction objectif intègre une **pénalité de
changement** pour minimiser les perturbations au planning déjà publié :

$$\text{Maximiser} \quad Z_{robuste} = Z_{sat} - \beta \cdot Z_{equite} - \alpha \cdot \sum_{i,c,s,t} \left| x_{i,c,s,t} - x^{init}_{i,c,s,t} \right|$$

Un $\alpha$ très élevé force le solveur à chercher en priorité un remplaçant habilité au
même créneau et dans la même salle, avant d'envisager tout déplacement de cours.

---

## 3. Contraintes du Modèle

### 3.1 Contraintes de Couverture **(Mise à jour V2 — Soft Constraint)**

Chaque cours $c$ planifiable doit être affecté **au plus une fois** sur la semaine :

$$\forall c \in C : \quad \sum_{i \in I} \sum_{s \in S} \sum_{t \in T} x_{i,c,s,t} \leq 1$$

> **Note d'implémentation :** La contrainte stricte `= 1` rendrait le problème infaisable dans le cas réel, car certains cours pourraient manquer d'enseignants disponibles à un créneau compatible. La contrainte est relâchée à `≤ 1`, et **la maximisation de la couverture est assurée par le terme $Z_{couverture}$ dans la fonction objectif** (bonus de 100 par cours planifié). Ce mécanisme garantit que le solveur planifie le maximum possible tout en restant mathématiquement faisable.

#### Contrainte d'Habilitation par les Préférences **(Nouveau V2)**

Un enseignant ne peut être affecté à un cours que s'il a explicitement exprimé une 
préférence pour cette matière dans ses vœux. Si la préférence n'existe pas, l'affectation
est strictement interdite :

$$\forall i \in I,\ \forall c \in C : \quad \text{Si } P_{i,c} \text{ n'est pas défini, alors } \forall s \in S,\ \forall t \in T, \ x_{i,c,s,t} = 0$$

> **Conséquence architecturale :** Dans le DataLoader, nous ne créons des variables de
> décision $x_{i,c,s,t}$ **que** pour les triplets $(i, c, s)$ où la paire $(i,c)$ est présente
> dans `preferences_enseignants.csv` ET où la salle $s$ est compatible (bon type + capacité
> suffisante). Cela réduit l'espace de variables de **30 millions à ~15 000** (Sparse Variables avancées).

### 3.2 Conflits de Ressources (Unicité)

**Unicité de l'enseignant :** Un enseignant ne peut pas dispenser deux cours simultanément.

$$\forall i \in I,\ \forall t \in T : \quad \sum_{c \in C} \sum_{s \in S} x_{i,c,s,t} \leq 1$$

**Unicité de la salle :** Une salle ne peut pas accueillir deux cours au même créneau.

$$\forall s \in S,\ \forall t \in T : \quad \sum_{i \in I} \sum_{c \in C} x_{i,c,s,t} \leq 1$$

**Unicité du groupe **(Améliorée V2)** :** Un groupe d'étudiants ne peut assister à deux cours
simultanément. Grâce au paramètre $A_{c,g}$, cette contrainte est désormais formalisée
rigoureusement (sans dépendre de la notation informelle $C_g$) :

$$\forall g \in G,\ \forall t \in T : \quad \sum_{i \in I} \sum_{c \in C} \sum_{s \in S} x_{i,c,s,t} \cdot A_{c,g} \leq 1$$

### 3.3 Contraintes d'Adéquation

**Capacité des salles :** La salle affectée doit pouvoir contenir tous les étudiants du cours.

$$\forall i \in I,\ \forall c \in C,\ \forall s \in S,\ \forall t \in T : \quad x_{i,c,s,t} \cdot Size_c \leq Cap_s$$

**Disponibilités temporelles :** Un cours ne peut être planifié que si l'enseignant est disponible.

$$\forall i \in I,\ \forall c \in C,\ \forall s \in S,\ \forall t \in T : \quad x_{i,c,s,t} \leq D_{i,t}$$

**Ressources matérielles :** La salle doit posséder les équipements requis par le cours.

$$\forall i \in I,\ \forall c \in C,\ \forall s \in S,\ \forall t \in T,\ \forall r \in R : \quad x_{i,c,s,t} \cdot Req_{c,r} \leq Has_{s,r}$$

### 3.4 Charge de Travail et Équité

**Plafond absolu (Hard Constraint — inchangée) :** Pour éviter toute surcharge au-delà du
plafond légal ou réglementaire, la contrainte dure originale est maintenue :

$$\forall i \in I : \quad \sum_{c \in C} \sum_{s \in S} \sum_{t \in T} x_{i,c,s,t} \cdot Duration_c \leq MaxH_i$$

**Lissage par rapport à la moyenne (Soft Constraint — Nouveau V2) :** Cette contrainte
remplace l'ancienne approche qui se contentait d'un plafond maximum. Nous minimisons
désormais activement les écarts à la charge moyenne $\bar{H}$, ce qui garantit l'équité
entre collègues :

$$\text{Minimiser} \quad Z_{equite} = \sum_{i \in I} \left| Charge_i - \bar{H} \right| \quad \text{avec} \quad \bar{H} = \frac{1}{|I|} \sum_{i \in I} Charge_i$$

> **Relation entre les deux contraintes :** Le plafond $MaxH_i$ est une **barrière absolue
> infranchissable**. L'objectif de lissage, lui, opère en-dessous de ce plafond pour
> rapprocher toutes les charges de la valeur idéale commune.

---

## 4. Justification du Formalisme

Le choix de la PLNE se justifie par la nature discrète des décisions : une affectation
est entière (0 ou 1). Bien que ce problème soit NP-difficile, la formulation linéaire
permet d'utiliser des techniques de Séparation et Évaluation (*Branch and Bound*) ou
de Coupes de Gomory, garantissant ainsi l'optimalité sur des instances de taille
moyenne, ce qui est crucial pour l'équité de traitement au sein de l'université.

---

## 5. Méthode de Résolution

Une fois le modèle mathématique posé, il convient d'analyser sa structure pour choisir la
stratégie de résolution la plus performante. Cette section détaille les propriétés
computationnelles du problème et justifie l'approche algorithmique retenue.

### 5.1 Analyse de la Structure du Problème

Le problème de planification des horaires est une forme complexe de problème d'optimisation
combinatoire. Sa structure peut être décomposée en deux sous-problèmes classiques de la
théorie des graphes :

**La coloration de graphe :** Chaque cours peut être vu comme un sommet d'un graphe. Une
arête relie deux cours s'ils partagent le même enseignant ou le même groupe d'étudiants.
Trouver un créneau pour chaque cours revient à colorier les sommets du graphe de sorte
que deux sommets adjacents n'aient pas la même "couleur" (créneau).

**Le problème du sac à dos (*Knapsack*) :** L'affectation des groupes aux salles selon
leur capacité ($Size_c \leq Cap_s$) s'apparente à un problème de remplissage de conteneurs
sous contrainte de volume.

### 5.2 Analyse de la Complexité

Ce problème appartient à la catégorie **NP-difficile**.

**Preuve intuitive :** Le nombre de combinaisons possibles pour affecter 200 cours à
30 créneaux et 100 salles par 50 enseignants est de l'ordre de $(30 \times 100)^{200}$.
Même en éliminant les solutions non réalisables, l'espace de recherche reste trop vaste
pour une exploration exhaustive.

**Implication :** Le temps de résolution croît de façon exponentielle avec la taille de
l'instance. Il faut donc arbitrer entre l'optimalité (trouver la solution parfaite) et
la tractabilité (trouver une solution en un temps raisonnable).

### 5.3 Choix de l'Algorithme : Branch and Bound (PLNE)

Nous retenons la Programmation Linéaire en Nombres Entiers via l'algorithme
**Branch and Bound** (Séparation et Évaluation), implémenté avec la bibliothèque Python **PuLP**.

**Justification :**
- **Garantie d'optimalité :** Contrairement aux métaheuristiques, la PLNE prouve que la solution est la meilleure possible.
- **Rigueur des contraintes :** Le solveur garantit qu'aucune contrainte dure n'est violée.
- **Flexibilité :** Il est aisé d'ajouter ou de modifier une contrainte sans changer l'algorithme.

### 5.4 Justification Théorique du Branch and Bound

L'algorithme procède par exploration intelligente de l'arbre des solutions :

- **Relaxation linéaire :** Le solveur résout d'abord le problème en autorisant des variables continues (ex : $x = 0.5$), ce qui donne une borne supérieure.
- **Séparation (*Branching*) :** Si la solution n'est pas entière, le problème est divisé en deux sous-problèmes ($x = 0$ et $x = 1$).
- **Évaluation (*Bounding*) :** Les branches qui ne peuvent pas améliorer la meilleure solution trouvée sont élaguées, réduisant drastiquement l'espace de recherche.

### 5.5 Limites et Alternatives

Si l'instance venait à doubler (ex : 400 cours), le temps de calcul du Branch and Bound
pourrait devenir prohibitif. Dans ce cas, nous basculerions vers une **métaheuristique de
recherche locale Tabou** ou un **algorithme génétique**, afin de privilégier la rapidité
sur l'optimalité absolue.

---

*Ce document est la référence mathématique du projet. Il doit être consulté avant toute décision d'implémentation.*
