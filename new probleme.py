import numpy as np
import pandas as pd
import os

def generer_donnees_planification(seed, n_enseignants=50, n_groupes=200, n_salles=100, n_creneaux=30):
    """Génère les données normalisées pour le problème de planification des cours."""

    np.random.seed(seed)
    
    # Créer le dossier s'il n'existe pas
    os.makedirs('donnees_problemes', exist_ok=True)

    # 1. Enseignants
    enseignants_df = pd.DataFrame({
        'enseignant_id': [f'E{i:03d}' for i in range(n_enseignants)],
        'nom': [f'Enseignant_{i}' for i in range(n_enseignants)],
        'departement': np.random.choice(['INFO', 'MATH', 'PHYS', 'CHIM', 'BIO'], n_enseignants),
        'grade': np.random.choice(['MCF', 'PR', 'ATER'], n_enseignants, p=[0.5, 0.3, 0.2]),
        'charge_max': np.random.choice([6, 9, 12], n_enseignants, p=[0.2, 0.5, 0.3]),
        'disponibilites': [
            np.random.choice([True, False], n_creneaux, p=[0.7, 0.3])
            for _ in range(n_enseignants)
        ]
    })

    # 2. Groupes d'étudiants
    niveaux = ['L1', 'L2', 'L3', 'M1', 'M2']
    filieres = ['INFO', 'MATH', 'PHYS', 'CHIM', 'BIO']

    groupes_df = pd.DataFrame({
        'groupe_id': [f'G{i:04d}' for i in range(n_groupes)],
        'nom': [f'Groupe_{i}' for i in range(n_groupes)],
        'niveau': np.random.choice(niveaux, n_groupes),
        'filiere': np.random.choice(filieres, n_groupes),
        'effectif': np.random.randint(15, 50, n_groupes),
        'annee': 2024
    })

    # 3. Salles
    types_salle = ['Amphi', 'TD', 'TP', 'Labo']
    capacites = {'Amphi': (100, 300), 'TD': (30, 50), 'TP': (20, 30), 'Labo': (15, 25)}

    salles_df = pd.DataFrame({
        'salle_id': [f'S{i:04d}' for i in range(n_salles)],
        'nom': [f'Salle_{i}' for i in range(n_salles)],
        'type': np.random.choice(types_salle, n_salles, p=[0.1, 0.4, 0.3, 0.2]),
        'batiment': np.random.choice(['A', 'B', 'C', 'D', 'E'], n_salles),
        'etage': np.random.randint(0, 5, n_salles),
        'capacite': [
            int(np.random.uniform(*capacites[t]))
            for t in np.random.choice(types_salle, n_salles, p=[0.1, 0.4, 0.3, 0.2])
        ],
        'equipement': np.random.choice(['videoproj', 'tableau', 'ordi'], n_salles)
    })

    # 4. Cours (Initialisation sans l'effectif)
    n_cours = 300
    cours_df = pd.DataFrame({
        'cours_id': [f'C{i:04d}' for i in range(n_cours)],
        'intitule': [f'Cours_{i}' for i in range(n_cours)],
        'duree': np.random.choice([2.0, 4.0], n_cours, p=[0.7, 0.3]),
        'type_cours': np.random.choice(['CM', 'TD', 'TP'], n_cours, p=[0.3, 0.4, 0.3]),
        'semestre': np.random.choice([1, 2], n_cours)
    })

    # Prérequis matériels
    prerequis = []
    for _, cours in cours_df.iterrows():
        if cours['type_cours'] == 'CM':
            prerequis.append('Amphi')
        elif cours['type_cours'] == 'TD':
            prerequis.append('TD')
        else:
            prerequis.append('TP' if np.random.random() < 0.7 else 'Labo')
    cours_df['prerequis'] = prerequis

    # 5. Table de Jonction (Inscriptions) et calcul dynamique des effectifs
    inscriptions = []
    effectifs_calcules = []

    # Création d'un dictionnaire rapide pour chercher les effectifs des groupes
    groupe_effectif_dict = dict(zip(groupes_df['groupe_id'], groupes_df['effectif']))

    for cours_id in cours_df['cours_id']:
        # Un cours concerne entre 1 et 3 groupes aléatoirement
        n_grp = np.random.randint(1, 4)
        groupes_assignes = np.random.choice(groupes_df['groupe_id'], n_grp, replace=False)
        
        effectif_cours = 0
        for g_id in groupes_assignes:
            inscriptions.append({
                'cours_id': cours_id,
                'groupe_id': g_id
            })
            effectif_cours += groupe_effectif_dict[g_id]
            
        # On sauvegarde la somme totale des effectifs pour ce cours
        effectifs_calcules.append(effectif_cours)

    # Assigner la colonne d'effectif normalisée
    cours_df['effectif'] = effectifs_calcules
    inscriptions_df = pd.DataFrame(inscriptions)

    # 5. Préférences (habilitations V2)
    # Pour que le problème soit réaliste, CHAQUE cours doit avoir au moins un prof habilité.
    pref_list = []
    
    # Étape A : On assure la couverture de CHAQUE cours
    for c_id in cours_df['cours_id']:
        e_id = np.random.choice(enseignants_df['enseignant_id'])
        pref_list.append({
            'enseignant_id': e_id,
            'cours_id': c_id,
            'preference': np.random.randint(1, 6)
        })
    
    # Étape B : On ajoute quelques préférences bonus pour donner du choix au solveur (~150 de plus)
    for _ in range(150):
        e_id = np.random.choice(enseignants_df['enseignant_id'])
        c_id = np.random.choice(cours_df['cours_id'])
        # Éviter les doublons (prof, cours)
        if not any(p['enseignant_id'] == e_id and p['cours_id'] == c_id for p in pref_list):
            pref_list.append({
                'enseignant_id': e_id,
                'cours_id': c_id,
                'preference': np.random.randint(1, 6)
            })

    preferences_df = pd.DataFrame(pref_list)

    # Sauvegarde de tous les fichiers (y compris le nouveau inscriptions.csv)
    enseignants_df.to_csv('donnees_problemes/enseignants.csv', index=False)
    groupes_df.to_csv('donnees_problemes/groupes.csv', index=False)
    salles_df.to_csv('donnees_problemes/salles.csv', index=False)
    cours_df.to_csv('donnees_problemes/cours.csv', index=False)
    preferences_df.to_csv('donnees_problemes/preferences_enseignants.csv', index=False)
    inscriptions_df.to_csv('donnees_problemes/inscriptions.csv', index=False)

    # Créneaux horaires
    creneaux = []
    jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
    heures = ['8h-10h', '10h-12h', '13h-15h', '15h-17h']
    for jour in jours:
        for heure in heures:
            creneaux.append(f'{jour}_{heure}')

    with open('donnees_problemes/creneaux.txt', 'w') as f:
        for c in creneaux[:n_creneaux]:
            f.write(f'{c}\n')

    print("Données du problème 2 générées avec succès (Architecture V2) !")
    print(f"Enseignants: {len(enseignants_df)}")
    print(f"Groupes: {len(groupes_df)}")
    print(f"Salles: {len(salles_df)}")
    print(f"Cours: {len(cours_df)}")
    print(f"Préférences: {len(preferences_df)}")
    print(f"Inscriptions (Jonctions N:M): {len(inscriptions_df)}")

# Exécution
generer_donnees_planification(seed=200)
