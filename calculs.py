# calculs.py

import pandas as pd

def charger_fichier(fichier):
    df = pd.read_csv(fichier, encoding='utf-8')
    df.columns = df.columns.str.strip()
    df = df[df['status'] == 'accepted'].copy()
    df = df[df['property_name'].notna()].copy()
    return df

def formater_df(df):
    df_copy = df.copy()
    for col in df_copy.columns:
        if df_copy[col].dtype in ['float64', 'float32']:
            df_copy[col] = df_copy[col].apply(
                lambda x: round(x, 2) if pd.notna(x) and x != '' else x
            )
    return df_copy

def calculer_bien(df, property_name, config):
    bien_df = df[df['property_name'] == property_name].copy()

    commission_pct = config['commission'] / 100
    prix_menage = config['prix_menage']
    femme_menage = config['femme_menage']
    menage_inclus = config.get('menage_inclus', True)
    commission_label = f"Commission ({config['commission']}%)"

    resultats = []
    for _, row in bien_df.iterrows():
        revenue = float(row['revenue']) if pd.notna(row['revenue']) else 0
        cleaning_fee = float(row['cleaning_fee']) if pd.notna(row['cleaning_fee']) else 0

        if menage_inclus:
            # ─── Ménage géré par toi ──────────────────────────
            net_base = round(revenue - cleaning_fee, 2)
            commission = round(net_base * commission_pct, 2)
            net_proprietaire = round(net_base - commission, 2)
            gain_menage = round(cleaning_fee - prix_menage, 2)
            prix_menage_row = round(float(prix_menage), 2)
            femme_menage_row = femme_menage

        else:
            # ─── Ménage non géré ──────────────────────────────
            # Net Base = Revenue - Cleaning Fee
            net_base = round(revenue - cleaning_fee, 2)
            commission = round(net_base * commission_pct, 2)
            # Net Propriétaire = (Net Base - Commission) + Cleaning Fee
            net_proprietaire = round(net_base - commission + cleaning_fee, 2)
            gain_menage = 0.00
            prix_menage_row = 0.00
            femme_menage_row = ''

        resultats.append({
            'Code': row['code'],
            'Check-in': str(row['checkin_date'])[:10],
            'Check-out': str(row['checkout_date'])[:10],
            'Nuits': int(row['nights']),
            'Revenue': round(revenue, 2),
            'Cleaning Fee': round(cleaning_fee, 2),
            'Net Base': net_base,
            commission_label: commission,
            'Net Propriétaire (80%)': net_proprietaire,
            'Gain Ménage': gain_menage,
            'Femme de Ménage': femme_menage_row,
            'Prix Ménage': prix_menage_row
        })

    df_result = pd.DataFrame(resultats)

    # ─── Ligne TOTAL ──────────────────────────────────────────
    total_row = {
        'Code': 'TOTAL',
        'Check-in': '',
        'Check-out': '',
        'Nuits': int(df_result['Nuits'].sum()),
        'Revenue': round(df_result['Revenue'].sum(), 2),
        'Cleaning Fee': round(df_result['Cleaning Fee'].sum(), 2),
        'Net Base': round(df_result['Net Base'].sum(), 2),
        commission_label: round(df_result[commission_label].sum(), 2),
        'Net Propriétaire (80%)': round(df_result['Net Propriétaire (80%)'].sum(), 2),
        'Gain Ménage': round(df_result['Gain Ménage'].sum(), 2),
        'Femme de Ménage': '',
        'Prix Ménage': round(df_result['Prix Ménage'].sum(), 2)
    }

    df_result = pd.concat([df_result, pd.DataFrame([total_row])], ignore_index=True)
    return formater_df(df_result)

def calculer_totaux(df_resultat, config):
    commission_label = f"Commission ({config['commission']}%)"
    df = df_resultat[df_resultat['Code'] != 'TOTAL']
    totaux = {
        'Net Base Total': round(df['Net Base'].sum(), 2),
        'Commission Total': round(df[commission_label].sum(), 2),
        'Net Propriétaire Total': round(df['Net Propriétaire (80%)'].sum(), 2),
        'Gain Ménage Total': round(df['Gain Ménage'].sum(), 2),
        'Prix Ménage Total': round(df['Prix Ménage'].sum(), 2),
    }
    totaux['Gain Total'] = round(totaux['Commission Total'] + totaux['Gain Ménage Total'], 2)
    return totaux
