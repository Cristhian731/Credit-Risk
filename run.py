"""Entry point.

Development: ``python run.py``
Production:  ``FLASK_CONFIG=production SECRET_KEY=... gunicorn run:app``
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
