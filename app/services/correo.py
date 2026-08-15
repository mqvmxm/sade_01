# Servicio de envío de correo para el flujo de "olvidé mi contraseña" (RF-1).
# Con EMAIL_SIMULATE=True (default, ver config.py) no se conecta a ningún
# servidor SMTP real: solo se imprime el envío simulado, exactamente la
# misma filosofía que app/services/notificaciones.py usa con Twilio, para
# poder desarrollar y probar el flujo completo sin credenciales de correo.
# La simulación reemplaza únicamente la conexión SMTP, nunca la validación
# del destinatario: un correo vacío o con formato inválido debe fallar igual
# en modo simulado que en modo real.

import re
import smtplib
from email.message import EmailMessage

from flask import current_app

_PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# es para validar el formato del correo, no para verificar que exista
def _email_valido(correo): 
    return bool(correo) and bool(_PATRON_EMAIL.match(correo))

# es para decidir si se conecta a un servidor SMTP real o solo se imprime el envío simulado
def _simulacion_activa(): 
    return current_app.config.get("EMAIL_SIMULATE", True)


def enviar_correo(destinatario, asunto, cuerpo):
    """Envía un correo (usado por RF-1: recuperación de contraseña).

    Devuelve (exito: bool, error: str | None), igual que
    enviar_whatsapp()/enviar_sms() en notificaciones.py. El destinatario se
    valida ANTES de decidir si simular o conectar de verdad: si el correo no
    tiene formato válido, la función falla con "correo inválido o no
    configurado" sin importar el valor de EMAIL_SIMULATE.
    """
    # es para validar el formato del correo, no para verificar que exista
    if not _email_valido(destinatario): 
        return False, "correo inválido o no configurado"
    
# es para decidir si se conecta a un servidor SMTP real o solo se imprime el envío simulado
    if _simulacion_activa(): 
        print(
            "[SIMULADO][Correo] "
            f"Para: {destinatario} | Asunto: {asunto}\n{cuerpo}"
        )
        return True, None

# manda un mensaje de correo con asunto, remitente, destinatario y cuerpo
    mensaje = EmailMessage() 
    mensaje["Subject"] = asunto
    mensaje["From"] = current_app.config.get("EMAIL_FROM", "")
    mensaje["To"] = destinatario
    mensaje.set_content(cuerpo)

# es para decidir si se conecta a un servidor SMTP real o solo se imprime el envío simulado
    host = current_app.config.get("EMAIL_HOST", "") 
    puerto = int(current_app.config.get("EMAIL_PORT", 587))
    usuario_smtp = current_app.config.get("EMAIL_USER", "")
    password_smtp = current_app.config.get("EMAIL_PASSWORD", "")
    
# esto maneja errores de conexión y envío, devolviendo (False, str(error)) en caso de fallo
    try: 
        with smtplib.SMTP(host, puerto, timeout=10) as servidor:
            servidor.starttls()
            servidor.login(usuario_smtp, password_smtp)
            servidor.send_message(mensaje)
        return True, None
    except smtplib.SMTPException as error:
        return False, str(error)
    except OSError as error:
        # Errores de conexión (host inalcanzable, timeout, DNS) no heredan de
        # SMTPException; se capturan aparte para no dejar pasar una excepción
        # genérica sin manejar, igual que notificaciones.py hace con
        # TwilioRestException.
        return False, str(error)
