"""
Module : src/io/loader.py
Rôle   : Lecture, validation et structuration des données d'entrée du solveur UCTP.

Ce module joue le rôle de "Gardien" : il s'assure que les données sont cohérentes
et mathématiquement faisables AVANT de les transmettre au solveur PuLP.
Aucune variable de décision n'est créée ici ; ce module ne fait que préparer
des structures de données Python "propres" et prêtes à l'emploi.
"""

import pandas as pd
import ast
import os


class FeasibilityError(Exception):
    """Exception levée quand les données rendent le problème mathématiquement insoluble."""
    pass


class DataLoader:
    """
    Charge et valide l'ensemble des données du problème UCTP depuis le dossier CSV.

    Attributs publics (accessibles par le Solver) :
        enseignants   (DataFrame) : Informations sur les 50 enseignants.
        groupes       (DataFrame) : Informations sur les 200 groupes.
        salles        (DataFrame) : Informations sur les 100 salles.
        cours         (DataFrame) : Informations sur les 300 cours.
        preferences   (DataFrame) : Vœux des enseignants (source d'habilitation V2).
        inscriptions  (DataFrame) : Table de jonction cours <-> groupes (relation N:M).
        creneaux      (list[str]) : Liste ordonnée des 30 créneaux horaires de la semaine.

        disponibilites (dict) : {enseignant_id: [bool, bool, ...]} — 30 booléens.
        preferences_index (dict) : {(enseignant_id, cours_id): score} — Matrice creuse.
        cours_groupes (dict) : {cours_id: [groupe_id, ...]} — Groupes liés à chaque cours.
    """

    def __init__(self, dossier: str = "donnees_problemes"):
        """
        Initialise le DataLoader et déclenche immédiatement le chargement complet.

        Args:
            dossier: Chemin relatif ou absolu vers le dossier contenant les CSV.
        """
        self.dossier = dossier
        self._charger_tous_les_fichiers()
        self._construire_index_preferences()
        self._construire_index_disponibilites()
        self._construire_index_cours_groupes()
        self._verifier_faisabilite()

    # -------------------------------------------------------------------------
    # ÉTAPE 1 : Chargement brut des fichiers CSV
    # -------------------------------------------------------------------------

    def _charger_tous_les_fichiers(self):
        """Lit les 6 fichiers CSV et le fichier texte des créneaux."""
        chemin = self.dossier

        self.enseignants = pd.read_csv(os.path.join(chemin, "enseignants.csv"))
        self.groupes     = pd.read_csv(os.path.join(chemin, "groupes.csv"))
        self.salles      = pd.read_csv(os.path.join(chemin, "salles.csv"))
        self.cours       = pd.read_csv(os.path.join(chemin, "cours.csv"))
        self.preferences = pd.read_csv(os.path.join(chemin, "preferences_enseignants.csv"))
        self.inscriptions = pd.read_csv(os.path.join(chemin, "inscriptions.csv"))

        # Lecture des créneaux depuis le fichier texte
        with open(os.path.join(chemin, "creneaux.txt"), "r") as f:
            self.creneaux = [ligne.strip() for ligne in f if ligne.strip()]

        print(f"[DataLoader] ✅ Chargement réussi :")
        print(f"  - Enseignants : {len(self.enseignants)}")
        print(f"  - Groupes     : {len(self.groupes)}")
        print(f"  - Salles      : {len(self.salles)}")
        print(f"  - Cours       : {len(self.cours)}")
        print(f"  - Créneaux    : {len(self.creneaux)}")
        print(f"  - Préférences : {len(self.preferences)}")
        print(f"  - Inscriptions: {len(self.inscriptions)}")

    # -------------------------------------------------------------------------
    # ÉTAPE 2 : Construction des index (structures rapides pour le Solver)
    # -------------------------------------------------------------------------

    def _construire_index_preferences(self):
        """
        Construit la Matrice Creuse des préférences.

        Principe (Architecture V2 / Brainstorming) :
        Au lieu de parcourir (50 profs x 300 cours) = 15 000 paires possibles,
        on ne conserve QUE les paires (enseignant, cours) déclarées dans le CSV.
        Cela réduit les variables PuLP de millions à quelques centaines, rendant
        la résolution réaliste au lieu de faire planter la machine.

        Résultat : {(enseignant_id, cours_id): score_preference}
        """
        self.preferences_index = {
            (row["enseignant_id"], row["cours_id"]): int(row["preference"])
            for _, row in self.preferences.iterrows()
        }
        print(f"[DataLoader] ✅ Matrice creuse construite : {len(self.preferences_index)} paires (prof, cours) actives.")

    def _construire_index_disponibilites(self):
        """
        Parse la colonne 'disponibilites' (stockée sous forme de chaîne numpy)
        et construit un dictionnaire {enseignant_id: [bool, bool, ...]}.

        Exemple de valeur brute dans le CSV :
            "[ True False  True ...]"
        On la nettoie pour obtenir une liste Python de booléens.
        """
        self.disponibilites = {}
        for _, row in self.enseignants.iterrows():
            eid = row["enseignant_id"]
            # La chaîne numpy "[ True False ...]" nécessite un nettoyage avant parsing
            chaine = str(row["disponibilites"])
            # Conversion robuste : on remplace les tokens numpy par des booléens Python
            chaine_propre = chaine.replace("[ ", "[").replace("  ", " ").strip()
            valeurs = chaine_propre.strip("[]").split()
            self.disponibilites[eid] = [v == "True" for v in valeurs]

        print(f"[DataLoader] ✅ Disponibilités parsées pour {len(self.disponibilites)} enseignants.")

    def _construire_index_cours_groupes(self):
        """
        Construit un dictionnaire {cours_id: [groupe_id, ...]} depuis la table de jonction.

        Ce dictionnaire sera utilisé par le Solver pour appliquer la contrainte :
        "Un groupe ne peut pas assister à deux cours simultanément."
        (Contrainte d'Unicité du Groupe — Paramètre A_{c,g} du modèle V2)
        """
        self.cours_groupes = {}
        for _, row in self.inscriptions.iterrows():
            cid = row["cours_id"]
            gid = row["groupe_id"]
            if cid not in self.cours_groupes:
                self.cours_groupes[cid] = []
            self.cours_groupes[cid].append(gid)

        print(f"[DataLoader] ✅ Index cours->groupes construit pour {len(self.cours_groupes)} cours.")

    # -------------------------------------------------------------------------
    # ÉTAPE 3 : Vérifications de faisabilité (Garde-fous pré-résolution)
    # -------------------------------------------------------------------------

    def _verifier_faisabilite(self):
        """
        Lance les deux contrôles mathématiques AVANT d'appeler PuLP.

        Objectif : Éviter qu'un problème structurellement insoluble gaspille
        plusieurs minutes de calcul avant d'échouer silencieusement ("INFEASIBLE").
        Ces vérifications s'effectuent en microsecondes.
        """
        self._verifier_capacite_salles()
        self._verifier_volume_horaire()

    def _verifier_capacite_salles(self):
        """
        Garde-Fou #1 : Aucun cours ne doit excéder la capacité de la plus grande salle.

        Si un cours a 500 étudiants et que le plus grand amphi n'a que 450 places,
        la contrainte de capacité (x * Size_c <= Cap_s) sera mathématiquement inviolable.
        Le solveur planterait en "INFEASIBLE" après de longs calculs.
        On préfère l'arrêter ICI avec un message clair.
        """
        effectif_max_cours = self.cours["effectif"].max()
        capacite_max_salle = self.salles["capacite"].max()

        if effectif_max_cours > capacite_max_salle:
            # On identifie les cours fautifs pour aider l'utilisateur
            cours_problematiques = self.cours[
                self.cours["effectif"] > capacite_max_salle
            ][["cours_id", "intitule", "effectif"]]

            message = (
                f"\n[DataLoader] ❌ ERREUR DE FAISABILITÉ — Capacité des salles insuffisante !\n"
                f"  La capacité maximale de vos salles est : {capacite_max_salle} places.\n"
                f"  Mais les cours suivants dépassent cette limite :\n"
                f"{cours_problematiques.to_string(index=False)}\n\n"
                f"  ➡️  Veuillez revoir les effectifs de ces cours ou ajouter une salle plus grande."
            )
            raise FeasibilityError(message)

        print(f"[DataLoader] ✅ Garde-fou Capacité OK "
              f"(Effectif max cours={effectif_max_cours}, Capacité max salle={capacite_max_salle}).")

    def _verifier_volume_horaire(self):
        """
        Garde-Fou #2 : Le volume horaire total des cours ne doit pas dépasser
        la capacité hebdomadaire physique de l'université.

        Formule :
            Volume demandé  = Somme(cours.duree)
            Volume disponible = Nombre de Salles × Nombre de Créneaux × Durée par créneau (h)

        Si la demande dépasse l'offre, il est physiquement impossible de tout planifier
        sur la semaine type, quelle que soit l'organisation.
        """
        volume_demande = self.cours["duree"].sum()

        # Chaque créneau dure 2h (format "8h-10h")
        # Le volume total disponible s'exprime en unités de "duree" (1.5h ou 3.0h)
        # On le compare en heures brutes
        n_salles = len(self.salles)
        n_creneaux = len(self.creneaux)
        duree_creneau_h = 2.0  # chaque créneau = 2 heures réelles
        volume_disponible = n_salles * n_creneaux * duree_creneau_h

        if volume_demande > volume_disponible:
            message = (
                f"\n[DataLoader] ❌ ERREUR DE FAISABILITÉ — Volume horaire insuffisant !\n"
                f"  Volume total de cours à planifier : {volume_demande:.1f}h\n"
                f"  Capacité hebdomadaire de l'université : "
                f"{n_salles} salles × {n_creneaux} créneaux × {duree_creneau_h}h = {volume_disponible:.1f}h\n\n"
                f"  ➡️  Veuillez réduire le nombre de cours ou augmenter les créneaux disponibles."
            )
            raise FeasibilityError(message)

        print(f"[DataLoader] ✅ Garde-fou Volume horaire OK "
              f"(Demande={volume_demande:.1f}h, Disponible={volume_disponible:.1f}h).")

    # -------------------------------------------------------------------------
    # MÉTHODES UTILITAIRES (appelées par le Solver et l'Exporter)
    # -------------------------------------------------------------------------

    def get_paires_actives(self):
        """
        Retourne la liste de toutes les paires (enseignant_id, cours_id) actives,
        c'est-à-dire pour lesquelles le solveur DOIT créer une variable binaire x.

        C'est le cœur de la technique des Sparse Variables (Architecture #4).
        """
        return list(self.preferences_index.keys())

    def get_preference(self, enseignant_id: str, cours_id: str) -> int:
        """Retourne le score de préférence P_{i,c} pour une paire donnée. 0 si inexistant."""
        return self.preferences_index.get((enseignant_id, cours_id), 0)

    def get_disponibilite(self, enseignant_id: str, creneau_index: int) -> bool:
        """Retourne True si l'enseignant est disponible au créneau donné (D_{i,t})."""
        return self.disponibilites[enseignant_id][creneau_index]

    def get_groupes_du_cours(self, cours_id: str) -> list:
        """Retourne la liste des groupes inscrits à un cours via la table de jonction."""
        return self.cours_groupes.get(cours_id, [])


# ===========================================================================
# SCRIPT DE TEST AUTONOME
# Exécuter ce fichier directement pour valider le chargement des données :
#   ./mon_env/bin/python src/io/loader.py
# ===========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print(" TEST DU DataLoader — Validation des données UCTP")
    print("=" * 60)

    loader = DataLoader(dossier="donnees_problemes")

    print("\n--- Aperçu des données chargées ---")
    print(f"Première paire active (prof, cours) : {loader.get_paires_actives()[:3]}")
    print(f"Disponibilité E000 créneau 0 : {loader.get_disponibilite('E000', 0)}")
    print(f"Groupes du cours C0000 : {loader.get_groupes_du_cours('C0000')}")

    print("\n[DataLoader] ✅ TOUS LES TESTS PASSÉS. Les données sont prêtes pour le Solver.")
