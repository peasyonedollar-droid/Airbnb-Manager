import streamlit as st
import pandas as pd
import os
from calculs import charger_fichier, calculer_bien, calculer_totaux
from facture import generer_facture
from config import DEFAULT_CONFIG
from entrees_depenses import (
    charger_entrees, charger_depenses,
    calculer_recap_entrees, calculer_recap_depenses,
    calculer_bilan_par_bien, calculer_recap_par_responsable
)

# ─── Configuration de la page ────────────────────────────────────────────────
st.set_page_config(page_title="Airbnb Manager", page_icon="🏠", layout="wide")

# ─── Fonctions utilitaires ───────────────────────────────────────────────────
def style_total(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    if 'Code' in df.columns:
        mask = df['Code'] == 'TOTAL'
    elif 'Bien' in df.columns:
        mask = df['Bien'] == 'TOTAL'
    elif 'Responsable' in df.columns:
        mask = df['Responsable'] == 'TOTAL'
    else:
        mask = pd.Series(False, index=df.index)
    styles[mask] = 'font-weight: bold; background-color: #2980b9; color: white;'
    return styles

def formater_colonnes(df):
    fmt = {}
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            fmt[col] = '{:.2f}'
    return fmt

def recalculer_df(df_edite, config):
    commission_label = f"Commission ({config['commission']}%)"
    pct              = config['commission'] / 100
    prix_menage      = config.get('prix_menage', 0)
    menage_inclus    = config.get('menage_inclus', True)

    df = df_edite[df_edite['Code'] != 'TOTAL'].copy()
    df['Net Base'] = (df['Revenue'] - df['Cleaning Fee']).round(2)
    df[commission_label] = (df['Net Base'] * pct).round(2)

    if menage_inclus:
        df['Net Propriétaire (80%)'] = (df['Net Base'] - df[commission_label]).round(2)
        df['Gain Ménage']            = (df['Cleaning Fee'] - df['Prix Ménage']).round(2)
    else:
        df['Net Propriétaire (80%)'] = (df['Net Base'] - df[commission_label] + df['Cleaning Fee']).round(2)
        df['Gain Ménage']            = 0.00

    total_row = {c: '' for c in df.columns}
    total_row.update({
        'Code':                   'TOTAL',
        'Nuits':                  int(df['Nuits'].sum()),
        'Revenue':                round(df['Revenue'].sum(), 2),
        'Cleaning Fee':           round(df['Cleaning Fee'].sum(), 2),
        'Net Base':               round(df['Net Base'].sum(), 2),
        commission_label:         round(df[commission_label].sum(), 2),
        'Net Propriétaire (80%)': round(df['Net Propriétaire (80%)'].sum(), 2),
        'Gain Ménage':            round(df['Gain Ménage'].sum(), 2),
        'Prix Ménage':            round(df['Prix Ménage'].sum(), 2),
    })
    return pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

def get_df_bien(df_mois, bien, config):
    mois_key = df_mois['checkin_date'].astype(str).str[:7].iloc[0] if not df_mois.empty else 'unknown'
    cle      = f"{bien}_{mois_key}"
    if cle in st.session_state.df_valides:
        return st.session_state.df_valides[cle]
    if cle in st.session_state.df_modifies:
        return st.session_state.df_modifies[cle]
    return calculer_bien(df_mois, bien, config)

# ─── Session state ────────────────────────────────────────────────────────────
if 'config' not in st.session_state:
    st.session_state.config = {k: v.copy() for k, v in DEFAULT_CONFIG.items()}
if 'df_modifies' not in st.session_state:
    st.session_state.df_modifies = {}
if 'df_valides' not in st.session_state:
    st.session_state.df_valides = {}

# ─── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.title("🏠 Airbnb Manager")
page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "⚙️ Configuration", "👥 Rapports",
     "💰 Entrées / Dépenses", "📒 Compta", "🧾 Factures"]
)
st.sidebar.divider()
fichier          = st.sidebar.file_uploader("📂 Importer Réservations CSV", type=['csv'])
st.sidebar.divider()
fichier_entrees  = st.sidebar.file_uploader("📥 Importer Entrées CSV",      type=['csv'])
fichier_depenses = st.sidebar.file_uploader("📤 Importer Dépenses CSV",     type=['csv'])

