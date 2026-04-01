"""
main.py — Chef d'orchestre du système UCTP

Lance le pipeline complet :
    1. DataLoader   : Lecture + Validation des CSV
    2. UCTPSolver   : Résolution PLNE via PuLP
    3. TimetableExporter : Export Excel multi-vues + Rapport d'audit RH

Usage :
    ./mon_env/bin/python main.py
    PYTHONPATH=. ./mon_env/bin/python main.py  (si nécessaire)
"""

import sys

from src.io.loader import DataLoader, FeasibilityError
from src.core.solver import UCTPSolver
from src.reporting.exporter import TimetableExporter


def main():
    print("=" * 65)
    print(" SOLVEUR UCTP — Génération de l'Emploi du Temps Universitaire")
    print("=" * 65)

    # -------------------------------------------------------------------------
    # ÉTAPE 1 : Chargement et validation des données
    # -------------------------------------------------------------------------
    try:
        loader = DataLoader(dossier="donnees_problemes")
    except FeasibilityError as e:
        print(e)
        print("\n❌ Résolution interrompue. Corrigez les données et relancez.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # ÉTAPE 2 : Résolution du problème PLNE
    # -------------------------------------------------------------------------
    solver = UCTPSolver(loader=loader, beta=0.5)
    solution = solver.resoudre(timeout_secondes=120)

    if not solution:
        print("\n❌ Aucune solution trouvée. Vérifiez les préférences et les données.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # ÉTAPE 3 : Export des emplois du temps
    # -------------------------------------------------------------------------
    exporter = TimetableExporter(loader=loader, solution=solution, dossier_sortie="output")
    exporter.exporter_tout()

    print("\n" + "=" * 65)
    print(" ✅ TERMINÉ — Emplois du temps générés dans le dossier ./output/")
    print("=" * 65)


if __name__ == "__main__":
    main()
