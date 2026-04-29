from fpdf import FPDF
import pandas as pd
from datetime import datetime
import os
import urllib.request

# ─── CONFIGURATION LOGO ───────────────────────────────────────────────────────
LOGO_URL  = "src/logo-site.png"   # ← Remplace par ton URL ou chemin local
LOGO_PATH = "src/logo-site.png"   # ← Chemin de sauvegarde local
# ──────────────────────────────────────────────────────────────────────────────


def telecharger_logo():
    """Retourne le chemin absolu du logo."""
    base_dir = os.path.dirname(os.path.abspath(__file__))

    candidats = [
        os.path.join(base_dir, "src", "logo-site.png"),
        os.path.join(os.getcwd(), "src", "logo-site.png"),
        os.path.abspath("src/logo-site.png"),
    ]

    for chemin in candidats:
        if os.path.exists(chemin):
            return chemin

    print("Logo introuvable. Chemins testes :")
    for c in candidats:
        print(f"   - {c}")
    return None


class FacturePDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.3)
        self.line(15, 272, 195, 272)
        self.set_xy(15, 275)
        self.set_font('Helvetica', 'U', 8)
        self.set_text_color(60, 60, 60)
        self.cell(0, 5, 'PRESTIGE-CONCIERGERIE.COM', align='C')


