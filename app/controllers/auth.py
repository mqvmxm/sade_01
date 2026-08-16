# Blueprint de autenticación: login, logout, redirección a la raíz y
# recuperación de contraseña por correo (RF-1: Autenticación y accesos).

# Realiza la serialización y deserialización de datos de manera segura, con firma y expiración de tokens
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer 

# Genera URLs para rutas de la aplicación y redirige a ellas
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for 
# Sirve para manejar la sesión de usuario y proteger rutas que requieren autenticación
from flask_login import current_user, login_required, login_user, logout_user 

# Importa la instancia de la base de datos SQLAlchemy para interactuar con la base de datos
from app import db 
from app.models.bitacora import Bitacora
from app.models.usuario import Usuario
from app.services.correo import enviar_correo

auth = Blueprint("auth", __name__)

# Minutos que un enlace de restablecimiento de contraseña sigue siendo válido.
RESTABLECER_MAX_EDAD_SEGUNDOS = 30 * 60


def _serializer_restablecer():
    """Serializador de tokens firmados para "olvidé mi contraseña" (RF-1).

    Usa un salt distinto al de las cookies de sesión de Flask para que un
    token de este flujo nunca pueda confundirse con otro tipo de firma de la
    app, aunque ambos usen la misma SECRET_KEY. No se guarda nada en BD: el
    token en sí (id_usuario + firma + fecha de emisión) es toda la prueba
    necesaria, y expira solo por el paso del tiempo (max_age en .loads()).
    """
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="restablecer-contrasena")


def _dashboard_redirect(usuario):
    """Redirige al dashboard correspondiente según el rol del usuario (RF-1.3)."""
    if usuario.es_admin():
        return redirect(url_for("admin.dashboard"))
    if usuario.es_conductor():
        return redirect(url_for("conductor.dashboard"))
    if usuario.es_mecanico():
        return redirect(url_for("mecanico.vehiculos_lista"))
    return redirect(url_for("auth.login"))


@auth.route("/")
def index():
    """Punto de entrada: manda a login o al dashboard según haya sesión activa."""
    if current_user.is_authenticated:
        return _dashboard_redirect(current_user)
    return redirect(url_for("auth.login"))


@auth.route("/login", methods=["GET", "POST"])
def login():
    """Valida credenciales e inicia sesión (RF-1.2), o muestra el formulario de login."""
    if request.method == "POST":
        identificador = request.form.get("nombre_usuario")
        contrasena = request.form.get("contrasena")

        usuario = Usuario.query.filter(
            (Usuario.email == identificador) | (Usuario.nombre_usuario == identificador)
        ).first()

        if usuario is None or not usuario.check_password(contrasena):
            flash("Usuario o contraseña incorrectos", "error")
            return render_template("auth/login.html")

        # login_user() devuelve False sin iniciar sesión si Usuario.is_active
        # es False (cuenta desactivada, ver admin.cuentas_cambiar_estado):
        # sin este chequeo, el flujo seguiría a _dashboard_redirect() como si
        # hubiera entrado, y el usuario recién ahí (en el dashboard) se
        # toparía con el redirect a login de @login_required, sin ningún
        # mensaje que explique por qué.
        if not login_user(usuario):
            flash("Esta cuenta está desactivada. Contacta a un administrador.", "error")
            return render_template("auth/login.html")

        return _dashboard_redirect(usuario)

    return render_template("auth/login.html")


@auth.route("/logout")
@login_required
def logout():
    """Cierra la sesión del usuario actual (RF-1.5)."""
    logout_user()
    return redirect(url_for("auth.login"))


