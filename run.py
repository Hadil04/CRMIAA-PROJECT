"""
CRMIAA - Application entry point.

Run the development server with:
    python run.py

For production, use a WSGI server (e.g. gunicorn / waitress) pointing at the
`app` object exposed below.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Debug mode is convenient for development only. Turn it off in production.
    app.run(host="127.0.0.1", port=5000, debug=True)