def generer_facture(property_name, df_resultat, totaux, config, mois, output_dir='output/factures'):
    os.makedirs(output_dir, exist_ok=True)

    pdf = FacturePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.set_margins(15, 15, 15)

    commission_label = f"Commission ({config['commission']}%)"
    nom_client       = config.get('nom_client',     '')
    adresse_client   = config.get('adresse_client', 'Marrakech, Maroc')
    date_facture     = datetime.now().strftime('%d/%m/%Y')
    OR_R, OR_G, OR_B = 200, 145, 50

    # ══════════════════════════════════════════════════════════════════════════
    # EN-TÊTE : BILAN (or) + LOGO (droite)
    # ══════════════════════════════════════════════════════════════════════════
    pdf.set_xy(15, 15)
    pdf.set_font('Helvetica', 'B', 36)
    pdf.set_text_color(OR_R, OR_G, OR_B)
    pdf.cell(90, 18, 'BILAN', align='L')

    # Cadre logo
    logo_x, logo_y, logo_w, logo_h = 130, 10, 65, 30
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(OR_R, OR_G, OR_B)
    pdf.set_line_width(0.8)
    pdf.rect(logo_x, logo_y, logo_w, logo_h, style='D')

    # Insertion logo
    logo_path = telecharger_logo()
    if logo_path:
        try:
            pdf.image(logo_path,
                      x=logo_x + 3,
                      y=logo_y + 3,
                      w=logo_w - 6,
                      h=logo_h - 6)
        except Exception as e:
            print(f"Erreur chargement logo : {e}")
            logo_path = None

    if not logo_path:
        pdf.set_xy(logo_x, logo_y + 5)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(OR_R, OR_G, OR_B)
        pdf.cell(logo_w, 8, 'PRESTIGE', align='C')
        pdf.set_xy(logo_x, logo_y + 14)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(logo_w, 5, 'CONCIERGERIE', align='C')

    # DATE
    pdf.set_xy(15, 34)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(90, 5, f'DATE: {date_facture}', align='L')

    # Ligne séparatrice
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    pdf.line(15, 42, 195, 42)
    pdf.set_y(46)

    # ══════════════════════════════════════════════════════════════════════════
    # INFOS CLIENT
    # ══════════════════════════════════════════════════════════════════════════
    pdf.ln(7)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 6, f'Client : {nom_client}', ln=True)
    pdf.cell(0, 6, f'Adresse : {adresse_client}', ln=True)
    pdf.ln(20)

    # ══════════════════════════════════════════════════════════════════════════
    # CALCULS
    # ══════════════════════════════════════════════════════════════════════════
    col_g = 85
    col_d = 90

    df_data = df_resultat[df_resultat['Code'] != 'TOTAL'].copy()

    total_nuits = int(pd.to_numeric(df_data['Nuits'], errors='coerce').fillna(0).sum())
    total_ca    = round(pd.to_numeric(df_data['Net Base'], errors='coerce').fillna(0).sum(), 2)
    total_comm  = round(
        pd.to_numeric(
            df_data[commission_label] if commission_label in df_data.columns else pd.Series([0]),
            errors='coerce'
        ).fillna(0).sum(), 2
    )
    net_proprio    = round(totaux.get('Net Propriétaire Total', total_ca - total_comm), 2)
    autres_charges = 0.00

    try:
        date_debut = df_data['Check-in'].iloc[0][:10]
        date_fin   = df_data['Check-out'].iloc[-1][:10]
    except Exception:
        date_debut = mois
        date_fin   = mois

    # ══════════════════════════════════════════════════════════════════════════
    # FONCTIONS TABLEAU
    # ══════════════════════════════════════════════════════════════════════════
    def draw_row_tableau(label, valeur, hauteur=10):
        """Ligne standard : fond or gauche, fond blanc droite."""
        pdf.set_fill_color(OR_R, OR_G, OR_B)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.cell(col_g, hauteur, f'  {label.upper()}', border=1, fill=True, align='L')

        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(20, 20, 20)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_draw_color(200, 200, 200)
        pdf.cell(col_d, hauteur, f'  {valeur}', border=1, fill=True, align='L')
        pdf.ln()

    def draw_row_periode(date_deb, date_fin_val, hauteur=10):
        """Ligne Période : DU xx/xx  A  xx/xx."""
        pdf.set_fill_color(OR_R, OR_G, OR_B)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.cell(col_g, hauteur, '  PERIODE', border=1, fill=True, align='L')

        sous_w = col_d / 4
        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(20, 20, 20)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_draw_color(200, 200, 200)
        pdf.cell(sous_w * 0.6, hauteur, '  DU :',           border='LTB', fill=True, align='L')
        pdf.cell(sous_w * 1.4, hauteur, f' {date_deb}',     border='TB',  fill=True, align='L')
        pdf.cell(sous_w * 0.6, hauteur, '  A :',            border='TB',  fill=True, align='L')
        pdf.cell(sous_w * 1.4, hauteur, f' {date_fin_val}', border='TRB', fill=True, align='L')
        pdf.ln()

    def draw_row_commission(pct, montant, hauteur=14):
        """Ligne Commission sur 2 lignes dans la cellule label."""
        x = pdf.get_x()
        y = pdf.get_y()

        # Cellule or (vide – texte dessiné manuellement)
        pdf.set_fill_color(OR_R, OR_G, OR_B)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.cell(col_g, hauteur, '', border=1, fill=True)

        # Ligne 1
        pdf.set_xy(x + 2, y + 2)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(col_g - 4, 5, 'COMMISSION CONCIERGERIE', align='L')

        # Ligne 2
        pdf.set_xy(x + 2, y + 8)
        pdf.cell(col_g - 4, 5, f'({pct} %)', align='L')

        # Cellule blanche valeur
        pdf.set_xy(x + col_g, y)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(20, 20, 20)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_draw_color(200, 200, 200)
        pdf.cell(col_d, hauteur, f'  {montant:.2f} EUR', border=1, fill=True, align='L')
        pdf.ln()

    # ══════════════════════════════════════════════════════════════════════════
    # DESSIN DU TABLEAU
    # ══════════════════════════════════════════════════════════════════════════
    draw_row_tableau('Logement',          property_name[:45])
    draw_row_periode(date_debut,           date_fin)
    draw_row_tableau('Nombre de nuits',   str(total_nuits))
    draw_row_tableau("Chiffre d'affaire", f"{total_ca:.2f} EUR")
    draw_row_commission(config['commission'], total_comm)
    draw_row_tableau('Autres charges',    f"{autres_charges:.2f} EUR")

    pdf.ln(8)

    # ══════════════════════════════════════════════════════════════════════════
    # SOUS-TOTAL + TVA (alignés à droite)
    # ══════════════════════════════════════════════════════════════════════════
    tva_val   = 0.00
    total_ttc = round(net_proprio + tva_val, 2)
    x_right   = 125
    label_w   = 35
    val_w     = 35

    pdf.set_xy(x_right, pdf.get_y())
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(label_w, 7, 'Sous total :', align='R')
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(val_w, 7, f'{net_proprio:.2f} EUR', align='R')
    pdf.ln()

    pdf.set_xy(x_right, pdf.get_y())
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(label_w, 7, 'TVA (0%) :', align='R')
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(val_w, 7, f'{tva_val:.2f} EUR', align='R')
    pdf.ln(15)

    # Ligne séparatrice
    y_sep = pdf.get_y()
    pdf.set_draw_color(150, 150, 150)
    pdf.set_line_width(0.3)
    pdf.line(15, y_sep, 195, y_sep)
    pdf.ln(4)

    # ══════════════════════════════════════════════════════════════════════════
    # PIED : texte légal (gauche) + TOTAL en or (droite)
    # ══════════════════════════════════════════════════════════════════════════
    y_bas = pdf.get_y()

    # Texte légal
    pdf.set_xy(15, y_bas)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(90, 5, 'Facture etablie sans TVA', ln=False)
    pdf.set_xy(15, y_bas + 6)
    pdf.cell(90, 5, 'Prestations de conciergerie.', ln=False)
    pdf.set_xy(15, y_bas + 12)
    pdf.cell(90, 5, 'Merci pour votre confiance.', ln=False)

    # TOTAL à droite
    pdf.set_xy(108, y_bas + 2)
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(38, 12, 'TOTAL :', align='R')
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(OR_R, OR_G, OR_B)
    pdf.cell(48, 12, f'{total_ttc:.2f} EUR', align='R')

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    nom_safe    = (property_name[:30].strip()
                   .replace(' ', '_').replace('|', '')
                   .replace(',', '').replace('/', ''))
    nom_fichier = f"{output_dir}/{nom_safe}_{mois}.pdf"
    pdf.output(nom_fichier)
    return nom_fichier
