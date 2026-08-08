# Carga la configuración de la aplicación desde variables de entorno (.env):
# credenciales de base de datos, clave de sesión de Flask y credenciales de
# Twilio usadas por el módulo de emergencias (RF-4).

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Contenedor de configuración de Flask poblado desde variables de entorno.

    Cada valor tiene un default de desarrollo para que la app arranque sin
    un .env presente, pero en producción debe sobreescribirse vía entorno.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    # Distingue desarrollo de producción de forma explícita (en vez de
    # depender implícitamente de qué script se ejecuta), para que Flask
    # jamás quede en modo debug al desplegarse en Render -- ese modo expone
    # el debugger interactivo de Werkzeug, que permite ejecutar código
    # arbitrario en el servidor con solo llegar a una página de error.
    # Default deliberado: "production" (DEBUG=False), así que si esta
    # variable se omite por descuido en el entorno de Render, la app arranca
    # segura de todas formas. python run.py (uso exclusivamente local) NO
    # depende de este valor: sigue pasando debug=True de forma explícita e
    # independiente, así que el flujo de desarrollo local no cambia.
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = FLASK_ENV != "production"

    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "sade_db")

    # Render (y otros proveedores con herencia de Heroku) entregan la
    # conexión de BD como una sola variable DATABASE_URL en vez de piezas
    # sueltas; se usa si está presente, y si no se arma con DB_USER/
    # DB_PASSWORD/etc. (comportamiento local con .env, sin cambios). Algunos
    # proveedores todavía entregan el esquema viejo "postgres://" -- SQLAlchemy
    # 1.4+ solo reconoce "postgresql://" y lanza NoSuchModuleError con el
    # otro-- así que se normaliza aquí si hace falta.
    _database_url = os.environ.get("DATABASE_URL")
    if _database_url and _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _database_url or (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    TWILIO_SMS_FROM = os.environ.get("TWILIO_SMS_FROM", "")

    # Número del administrador que recibe copia de cada notificación de
    # emergencia (RF-4.3/4.4). No vive en la tabla usuarios: el esquema de
    # BD ya fue aprobado y cerrado, así que este dato queda solo en config.
    ADMIN_PHONE_NUMBER = os.environ.get("ADMIN_PHONE_NUMBER", "")

    # Con SIMULATE_TWILIO=True (default), app/services/notificaciones.py no
    # llama a la API real de Twilio: solo simula el envío por consola. Poner
    # en False para usar credenciales reales.
    SIMULATE_TWILIO = os.environ.get("SIMULATE_TWILIO", "True").strip().lower() in (
        "true",
        "1",
        "yes",
    )

    # Credenciales de correo para el flujo de "olvidé mi contraseña" (RF-1).
    # Con EMAIL_SIMULATE=True (default), app/services/correo.py no se conecta
    # a ningún servidor SMTP real: solo imprime el envío simulado por
    # consola, igual que SIMULATE_TWILIO hace con las notificaciones.
    EMAIL_SIMULATE = os.environ.get("EMAIL_SIMULATE", "True").strip().lower() in (
        "true",
        "1",
        "yes",
    )
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
    EMAIL_PORT = os.environ.get("EMAIL_PORT", "587")
    EMAIL_USER = os.environ.get("EMAIL_USER", "")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
