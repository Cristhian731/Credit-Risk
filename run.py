"""Entry point: starts the development server with `python run.py`."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