@auth.route("/olvide-contrasena", methods=["GET", "POST"])
def olvide_contrasena():
    """Solicita el restablecimiento de contraseña por correo o nombre de usuario (RF-1).

    Muestra siempre el mismo mensaje genérico de éxito, exista o no la
    cuenta, y tenga o no correo registrado: revelar la diferencia permitiría
    a un atacante enumerar qué usuarios/correos existen en el sistema, así
    que la respuesta visible nunca depende del resultado real de la
    búsqueda.
    """
    if request.method == "POST":
        identificador = request.form.get("identificador", "").strip()

        usuario = None
        if identificador:
            usuario = Usuario.query.filter(
                (Usuario.email == identificador) | (Usuario.nombre_usuario == identificador)
            ).first()

        if usuario is not None:
            if usuario.email:
                token = _serializer_restablecer().dumps(usuario.id_usuario)
                enlace = url_for("auth.restablecer_contrasena", token=token, _external=True)
                cuerpo = (
                    f"Hola {usuario.nombre},\n\n"
                    "Recibimos una solicitud para restablecer tu contraseña en S.A.D.E.\n"
                    "Si fuiste tú, entra al siguiente enlace (válido por 30 minutos):\n"
                    f"{enlace}\n\n"
                    "Si tú no solicitaste esto, puedes ignorar este correo."
                )
                exito, error = enviar_correo(
                    usuario.email, "Restablecer tu contraseña — S.A.D.E.", cuerpo
                )

                if not exito:
                    print(
                        f"[olvide_contrasena] Error al enviar correo a "
                        f"{usuario.email}: {error}"
                    )

                resultado = (
                    "correo enviado"
                    if exito
                    else f"correo fallido ({error})" if error else "correo fallido"
                )
                descripcion = (
                    f"Solicitud de restablecimiento de contraseña para la cuenta "
                    f"'{usuario.nombre_usuario}': {resultado}."
                )
            else:
                descripcion = (
                    f"Solicitud de restablecimiento de contraseña para la cuenta "
                    f"'{usuario.nombre_usuario}': sin correo registrado, no se envió correo."
                )

            bitacora = Bitacora(
                id_usuario=usuario.id_usuario,
                accion="solicitud_restablecer_contrasena",
                descripcion=descripcion,
                tabla_afectada="usuarios",
                registro_id=usuario.id_usuario,
            )
            db.session.add(bitacora)
            db.session.commit()

        return redirect(url_for("auth.solicitud_enviada"))

    return render_template("auth/olvide_contrasena.html")


@auth.route("/solicitud-enviada")
def solicitud_enviada():
    """Pantalla de confirmación tras solicitar el restablecimiento (RF-1).

    Contenido siempre estático y genérico: no depende de si la cuenta
    existía ni de si se envió correo de verdad, por la misma razón de
    anti-enumeración que ya aplica en olvide_contrasena().
    """
    return render_template("auth/olvide_contrasena_enviado.html")


@auth.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer_contrasena(token):
    """Valida el token de restablecimiento y actualiza la contraseña (RF-1)."""
    try:
        id_usuario = _serializer_restablecer().loads(
            token, max_age=RESTABLECER_MAX_EDAD_SEGUNDOS
        )
    except SignatureExpired:
        flash(
            "El enlace para restablecer tu contraseña ya expiró. Solicita uno nuevo.",
            "error",
        )
        return redirect(url_for("auth.olvide_contrasena"))
    except BadSignature:
        flash(
            "El enlace para restablecer tu contraseña no es válido. Solicita uno nuevo.",
            "error",
        )
        return redirect(url_for("auth.olvide_contrasena"))

    usuario = Usuario.query.get(id_usuario)
    if usuario is None:
        flash(
            "El enlace para restablecer tu contraseña no es válido. Solicita uno nuevo.",
            "error",
        )
        return redirect(url_for("auth.olvide_contrasena"))

    if request.method == "POST":
        nueva_contrasena = request.form.get("nueva_contrasena", "")
        confirmar_contrasena = request.form.get("confirmar_contrasena", "")

        if len(nueva_contrasena) < 8:
            flash("La nueva contraseña debe tener al menos 8 caracteres.", "error")
            return render_template("auth/restablecer_contrasena.html", token=token)

        if nueva_contrasena != confirmar_contrasena:
            flash("Las contraseñas no coinciden.", "error")
            return render_template("auth/restablecer_contrasena.html", token=token)

        usuario.set_password(nueva_contrasena)

        bitacora = Bitacora(
            id_usuario=usuario.id_usuario,
            accion="contrasena_restablecida",
            descripcion=(
                f"Contraseña restablecida vía enlace de recuperación para la cuenta "
                f"'{usuario.nombre_usuario}'."
            ),
            tabla_afectada="usuarios",
            registro_id=usuario.id_usuario,
        )
        db.session.add(bitacora)
        db.session.commit()

        flash("Tu contraseña se actualizó correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/restablecer_contrasena.html", token=token)
