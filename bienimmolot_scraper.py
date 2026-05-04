#!/usr/bin/env python3
"""
BienImmoLot — Scraper automatique
Scrape PAP.fr, envoie alertes via Brevo
Se lance toutes les heures sur Render.com
"""

import requests
import json
import time
import os
from datetime import datetime
import xml.etree.ElementTree as ET

# ── CONFIG ────────────────────────────────────────────────────────────
BREVO_KEY = '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'
FROM_EMAIL = 'ben.akbas2004@gmail.com'
FROM_NAME = 'BienImmoLot'
ADMIN_EMAIL = 'ben.akbas2004@gmail.com'

SUPABASE_URL = 'https://gijswxsbasasnfjsrasn.supabase.co'
SUPABASE_KEY = 'sb_publishable_Xt1nC704NX4erWAbdRo1Bg_WzPonFPf1'

RSS_FEEDS = [
    'https://rss.pap.fr/annonces/ventes-immobilieres-lot-46',
    'https://rss.pap.fr/annonces/ventes-immobilieres-aveyron-12',
    'https://rss.pap.fr/annonces/ventes-immobilieres-correze-19',
    'https://rss.pap.fr/annonces/ventes-immobilieres-cantal-15',
    'https://rss.pap.fr/annonces/ventes-immobilieres-tarn-81',
    'https://rss.pap.fr/annonces/ventes-immobilieres-lot-et-garonne-47',
]

SEEN_FILE = 'seen_annonces.json'

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, 'w') as f:
        json.dump(list(seen), f)

def get_inscrits():
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        r = requests.get(f'{SUPABASE_URL}/rest/v1/bienimmolot_inscrits?select=*', headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        print(f"Supabase erreur: {r.status_code}")
        return []
    except Exception as e:
        print(f"Erreur Supabase: {e}")
        return []

def parse_prix(texte):
    import re
    nombres = re.findall(r'\d[\d\s]{2,8}', texte.replace('\xa0', ' '))
    for n in nombres:
        try:
            val = int(n.replace(' ', ''))
            if 10000 < val < 2000000:
                return val
        except:
            pass
    return None

def parse_surface(texte):
    import re
    match = re.search(r'(\d+)\s*m', texte, re.IGNORECASE)
    return int(match.group(1)) if match else None

def scrape_rss():
    nouvelles = []
    seen = load_seen()
    headers = {'User-Agent': 'Mozilla/5.0 BienImmoLot/1.0'}
    
    for url in RSS_FEEDS:
        try:
            print(f"Scraping: {url}")
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"  Erreur {r.status_code}")
                continue
            root = ET.fromstring(r.content)
            channel = root.find('channel')
            if not channel:
                continue
            items = channel.findall('item')
            print(f"  → {len(items)} annonces")
            for item in items:
                link = item.findtext('link', '')
                title = item.findtext('title', '')
                desc = item.findtext('description', '')
                if not link or link in seen:
                    continue
                full = title + ' ' + desc
                nouvelles.append({
                    'id': link, 'titre': title,
                    'description': desc[:300],
                    'lien': link,
                    'prix': parse_prix(full),
                    'surface': parse_surface(full),
                    'date': item.findtext('pubDate', ''),
                    'source': 'PAP.fr'
                })
                seen.add(link)
        except Exception as e:
            print(f"Erreur: {e}")
    
    save_seen(seen)
    return nouvelles

def correspond(annonce, inscrit):
    if annonce.get('prix') and inscrit.get('budget_max'):
        try:
            budget = int(str(inscrit['budget_max']).replace(' ', '').replace('€', ''))
            if annonce['prix'] > budget:
                return False
        except:
            pass
    if annonce.get('surface') and inscrit.get('surface_min'):
        try:
            smin = int(str(inscrit['surface_min']).replace(' ', '').replace('m²', ''))
            if annonce['surface'] < smin:
                return False
        except:
            pass
    return True

