# Punto de entrada para servidores WSGI de producción (gunicorn, ver
# Procfile). Sigue el mismo patrón de application factory que usa
# app/__init__.py: gunicorn importa este módulo y busca el objeto `app`
# (gunicorn wsgi:app), pero a diferencia de run.py NO llama a app.run() ni
# fuerza modo debug -- eso lo maneja el propio servidor WSGI.

from app import create_app

app = create_app()
