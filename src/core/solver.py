"""
Module : src/core/solver.py
Rôle   : Modélisation et résolution du problème UCTP en PLNE via la bibliothèque PuLP.
         Supporte désormais les cours de durée variable (2h et 4h).
"""

import pulp
from collections import defaultdict
from src.io.loader import DataLoader


class UCTPSolver:
    """
    Solveur UCTP supportant des durées variables (2h et 4h).
    Un cours de 4h occupe 2 créneaux consécutifs de 2h.
    """

    def __init__(self, loader: DataLoader, beta: float = 0.5):
        self.loader = loader
        self.beta = beta
        self.statut = None
        self.solution = {}
        self.valeur_objectif = 0.0

        self._enseignants = list(loader.enseignants["enseignant_id"])
        self._cours       = list(loader.cours["cours_id"])
        self._salles      = list(loader.salles["salle_id"])
        self._creneaux    = list(range(len(loader.creneaux)))

        self._index_cours      = loader.cours.set_index("cours_id")
        self._index_salles     = loader.salles.set_index("salle_id")
        self._index_enseignant = loader.enseignants.set_index("enseignant_id")

        self._probleme = pulp.LpProblem("UCTP_V2", pulp.LpMaximize)
        self._variables_x = {}

    def resoudre(self, timeout_secondes: int = 120):
        print("\n[UCTPSolver] 🔧 Construction du modèle PLNE (Durées variables)...")
        self._creer_variables()
        self._ajouter_objectif()
        self._contrainte_couverture()
        self._contrainte_unicite_ressources() # Fusionnée pour gérer les intervalles
        self._contrainte_charge_max()

        n_vars        = len(self._variables_x)
        n_contraintes = len(self._probleme.constraints)
        print(f"[UCTPSolver] ✅ Modèle construit : {n_vars} variables, {n_contraintes} contraintes.")

        solveur = pulp.PULP_CBC_CMD(timeLimit=timeout_secondes, msg=0)
        self._probleme.solve(solveur)

        self.statut = pulp.LpStatus[self._probleme.status]
        self.valeur_objectif = pulp.value(self._probleme.objective) or 0.0

        if self.statut in ("Optimal", "Feasible"):
            self._extraire_solution()
        return self.solution

    def _creer_variables(self):
        """
        Crée les variables x_{i,c,s,t} où t est le créneau de DEBUT du cours.
        """
        paires_actives = self.loader.get_paires_actives()
        idx_cours  = self._index_cours
        idx_salles = self._index_salles

        for (ens_id, cours_id) in paires_actives:
            duree_h = idx_cours.loc[cours_id, "duree"]
            k_slots = int(duree_h / 2.0) # Nombre de créneaux (1 ou 2)
            
            prerequis = idx_cours.loc[cours_id, "prerequis"]
            effectif  = idx_cours.loc[cours_id, "effectif"]

            salles_ok = idx_salles[
                (idx_salles["type"] == prerequis) & (idx_salles["capacite"] >= effectif)
            ].index.tolist()

            for t in self._creneaux:
                # Vérifier si le cours "tient" dans la journée sans déborder
                if t + k_slots > len(self._creneaux):
                    continue
                
                # Vérifier si le cours change de jour (ex: Lundi soir -> Mardi matin interdit)
                label_debut = self.loader.creneaux[t]
                label_fin   = self.loader.creneaux[t + k_slots - 1]
                if label_debut.split('_')[0] != label_fin.split('_')[0]:
                    continue

                # Vérifier la disponibilité de l'enseignant sur TOUS les créneaux occupés
                if not all(self.loader.get_disponibilite(ens_id, t + offset) for offset in range(k_slots)):
                    continue

                for salle_id in salles_ok:
                    nom_var = f"x_{ens_id}_{cours_id}_{salle_id}_t{t}"
                    self._variables_x[(ens_id, cours_id, salle_id, t)] = pulp.LpVariable(nom_var, cat="Binary")

        print(f"[UCTPSolver]   → {len(self._variables_x)} variables de début créées.")

    def _ajouter_objectif(self):
        BONUS_COUVERTURE = 100
        z_couv = pulp.lpSum(BONUS_COUVERTURE * var for var in self._variables_x.values())
        z_sat  = pulp.lpSum(self.loader.get_preference(i, c) * var for (i, c, s, t), var in self._variables_x.items())

        charges = {ens: pulp.lpSum(self._index_cours.loc[c, "duree"] * var 
                   for (i, c, s, t), var in self._variables_x.items() if i == ens)
                   for ens in self._enseignants}

        h_bar = self.loader.cours["duree"].sum() / len(self._enseignants)
        e_vars = {ens: pulp.LpVariable(f"e_{ens}", lowBound=0) for ens in self._enseignants}
        
        for ens in self._enseignants:
            self._probleme += e_vars[ens] >= charges[ens] - h_bar
            self._probleme += e_vars[ens] >= h_bar - charges[ens]

        self._probleme += z_couv + z_sat - self.beta * pulp.lpSum(e_vars.values())

    def _contrainte_couverture(self):
        cours_vars = defaultdict(list)
        for (i, c, s, t), var in self._variables_x.items():
            cours_vars[c].append(var)
        for c in self._cours:
            if c in cours_vars:
                self._probleme += pulp.lpSum(cours_vars[c]) <= 1

    def _contrainte_unicite_ressources(self):
        """
        Gère les conflits de créneaux en tenant compte de la durée de chaque cours.
        Un prof/salle/groupe est occupé au créneau T si un cours a débuté à t <= T
        et finit après T.
        """
        # Indexation : ressources -> créneau -> variables qui l'occupent
        ens_occup = defaultdict(lambda: defaultdict(list))
        salle_occup = defaultdict(lambda: defaultdict(list))
        groupe_occup = defaultdict(lambda: defaultdict(list))

        for (i, c, s, t), var in self._variables_x.items():
            k_slots = int(self._index_cours.loc[c, "duree"] / 2.0)
            for offset in range(k_slots):
                t_global = t + offset
                ens_occup[i][t_global].append(var)
                salle_occup[s][t_global].append(var)
                for g in self.loader.get_groupes_du_cours(c):
                    groupe_occup[g][t_global].append(var)

        # Application des contraintes d'unicité (max 1 cours par créneau)
        for i in self._enseignants:
            for t in self._creneaux:
                if ens_occup[i][t]:
                    self._probleme += pulp.lpSum(ens_occup[i][t]) <= 1, f"u_ens_{i}_t{t}"
        
        for s in self._salles:
            for t in self._creneaux:
                if salle_occup[s][t]:
                    self._probleme += pulp.lpSum(salle_occup[s][t]) <= 1, f"u_salle_{s}_t{t}"

        for g in groupe_occup:
            for t in self._creneaux:
                if groupe_occup[g][t]:
                    self._probleme += pulp.lpSum(groupe_occup[g][t]) <= 1, f"u_grp_{g}_t{t}"

    def _contrainte_charge_max(self):
        for i in self._enseignants:
            charge = pulp.lpSum(self._index_cours.loc[c, "duree"] * var 
                               for (ei, c, s, t), var in self._variables_x.items() if ei == i)
            self._probleme += charge <= self._index_enseignant.loc[i, "charge_max"]

    def _extraire_solution(self):
        self.solution = {cle: 1 for cle, var in self._variables_x.items() if pulp.value(var) == 1}
