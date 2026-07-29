# Blueprint del rol conductor: check-in de viajes y confirmación de llegada
# (RF-3: Monitoreo de rutas). El botón de pánico (RF-4) vive en el blueprint
# 'emergencia'.

from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.alerta import Alerta
from app.models.vehiculo import Vehiculo
from app.models.viaje import Viaje

conductor = Blueprint("conductor", __name__)


def conductor_required(view_func):
    """Exige sesión iniciada y rol conductor (RF-1.3), igual que hacía dashboard()."""

    @wraps(view_func)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.es_conductor():
            flash("No tienes permiso para acceder a esa sección", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper


@conductor.route("/dashboard")
@conductor_required
def dashboard():
    """Muestra el viaje activo del conductor, o el formulario de check-in (RF-3.1/3.2).

    Si la licencia está vencida, el template debe bloquear el formulario de
    check-in (RF-6.2) usando conductor.licencia_vigente().
    """
    perfil = current_user.conductor
    if perfil is None:
        flash("Tu cuenta no tiene un perfil de conductor asociado.", "error")
        return redirect(url_for("auth.login"))

    viaje_activo = Viaje.query.filter(
        Viaje.id_conductor == perfil.id_conductor,
        Viaje.estado.in_(["activo", "alerta", "emergencia"]),
    ).first()

    return render_template(
        "conductor/dashboard.html", conductor=perfil, viaje_activo=viaje_activo
    )


@conductor.route("/historial")
@conductor_required
def historial():
    """Historial de rutas ya cerradas y eventos propios del conductor
    (responsabilidad del rol conductor: "consultar su propio historial de
    rutas y eventos registrados").

    SEGURIDAD: filtra SIEMPRE por current_user.conductor.id_conductor. No se
    acepta ningún id de conductor por query param, form ni ninguna otra
    vía — un conductor jamás debe poder ver los viajes de otro.
    """
    perfil = current_user.conductor
    if perfil is None:
        flash("Tu cuenta no tiene un perfil de conductor asociado.", "error")
        return redirect(url_for("auth.login"))

    viajes = (
        Viaje.query.filter(
            Viaje.id_conductor == perfil.id_conductor,
            Viaje.estado.in_(["completado", "cerrado_admin"]),
        )
        .order_by(Viaje.hora_llegada.desc())
        .all()
    )

    alertas_por_viaje = {}
    if viajes:
        ids_viajes = [viaje.id_viaje for viaje in viajes]
        for alerta in Alerta.query.filter(Alerta.id_viaje.in_(ids_viajes)).all():
            alertas_por_viaje.setdefault(alerta.id_viaje, []).append(alerta)

    return render_template(
        "conductor/historial.html",
        viajes=viajes,
        alertas_por_viaje=alertas_por_viaje,
    )


@conductor.route("/viajes/nuevo", methods=["POST"])
@conductor_required
def viajes_nuevo():
    """Registra el check-in de un viaje para el conductor autenticado (RF-3.2).

    Simplificación temporal: el conductor todavía no elige vehículo
    manualmente en la UI, así que se asigna el primer Vehiculo con estado
    'disponible' que se encuentre. Cuando exista selección real de vehículo,
    esta asignación automática debe reemplazarse.
    """
    perfil = current_user.conductor
    if perfil is None:
        flash("Tu cuenta no tiene un perfil de conductor asociado.", "error")
        return redirect(url_for("conductor.dashboard"))

    # Nunca confiar solo en el frontend: se revalida la licencia (RF-6.2).
    if not perfil.licencia_vigente():
        flash("No puedes iniciar un viaje: tu licencia está vencida.", "error")
        return redirect(url_for("conductor.dashboard"))

    # Un conductor no puede tener dos viajes sin cerrar a la vez: bloquea el
    # check-in si ya tiene uno en 'activo', 'alerta' o 'emergencia' (evita
    # duplicados como el que dejó un viaje viejo sin confirmar llegada).
    viaje_sin_cerrar = Viaje.query.filter(
        Viaje.id_conductor == perfil.id_conductor,
        Viaje.estado.in_(["activo", "alerta", "emergencia"]),
    ).first()
    if viaje_sin_cerrar is not None:
        flash("Ya tienes un viaje sin cerrar. Confirma la llegada antes de iniciar uno nuevo.", "error")
        return redirect(url_for("conductor.dashboard"))

    origen = request.form.get("origen", "").strip()
    destino = request.form.get("destino", "").strip()
    if not origen or not destino:
        flash("Debes indicar origen y destino.", "error")
        return redirect(url_for("conductor.dashboard"))

    eta_texto = request.form.get("eta", "")
    try:
        eta = datetime.strptime(eta_texto, "%Y-%m-%dT%H:%M")
    except ValueError:
        flash("La hora estimada de llegada (ETA) no es válida.", "error")
        return redirect(url_for("conductor.dashboard"))

    vehiculo = Vehiculo.query.filter_by(estado="disponible").first()
    if vehiculo is None:
        flash("No hay vehículos disponibles en este momento.", "error")
        return redirect(url_for("conductor.dashboard"))

    # RF-3.6 (regla de integridad): un vehículo no puede tener dos viajes
    # 'activo' a la vez. En teoría ya se descartó al filtrar por 'disponible',
    # pero se revalida explícitamente antes del INSERT; la BD también lo
    # protege con un índice único parcial (idx_viaje_activo_unico) como
    # última defensa ante condiciones de carrera (ver excepto IntegrityError).
    viaje_activo_existente = Viaje.query.filter_by(
        id_vehiculo=vehiculo.id_vehiculo, estado="activo"
    ).first()
    if viaje_activo_existente is not None:
        flash("El vehículo asignado ya tiene un viaje activo.", "error")
        return redirect(url_for("conductor.dashboard"))

    viaje = Viaje(
        id_conductor=perfil.id_conductor,
        id_vehiculo=vehiculo.id_vehiculo,
        origen=origen,
        destino=destino,
        hora_salida=datetime.now(),
        eta=eta,
        estado="activo",
    )
    vehiculo.estado = "en_ruta"

    try:
        db.session.add(viaje)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("El vehículo asignado ya tiene un viaje activo.", "error")
        return redirect(url_for("conductor.dashboard"))

    flash(f"Viaje iniciado correctamente hacia '{destino}'.", "success")
    return redirect(url_for("conductor.dashboard"))


@conductor.route("/viajes/<int:id_viaje>/confirmar-llegada", methods=["POST"])
@conductor_required
def viajes_confirmar_llegada(id_viaje):
    """Cierra un viaje 'activo', 'alerta' o 'emergencia' al confirmar la llegada del conductor (RF-3.3).

    Cerrar un viaje en 'emergencia' no toca la Alerta tipo='panico' asociada:
    eso lo marca atendida el administrador manualmente desde su panel.
    """
    perfil = current_user.conductor
    viaje = Viaje.query.get_or_404(id_viaje)

    if perfil is None or viaje.id_conductor != perfil.id_conductor:
        flash("No tienes permiso para modificar ese viaje.", "error")
        return redirect(url_for("conductor.dashboard"))

    if viaje.estado not in ("activo", "alerta", "emergencia"):
        flash("Ese viaje ya no está en curso.", "error")
        return redirect(url_for("conductor.dashboard"))

    viaje.hora_llegada = datetime.now()
    viaje.estado = "completado"
    viaje.vehiculo.estado = "disponible"
    db.session.commit()

    flash("Llegada confirmada. Viaje completado.", "success")
    return redirect(url_for("conductor.dashboard"))
