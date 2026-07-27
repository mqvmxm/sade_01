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

    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "sade_db")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
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
