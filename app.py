# app.py - UMWAMPI Monnaie Electronique
from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
import random
from datetime import datetime, timedelta

app = Flask(__name__)

# ============ NOMS ALEATOIRES POUR BENEFICIAIRES ============
NOMS_BENEFICIAIRES = [
    "Jean Baptiste HABIMANA",
    "Marie Claire UWIMANA",
    "Pierre Celestin NDAYISABA",
    "Agnes MUKAMANA",
    "Emmanuel DUSABE",
    "Beatrice MUKAMURENZI",
    "Celestin HAKIZIMANA",
    "Immaculee MUKANDOLI",
    "Jean Paul NSENGIMANA",
    "Esperance MUKESHIMANA",
    "Francois Xavier HABIYAREMYE",
    "Console MUKANTWARI",
    "Jean Damascene NIZEYIMANA",
    "Clementine MUKAMUSONI",
    "Leonidas NDAYISENGA"
]

# ============ BASE DE DONNEES ============
def init_db():
    conn = sqlite3.connect('umwampi.db')
    c = conn.cursor()
    
    # Table transactions
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  msisdn TEXT,
                  session_id TEXT,
                  operation TEXT,
                  full_path TEXT,
                  input_data TEXT,
                  payload_cecadm TEXT,
                  reponse_cecadm TEXT,
                  message_ussd TEXT,
                  statut TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Table historique simplifiee
    c.execute('''CREATE TABLE IF NOT EXISTS historique
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  msisdn TEXT,
                  type_transaction TEXT,
                  montant REAL,
                  destinataire TEXT,
                  reference TEXT,
                  date_heure DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Donnees demo
    c.execute("SELECT COUNT(*) FROM historique")
    if c.fetchone()[0] == 0:
        demo_data = [
            ("0788000001", "depot", 5000, "Compte propre", "REF001", datetime.now() - timedelta(hours=2)),
            ("0788000001", "retrait", 2000, "Compte propre", "REF002", datetime.now() - timedelta(days=1)),
            ("0788000001", "achat_unites", 1000, "Lydia", "REF003", datetime.now() - timedelta(days=2)),
            ("0788000001", "depot", 10000, "Compte propre", "REF004", datetime.now() - timedelta(days=3)),
        ]
        c.executemany("INSERT INTO historique (msisdn, type_transaction, montant, destinataire, reference, date_heure) VALUES (?,?,?,?,?,?)", demo_data)
    
    conn.commit()
    conn.close()

# ============ FONCTIONS UTILITAIRES ============
def get_random_name():
    return random.choice(NOMS_BENEFICIAIRES)

def generate_reference():
    return f"UMW{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(10,99)}"

def save_transaction(msisdn, session_id, operation, full_path, input_data, payload, reponse, message, statut):
    conn = sqlite3.connect('umwampi.db')
    c = conn.cursor()
    c.execute('''INSERT INTO transactions 
                 (msisdn, session_id, operation, full_path, input_data,
                  payload_cecadm, reponse_cecadm, message_ussd, statut)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (msisdn, session_id, operation, full_path, json.dumps(input_data),
               json.dumps(payload) if payload else None,
               json.dumps(reponse) if reponse else None,
               message, statut))
    conn.commit()
    conn.close()

def save_historique(msisdn, type_trans, montant, destinataire, reference):
    conn = sqlite3.connect('umwampi.db')
    c = conn.cursor()
    c.execute('''INSERT INTO historique (msisdn, type_transaction, montant, destinataire, reference)
                 VALUES (?, ?, ?, ?, ?)''',
              (msisdn, type_trans, montant, destinataire, reference))
    conn.commit()
    conn.close()

