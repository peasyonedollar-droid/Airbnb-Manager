from fpdf import FPDF
import pandas as pd
from datetime import datetime
import os

class FacturePDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-20)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, 'Facture etablie sans TVA - Prestations de conciergerie.', align='C')
        self.ln(4)
        self.cell(0, 5, f'Page {self.page_no()}', align='C')


def generer_facture(property_name, df_resultat, totaux, config, mois, output_dir='output/factures'):
    os.makedirs(output_dir, exist_ok=True)

    pdf = FacturePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(15, 15, 15)

    commission_label = f"Commission ({config['commission']}%)"

    # ══════════════════════════════════════════════════════════════════════════
    # EN-TÊTE : FACTURE
    # ══════════════════════════════════════════════════════════════════════════
    pdf.set_font('Helvetica', 'B', 28)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 14, 'FACTURE', align='C')
    pdf.ln(4)

    # Ligne de séparation bleue
    pdf.ln(8)
    pdf.set_draw_color(41, 128, 185)
    pdf.set_line_width(0.8)
    pdf.line(15, pdf.get_y(), 205, pdf.get_y())
    pdf.ln(8)

    # ══════════════════════════════════════════════════════════════════════════
    # BLOC INFO : Société | Client | Date
    # ══════════════════════════════════════════════════════════════════════════
    date_facture   = datetime.now().strftime('%d/%m/%Y')
    nom_client     = config.get('nom_client',     'Propriétaire')
    adresse_client = config.get('adresse_client', 'Marrakech, Maroc')
    col_w          = 60
    y_info         = pdf.get_y()

    # Colonne Société
    pdf.set_xy(15, y_info)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(col_w, 6, 'Societe :', ln=False)
    pdf.set_xy(15, y_info + 6)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(col_w, 6, 'Prestige Conciergerie', ln=False)

    # Colonne Client
    pdf.set_xy(15 + col_w, y_info)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(col_w, 6, 'Client :', ln=False)
    pdf.set_xy(15 + col_w, y_info + 6)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(col_w, 6, nom_client[:40], ln=False)
    pdf.set_xy(15 + col_w, y_info + 12)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(col_w, 5, adresse_client[:40], ln=False)

    # Colonne Date
    pdf.set_xy(15 + col_w * 2, y_info)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(col_w, 6, 'Date :', ln=False)
    pdf.set_xy(15 + col_w * 2, y_info + 6)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(col_w, 6, date_facture, ln=False)

    pdf.set_y(y_info + 24)
    pdf.ln(4)

    # Ligne de séparation grise
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(10)

    # ══════════════════════════════════════════════════════════════════════════
    # TABLEAU DES RÉSERVATIONS
    # ══════════════════════════════════════════════════════════════════════════
    headers  = ['Logement', 'Periode', 'Nuits', "Chiffre d'affaires", commission_label]
    largeurs = [52, 38, 12, 30, 30]

    # En-tête tableau
    pdf.set_fill_color(41, 128, 185)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_draw_color(255, 255, 255)
    pdf.set_line_width(0.1)
    for h, w in zip(headers, largeurs):
        pdf.cell(w, 9, h, border=1, fill=True, align='C')
    pdf.ln()

    # Lignes de données
    df_data = df_resultat[df_resultat['Code'] != 'TOTAL'].copy()




    total_nuits = int(pd.to_numeric(df_data['Nuits'],             errors='coerce').fillna(0).sum())
    total_ca    = round(pd.to_numeric(df_data['Net Base'],         errors='coerce').fillna(0).sum(), 2)
    total_comm  = round(pd.to_numeric(
        df_data[commission_label] if commission_label in df_data.columns else pd.Series([0]),
        errors='coerce').fillna(0).sum(), 2)


    # Ligne TOTAL tableau
    pdf.set_fill_color(41, 128, 185)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 9)
    # ══════════════════════════════════════════════════════════════════════════
    # BLOC TOTAL PROPRIÉTAIRE
    # ══════════════════════════════════════════════════════════════════════════
    net_proprio = round(totaux.get('Net Propriétaire Total', total_ca - total_comm), 2)

    y_box = pdf.get_y()
    pdf.set_fill_color(235, 245, 255)
    pdf.set_draw_color(41, 128, 185)
    pdf.set_line_width(0.5)
    pdf.rect(15, y_box, 180, 16, style='FD')

    pdf.set_xy(15, y_box + 3)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(120, 8, 'Total Proprietaire', align='L')
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(60, 8, f"{net_proprio:.2f} EUR", align='R')
    pdf.ln(22)

    # ══════════════════════════════════════════════════════════════════════════
    # RÉCAPITULATIF FINAL (sans Logement ni Détail Ménage)
    # ══════════════════════════════════════════════════════════════════════════
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 7, 'Recapitulatif', ln=True)
    pdf.ln(3)

    menage_inclus = config.get('menage_inclus', True)

    recap_items = [
        ("Chiffre d'affaires Airbnb",  f"{total_ca:.2f} EUR"),
        (commission_label,              f"{total_comm:.2f} EUR"),
        ("Net Proprietaire (80%)",      f"{net_proprio:.2f} EUR"),
    ]
    if menage_inclus:
        recap_items += [
            ("Prix Menage total",       f"{totaux.get('Prix Ménage Total', 0):.2f} EUR"),
            ("total_nuits",         f"{totaux.get('total_nuits', 0):.2f} EUR"),
        ]
   

    for label, valeur in recap_items:
        is_total = label == "TON GAIN TOTAL"
        if is_total:
            pdf.set_fill_color(41, 128, 185)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', 'B', 11)
            h_row = 11
        else:
            pdf.set_fill_color(245, 248, 252)
            pdf.set_text_color(50, 50, 50)
            pdf.set_font('Helvetica', '', 10)
            h_row = 9

        pdf.set_draw_color(200, 200, 200)
        pdf.cell(120, h_row, label, border=1, fill=True, align='L')
        if is_total:
            pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(60, h_row, valeur, border=1, fill=True, align='R')
        pdf.ln()

    # Ligne finale + message
    pdf.ln(8)
    pdf.set_draw_color(41, 128, 185)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, 'Merci pour votre confiance.', align='C')

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    nom_safe    = (property_name[:30].strip()
                   .replace(' ', '_').replace('|', '')
                   .replace(',', '').replace('/', ''))
    nom_fichier = f"{output_dir}/{nom_safe}_{mois}.pdf"
    pdf.output(nom_fichier)
    return nom_fichier
