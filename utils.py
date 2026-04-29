# utils.py

import re

def nettoyer_nom(nom):
    """Supprime les liens Notion et nettoie le nom"""
    if not isinstance(nom, str):
        return ''
    # Supprime tout ce qui est entre parenthèses (liens Notion)
    nom = re.sub(r'\(https?://[^\)]+\)', '', nom)
    return nom.strip()
