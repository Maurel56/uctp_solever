"""
Module : src/reporting/exporter.py
Rôle   : Traduit la solution binaire du solveur en emplois du temps lisibles
         et les exporte sous format Excel (multi-vues).

Ce module incarne le principe "Un module = Une responsabilité" :
il ne calcule rien, ne lit aucun CSV — il reçoit la solution et la transforme.

Vues Excel générées :
    1. par_filiere_niveau/   (ex: M2_INFO.xlsx)
    2. par_enseignant/       (ex: E014.xlsx)
    3. par_salle/            (ex: S0032.xlsx)
    4. emploi_du_temps_global.xlsx  (toutes les affectations)
"""

import os
import pandas as pd
from collections import defaultdict
from src.io.loader import DataLoader


class TimetableExporter:
    """
    Génère les exports Excel à partir de la solution du solveur UCTP.

    Usage :
        exporter = TimetableExporter(loader, solution, dossier_sortie="output")
        exporter.exporter_tout()
    """

    def __init__(self, loader: DataLoader, solution: dict, dossier_sortie: str = "output"):
        """
        Args:
            loader         : DataLoader déjà chargé (source des données de référence).
            solution       : Dictionnaire {(ens_id, cours_id, salle_id, t): 1}
                             retourné par UCTPSolver.resoudre().
            dossier_sortie : Dossier où seront écrits tous les fichiers Excel.
        """
        self.loader = loader
        self.solution = solution
        self.dossier_sortie = dossier_sortie

        # Index rapides depuis les DataFrames du loader
        self._idx_cours      = loader.cours.set_index("cours_id")
        self._idx_salles      = loader.salles.set_index("salle_id")
        self._idx_enseignants = loader.enseignants.set_index("enseignant_id")
        self._idx_groupes     = loader.groupes.set_index("groupe_id")

        # Construction du tableau en mémoire (source de toutes les vues)
        self._df_solution = self._construire_dataframe_solution()

        # Créer les dossiers de sortie
        os.makedirs(os.path.join(dossier_sortie, "par_filiere_niveau"), exist_ok=True)
        os.makedirs(os.path.join(dossier_sortie, "par_enseignant"), exist_ok=True)
        os.makedirs(os.path.join(dossier_sortie, "par_salle"), exist_ok=True)

    # =========================================================================
    # MÉTHODE PRINCIPALE
    # =========================================================================

    def exporter_tout(self):
        """Lance l'export de toutes les vues."""
        print("\n[Exporter] 📊 Génération des exports Excel...")
        self._exporter_global()
        self._exporter_par_filiere_niveau()
        self._exporter_par_enseignant()
        self._exporter_par_salle()
        print(f"[Exporter] ✅ Tous les fichiers ont été écrits dans : '{self.dossier_sortie}/'")

    # =========================================================================
    # CONSTRUCTION DU DATAFRAME CENTRAL
    # =========================================================================

    def _construire_dataframe_solution(self) -> pd.DataFrame:
        """
        Transforme le dictionnaire brut {(i,c,s,t): 1} en un DataFrame riche
        en enrichissant les IDs avec les informations de chaque entité.

        Colonnes produites :
            enseignant_id, nom_enseignant, cours_id, intitule_cours, type_cours,
            duree, salle_id, nom_salle, type_salle, creneau_idx, creneau_label,
            groupes_concernes, filiere_groupe, niveau_groupe
        """
        lignes = []
        for (ens_id, cours_id, salle_id, t), _ in self.solution.items():
            ens   = self._idx_enseignants.loc[ens_id]
            cours = self._idx_cours.loc[cours_id]
            salle = self._idx_salles.loc[salle_id]
            creneau_label = self.loader.creneaux[t]

            # Groupes concernés par ce cours (via la table de jonction)
            ids_groupes = self.loader.get_groupes_du_cours(cours_id)
            
            # On traduit les IDs techniques en noms lisibles (ex: G0001 -> INFO-M2)
            noms_groupes = []
            for gid in ids_groupes:
                if gid in self._idx_groupes.index:
                    grp = self._idx_groupes.loc[gid]
                    noms_groupes.append(f"{grp['filiere']}-{grp['niveau']}")
                else:
                    noms_groupes.append(gid)

            # Doublons possibles (ex: plusieurs groupes de la même filière), on déduplique
            noms_groupes_uniques = sorted(list(set(noms_groupes)))

            # On prend la filière et le niveau du premier groupe pour la vue filière
            if ids_groupes:
                grp = self._idx_groupes.loc[ids_groupes[0]]
                filiere = grp["filiere"]
                niveau  = grp["niveau"]
            else:
                filiere, niveau = "N/A", "N/A"

            # Calcul du label horaire complet (ex: "8h-10h" devient "8h-12h" pour 4.0h)
            k_slots = int(cours["duree"] / 2.0)
            label_debut = self.loader.creneaux[t]
            if k_slots > 1:
                # On prend la fin du créneau suivant
                label_fin = self.loader.creneaux[t + k_slots - 1]
                heure_debut = label_debut.split('_')[1].split('-')[0]
                heure_fin   = label_fin.split('_')[1].split('-')[1]
                jour        = label_debut.split('_')[0]
                creneau_label = f"{jour}_{heure_debut}-{heure_fin}"
            else:
                creneau_label = label_debut

            lignes.append({
                "enseignant_id"   : ens_id,
                "nom_enseignant"  : ens["nom"],
                "cours_id"        : cours_id,
                "intitule_cours"  : cours["intitule"],
                "type_cours"      : cours["type_cours"],
                "duree"           : cours["duree"],
                "salle_id"        : salle_id,
                "nom_salle"       : salle["nom"],
                "type_salle"      : salle["type"],
                "creneau_idx"     : t,
                "creneau_label"   : creneau_label, # Nouveau label dynamique (ex: Lundi_8h-12h)
                "groupes_concernes": ", ".join(noms_groupes_uniques),
                "filiere"         : filiere,
                "niveau"          : niveau,
            })



        df = pd.DataFrame(lignes)
        if not df.empty:
            df = df.sort_values(["creneau_idx", "salle_id"])
        print(f"[Exporter] ✅ Tableau central construit : {len(df)} affectations.")
        return df

    # =========================================================================
    # VUE 1 : Emploi du temps global (toutes les salles)
    # =========================================================================

    def _exporter_global(self):
        """Exporte le planning maître global en un seul fichier Excel."""
        chemin = os.path.join(self.dossier_sortie, "emploi_du_temps_global.xlsx")
        colonnes = [
            "creneau_label", "enseignant_id", "nom_enseignant",
            "cours_id", "intitule_cours", "type_cours", "duree",
            "salle_id", "nom_salle", "groupes_concernes"
        ]
        df = self.df_solution_public[colonnes] if not self._df_solution.empty else pd.DataFrame(columns=colonnes)
        self._ecrire_excel(chemin, {"Planning Global": self._df_solution[colonnes]})
        print(f"[Exporter]   → Global            : {chemin}")

    # =========================================================================
    # VUE 2 : Par Filière + Niveau (ex: M2_INFO.xlsx)
    # =========================================================================

    def _exporter_par_filiere_niveau(self):
        """Génère un fichier Excel par combinaison (filière, niveau) unique."""
        if self._df_solution.empty:
            return

        groupes_filieres = self._df_solution.groupby(["filiere", "niveau"])
        for (filiere, niveau), df_groupe in groupes_filieres:
            nom_fichier = f"{niveau}_{filiere}.xlsx"
            chemin = os.path.join(self.dossier_sortie, "par_filiere_niveau", nom_fichier)
            colonnes = ["creneau_label", "intitule_cours", "type_cours",
                        "nom_enseignant", "nom_salle", "groupes_concernes"]
            self._ecrire_excel(chemin, {f"{niveau} {filiere}": df_groupe[colonnes]})

        nb = len(groupes_filieres)
        print(f"[Exporter]   → Par filière/niveau : {nb} fichiers générés.")

    # =========================================================================
    # VUE 3 : Par enseignant (ex: E014.xlsx)
    # =========================================================================

    def _exporter_par_enseignant(self):
        """Génère un fichier Excel personnel pour chaque enseignant planifié."""
        if self._df_solution.empty:
            return

        groupes_ens = self._df_solution.groupby("enseignant_id")
        for ens_id, df_ens in groupes_ens:
            nom_fichier = f"{ens_id}.xlsx"
            chemin = os.path.join(self.dossier_sortie, "par_enseignant", nom_fichier)
            nom_ens = df_ens["nom_enseignant"].iloc[0]
            colonnes = ["creneau_label", "intitule_cours", "type_cours",
                        "nom_salle", "groupes_concernes", "duree"]
            self._ecrire_excel(chemin, {f"Planning {nom_ens}": df_ens[colonnes]})

        print(f"[Exporter]   → Par enseignant    : {len(groupes_ens)} fichiers générés.")

    # =========================================================================
    # VUE 4 : Par salle (ex: S0032.xlsx)
    # =========================================================================

    def _exporter_par_salle(self):
        """Génère un fichier Excel pour chaque salle planifiée."""
        if self._df_solution.empty:
            return

        groupes_salle = self._df_solution.groupby("salle_id")
        for salle_id, df_salle in groupes_salle:
            nom_fichier = f"{salle_id}.xlsx"
            chemin = os.path.join(self.dossier_sortie, "par_salle", nom_fichier)
            nom_salle = df_salle["nom_salle"].iloc[0]
            colonnes = ["creneau_label", "intitule_cours", "type_cours",
                        "nom_enseignant", "groupes_concernes", "duree"]
            self._ecrire_excel(chemin, {f"Salle {nom_salle}": df_salle[colonnes]})

        print(f"[Exporter]   → Par salle         : {len(groupes_salle)} fichiers générés.")

    # =========================================================================
    # VUE 5 : Rapport d'audit RH (statistiques de qualité)
    # =========================================================================

    def _exporter_rapport_audit(self):
        """
        Génère un rapport Excel d'audit de la qualité de la solution.

        Statistiques calculées (avec formules documentées) :
            - Taux de satisfaction global
            - Charge hebdomadaire par enseignant vs moyenne
            - Écart max et écart moyen à la charge cible (indicateur équité)
            - Taux d'occupation des salles
        """
        chemin = os.path.join(self.dossier_sortie, "rapport_audit_RH.xlsx")

        # --- Statistique 1 : Satisfaction ---
        # Formule : Z_sat = Σ P_{i,c} · x_{i,c,s,t} / Z_sat_max_theorique
        # Z_sat_max_theorique = Σ max_preference_de_chaque_cours_affecte
        score_obtenu = sum(
            self.loader.get_preference(i, c)
            for (i, c, s, t) in self.solution
        )
        score_max_possible = sum(
            max((self.loader.get_preference(i2, c2)
                 for (i2, c2) in self.loader.get_paires_actives()
                 if c2 == c), default=0)
            for (i, c, s, t) in self.solution
        )
        taux_satisfaction = (score_obtenu / score_max_possible * 100) if score_max_possible > 0 else 0

        # --- Statistique 2 : Charge par enseignant ---
        # Formule : Charge_i = Σ Duration_c pour x_{i,c,s,t} = 1
        charges = defaultdict(float)
        for (i, c, s, t) in self.solution:
            duree = self.loader.cours.set_index("cours_id").loc[c, "duree"]
            charges[i] += duree

        charge_moyenne = sum(charges.values()) / len(charges) if charges else 0
        ecarts = {i: abs(h - charge_moyenne) for i, h in charges.items()}
        ecart_moyen = sum(ecarts.values()) / len(ecarts) if ecarts else 0
        ecart_max   = max(ecarts.values()) if ecarts else 0

        # DataFrame pour la feuille "Charges Enseignants"
        df_charges = pd.DataFrame([
            {
                "enseignant_id"   : i,
                "nom"             : self._idx_enseignants.loc[i, "nom"] if i in self._idx_enseignants.index else i,
                "charge_reelle_h" : round(h, 1),
                "charge_max_h"    : self._idx_enseignants.loc[i, "charge_max"] if i in self._idx_enseignants.index else "N/A",
                "charge_moyenne_h": round(charge_moyenne, 1),
                "ecart_h"         : round(ecarts.get(i, 0), 1),
            }
            for i, h in sorted(charges.items())
        ])

        # DataFrame pour la feuille "Résumé"
        df_resume = pd.DataFrame([
            {"Indicateur": "Cours planifiés", "Valeur": len(self.solution)},
            {"Indicateur": "Score satisfaction obtenu (Σ P·x)", "Valeur": score_obtenu},
            {"Indicateur": "Score satisfaction max théorique", "Valeur": score_max_possible},
            {"Indicateur": "Taux de satisfaction (%)", "Valeur": f"{taux_satisfaction:.1f}%"},
            {"Indicateur": "Charge horaire moyenne (H_bar)", "Valeur": f"{charge_moyenne:.1f}h"},
            {"Indicateur": "Écart moyen à la moyenne (Équité)", "Valeur": f"{ecart_moyen:.1f}h"},
            {"Indicateur": "Écart maximum à la moyenne", "Valeur": f"{ecart_max:.1f}h"},
        ])

        # Feuille de documentation des formules
        df_formules = pd.DataFrame([
            {
                "Indicateur": "Taux de satisfaction",
                "Formule": "Z_sat = Σ P_{i,c}·x_{i,c,s,t}",
                "Interprétation": "Somme des scores de préférence des affectations retenues."
            },
            {
                "Indicateur": "Charge réelle (heures/semaine)",
                "Formule": "Charge_i = Σ Duration_c · x_{i,c,s,t}  pour i fixé",
                "Interprétation": "Total des heures de cours attribuées à chaque enseignant."
            },
            {
                "Indicateur": "Charge moyenne H_bar",
                "Formule": "H_bar = (1/|I|) · Σ Charge_i",
                "Interprétation": "Distribution idéale équitable entre tous les enseignants actifs."
            },
            {
                "Indicateur": "Écart à la moyenne (Équité)",
                "Formule": "e_i = |Charge_i - H_bar|",
                "Interprétation": "Plus e_i est proche de 0, plus l'enseignant i est traité équitablement."
            },
        ])

        self._ecrire_excel(chemin, {
            "Résumé"              : df_resume,
            "Charges Enseignants" : df_charges,
            "Formules & Méthodes" : df_formules,
        })
        print(f"[Exporter]   → Rapport audit RH  : {chemin}")
        print(f"[Exporter]   → Taux satisfaction : {taux_satisfaction:.1f}%")
        print(f"[Exporter]   → Équité (écart moy): {ecart_moyen:.1f}h")

    # =========================================================================
    # UTILITAIRE D'ÉCRITURE EXCEL
    # =========================================================================

    @property
    def df_solution_public(self):
        """Propriété publique pour accéder au DataFrame de solution depuis l'extérieur."""
        return self._df_solution

    def _ecrire_excel(self, chemin: str, feuilles: dict):
        """
        Écrit un classeur Excel multi-feuilles.

        Args:
            chemin  : Chemin complet du fichier à créer.
            feuilles: Dictionnaire {nom_feuille: DataFrame}.
        """
        with pd.ExcelWriter(chemin, engine="openpyxl") as writer:
            for nom_feuille, df in feuilles.items():
                df.to_excel(writer, sheet_name=nom_feuille, index=False)


# ===========================================================================
# SCRIPT DE TEST AUTONOME (nécessite d'avoir lancé le solver avant)
# ===========================================================================
if __name__ == "__main__":
    import sys
    from src.io.loader import DataLoader
    from src.core.solver import UCTPSolver

    print("=" * 60)
    print(" TEST TimetableExporter — Génération des fichiers Excel")
    print("=" * 60)

    loader = DataLoader(dossier="donnees_problemes")
    solver = UCTPSolver(loader=loader, beta=0.5)
    solution = solver.resoudre(timeout_secondes=30)

    if solution:
        exporter = TimetableExporter(loader, solution, dossier_sortie="output")
        exporter.exporter_tout()
    else:
        print("[Exporter] ⚠️  Aucune solution à exporter.")
