import pandas as pd
from utils import nettoyer_nom

# ─── Helper : conversion robuste des montants ─────────────────────────────────

def convertir_montant(serie):
    """Convertit une série avec virgule décimale et guillemets en float."""
    return (
        serie.astype(str)
             .str.replace('"', '', regex=False)
             .str.replace('\xa0', '', regex=False)
             .str.replace(' ', '', regex=False)
             .str.replace(',', '.', regex=False)
             .pipe(pd.to_numeric, errors='coerce')
             .fillna(0)
    )

# ─── Chargement ───────────────────────────────────────────────────────────────

def charger_entrees(fichier):
    df = pd.read_csv(fichier, encoding='utf-8-sig')
    df.columns = [c.strip().replace('\xa0', ' ') for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()].copy()

    # ── Colonne propriétaire ──────────────────────────────────────────────────
    col_proprio = next(
        (c for c in df.columns if 'propri' in c.lower()),
        None
    )
    if col_proprio is None:
        raise ValueError(f"Colonne propriétaire introuvable. Colonnes : {list(df.columns)}")
    df['Propriétaire'] = df[col_proprio].apply(nettoyer_nom)

    # ── Filtre statut ─────────────────────────────────────────────────────────
    col_statut = next(
        (c for c in df.columns if 'statut' in c.lower()),
        None
    )
    if col_statut:
        df = df[df[col_statut].fillna('').str.strip() == '✅ Encaissé'].copy()

    # ── Montant encaissé en € ─────────────────────────────────────────────────
    # Cherche la colonne exacte "Montant encaissé en €"
    col_montant = next(
        (c for c in df.columns if 'encaiss' in c.lower() and '€' in c),
        None
    )
    if col_montant is None:
        col_montant = next(
            (c for c in df.columns if 'encaiss' in c.lower()),
            None
        )
    if col_montant is None:
        col_montant = next(
            (c for c in df.columns if 'montant' in c.lower()),
            None
        )

    df['Montant encaissé en €'] = convertir_montant(df[col_montant]) if col_montant else 0.0

    # ── Dates & Mois ──────────────────────────────────────────────────────────
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
        df['Mois'] = df['Date'].dt.strftime('%Y-%m')
    else:
        df['Date'] = pd.NaT
        df['Mois'] = ''

    # ── Colonnes texte optionnelles ───────────────────────────────────────────
    for col in ['Responsable', 'Type de service', 'Mode de paiement',
                'Description', 'Prénom voyageur']:
        df[col] = df[col].fillna('').str.strip() if col in df.columns else ''

    df = df[df['Propriétaire'] != ''].copy()
    return df


def charger_depenses(fichier):
    df = pd.read_csv(fichier, encoding='utf-8-sig')
    df.columns = [c.strip().replace('\xa0', ' ') for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()].copy()

    # ── Colonne propriété (peut contenir liens Notion) ────────────────────────
    col_proprio = None
    for col in df.columns:
        sample = df[col].dropna().astype(str)
        if sample.str.contains('notion.so', na=False).any():
            col_proprio = col
            break
    if col_proprio is None:
        col_proprio = next(
            (c for c in df.columns if 'propri' in c.lower()),
            None
        )
    if col_proprio:
        df['Propriété'] = df[col_proprio].apply(nettoyer_nom)
    else:
        raise ValueError(f"Colonne propriété introuvable. Colonnes : {list(df.columns)}")

    # ── Filtre statut : uniquement ✅ Payé ────────────────────────────────────
    col_statut = next(
        (c for c in df.columns if 'statut' in c.lower()),
        None
    )
    if col_statut:
        df = df[df[col_statut].fillna('').str.strip() == '✅ Payé'].copy()

    # ── Montant payé en € ─────────────────────────────────────────────────────
    # Cherche d'abord "Montant payé en €" ou variantes
    col_montant = next(
        (c for c in df.columns if 'montant' in c.lower() and 'pay' in c.lower() and '€' in c),
        None
    )
    if col_montant is None:
        col_montant = next(
            (c for c in df.columns if 'montant' in c.lower() and '€' in c),
            None
        )
    if col_montant is None:
        col_montant = next(
            (c for c in df.columns if 'montant' in c.lower() and 'pay' in c.lower()),
            None
        )
    if col_montant is None:
        col_montant = next(
            (c for c in df.columns if 'montant' in c.lower()),
            None
        )

    df['Montant payé en €'] = convertir_montant(df[col_montant]) if col_montant else 0.0

    # ── Dates & Mois ──────────────────────────────────────────────────────────
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
        df['Mois'] = df['Date'].dt.strftime('%Y-%m')
    else:
        df['Date'] = pd.NaT
        df['Mois'] = ''

    # ── Colonnes texte optionnelles ───────────────────────────────────────────
    for col in ['Payé par', 'Catégorie', 'Description', 'A la charge de']:
        df[col] = df[col].fillna('').str.strip() if col in df.columns else ''

    df = df[df['Propriété'] != ''].copy()
    return df