# ============ MENUS USSD ============
@app.route('/ussd/callback', methods=['POST'])
def ussd_callback():
    data = request.json
    msisdn = data.get('msisdn', '25761069606')
    session_id = data.get('transaction_id"', 'test123')
    text = data.get('ussd_request_msg', '')
    
    parts = text.split('*') if text else []
    print(f"{msisdn} => {text}")
    
    # ============ MENU PRINCIPAL ============
    if text == '':
        msg = """Bienvenue sur UMWAMPI
1. Depot
2. Retrait
3. Historique
4. Balance
5. Vente unites
6. Banque"""
        save_transaction(msisdn, session_id, "menu", "", {}, {}, {}, msg, "success")
        return jsonify({"text": msg, "action": "input"})
    
    # ============ 1. DEPOT ============
    if parts[0] == '1':
        if len(parts) == 1:
            msg = "Montant du depot\nEntrez le montant:"
        elif len(parts) == 2:
            msg = "Entrez votre PIN a 4 chiffres:"
        elif len(parts) == 3:
            pin = parts[2]
            if len(pin) == 4 and pin.isdigit():
                montant = parts[1]
                ref = generate_reference()
                msg = f"""Confirmation depot
Montant: {montant} Fbu
Reference: {ref}
Pin: ****
                
1. Confirmer
2. Annuler"""
            else:
                msg = "PIN invalide. Doit etre 4 chiffres.\nEntrez votre PIN:"
        elif len(parts) == 4:
            if parts[3] == '1':
                montant = parts[1]
                ref = generate_reference()
                
                # Simuler reponse CECADM
                payload_cecadm = {
                    "endpoint": "CECADM_API/deposit",
                    "phone": msisdn,
                    "amount": int(montant),
                    "reference": ref
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "message": "Depot effectue",
                    "transaction_id": ref,
                    "nouveau_solde": 50000 + int(montant)
                }
                
                save_historique(msisdn, "depot", int(montant), "Compte propre", ref)
                save_transaction(msisdn, session_id, "depot", text, 
                               {"montant": montant, "pin": parts[2]},
                               payload_cecadm, reponse_cecadm,
                               f"Depot de {montant} Fbu effectue\nRef: {ref}", "success")
                
                msg = f"""Depot effectue avec succes!
Montant: {montant} Fbu
Reference: {ref}
Nouveau solde: {reponse_cecadm['nouveau_solde']} Fbu
                
Merci d'utiliser UMWAMPI"""
                return jsonify({"text": msg, "action": "end"})
            else:
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                return jsonify({"text": msg, "action": "end"})
        
        save_transaction(msisdn, session_id, "depot", text, {}, {}, {}, msg, "pending")
        return jsonify({"text": msg, "action": "input"})
    
    # ============ 2. RETRAIT ============
    elif parts[0] == '2':
        if len(parts) == 1:
            msg = "Montant du retrait\nEntrez le montant:"
        elif len(parts) == 2:
            msg = "Entrez votre PIN a 4 chiffres:"
        elif len(parts) == 3:
            pin = parts[2]
            if len(pin) == 4 and pin.isdigit():
                montant = parts[1]
                ref = generate_reference()
                msg = f"""Confirmation retrait
Montant: {montant} Fbu
Reference: {ref}
                
1. Confirmer
2. Annuler"""
            else:
                msg = "PIN invalide. Doit etre 4 chiffres.\nEntrez votre PIN:"
        elif len(parts) == 4:
            if parts[3] == '1':
                montant = parts[1]
                ref = generate_reference()
                
                payload_cecadm = {
                    "endpoint": "CECADM_API/withdraw",
                    "phone": msisdn,
                    "amount": int(montant),
                    "reference": ref
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "message": "Retrait effectue",
                    "transaction_id": ref,
                    "nouveau_solde": 50000 - int(montant)
                }
                
                save_historique(msisdn, "retrait", int(montant), "Compte propre", ref)
                save_transaction(msisdn, session_id, "retrait", text,
                               {"montant": montant, "pin": parts[2]},
                               payload_cecadm, reponse_cecadm,
                               f"Retrait de {montant} Fbu effectue\nRef: {ref}", "success")
                
                msg = f"""Retrait effectue avec succes!
Montant: {montant} Fbu
Reference: {ref}
Nouveau solde: {reponse_cecadm['nouveau_solde']} Fbu
                
Merci d'utiliser UMWAMPI"""
                return jsonify({"text": msg, "action": "end"})
            else:
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                return jsonify({"text": msg, "action": "end"})
        
        save_transaction(msisdn, session_id, "retrait", text, {}, {}, {}, msg, "pending")
        return jsonify({"text": msg, "action": "input"})
    
    # ============ 3. HISTORIQUE ============
    elif parts[0] == '3':
        conn = sqlite3.connect('umwampi.db')
        historique = conn.execute(
            "SELECT * FROM historique WHERE msisdn=? ORDER BY date_heure DESC LIMIT 5",
            (msisdn,)
        ).fetchall()
        conn.close()
        
        if historique:
            msg = "Dernieres transactions:\n"
            for h in historique:
                type_trans = h[2].upper()
                montant = h[3]
                date_trans = h[6][:10] if len(h) > 6 else "Recent"
                msg += f"{date_trans} {type_trans}: {montant} Fbu\n"
            msg += "\n0. Menu principal"
        else:
            msg = "Aucune transaction recente\n0. Menu principal"
        
        save_transaction(msisdn, session_id, "historique", text, {}, {}, {}, msg, "success")
        return jsonify({"text": msg, "action": "input"})
    
    # ============ 4. BALANCE ============
    elif parts[0] == '4':
        if len(parts) == 1:
            msg = "Entrez votre PIN a 4 chiffres:"
        elif len(parts) == 2:
            pin = parts[1]
            if len(pin) == 4 and pin.isdigit():
                payload_cecadm = {
                    "endpoint": "CECADM_API/balance",
                    "phone": msisdn
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "balance": 50000,
                    "message": "Solde disponible"
                }
                
                msg = f"""Votre solde UMWAMPI
Solde: {reponse_cecadm['balance']} Fbu
                
0. Menu principal"""
                
                save_transaction(msisdn, session_id, "balance", text,
                               {"pin": pin}, payload_cecadm, reponse_cecadm,
                               f"Solde: {reponse_cecadm['balance']} Fbu", "success")
            else:
                msg = "PIN invalide. Doit etre 4 chiffres.\nEntrez votre PIN:"
        
        return jsonify({"text": msg, "action": "input"})
    
    # ============ 5. VENTE UNITES ============
    elif parts[0] == '5':
        if len(parts) == 1:
            msg = """Vente unites
1. Acheter unites
2. Vendre unites
0. Menu principal"""
        elif len(parts) == 2:
            if parts[1] == '1':
                msg = "Achat unites\nEntrez le montant (min 1000 Fbu):"
            elif parts[1] == '2':
                msg = "Vente unites\nEntrez le nombre d'unites:"
            else:
                msg = "Option invalide"
        elif len(parts) == 3:
            if parts[1] == '1':
                msg = "Entrez le numero du beneficiaire:"
            elif parts[1] == '2':
                msg = "Entrez le numero du beneficiaire:"
        elif len(parts) == 4:
            if parts[1] == '1':
                msg = "Entrez votre PIN a 4 chiffres:"
            elif parts[1] == '2':
                msg = "Entrez votre PIN a 4 chiffres:"
        elif len(parts) == 5:
            pin = parts[4]
            if len(pin) == 4 and pin.isdigit():
                nom_random = get_random_name()
                if parts[1] == '1':
                    msg = f"""Confirmer achat unites
Montant: {parts[2]} Fbu
Beneficiaire: {parts[3]}
Nom: {nom_random}
                
1. Confirmer
2. Annuler"""
                else:
                    msg = f"""Confirmer vente unites
Unites: {parts[2]}
Beneficiaire: {parts[3]}
Nom: {nom_random}
                
1. Confirmer
2. Annuler"""
            else:
                msg = "PIN invalide. Doit etre 4 chiffres.\nEntrez votre PIN:"
        elif len(parts) == 6:
            if parts[5] == '1':
                ref = generate_reference()
                nom_random = get_random_name()
                type_trans = "achat_unites" if parts[1] == '1' else "vente_unites"
                montant = int(parts[2])
                
                payload_cecadm = {
                    "endpoint": "CECADM_API/units",
                    "phone": msisdn,
                    "type": type_trans,
                    "amount": montant,
                    "beneficiaire": parts[3],
                    "reference": ref
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "message": "Transaction unites reussie",
                    "transaction_id": ref
                }
                
                save_historique(msisdn, type_trans, montant, nom_random, ref)
                save_transaction(msisdn, session_id, "vente_unites", text,
                               {"type": type_trans, "montant": montant, "beneficiaire": parts[3]},
                               payload_cecadm, reponse_cecadm,
                               f"{type_trans} reussi\nRef: {ref}", "success")
                
                msg = f"""Transaction reussie!
Type: {type_trans}
Montant: {montant} Fbu
Beneficiaire: {nom_random}
Ref: {ref}
                
Merci d'utiliser UMWAMPI"""
                return jsonify({"text": msg, "action": "end"})
            else:
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                return jsonify({"text": msg, "action": "end"})
        
        save_transaction(msisdn, session_id, "vente_unites", text, {}, {}, {}, msg, "pending")
        return jsonify({"text": msg, "action": "input"})
    
    # ============ 6. BANQUE ============
    elif parts[0] == '6':
        if len(parts) == 1:
            msg = """Banque
1. UMWAMPI vers Banque
2. Banque vers UMWAMPI
0. Menu principal"""
        elif len(parts) == 2:
            if parts[1] == '1':
                msg = "UMWAMPI vers Banque\nEntrez le montant:"
            elif parts[1] == '2':
                msg = "Banque vers UMWAMPI\nEntrez le montant:"
            else:
                msg = "Option invalide"
        elif len(parts) == 3:
            msg = "Entrez le numero de compte bancaire:"
        elif len(parts) == 4:
            msg = "Entrez votre PIN a 4 chiffres:"
        elif len(parts) == 5:
            pin = parts[4]
            if len(pin) == 4 and pin.isdigit():
                nom_random = get_random_name()
                direction = "UMWAMPI -> Banque" if parts[1] == '1' else "Banque -> UMWAMPI"
                msg = f"""Voulez-vous vraiment envoyer
{parts[2]} Fbu
vers Compte {parts[3]}
Nom: {nom_random}
                
1. Confirmer
2. Annuler"""
            else:
                msg = "PIN invalide. Doit etre 4 chiffres.\nEntrez votre PIN:"
        elif len(parts) == 6:
            if parts[5] == '1':
                ref = generate_reference()
                nom_random = get_random_name()
                montant = int(parts[2])
                type_trans = "umwampi_to_bank" if parts[1] == '1' else "bank_to_umwampi"
                
                payload_cecadm = {
                    "endpoint": "CECADM_API/bank_transfer",
                    "phone": msisdn,
                    "type": type_trans,
                    "amount": montant,
                    "compte": parts[3],
                    "nom_beneficiaire": nom_random,
                    "reference": ref
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "message": "Transfert bancaire effectue",
                    "transaction_id": ref,
                    "banque_destinataire": "CECADM"
                }
                
                save_historique(msisdn, type_trans, montant, nom_random, ref)
                save_transaction(msisdn, session_id, "banque", text,
                               {"montant": montant, "compte": parts[3], "beneficiaire": nom_random},
                               payload_cecadm, reponse_cecadm,
                               f"Transfert {montant} Fbu vers {nom_random}", "success")
                
                msg = f"""Transfert bancaire reussi!
Montant: {montant} Fbu
Beneficiaire: {nom_random}
Compte: {parts[3]}
Ref: {ref}
                
Merci d'utiliser UMWAMPI"""
                return jsonify({"text": msg, "action": "end"})
            else:
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                return jsonify({"text": msg, "action": "end"})
        
        save_transaction(msisdn, session_id, "banque", text, {}, {}, {}, msg, "pending")
        return jsonify({"text": msg, "action": "input"})
    
    # ============ RETOUR MENU PRINCIPAL ============
    elif text == '0' or '0' in parts:
        msg = """Bienvenue sur UMWAMPI
1. Depot
2. Retrait
3. Historique
4. Balance
5. Vente unites
6. Banque"""
        save_transaction(msisdn, session_id, "menu", text, {}, {}, {}, msg, "success")
        return jsonify({"text": msg, "action": "input"})
    
    # ============ DEFAUT ============
    else:
        msg = "Option invalide. Reessayez."
        return jsonify({"text": msg, "action": "end"})

