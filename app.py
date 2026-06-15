# app.py - UMWAMPI Monnaie Electronique (Version finale propre)
from flask import Flask, request, jsonify
import sqlite3
import json
import random
from datetime import datetime, timedelta

app = Flask(__name__)

# ============ NOMS ALEATOIRES ============
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

# ============ SESSIONS ============
sessions = {}

# ============ BASE DE DONNEES ============
def init_db():
    conn = sqlite3.connect('umwampi.db')
    c = conn.cursor()
    
    # Table transactions - UNIQUEMENT transactions finales
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  msisdn TEXT,
                  transaction_id TEXT,
                  operation TEXT,
                  montant REAL,
                  destinataire TEXT,
                  reference TEXT,
                  payload_cecadm TEXT,
                  reponse_cecadm TEXT,
                  statut TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Table historique utilisateur
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
            ("25761000001", "depot", 5000, "Compte propre", "REF001", datetime.now() - timedelta(hours=2)),
            ("25761000001", "retrait", 2000, "Compte propre", "REF002", datetime.now() - timedelta(days=1)),
            ("25761000001", "achat_unites", 1000, "Lydia", "REF003", datetime.now() - timedelta(days=2)),
            ("25761000001", "depot", 10000, "Compte propre", "REF004", datetime.now() - timedelta(days=3)),
        ]
        c.executemany("INSERT INTO historique (msisdn, type_transaction, montant, destinataire, reference, date_heure) VALUES (?,?,?,?,?,?)", demo_data)
    
    conn.commit()
    conn.close()

# ============ FONCTIONS UTILITAIRES ============
def get_random_name():
    return random.choice(NOMS_BENEFICIAIRES)

def generate_reference():
    return f"UMW{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(10,99)}"