# ─── Agrégations ──────────────────────────────────────────────────────────────

def calculer_recap_entrees(df, mois=None):
    df = df.copy()
    if mois:
        df = df[df['Mois'] == mois]
    recap = df.groupby(['Propriétaire', 'Type de service'], as_index=False).agg(
        Nb_Operations=('Montant encaissé en €', 'count'),
        Total=('Montant encaissé en €', 'sum')
    )
    recap['Total'] = recap['Total'].round(2)
    return recap


def calculer_recap_depenses(df, mois=None):
    df = df.copy()
    if mois:
        df = df[df['Mois'] == mois]
    recap = df.groupby(['Propriété', 'Catégorie'], as_index=False).agg(
        Nb_Operations=('Montant payé en €', 'count'),
        Total=('Montant payé en €', 'sum')
    )
    recap['Total'] = recap['Total'].round(2)
    return recap


def calculer_bilan_par_bien(df_entrees, df_depenses, mois=None):
    df_e = df_entrees.copy()
    df_d = df_depenses.copy()
    if mois:
        df_e = df_e[df_e['Mois'] == mois]
        df_d = df_d[df_d['Mois'] == mois]

    entrees_par_bien = (
        df_e.groupby('Propriétaire', as_index=False)['Montant encaissé en €']
            .sum()
            .rename(columns={
                'Propriétaire': 'Bien',
                'Montant encaissé en €': 'Total Entrées'
            })
    )

    depenses_par_bien = (
        df_d.groupby('Propriété', as_index=False)['Montant payé en €']
            .sum()
            .rename(columns={
                'Propriété': 'Bien',
                'Montant payé en €': 'Total Dépenses'
            })
    )

    bilan = pd.merge(entrees_par_bien, depenses_par_bien, on='Bien', how='outer').fillna(0)
    bilan['Total Entrées']  = bilan['Total Entrées'].round(2)
    bilan['Total Dépenses'] = bilan['Total Dépenses'].round(2)
    bilan['Bilan']          = (bilan['Total Entrées'] - bilan['Total Dépenses']).round(2)
    return bilan


def calculer_recap_par_responsable(df_entrees, df_depenses, mois=None):
    df_e = df_entrees.copy()
    df_d = df_depenses.copy()
    if mois:
        df_e = df_e[df_e['Mois'] == mois]
        df_d = df_d[df_d['Mois'] == mois]

    entrees_resp = (
        df_e.groupby('Responsable', as_index=False)['Montant encaissé en €']
            .sum()
            .rename(columns={'Montant encaissé en €': 'Total Encaissé'})
    )

    depenses_resp = (
        df_d.groupby('Payé par', as_index=False)['Montant payé en €']
            .sum()
            .rename(columns={
                'Payé par': 'Responsable',
                'Montant payé en €': 'Total Dépensé'
            })
    )

    recap = pd.merge(entrees_resp, depenses_resp, on='Responsable', how='outer').fillna(0)
    recap['Total Encaissé'] = recap['Total Encaissé'].round(2)
    recap['Total Dépensé']  = recap['Total Dépensé'].round(2)
    recap['Bilan']          = (recap['Total Encaissé'] - recap['Total Dépensé']).round(2)
    return recap
