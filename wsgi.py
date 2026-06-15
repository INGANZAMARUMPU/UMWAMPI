# wsgi.py - Point d'entrée WSGI pour déploiement
from app import app

# Configuration pour la production
app.config.update(
    DEBUG=False,
    TESTING=False
)

if __name__ == "__main__":
    # Pour test local seulement
    app.run(host='0.0.0.0', port=5000, debug=True)