# ══════════════════════════════════════════════════════════════════════════════
# 📊 DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.title("📊 Dashboard - Vue Globale")

    if fichier is None:
        st.info("👈 Veuillez importer votre fichier CSV Airbnb depuis la sidebar.")
        st.stop()

    df     = charger_fichier(fichier)
    ca_global = round(pd.to_numeric(df['revenue'], errors='coerce').fillna(0).sum(), 2)
    st.metric(label="💶 Chiffre d'Affaire Global (tous mois confondus)", value=f"{ca_global:.2f} €")
    st.divider()

    mois = st.selectbox(
        "📅 Sélectionner le mois",
        options=sorted(df['checkin_date'].astype(str).str[:7].unique(), reverse=True),
        key="mois_dashboard"
    )
    df_mois = df[df['checkin_date'].astype(str).str[:7] == mois]
    biens   = df_mois['property_name'].dropna().unique()

    recap_global = []
    for bien in biens:
        if bien not in st.session_state.config:
            st.session_state.config[bien] = {
                "commission": 20, "prix_menage": 10,
                "femme_menage": "", "menage_inclus": True,
                "nom_client": "", "adresse_client": "Marrakech, Maroc"
            }
        config  = st.session_state.config[bien]
        df_res  = get_df_bien(df_mois, bien, config)
        totaux  = calculer_totaux(df_res, config)
        recap_global.append({
            'Bien':          bien[:45],
            'Nuits':         int(df_res[df_res['Code'] != 'TOTAL']['Nuits'].sum()),
            'Net Base':      round(totaux['Net Base Total'],         2),
            'Commission':    round(totaux['Commission Total'],       2),
            'Net Proprio':   round(totaux['Net Propriétaire Total'], 2),
            'Gain Ménage':   round(totaux['Gain Ménage Total'],      2),
            'Gain Total':    round(totaux['Gain Total'],             2),
        })

    df_recap = pd.DataFrame(recap_global)
    if df_recap.empty:
        st.warning("Aucune donnée pour ce mois.")
        st.stop()

    total_ca_mois  = round(df_recap['Net Base'].sum(),    2)
    total_comm     = round(df_recap['Commission'].sum(),  2)
    total_menage   = round(df_recap['Gain Ménage'].sum(), 2)
    total_gain     = round(df_recap['Gain Total'].sum(),  2)
    total_nuits    = int(df_recap['Nuits'].sum())

    total_row = {
        'Bien': 'TOTAL', 'Nuits': total_nuits,
        'Net Base': total_ca_mois, 'Commission': total_comm,
        'Net Proprio': round(df_recap['Net Proprio'].sum(), 2),
        'Gain Ménage': total_menage, 'Gain Total': total_gain
    }
    df_recap = pd.concat([df_recap, pd.DataFrame([total_row])], ignore_index=True)

    col_t, col_ca = st.columns([3, 1])
    with col_t:
        st.subheader(f"📅 Récapitulatif – {mois}")
    with col_ca:
        st.metric("💶 CA du mois", f"{total_ca_mois:.2f} €")

    st.dataframe(
        df_recap.style.apply(style_total, axis=None).format(formater_colonnes(df_recap)),
        use_container_width=True, hide_index=True
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌙 Total Nuits",     total_nuits)
    c2.metric("💰 Total Commission", f"{total_comm:.2f} €")
    c3.metric("🧹 Gain Ménage",      f"{total_menage:.2f} €")
    c4.metric("💵 Ton Gain Total",   f"{total_gain:.2f} €")

    st.divider()
    st.subheader("📋 Détail par Bien")
    bien_sel = st.selectbox("🏠 Choisir un bien", biens, key="bien_dashboard")

    if bien_sel:
        config           = st.session_state.config[bien_sel]
        commission_label = f"Commission ({config['commission']}%)"
        df_res           = get_df_bien(df_mois, bien_sel, config)

        cols_disabled = ['Code', 'Check-in', 'Check-out', 'Net Base',
                         commission_label, 'Net Propriétaire (80%)', 'Gain Ménage']
        cols_cfg = {
            'Revenue':                st.column_config.NumberColumn('Revenue',               format="%.2f"),
            'Cleaning Fee':           st.column_config.NumberColumn('Cleaning Fee',           format="%.2f"),
            'Femme de Ménage':        st.column_config.TextColumn('Femme de Ménage'),
            'Prix Ménage':            st.column_config.NumberColumn('Prix Ménage',            format="%.2f"),
            'Nuits':                  st.column_config.NumberColumn('Nuits',                  format="%d"),
            'Net Base':               st.column_config.NumberColumn('Net Base',               format="%.2f"),
            commission_label:         st.column_config.NumberColumn(commission_label,         format="%.2f"),
            'Net Propriétaire (80%)': st.column_config.NumberColumn('Net Propriétaire (80%)', format="%.2f"),
            'Gain Ménage':            st.column_config.NumberColumn('Gain Ménage',            format="%.2f"),
        }
        df_edit = st.data_editor(
            df_res.style.apply(style_total, axis=None),
            use_container_width=True, hide_index=True,
            disabled=cols_disabled, column_config=cols_cfg,
            key=f"editor_dash_{bien_sel}"
        )
        col_s, col_r = st.columns([1, 5])
        with col_s:
            if st.button("💾 Enregistrer", type="primary", key=f"save_dash_{bien_sel}"):
                mois_key = df_mois['checkin_date'].astype(str).str[:7].iloc[0]
                cle      = f"{bien_sel}_{mois_key}"
                df_final = recalculer_df(df_edit, config)
                st.session_state.df_modifies[cle] = df_final
                st.session_state.df_valides[cle]  = df_final
                st.success(f"✅ Enregistré pour {bien_sel[:30]}")
                st.dataframe(df_final.style.apply(style_total, axis=None),
                             use_container_width=True, hide_index=True)
        with col_r:
            if st.button("🔄 Réinitialiser", key=f"reset_dash_{bien_sel}"):
                mois_key = df_mois['checkin_date'].astype(str).str[:7].iloc[0]
                cle      = f"{bien_sel}_{mois_key}"
                st.session_state.df_modifies.pop(cle, None)
                st.session_state.df_valides.pop(cle, None)
                st.success("✅ Réinitialisé !")
                st.rerun()

        totaux = calculer_totaux(df_res, config)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📊 Net Base",        f"{totaux['Net Base Total']:.2f} €")
        m2.metric("💰 Commission",       f"{totaux['Commission Total']:.2f} €")
        m3.metric("🏠 Net Propriétaire", f"{totaux['Net Propriétaire Total']:.2f} €")
        m4.metric("💵 Gain Total",       f"{totaux['Gain Total']:.2f} €")

# ══════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Configuration":
    st.title("⚙️ Configuration des Biens")

    if fichier is None:
        st.info("👈 Veuillez importer votre fichier CSV Airbnb depuis la sidebar.")
        st.stop()

    df    = charger_fichier(fichier)
    biens = df['property_name'].dropna().unique()

    bien_sel = st.selectbox("🏠 Choisir un bien", biens, key="bien_config")

    if bien_sel:
        if bien_sel not in st.session_state.config:
            st.session_state.config[bien_sel] = {
                "commission":     20,
                "prix_menage":    10,
                "femme_menage":   "",
                "menage_inclus":  True,
                "nom_client":     "",
                "adresse_client": "Marrakech, Maroc"
            }
        cfg = st.session_state.config[bien_sel]

        st.subheader("🔧 Paramètres")
        col1, col2 = st.columns(2)

        with col1:
            commission    = st.number_input(
                "Commission (%)", 0, 100, int(cfg.get('commission', 20)),
                key=f"com_{bien_sel}"
            )
            menage_inclus = st.checkbox(
                "🧹 Calcul du ménage inclus",
                value=cfg.get('menage_inclus', True),
                key=f"men_{bien_sel}"
            )
        with col2:
            if menage_inclus:
                prix_menage  = st.number_input(
                    "Prix Ménage (€)", 0,
                    value=int(cfg.get('prix_menage', 10)),
                    key=f"pm_{bien_sel}"
                )
                femme_menage = st.text_input(
                    "Femme de Ménage", cfg.get('femme_menage', ''),
                    key=f"fm_{bien_sel}"
                )
            else:
                prix_menage  = 0
                femme_menage = ''
                st.info("ℹ️ Ménage non géré – les cleaning fees reviennent au propriétaire.")

        st.divider()
        st.subheader("👤 Informations Client (pour la facture)")
        col3, col4 = st.columns(2)
        with col3:
            nom_client = st.text_input(
                "Nom du Client", cfg.get('nom_client', ''),
                key=f"nc_{bien_sel}"
            )
        with col4:
            adresse_client = st.text_input(
                "Adresse du Client", cfg.get('adresse_client', 'Marrakech, Maroc'),
                key=f"ac_{bien_sel}"
            )

        st.divider()
        col_v, col_r = st.columns([1, 5])
        with col_v:
            if st.button("✅ Valider Paramètres", key=f"val_cfg_{bien_sel}"):
                new_cfg = {
                    "commission":     commission,
                    "prix_menage":    prix_menage,
                    "femme_menage":   femme_menage,
                    "menage_inclus":  menage_inclus,
                    "nom_client":     nom_client,
                    "adresse_client": adresse_client,
                }
                st.session_state.config[bien_sel] = new_cfg
                for m in sorted(df['checkin_date'].astype(str).str[:7].unique(), reverse=True):
                    df_tmp = df[df['checkin_date'].astype(str).str[:7] == m]
                    if bien_sel in df_tmp['property_name'].values:
                        cle = f"{bien_sel}_{m}"
                        st.session_state.df_valides[cle] = calculer_bien(df_tmp, bien_sel, new_cfg)
                st.success(f"✅ Paramètres validés pour {bien_sel[:30]}")
                st.rerun()
        with col_r:
            if st.button("🔄 Réinitialiser", key=f"res_cfg_{bien_sel}"):
                st.session_state.config[bien_sel] = {
                    "commission": 20, "prix_menage": 10,
                    "femme_menage": "", "menage_inclus": True,
                    "nom_client": "", "adresse_client": "Marrakech, Maroc"
                }
                for k in [k for k in st.session_state.df_valides if k.startswith(bien_sel)]:
                    del st.session_state.df_valides[k]
                st.success("✅ Réinitialisé !")
                st.rerun()

        st.divider()
        st.subheader(f"📋 Réservations – {bien_sel[:40]}")
        mois_dispo = sorted(df['checkin_date'].astype(str).str[:7].unique(), reverse=True)
        mois       = st.selectbox("Sélectionner le mois", mois_dispo, key="mois_config")
        df_mois    = df[df['checkin_date'].astype(str).str[:7] == mois]

        commission_label = f"Commission ({commission}%)"
        cfg_courante = {
            "commission":     commission,
            "prix_menage":    prix_menage,
            "femme_menage":   femme_menage,
            "menage_inclus":  menage_inclus,
            "nom_client":     nom_client,
            "adresse_client": adresse_client,
        }
        df_res = get_df_bien(df_mois, bien_sel, cfg_courante)

        cols_disabled    = ['Code', 'Check-in', 'Check-out', 'Net Base',
                            commission_label, 'Net Propriétaire (80%)', 'Gain Ménage']
        cols_config_ed   = {
            'Revenue':                st.column_config.NumberColumn('Revenue',               format="%.2f"),
            'Cleaning Fee':           st.column_config.NumberColumn('Cleaning Fee',           format="%.2f"),
            'Femme de Ménage':        st.column_config.TextColumn('Femme de Ménage'),
            'Prix Ménage':            st.column_config.NumberColumn('Prix Ménage',            format="%.2f"),
            'Nuits':                  st.column_config.NumberColumn('Nuits',                  format="%d"),
            'Net Base':               st.column_config.NumberColumn('Net Base',               format="%.2f"),
            commission_label:         st.column_config.NumberColumn(commission_label,         format="%.2f"),
            'Net Propriétaire (80%)': st.column_config.NumberColumn('Net Propriétaire (80%)', format="%.2f"),
            'Gain Ménage':            st.column_config.NumberColumn('Gain Ménage',            format="%.2f"),
        }
        df_edit = st.data_editor(
            df_res.style.apply(style_total, axis=None),
            use_container_width=True, hide_index=True,
            disabled=cols_disabled, column_config=cols_config_ed,
            key=f"editor_cfg_{bien_sel}"
        )

        if st.button("💾 Enregistrer Tableau", key=f"save_tbl_{bien_sel}"):
            mois_key = df_mois['checkin_date'].astype(str).str[:7].iloc[0]
            cle      = f"{bien_sel}_{mois_key}"
            df_final = recalculer_df(df_edit, cfg_courante)
            st.session_state.df_valides[cle]  = df_final
            st.session_state.df_modifies[cle] = df_final
            st.success(f"✅ Tableau enregistré pour {bien_sel[:30]}")
            st.dataframe(df_final.style.apply(style_total, axis=None),
                         use_container_width=True, hide_index=True)

        st.divider()
        totaux = calculer_totaux(df_res, cfg_courante)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📊 Net Base",        f"{totaux['Net Base Total']:.2f} €")
        m2.metric("💰 Commission",       f"{totaux['Commission Total']:.2f} €")
        m3.metric("🏠 Net Propriétaire", f"{totaux['Net Propriétaire Total']:.2f} €")
        m4.metric("💵 Gain Total",       f"{totaux['Gain Total']:.2f} €")

# ══════════════════════════════════════════════════════════════════════════════
# 👥 RAPPORTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "👥 Rapports":
    st.title("👥 Rapports – Gains des Employés")

    if fichier is None:
        st.info("👈 Veuillez importer votre fichier CSV Airbnb depuis la sidebar.")
        st.stop()

    df   = charger_fichier(fichier)
    mois = st.selectbox(
        "📅 Sélectionner le mois",
        options=["Tous"] + sorted(df['checkin_date'].astype(str).str[:7].unique(), reverse=True),
        key="mois_rapports"
    )
    df_mois = df if mois == "Tous" else df[df['checkin_date'].astype(str).str[:7] == mois]
    biens   = df_mois['property_name'].dropna().unique()

    lignes_employes = []
    lignes_gains    = []

    for bien in biens:
        if bien not in st.session_state.config:
            st.session_state.config[bien] = {
                "commission": 20, "prix_menage": 10,
                "femme_menage": "", "menage_inclus": True,
                "nom_client": "", "adresse_client": "Marrakech, Maroc"
            }
        config = st.session_state.config[bien]
        df_res = get_df_bien(df_mois, bien, config)
        totaux = calculer_totaux(df_res, config)

        lignes_gains.append({
            'Bien':       bien[:40],
            'Commission': round(totaux['Commission Total'],  2),
            'Gain Ménage':round(totaux['Gain Ménage Total'], 2),
            'Gain Total': round(totaux['Gain Total'],        2),
        })

        for _, row in df_res[df_res['Code'] != 'TOTAL'].iterrows():
            femme = str(row.get('Femme de Ménage', ''))
            if femme.strip():
                lignes_employes.append({
                    'Employée':    femme.strip(),
                    'Bien':        bien[:35],
                    'Code':        row['Code'],
                    'Check-in':    row['Check-in'],
                    'Check-out':   row['Check-out'],
                    'Nuits':       row['Nuits'],
                    'Cleaning Fee':round(float(row.get('Cleaning Fee', 0)), 2),
                    'Prix Ménage': round(float(row.get('Prix Ménage',  0)), 2),
                    'Gain Ménage': round(float(row.get('Gain Ménage',  0)), 2),
                })

    st.subheader("🧹 Interventions des Employées")
    if lignes_employes:
        df_emp    = pd.DataFrame(lignes_employes)
        employes  = ["Tous"] + sorted(df_emp['Employée'].unique().tolist())
        emp_sel   = st.selectbox("Filtrer par employée", employes, key="employe_rapports")
        df_emp_f  = df_emp if emp_sel == "Tous" else df_emp[df_emp['Employée'] == emp_sel]

        total_emp = {c: '' for c in df_emp_f.columns}
        total_emp.update({
            'Employée':    'TOTAL',
            'Nuits':       int(df_emp_f['Nuits'].sum()),
            'Cleaning Fee':round(df_emp_f['Cleaning Fee'].sum(), 2),
            'Prix Ménage': round(df_emp_f['Prix Ménage'].sum(),  2),
            'Gain Ménage': round(df_emp_f['Gain Ménage'].sum(),  2),
        })
        df_emp_d = pd.concat([df_emp_f, pd.DataFrame([total_emp])], ignore_index=True)

        def style_emp(df):
            s = pd.DataFrame('', index=df.index, columns=df.columns)
            s[df['Employée'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
            return s

        st.dataframe(df_emp_d.style.apply(style_emp, axis=None).format(formater_colonnes(df_emp_d)),
                     use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📊 Récapitulatif par Employée")
        df_recap_emp = df_emp.groupby('Employée', as_index=False).agg(
            Interventions=('Code',        'count'),
            Total_Nuits  =('Nuits',       'sum'),
            Total_Paye   =('Prix Ménage', 'sum'),
            Total_Gain   =('Gain Ménage', 'sum')
        ).round(2)
        total_r = {
            'Employée':     'TOTAL',
            'Interventions':int(df_recap_emp['Interventions'].sum()),
            'Total_Nuits':  int(df_recap_emp['Total_Nuits'].sum()),
            'Total_Paye':   round(df_recap_emp['Total_Paye'].sum(), 2),
            'Total_Gain':   round(df_recap_emp['Total_Gain'].sum(), 2),
        }
        df_recap_emp = pd.concat([df_recap_emp, pd.DataFrame([total_r])], ignore_index=True)

        def style_recap_emp(df):
            s = pd.DataFrame('', index=df.index, columns=df.columns)
            s[df['Employée'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
            return s

        st.dataframe(df_recap_emp.style.apply(style_recap_emp, axis=None).format(formater_colonnes(df_recap_emp)),
                     use_container_width=True, hide_index=True)
    else:
        st.info("Aucune employée renseignée pour cette période.")

    st.divider()
    st.subheader("💰 Mes Gains par Bien")
    if lignes_gains:
        df_gains   = pd.DataFrame(lignes_gains)
        total_gain = {
            'Bien':        'TOTAL',
            'Commission':  round(df_gains['Commission'].sum(),  2),
            'Gain Ménage': round(df_gains['Gain Ménage'].sum(), 2),
            'Gain Total':  round(df_gains['Gain Total'].sum(),  2),
        }
        df_gains = pd.concat([df_gains, pd.DataFrame([total_gain])], ignore_index=True)

        def style_gains(df):
            s = pd.DataFrame('', index=df.index, columns=df.columns)
            s[df['Bien'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
            return s

        st.dataframe(df_gains.style.apply(style_gains, axis=None).format(formater_colonnes(df_gains)),
                     use_container_width=True, hide_index=True)

        df_nt = df_gains[df_gains['Bien'] != 'TOTAL']
        g1, g2, g3 = st.columns(3)
        g1.metric("💰 Total Commission",  f"{round(df_nt['Commission'].sum(),  2):.2f} €")
        g2.metric("🧹 Total Gain Ménage", f"{round(df_nt['Gain Ménage'].sum(), 2):.2f} €")
        g3.metric("💵 Gain Global",        f"{round(df_nt['Gain Total'].sum(),  2):.2f} €")

# ══════════════════════════════════════════════════════════════════════════════
# 💰 ENTRÉES / DÉPENSES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💰 Entrées / Dépenses":
    st.title("💰 Entrées & Dépenses")

    if fichier_entrees is None or fichier_depenses is None:
        st.info("👈 Veuillez importer les fichiers CSV Entrées et Dépenses depuis la sidebar.")
        st.stop()

    df_entrees  = charger_entrees(fichier_entrees)
    df_depenses = charger_depenses(fichier_depenses)

    mois_dispo = sorted(
        set(df_entrees['Mois'].dropna().unique()) | set(df_depenses['Mois'].dropna().unique()),
        reverse=True
    )
    mois       = st.selectbox("📅 Sélectionner le mois", ["Tous"] + mois_dispo, key="mois_entrees_depenses")
    mois_filtre = None if mois == "Tous" else mois

    # Bilan par bien
    st.subheader("📊 Bilan par Bien")
    df_bilan = calculer_bilan_par_bien(df_entrees, df_depenses, mois_filtre)
    total_b  = {
        'Bien':          'TOTAL',
        'Total Entrées': round(df_bilan['Total Entrées'].sum(),  2),
        'Total Dépenses':round(df_bilan['Total Dépenses'].sum(), 2),
        'Bilan':         round(df_bilan['Bilan'].sum(),          2),
    }
    df_bilan = pd.concat([df_bilan, pd.DataFrame([total_b])], ignore_index=True)

    def style_bilan(df):
        s = pd.DataFrame('', index=df.index, columns=df.columns)
        s[df['Bien'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
        return s

    st.dataframe(df_bilan.style.apply(style_bilan, axis=None).format(formater_colonnes(df_bilan)),
                 use_container_width=True, hide_index=True)

    df_bnt = df_bilan[df_bilan['Bien'] != 'TOTAL']
    b1, b2, b3 = st.columns(3)
    b1.metric("📥 Total Entrées",  f"{round(df_bnt['Total Entrées'].sum(),  2):.2f} €")
    b2.metric("📤 Total Dépenses", f"{round(df_bnt['Total Dépenses'].sum(), 2):.2f} €")
    b3.metric("📊 Bilan Net",      f"{round(df_bnt['Bilan'].sum(),          2):.2f} €")

    # Entrées détaillées
    st.divider()
    st.subheader("📥 Entrées Détaillées")
    biens_e  = ["Tous"] + sorted(df_entrees['Propriétaire'].unique().tolist())
    bien_fe  = st.selectbox("Filtrer par bien", biens_e, key="filtre_bien_entrees")
    df_e_f   = df_entrees if bien_fe == "Tous" else df_entrees[df_entrees['Propriétaire'] == bien_fe]
    if mois_filtre:
        df_e_f = df_e_f[df_e_f['Mois'] == mois_filtre]

    cols_e   = [c for c in ['Date','Propriétaire','Prénom voyag€','Type de service',
                             'Montant encaissé en €','Mode de paiement','Responsable','Description']
                if c in df_e_f.columns]
    df_e_d   = df_e_f[cols_e].copy()
    total_e  = {c: '' for c in cols_e}
    total_e['Propriétaire'] = 'TOTAL'
    if 'Montant encaissé en €' in cols_e:
        total_e['Montant encaissé en €'] = round(df_e_d['Montant encaissé en €'].sum(), 2)
    df_e_d = pd.concat([df_e_d, pd.DataFrame([total_e])], ignore_index=True)

    def style_te(df):
        s = pd.DataFrame('', index=df.index, columns=df.columns)
        if 'Propriétaire' in df.columns:
            s[df['Propriétaire'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
        return s

    st.dataframe(df_e_d.style.apply(style_te, axis=None).format(formater_colonnes(df_e_d)),
                 use_container_width=True, hide_index=True)
    st.subheader("📊 Récap par Type de Service")
    st.dataframe(calculer_recap_entrees(df_entrees, mois_filtre), use_container_width=True, hide_index=True)

    # Dépenses détaillées
    st.divider()
    st.subheader("📤 Dépenses Détaillées")
    biens_d  = ["Tous"] + sorted(df_depenses['Propriété'].unique().tolist())
    bien_fd  = st.selectbox("Filtrer par bien", biens_d, key="filtre_bien_depenses")
    df_d_f   = df_depenses if bien_fd == "Tous" else df_depenses[df_depenses['Propriété'] == bien_fd]
    if mois_filtre:
        df_d_f = df_d_f[df_d_f['Mois'] == mois_filtre]

    cols_d   = [c for c in ['Date','Propriété','Catégorie','Montant payé en €','Payé par','Description']
                if c in df_d_f.columns]
    df_d_d   = df_d_f[cols_d].copy()
    total_d  = {c: '' for c in cols_d}
    total_d['Propriété'] = 'TOTAL'
    if 'Montant payé en €' in cols_d:
        total_d['Montant payé en €'] = round(df_d_d['Montant payé en €'].sum(), 2)
    df_d_d = pd.concat([df_d_d, pd.DataFrame([total_d])], ignore_index=True)

    def style_td(df):
        s = pd.DataFrame('', index=df.index, columns=df.columns)
        if 'Propriété' in df.columns:
            s[df['Propriété'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
        return s

    st.dataframe(df_d_d.style.apply(style_td, axis=None).format(formater_colonnes(df_d_d)),
                 use_container_width=True, hide_index=True)
    st.subheader("📊 Récap par Catégorie")
    st.dataframe(calculer_recap_depenses(df_depenses, mois_filtre), use_container_width=True, hide_index=True)

    # Récap par responsable
    st.divider()
    st.subheader("👤 Récapitulatif par Responsable")
    df_resp  = calculer_recap_par_responsable(df_entrees, df_depenses, mois_filtre)
    total_rp = {
        'Responsable':   'TOTAL',
        'Total Encaissé':round(df_resp['Total Encaissé'].sum(), 2),
        'Total Dépensé': round(df_resp['Total Dépensé'].sum(),  2),
        'Bilan':         round(df_resp['Bilan'].sum(),          2),
    }
    df_resp = pd.concat([df_resp, pd.DataFrame([total_rp])], ignore_index=True)

    def style_resp(df):
        s = pd.DataFrame('', index=df.index, columns=df.columns)
        s[df['Responsable'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
        return s

    st.dataframe(df_resp.style.apply(style_resp, axis=None).format(formater_colonnes(df_resp)),
                 use_container_width=True, hide_index=True)
    df_rnt = df_resp[df_resp['Responsable'] != 'TOTAL']
    r1, r2, r3 = st.columns(3)
    r1.metric("📥 Total Encaissé",     f"{round(df_rnt['Total Encaissé'].sum(), 2):.2f} €")
    r2.metric("📤 Total Dépensé",      f"{round(df_rnt['Total Dépensé'].sum(),  2):.2f} €")
    r3.metric("📊 Bilan Responsables", f"{round(df_rnt['Bilan'].sum(),          2):.2f} €")

# ══════════════════════════════════════════════════════════════════════════════
# 📒 COMPTA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📒 Compta":
    st.title("📒 Comptabilité Générale par Bien")

    if fichier is None:
        st.info("👈 Veuillez importer votre fichier CSV Airbnb depuis la sidebar.")
        st.stop()

    df         = charger_fichier(fichier)
    mois_airbnb = sorted(df['checkin_date'].astype(str).str[:7].unique(), reverse=True)
    mois_extra  = []
    df_entrees  = None
    df_depenses = None

    if fichier_entrees:
        df_entrees = charger_entrees(fichier_entrees)
        mois_extra += list(df_entrees['Mois'].dropna().unique())
    if fichier_depenses:
        df_depenses = charger_depenses(fichier_depenses)
        mois_extra += list(df_depenses['Mois'].dropna().unique())

    tous_mois   = sorted(set(mois_airbnb + mois_extra), reverse=True)
    mois        = st.selectbox("📅 Sélectionner le mois", ["Tous"] + tous_mois, key="mois_compta")
    mois_filtre = None if mois == "Tous" else mois

    df_mois     = df if mois_filtre is None else df[df['checkin_date'].astype(str).str[:7] == mois_filtre]
    biens_airbnb = list(df_mois['property_name'].dropna().unique())

    lignes = []
    for bien in biens_airbnb:
        if bien not in st.session_state.config:
            st.session_state.config[bien] = {
                "commission": 20, "prix_menage": 10,
                "femme_menage": "", "menage_inclus": True,
                "nom_client": "", "adresse_client": "Marrakech, Maroc"
            }
        config  = st.session_state.config[bien]
        df_res  = get_df_bien(df_mois, bien, config)
        totaux  = calculer_totaux(df_res, config)

        revenu_airbnb = round(totaux['Net Base Total'],         2)
        cleaning_tot  = round(pd.to_numeric(
            df_res[df_res['Code'] != 'TOTAL']['Cleaning Fee'], errors='coerce'
        ).fillna(0).sum(), 2)
        commission    = round(totaux['Commission Total'],       2)
        gain_menage   = round(totaux['Gain Ménage Total'],      2)
        prix_men_tot  = round(totaux['Prix Ménage Total'],      2)
        net_proprio   = round(totaux['Net Propriétaire Total'], 2)

        entrees_sup   = 0.0
        if df_entrees is not None:
            df_e = df_entrees.copy()
            if mois_filtre:
                df_e = df_e[df_e['Mois'] == mois_filtre]
            masque = df_e['Propriétaire'].apply(
                lambda x: bien[:20].lower().strip() in x.lower().strip()
                          or x.lower().strip() in bien[:30].lower().strip()
            )
            entrees_sup = round(df_e[masque]['Montant encaissé en €'].sum(), 2)

        depenses_bien = 0.0
        if df_depenses is not None:
            df_d = df_depenses.copy()
            if mois_filtre:
                df_d = df_d[df_d['Mois'] == mois_filtre]
            masque_d = df_d['Propriété'].apply(
                lambda x: bien[:20].lower().strip() in x.lower().strip()
                          or x.lower().strip() in bien[:30].lower().strip()
            )
            depenses_bien = round(df_d[masque_d]['Montant payé en €'].sum(), 2)

        gain_net = round(commission + gain_menage + entrees_sup - depenses_bien, 2)

        lignes.append({
            'Bien':          bien[:45],
            'CA Airbnb':     revenu_airbnb,
            'Cleaning Fee':  cleaning_tot,
            'Net Proprio':   net_proprio,
            'Commission':    commission,
            'Gain Ménage':   gain_menage,
            'Prix Ménage':   prix_men_tot,
            'Entrées Sup.':  entrees_sup,
            'Dépenses':      depenses_bien,
            'Gain Net Total':gain_net,
        })

    df_compta = pd.DataFrame(lignes)
    if df_compta.empty:
        st.warning("Aucune donnée pour cette période.")
        st.stop()

    total_c = {
        'Bien':          'TOTAL',
        'CA Airbnb':     round(df_compta['CA Airbnb'].sum(),     2),
        'Cleaning Fee':  round(df_compta['Cleaning Fee'].sum(),  2),
        'Net Proprio':   round(df_compta['Net Proprio'].sum(),   2),
        'Commission':    round(df_compta['Commission'].sum(),    2),
        'Gain Ménage':   round(df_compta['Gain Ménage'].sum(),   2),
        'Prix Ménage':   round(df_compta['Prix Ménage'].sum(),   2),
        'Entrées Sup.':  round(df_compta['Entrées Sup.'].sum(),  2),
        'Dépenses':      round(df_compta['Dépenses'].sum(),      2),
        'Gain Net Total':round(df_compta['Gain Net Total'].sum(),2),
    }
    df_compta = pd.concat([df_compta, pd.DataFrame([total_c])], ignore_index=True)

    df_nt = df_compta[df_compta['Bien'] != 'TOTAL']
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💶 CA Airbnb",       f"{round(df_nt['CA Airbnb'].sum(),     2):.2f} €")
    c2.metric("💰 Commission",       f"{round(df_nt['Commission'].sum(),    2):.2f} €")
    c3.metric("📥 Entrées Sup.",     f"{round(df_nt['Entrées Sup.'].sum(),  2):.2f} €")
    c4.metric("📤 Dépenses",         f"{round(df_nt['Dépenses'].sum(),      2):.2f} €")
    c5.metric("💵 Gain Net Total",   f"{round(df_nt['Gain Net Total'].sum(),2):.2f} €")

    st.divider()
    st.subheader(f"📊 Récapitulatif Comptable – {mois}")

    def style_compta(df):
        s = pd.DataFrame('', index=df.index, columns=df.columns)
        s[df['Bien'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
        if 'Gain Net Total' in df.columns:
            for i, val in enumerate(df['Gain Net Total']):
                try:
                    if df.iloc[i]['Bien'] != 'TOTAL':
                        s.iloc[i, df.columns.get_loc('Gain Net Total')] = (
                            'color:#27ae60;font-weight:bold;' if float(val) >= 0
                            else 'color:#e74c3c;font-weight:bold;'
                        )
                except (ValueError, TypeError):
                    pass
        return s

    st.dataframe(
        df_compta.style.apply(style_compta, axis=None).format(formater_colonnes(df_compta)),
        use_container_width=True, hide_index=True
    )

    st.divider()
    st.subheader("🔍 Détail par Bien")
    bien_detail = st.selectbox("Choisir un bien", biens_airbnb, key="bien_compta")

    if bien_detail:
        config  = st.session_state.config[bien_detail]
        df_res  = get_df_bien(df_mois, bien_detail, config)

        st.markdown("**🏠 Réservations Airbnb**")
        st.dataframe(df_res.style.apply(style_total, axis=None).format(formater_colonnes(df_res)),
                     use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**📥 Entrées Supplémentaires**")
            if df_entrees is not None:
                df_e = df_entrees.copy()
                if mois_filtre:
                    df_e = df_e[df_e['Mois'] == mois_filtre]
                masque   = df_e['Propriétaire'].apply(
                    lambda x: bien_detail[:20].lower().strip() in x.lower().strip()
                              or x.lower().strip() in bien_detail[:30].lower().strip()
                )
                df_e_b   = df_e[masque][[c for c in
                    ['Date','Type de service','Description','Montant encaissé en €','Responsable']
                    if c in df_e.columns]].copy()
                if not df_e_b.empty:
                    tot_eb = {c: '' for c in df_e_b.columns}
                    tot_eb['Type de service'] = 'TOTAL'
                    if 'Montant encaissé en €' in df_e_b.columns:
                        tot_eb['Montant encaissé en €'] = round(df_e_b['Montant encaissé en €'].sum(), 2)
                    df_e_b = pd.concat([df_e_b, pd.DataFrame([tot_eb])], ignore_index=True)

                    def style_teb(df):
                        s = pd.DataFrame('', index=df.index, columns=df.columns)
                        s[df['Type de service'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
                        return s

                    st.dataframe(df_e_b.style.apply(style_teb, axis=None).format(formater_colonnes(df_e_b)),
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("Aucune entrée supplémentaire pour ce bien.")
            else:
                st.info("Fichier entrées non importé.")

        with col_b:
            st.markdown("**📤 Dépenses**")
            if df_depenses is not None:
                df_d = df_depenses.copy()
                if mois_filtre:
                    df_d = df_d[df_d['Mois'] == mois_filtre]
                masque_d = df_d['Propriété'].apply(
                    lambda x: bien_detail[:20].lower().strip() in x.lower().strip()
                              or x.lower().strip() in bien_detail[:30].lower().strip()
                )
                df_d_b   = df_d[masque_d][[c for c in
                    ['Date','Catégorie','Description','Montant payé en €','Payé par']
                    if c in df_d.columns]].copy()
                if not df_d_b.empty:
                    tot_db = {c: '' for c in df_d_b.columns}
                    tot_db['Catégorie'] = 'TOTAL'
                    if 'Montant payé en €' in df_d_b.columns:
                        tot_db['Montant payé en €'] = round(df_d_b['Montant payé en €'].sum(), 2)
                    df_d_b = pd.concat([df_d_b, pd.DataFrame([tot_db])], ignore_index=True)

                    def style_tdb(df):
                        s = pd.DataFrame('', index=df.index, columns=df.columns)
                        s[df['Catégorie'] == 'TOTAL'] = 'font-weight:bold;background-color:#2980b9;color:white;'
                        return s

                    st.dataframe(df_d_b.style.apply(style_tdb, axis=None).format(formater_colonnes(df_d_b)),
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("Aucune dépense pour ce bien.")
            else:
                st.info("Fichier dépenses non importé.")

        st.divider()
        st.markdown(f"**📋 Récapitulatif – {bien_detail[:45]}**")
        totaux = calculer_totaux(df_res, config)

        e_sup = 0.0
        d_tot = 0.0
        if df_entrees is not None:
            masque = df_entrees['Propriétaire'].apply(
                lambda x: bien_detail[:20].lower().strip() in x.lower().strip()
                          or x.lower().strip() in bien_detail[:30].lower().strip()
            )
            df_ef = df_entrees[masque]
            if mois_filtre:
                df_ef = df_ef[df_ef['Mois'] == mois_filtre]
            e_sup = round(df_ef['Montant encaissé en €'].sum(), 2)

        if df_depenses is not None:
            masque_d = df_depenses['Propriété'].apply(
                lambda x: bien_detail[:20].lower().strip() in x.lower().strip()
                          or x.lower().strip() in bien_detail[:30].lower().strip()
            )
            df_df = df_depenses[masque_d]
            if mois_filtre:
                df_df = df_df[df_df['Mois'] == mois_filtre]
            d_tot = round(df_df['Montant payé en €'].sum(), 2)

        gain_f = round(totaux['Commission Total'] + totaux['Gain Ménage Total'] + e_sup - d_tot, 2)

        r1, r2, r3, r4, r5, r6 = st.columns(6)
        r1.metric("🏠 CA Airbnb",   f"{totaux['Net Base Total']:.2f} €")
        r2.metric("💰 Commission",   f"{totaux['Commission Total']:.2f} €")
        r3.metric("🧹 Gain Ménage",  f"{totaux['Gain Ménage Total']:.2f} €")
        r4.metric("📥 Entrées Sup.", f"{e_sup:.2f} €")
        r5.metric("📤 Dépenses",     f"{d_tot:.2f} €")
        r6.metric("💵 Gain Final",   f"{gain_f:.2f} €",
                  delta=f"{gain_f:.2f}", delta_color="normal" if gain_f >= 0 else "inverse")

# ══════════════════════════════════════════════════════════════════════════════
# 🧾 FACTURES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧾 Factures":
    st.title("🧾 Génération des Factures PDF")

    if fichier is None:
        st.info("👈 Veuillez importer votre fichier CSV Airbnb depuis la sidebar.")
        st.stop()

    df           = charger_fichier(fichier)
    mois_options = sorted(df['checkin_date'].astype(str).str[:7].unique(), reverse=True)
    mois         = st.selectbox("📅 Sélectionner le mois", mois_options, key="mois_factures")
    df_mois      = df[df['checkin_date'].astype(str).str[:7] == mois]
    biens        = list(df_mois['property_name'].dropna().unique())
    bien_sel     = st.selectbox("🏠 Bien à facturer", ["Tous"] + biens, key="bien_factures")

    if st.button("🧾 Générer les Factures PDF", type="primary"):
        biens_a_facturer = biens if bien_sel == "Tous" else [bien_sel]
        factures         = []

        for bien in biens_a_facturer:
            if bien not in st.session_state.config:
                st.session_state.config[bien] = {
                    "commission": 20, "prix_menage": 10,
                    "femme_menage": "", "menage_inclus": True,
                    "nom_client": "", "adresse_client": "Marrakech, Maroc"
                }
            config  = st.session_state.config[bien]
            df_res  = get_df_bien(df_mois, bien, config)
            totaux  = calculer_totaux(df_res, config)

            try:
                nom_f = generer_facture(bien, df_res, totaux, config, mois)
                factures.append((bien, nom_f))
            except Exception as e:
                st.error(f"❌ Err€ pour {bien[:30]} : {e}")

        st.success(f"✅ {len(factures)} facture(s) générée(s) !")
        for bien, nom_f in factures:
            if os.path.exists(nom_f):
                with open(nom_f, 'rb') as f:
                    st.download_button(
                        label=f"📥 Télécharger – {bien[:35]}",
                        data=f,
                        file_name=os.path.basename(nom_f),
                        mime='application/pdf',
                        key=f"dl_{bien[:20]}_{mois}"
                    )