def envoyer_alerte(inscrit, annonce):
    nom = inscrit.get('nom', 'Rechercheur')
    email = inscrit.get('email', '')
    if not email:
        return False
    
    prix_str = f"{annonce['prix']:,}€".replace(',', ' ') if annonce.get('prix') else 'Non précisé'
    surface_str = f"{annonce['surface']} m²" if annonce.get('surface') else 'Non précisé'
    
    html = f"""<div style="font-family:Georgia,serif;max-width:580px;margin:0 auto;background:#F7F5F0;border:1px solid #DDD9D0;">
<div style="background:#1A1714;padding:24px 28px;border-bottom:3px solid #C0392B;">
<div style="font-size:22px;color:#F7F5F0;font-weight:bold;">🏡 BienImmoLot</div>
<div style="font-size:11px;color:rgba(247,245,240,.4);margin-top:4px;letter-spacing:.12em;text-transform:uppercase;">Nouvelle annonce correspondant à vos critères</div>
</div>
<div style="padding:28px;">
<p style="font-size:15px;color:#1A1714;margin-bottom:14px;">Bonjour {nom},</p>
<p style="font-size:14px;color:#8B8680;line-height:1.8;margin-bottom:20px;">Une nouvelle annonce correspond à vos critères !</p>
<div style="background:white;border:1px solid #DDD9D0;border-left:3px solid #C0392B;border-radius:4px;padding:20px;margin-bottom:20px;">
<div style="font-size:16px;font-weight:bold;color:#1A1714;margin-bottom:10px;">{annonce['titre']}</div>
<div style="font-size:13px;color:#8B8680;line-height:1.7;margin-bottom:14px;">{annonce['description']}</div>
<table style="width:100%;border-collapse:collapse;margin-bottom:14px;">
<tr><td style="padding:8px 12px;border:1px solid #DDD9D0;font-weight:600;font-size:12px;background:#EFECE5;">Prix</td><td style="padding:8px 12px;border:1px solid #DDD9D0;font-size:14px;font-weight:bold;color:#C0392B;">{prix_str}</td></tr>
<tr><td style="padding:8px 12px;border:1px solid #DDD9D0;font-weight:600;font-size:12px;background:#EFECE5;">Surface</td><td style="padding:8px 12px;border:1px solid #DDD9D0;font-size:13px;">{surface_str}</td></tr>
<tr><td style="padding:8px 12px;border:1px solid #DDD9D0;font-weight:600;font-size:12px;background:#EFECE5;">Source</td><td style="padding:8px 12px;border:1px solid #DDD9D0;font-size:13px;">{annonce['source']}</td></tr>
</table>
<a href="{annonce['lien']}" style="display:block;background:#C0392B;color:white;padding:12px;border-radius:4px;text-decoration:none;font-weight:bold;font-size:13px;text-align:center;">Voir l'annonce →</a>
</div>
<p style="font-size:12px;color:#B5B0A8;">Abonnement BienImmoLot — 4,99€/mois</p>
</div>
<div style="padding:12px 28px;background:#EFECE5;text-align:center;border-top:1px solid #DDD9D0;font-size:10px;color:#B5B0A8;">BienImmoLot · BenApps · Figeac, Lot</div>
</div>"""
    
    try:
        r = requests.post('https://api.brevo.com/v3/smtp/email',
            headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json'},
            json={
                'sender': {'name': FROM_NAME, 'email': FROM_EMAIL},
                'to': [{'email': email, 'name': nom}],
                'subject': f'🏡 Nouvelle annonce : {annonce["titre"][:50]}',
                'htmlContent': html
            }, timeout=15)
        return r.status_code == 201
    except Exception as e:
        print(f"Erreur email: {e}")
        return False

def main():
    print(f"\n{'='*50}")
    print(f"BienImmoLot Scraper — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")
    
    print("\n📋 Récupération inscrits Supabase...")
    inscrits = get_inscrits()
    print(f"  → {len(inscrits)} inscrits")
    
    if not inscrits:
        inscrits = [{'nom': 'Benjamin', 'email': ADMIN_EMAIL, 'budget_max': 500000, 'surface_min': 20}]
        print("  → Mode test avec email admin")
    
    print("\n🔍 Scraping annonces...")
    nouvelles = scrape_rss()
    print(f"  → {len(nouvelles)} nouvelles annonces")
    
    if not nouvelles:
        print("  ✓ Aucune nouvelle annonce — à relancer dans 1h")
        return
    
    print("\n📧 Envoi alertes...")
    total = 0
    for annonce in nouvelles:
        for inscrit in inscrits:
            if correspond(annonce, inscrit):
                if envoyer_alerte(inscrit, annonce):
                    total += 1
                    print(f"  ✓ → {inscrit['email']} : {annonce['titre'][:40]}")
                time.sleep(0.3)
    
    print(f"\n✅ {total} alertes envoyées")

if __name__ == '__main__':
    # Boucle toutes les heures
    while True:
        main()
        print("\n⏳ Pause 1 heure...")
        time.sleep(3600)
