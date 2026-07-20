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