def save_final_transaction(msisdn, transaction_id, operation, montant, destinataire, reference, payload, reponse, statut):
    """Sauvegarde UNIQUEMENT les transactions finales (confirmees ou annulees)"""
    conn = sqlite3.connect('umwampi.db')
    c = conn.cursor()
    c.execute('''INSERT INTO transactions 
                 (msisdn, transaction_id, operation, montant, destinataire, reference,
                  payload_cecadm, reponse_cecadm, statut)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (msisdn, transaction_id, operation, montant, destinataire, reference,
               json.dumps(payload) if payload else None,
               json.dumps(reponse) if reponse else None,
               statut))
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

# ============ ENDPOINT USSD ============
@app.route('/ussd/callback', methods=['POST'])
def ussd_callback():
    try:
        data = request.json
        transaction_id = data.get('transaction_id', '') # pyright: ignore
        msisdn = data.get('msisdn', '') # pyright: ignore
        user_input = data.get('ussd_request_msg', '').strip() # pyright: ignore
        
        # LOG: tout est loggué dans la console, rien en BD
        print(f"📱 [{transaction_id}] {msisdn} => '{user_input}'")
        
        # ============ INIT SESSION ============
        if transaction_id not in sessions:
            sessions[transaction_id] = {
                'step': 'init',
                'msisdn': msisdn,
                'data': {}
            }
            print(f"🆕 Nouvelle session: {transaction_id}")
        
        session = sessions[transaction_id]
        step = session.get('step', 'init')
        
        # ============ PREMIERE INTERACTION (peu importe le code) ============
        if step == 'init':
            # Premier appel = l'utilisateur vient de composer un code USSD
            # On accepte n'importe quel code, on affiche le menu
            session['step'] = 'main_menu'
            msg = """Bienvenue sur UMWAMPI
1. Depot
2. Retrait
3. Historique
4. Balance
5. Vente unites
6. Banque"""
            print(f"Menu principal affiche pour {msisdn}")
            return jsonify({"msg": msg, "request_type": "202"})
        
        # ============ RETOUR MENU ============
        if user_input == '0':
            session['step'] = 'main_menu'
            session['data'] = {}
            msg = """Bienvenue sur UMWAMPI
1. Depot
2. Retrait
3. Historique
4. Balance
5. Vente unites
6. Banque"""
            print(f"🔙 Retour menu: {msisdn}")
            return jsonify({"msg": msg, "request_type": "202"})
        
        # ============ MENU PRINCIPAL ============
        if step == 'main_menu':
            choix = user_input
            
            if choix == '1':  # DEPOT
                session['step'] = 'depot_montant'
                session['data'] = {'operation': 'depot'}
                msg = "Montant du depot\nEntrez le montant:"
                
            elif choix == '2':  # RETRAIT
                session['step'] = 'retrait_montant'
                session['data'] = {'operation': 'retrait'}
                msg = "Montant du retrait\nEntrez le montant:"
                
            elif choix == '3':  # HISTORIQUE
                return handle_historique(msisdn, transaction_id)
                
            elif choix == '4':  # BALANCE
                session['step'] = 'balance_pin'
                session['data'] = {'operation': 'balance'}
                msg = "Entrez votre PIN a 4 chiffres:"
                
            elif choix == '5':  # VENTE UNITES
                session['step'] = 'vente_menu'
                session['data'] = {'operation': 'vente_unites'}
                msg = """Vente unites
1. Acheter unites
2. Vendre unites
0. Menu principal"""
                
            elif choix == '6':  # BANQUE
                session['step'] = 'banque_menu'
                session['data'] = {'operation': 'banque'}
                msg = """Banque
1. UMWAMPI vers Banque
2. Banque vers UMWAMPI
0. Menu principal"""
                
            else:
                msg = """Option invalide
1. Depot
2. Retrait
3. Historique
4. Balance
5. Vente unites
6. Banque"""
            
            print(f"Etape: {session['step']} | Saisie: {user_input}")
            return jsonify({"msg": msg, "request_type": "202"})
        
        # ============ DEPOT ============
        elif step == 'depot_montant':
            if user_input.isdigit() and int(user_input) > 0:
                session['data']['montant'] = user_input
                session['step'] = 'depot_pin'
                msg = "Entrez votre PIN a 4 chiffres:"
            else:
                msg = "Montant invalide\nEntrez le montant:"
            print(f"Depot - Montant: {user_input}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'depot_pin':
            if len(user_input) == 4 and user_input.isdigit():
                session['data']['pin'] = user_input
                session['step'] = 'depot_confirm'
                ref = generate_reference()
                session['data']['reference'] = ref
                msg = f"""Confirmation depot
Montant: {session['data']['montant']} Fbu
Reference: {ref}
                
1. Confirmer
2. Annuler"""
            else:
                msg = "PIN invalide (4 chiffres)\nEntrez votre PIN:"
            print(f"Depot - PIN: ****")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'depot_confirm':
            montant = int(session['data']['montant'])
            ref = session['data']['reference']
            
            if user_input == '1':
                # SIMULATION CECADM
                payload_cecadm = {
                    "endpoint": "CECADM_API/deposit",
                    "phone": msisdn,
                    "amount": montant,
                    "reference": ref
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "message": "Depot effectue",
                    "transaction_id": ref,
                    "nouveau_solde": 50000 + montant
                }
                
                # Sauvegarde BD (finale seulement)
                save_final_transaction(msisdn, transaction_id, "depot", montant, 
                                      "Compte propre", ref, payload_cecadm, reponse_cecadm, "success")
                save_historique(msisdn, "depot", montant, "Compte propre", ref)
                
                print(f"Depot confirme: {montant} Fbu | Ref: {ref}")
                
                msg = f"""Depot effectue avec succes!
Montant: {montant} Fbu
Reference: {ref}
Nouveau solde: {reponse_cecadm['nouveau_solde']} Fbu
                
Merci d'utiliser UMWAMPI"""
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
            else:
                # Annulation - aussi sauvegardé en BD
                save_final_transaction(msisdn, transaction_id, "depot", montant,
                                      "Compte propre", ref, None, None, "annule")
                print(f"Depot annule: {montant} Fbu")
                
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
        
        # ============ RETRAIT ============
        elif step == 'retrait_montant':
            if user_input.isdigit() and int(user_input) > 0:
                session['data']['montant'] = user_input
                session['step'] = 'retrait_pin'
                msg = "Entrez votre PIN a 4 chiffres:"
            else:
                msg = "Montant invalide\nEntrez le montant:"
            print(f"Retrait - Montant: {user_input}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'retrait_pin':
            if len(user_input) == 4 and user_input.isdigit():
                session['data']['pin'] = user_input
                session['step'] = 'retrait_confirm'
                ref = generate_reference()
                session['data']['reference'] = ref
                msg = f"""Confirmation retrait
Montant: {session['data']['montant']} Fbu
Reference: {ref}
                
1. Confirmer
2. Annuler"""
            else:
                msg = "PIN invalide (4 chiffres)\nEntrez votre PIN:"
            print(f"Retrait - PIN: ****")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'retrait_confirm':
            montant = int(session['data']['montant'])
            ref = session['data']['reference']
            
            if user_input == '1':
                payload_cecadm = {
                    "endpoint": "CECADM_API/withdraw",
                    "phone": msisdn,
                    "amount": montant,
                    "reference": ref
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "message": "Retrait effectue",
                    "transaction_id": ref,
                    "nouveau_solde": 50000 - montant
                }
                
                save_final_transaction(msisdn, transaction_id, "retrait", montant,
                                      "Compte propre", ref, payload_cecadm, reponse_cecadm, "success")
                save_historique(msisdn, "retrait", montant, "Compte propre", ref)
                
                print(f"Retrait confirme: {montant} Fbu | Ref: {ref}")
                
                msg = f"""Retrait effectue avec succes!
Montant: {montant} Fbu
Reference: {ref}
Nouveau solde: {reponse_cecadm['nouveau_solde']} Fbu
                
Merci d'utiliser UMWAMPI"""
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
            else:
                save_final_transaction(msisdn, transaction_id, "retrait", montant,
                                      "Compte propre", ref, None, None, "annule")
                print(f"Retrait annule: {montant} Fbu")
                
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
        
        # ============ BALANCE ============
        elif step == 'balance_pin':
            if len(user_input) == 4 and user_input.isdigit():
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
                
                # Balance n'est pas une transaction financiere, pas de sauvegarde BD
                print(f"Balance affichee: {reponse_cecadm['balance']} Fbu")
                
                msg = f"""Votre solde UMWAMPI
Solde: {reponse_cecadm['balance']} Fbu
                
0. Menu principal"""
                session['step'] = 'main_menu'
                return jsonify({"msg": msg, "request_type": "202"})
            else:
                msg = "PIN invalide (4 chiffres)\nEntrez votre PIN:"
                return jsonify({"msg": msg, "request_type": "202"})
        
        # ============ VENTE UNITES ============
        elif step == 'vente_menu':
            if user_input == '1':
                session['step'] = 'achat_unites_montant'
                session['data']['type_vente'] = 'achat'
                msg = "Achat unites\nEntrez le montant (min 1000 Fbu):"
            elif user_input == '2':
                session['step'] = 'vente_unites_quantite'
                session['data']['type_vente'] = 'vente'
                msg = "Vente unites\nEntrez le nombre d'unites:"
            else:
                msg = "Option invalide"
            print(f"Vente unites - Type: {session['data'].get('type_vente')}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step in ['achat_unites_montant', 'vente_unites_quantite']:
            session['data']['montant'] = user_input
            session['step'] = 'unites_benef'
            msg = "Entrez le numero du beneficiaire:"
            print(f"Unites - Montant/Quantite: {user_input}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'unites_benef':
            session['data']['beneficiaire'] = user_input
            session['step'] = 'unites_pin'
            msg = "Entrez votre PIN a 4 chiffres:"
            print(f"Unites - Beneficiaire: {user_input}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'unites_pin':
            if len(user_input) == 4 and user_input.isdigit():
                session['data']['pin'] = user_input
                session['step'] = 'unites_confirm'
                nom_random = get_random_name()
                session['data']['nom'] = nom_random
                type_vente = session['data'].get('type_vente', 'achat')
                
                if type_vente == 'achat':
                    msg = f"""Confirmer achat unites
Montant: {session['data']['montant']} Fbu
Beneficiaire: {session['data']['beneficiaire']}
Nom: {nom_random}
                
1. Confirmer
2. Annuler"""
                else:
                    msg = f"""Confirmer vente unites
Unites: {session['data']['montant']}
Beneficiaire: {session['data']['beneficiaire']}
Nom: {nom_random}
                
1. Confirmer
2. Annuler"""
                print(f"Unites - Confirmation | Nom: {nom_random}")
                return jsonify({"msg": msg, "request_type": "202"})
            else:
                msg = "PIN invalide (4 chiffres)\nEntrez votre PIN:"
                return jsonify({"msg": msg, "request_type": "202"})
                
        elif step == 'unites_confirm':
            nom_random = session['data']['nom']
            type_vente = session['data']['type_vente']
            type_trans = "achat_unites" if type_vente == 'achat' else "vente_unites"
            montant = int(session['data']['montant'])
            ref = generate_reference()
            
            if user_input == '1':
                payload_cecadm = {
                    "endpoint": "CECADM_API/units",
                    "phone": msisdn,
                    "type": type_trans,
                    "amount": montant,
                    "beneficiaire": session['data']['beneficiaire'],
                    "reference": ref
                }
                reponse_cecadm = {
                    "status": "success",
                    "code": "200",
                    "message": "Transaction unites reussie",
                    "transaction_id": ref
                }
                
                save_final_transaction(msisdn, transaction_id, type_trans, montant,
                                      nom_random, ref, payload_cecadm, reponse_cecadm, "success")
                save_historique(msisdn, type_trans, montant, nom_random, ref)
                
                print(f"Unites confirme: {montant} | {nom_random} | Ref: {ref}")
                
                msg = f"""Transaction reussie!
Type: {type_trans}
Montant: {montant} Fbu
Beneficiaire: {nom_random}
Ref: {ref}
                
Merci d'utiliser UMWAMPI"""
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
            else:
                save_final_transaction(msisdn, transaction_id, type_trans, montant,
                                      nom_random, ref, None, None, "annule")
                print(f"Unites annule: {montant}")
                
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
        
        # ============ BANQUE ============
        elif step == 'banque_menu':
            if user_input == '1':
                session['step'] = 'banque_montant'
                session['data']['type_banque'] = 'umwampi_to_bank'
                msg = "UMWAMPI vers Banque\nEntrez le montant:"
            elif user_input == '2':
                session['step'] = 'banque_montant'
                session['data']['type_banque'] = 'bank_to_umwampi'
                msg = "Banque vers UMWAMPI\nEntrez le montant:"
            else:
                msg = "Option invalide"
            print(f"Banque - Type: {session['data'].get('type_banque')}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'banque_montant':
            session['data']['montant'] = user_input
            session['step'] = 'banque_compte'
            msg = "Entrez le numero de compte bancaire:"
            print(f"Banque - Montant: {user_input}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'banque_compte':
            session['data']['compte'] = user_input
            session['step'] = 'banque_pin'
            msg = "Entrez votre PIN a 4 chiffres:"
            print(f"Banque - Compte: {user_input}")
            return jsonify({"msg": msg, "request_type": "202"})
            
        elif step == 'banque_pin':
            if len(user_input) == 4 and user_input.isdigit():
                session['data']['pin'] = user_input
                session['step'] = 'banque_confirm'
                nom_random = get_random_name()
                session['data']['nom'] = nom_random
                
                msg = f"""Voulez-vous vraiment envoyer
{session['data']['montant']} Fbu
vers Compte {session['data']['compte']}
Nom: {nom_random}
                
1. Confirmer
2. Annuler"""
                print(f"Banque - Confirmation | Nom: {nom_random}")
                return jsonify({"msg": msg, "request_type": "202"})
            else:
                msg = "PIN invalide (4 chiffres)\nEntrez votre PIN:"
                return jsonify({"msg": msg, "request_type": "202"})
                
        elif step == 'banque_confirm':
            nom_random = session['data']['nom']
            montant = int(session['data']['montant'])
            type_trans = session['data']['type_banque']
            ref = generate_reference()
            
            if user_input == '1':
                payload_cecadm = {
                    "endpoint": "CECADM_API/bank_transfer",
                    "phone": msisdn,
                    "type": type_trans,
                    "amount": montant,
                    "compte": session['data']['compte'],
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
                
                save_final_transaction(msisdn, transaction_id, type_trans, montant,
                                      nom_random, ref, payload_cecadm, reponse_cecadm, "success")
                save_historique(msisdn, type_trans, montant, nom_random, ref)
                
                print(f"Banque confirme: {montant} Fbu | {nom_random} | Ref: {ref}")
                
                msg = f"""Transfert bancaire reussi!
Montant: {montant} Fbu
Beneficiaire: {nom_random}
Compte: {session['data']['compte']}
Ref: {ref}
                
Merci d'utiliser UMWAMPI"""
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
            else:
                save_final_transaction(msisdn, transaction_id, type_trans, montant,
                                      nom_random, ref, None, None, "annule")
                print(f"Banque annule: {montant} Fbu")
                
                msg = "Transaction annulee.\nMerci d'utiliser UMWAMPI"
                del sessions[transaction_id]
                return jsonify({"msg": msg, "request_type": "203"})
        
        # ============ DEFAUT ============
        else:
            print(f"Etape inconnue: {step} | Input: {user_input}")
            msg = "Session expiree. Veuillez recomposer."
            if transaction_id in sessions:
                del sessions[transaction_id]
            return jsonify({"msg": msg, "request_type": "205"})
            
    except Exception as e:
        print(f"ERREUR: {e}")
        return jsonify({"msg": "Service momentanement indisponible", "request_type": "205"})

def handle_historique(msisdn, transaction_id):
    """Affiche l'historique (pas de sauvegarde BD, juste affichage)"""
    try:
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
                msg += f"{type_trans}: {montant} Fbu\n"
            msg += "\n0. Menu principal"
        else:
            msg = "Aucune transaction recente\n0. Menu principal"
        
        print(f"Historique affiche pour {msisdn}")
        sessions[transaction_id]['step'] = 'main_menu'
        
        return jsonify({"msg": msg, "request_type": "202"})
    except Exception as e:
        print(f"Erreur historique: {e}")
        return jsonify({"msg": "Erreur historique", "request_type": "205"})

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
    
    # Même HTML que avant, juste adapté aux nouveaux champs
    html = """<!DOCTYPE html>
<html>
<head>
    <title>UMWAMPI - Dashboard CECADM</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="5">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; padding: 20px; background: #f0f2f5; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: #BCF; color: darkblue; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .header h1 { font-size: 24px; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-card h3 { color: #666; font-size: 14px; }
        .stat-card .value { font-size: 28px; font-weight: bold; }
        .success .value { color: #27ae60; }
        .section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { background: #f8f9fa; padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; }
        td { padding: 10px; border-bottom: 1px solid #f0f0f0; }
        tr:hover { background: #f8f9ff; }
        .badge { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
        .badge-depot { background: #d5f5e3; color: #27ae60; }
        .badge-retrait { background: #fadbd8; color: #e74c3c; }
        .badge-banque { background: #d5dbdb; color: #2c3e50; }
        pre { background: #f8f9fa; padding: 8px; border-radius: 4px; font-size: 11px; }
        .status-success { color: #27ae60; font-weight: bold; }
        .status-annule { color: #e74c3c; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 UMWAMPI - Transactions finales</h1>
            <p>Dashboard temps reel - Integration CECADM via Akanyenyeri 2.0</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Total Transactions</h3>
                <div class="value">""" + str(total) + """</div>
            </div>
            <div class="stat-card success">
                <h3>Reussies</h3>
                <div class="value">""" + str(reussies) + """</div>
            </div>
            <div class="stat-card">
                <h3>Annulees</h3>
                <div class="value" style="color: #e74c3c;">""" + str(total - reussies) + """</div>
            </div>
            <div class="stat-card">
                <h3>Derniere</h3>
                <div class="value" style="font-size: 14px;">""" + (transactions[0]['timestamp'][:19] if transactions else '-') + """</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📋 Transactions Finales (Confirmees ou Annulees)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Tel</th>
                        <th>Operation</th>
                        <th>Montant</th>
                        <th>Destinataire</th>
                        <th>Reference</th>
                        <th>Payload CECADM</th>
                        <th>Reponse CECADM</th>
                        <th>Statut</th>
                    </tr>
                </thead>
                <tbody>"""
    
    for t in transactions:
        badge_class = {
            'depot': 'badge-depot', 'retrait': 'badge-retrait',
            'achat_unites': 'badge-depot', 'vente_unites': 'badge-retrait',
            'umwampi_to_bank': 'badge-banque', 'bank_to_umwampi': 'badge-banque'
        }.get(t['operation'], '')
        
        html += f"""
                    <tr>
                        <td>{t['timestamp'][:19] if t['timestamp'] else ''}</td>
                        <td>{t['msisdn']}</td>
                        <td><span class="badge {badge_class}">{t['operation']}</span></td>
                        <td>{t['montant']} Fbu</td>
                        <td>{t['destinataire']}</td>
                        <td style="font-size:11px;">{t['reference']}</td>
                        <td><pre>{t['payload_cecadm'][:80] if t['payload_cecadm'] else '-'}</pre></td>
                        <td><pre>{t['reponse_cecadm'][:80] if t['reponse_cecadm'] else '-'}</pre></td>
                        <td class="status-{t['statut']}">{'✅' if t['statut'] == 'success' else '❌'} {t['statut']}</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""
    
    return html

# ============ INIT ============
init_db()
print("=" * 60)
print("UMWAMPI pret!")
print("USSD: http://localhost:5000/ussd/callback")
print("Dashboard: http://localhost:5000/dashboard")
print("Logs en console uniquement")
print("BD: Transactions finales uniquement")
print("=" * 60)