# ============ DASHBOARD ============
@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect('umwampi.db')
    conn.row_factory = sqlite3.Row
    
    transactions = conn.execute(
        "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()
    
    total = len(transactions)
    reussies = sum(1 for t in transactions if t['statut'] == 'success')
    
    conn.close()
    
    html = """<!DOCTYPE html>
<html>
<head>
    <title>UMWAMPI - Dashboard Demo CECADM</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="5">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #f0f2f5; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: #BCF; color: darkblue; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .header h1 { font-size: 24px; margin-bottom: 5px; }
        .header p { opacity: 0.9; font-size: 14px; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 28px; font-weight: bold; color: #333; }
        .stat-card.success .value { color: #27ae60; }
        .stat-card.pending .value { color: #f39c12; }
        .stat-card.total .value { color: #3498db; }
        .section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; 
                  box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .section h2 { font-size: 18px; margin-bottom: 15px; color: #333; 
                     border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; 
            border-bottom: 2px solid #dee2e6; color: #495057; }
        td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
        tr:hover { background: #f8f9ff; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 12px; 
                font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .badge-depot { background: #d5f5e3; color: #27ae60; }
        .badge-retrait { background: #fadbd8; color: #e74c3c; }
        .badge-historique { background: #d6eaf8; color: #2980b9; }
        .badge-balance { background: #f9e79f; color: #f39c12; }
        .badge-vente { background: #e8daef; color: #8e44ad; }
        .badge-banque { background: #d5dbdb; color: #2c3e50; }
        .badge-menu { background: #e5e7e9; color: #7f8c8d; }
        pre { background: #f8f9fa; padding: 8px; border-radius: 4px; font-size: 11px;
        overflow: hidden; margin: 0; white-space: pre-wrap; word-break: break-all; }
        .status-success { color: #27ae60; font-weight: bold; }
        .status-pending { color: #f39c12; font-weight: bold; }
        .live-indicator { display: inline-block; width: 10px; height: 10px; background: #27ae60; 
                         border-radius: 50%; animation: pulse 2s infinite; margin-right: 5px; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 UMWAMPI - Plateforme Monnaie Electronique</h1>
            <p><span class="live-indicator"></span> Dashboard en temps reel - Integration CECADM</p>
        </div>
        
        <div class="stats">
            <div class="stat-card total">
                <h3>Total Requetes</h3>
                <div class="value">""" + str(total) + """</div>
            </div>
            <div class="stat-card success">
                <h3>Transactions Reussies</h3>
                <div class="value">""" + str(reussies) + """</div>
            </div>
            <div class="stat-card pending">
                <h3>En Cours</h3>
                <div class="value">""" + str(total - reussies) + """</div>
            </div>
            <div class="stat-card">
                <h3>Derniere Transaction</h3>
                <div class="value" style="font-size: 14px;">""" + (transactions[0]['timestamp'][:19] if transactions else 'Aucune') + """</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📋 Donnees envoyees a CECADM</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date/Heure</th>
                        <th>Telephone</th>
                        <th>Operation</th>
                        <th>Payload ➔ CECADM</th>
                        <th>Reponse CECADM</th>
                        <th>Message USSD</th>
                        <th>Statut</th>
                    </tr>
                </thead>
                <tbody>"""
    
    for t in transactions:
        badge_class = {
            'depot': 'badge-depot', 'retrait': 'badge-retrait',
            'historique': 'badge-historique', 'balance': 'badge-balance',
            'vente_unites': 'badge-vente', 'banque': 'badge-banque',
            'menu': 'badge-menu'
        }.get(t['operation'], '')
        
        html += f"""
                    <tr>
                        <td>{t['timestamp'][:19] if t['timestamp'] else ''}</td>
                        <td>{t['msisdn']}</td>
                        <td><span class="badge {badge_class}">{t['operation']}</span></td>
                        <td><pre>{t['payload_cecadm'][:100] if t['payload_cecadm'] else 'En attente...'}</pre></td>
                        <td><pre>{t['reponse_cecadm'][:100] if t['reponse_cecadm'] else 'En attente...'}</pre></td>
                        <td>{t['message_ussd'][:80]}...</td>
                        <td class="status-{t['statut']}">{'✓' if t['statut'] == 'success' else '⏳'} {t['statut']}</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🔄 Arborescence USSD</h2>
            <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; font-size: 13px;">
MENU PRINCIPAL (*220*423#)
├── 1. Depot
│   └── Montant → PIN → Confirmation → SUCCESS
├── 2. Retrait
│   └── Montant → PIN → Confirmation → SUCCESS
├── 3. Historique
│   └── Affichage 5 dernieres transactions
├── 4. Balance
│   └── PIN → Solde affiche
├── 5. Vente unites
│   ├── 1. Acheter unites
│   │   └── Montant → Beneficiaire → PIN → Confirmation(Nom) → SUCCESS
│   └── 2. Vendre unites
│       └── Unites → Beneficiaire → PIN → Confirmation(Nom) → SUCCESS
└── 6. Banque
    ├── 1. UMWAMPI → Banque
    │   └── Montant → Compte → PIN → Confirmation(Nom) → SUCCESS
    └── 2. Banque → UMWAMPI
        └── Montant → Compte → PIN → Confirmation(Nom) → SUCCESS
            </pre>
        </div>
    </div>
</body>
</html>"""
    
    return html

# ============ EXPORT API ============
@app.route('/api/export')
def export_api():
    conn = sqlite3.connect('umwampi.db')
    conn.row_factory = sqlite3.Row
    transactions = conn.execute(
        "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 100"
    ).fetchall()
    conn.close()
    
    data = []
    for t in transactions:
        data.append({
            "date": t['timestamp'],
            "telephone": t['msisdn'],
            "operation": t['operation'],
            "payload_cecadm": json.loads(t['payload_cecadm']) if t['payload_cecadm'] else None,
            "reponse_cecadm": json.loads(t['reponse_cecadm']) if t['reponse_cecadm'] else None,
            "message_ussd": t['message_ussd'],
            "statut": t['statut']
        })
    return jsonify(data)

# # ============ DEMARRAGE ============
# if __name__ == '__main__':
#     init_db()
#     print("=" * 60)
#     print("UMWAMPI - Serveur USSD demarre!")
#     print("USSD Callback: http://localhost:5000/ussd/callback")
#     print("Dashboard: http://localhost:5000/dashboard")
#     print("Export API: http://localhost:5000/api/export")
#     print("=" * 60)
#     app.run(host='0.0.0.0', port=5000, debug=True)

init_db()