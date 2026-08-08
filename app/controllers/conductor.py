# Blueprint del rol conductor: inicio de rutas programadas por el admin y
# confirmación de llegada (RF-3: Monitoreo de rutas). El conductor ya no
# arma su propio check-in -eso lo hace el admin al programar la ruta, ver
# admin.viajes_programar-, solo inicia con un clic la ruta que se le asignó.
# El botón de pánico (RF-4) vive en el blueprint 'emergencia'.

from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.alerta import Alerta
from app.models.bitacora import Bitacora
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
    """Muestra el viaje activo del conductor, o sus rutas programadas
    pendientes de iniciar (RF-3.1/3.2).

    Si la licencia está vencida, el template debe bloquear el inicio de
    rutas (RF-6.2) usando conductor.licencia_vigente() -- igual criterio que
    antes tenía el check-in.
    """
    perfil = current_user.conductor
    if perfil is None:
        flash("Tu cuenta no tiene un perfil de conductor asociado.", "error")
        return redirect(url_for("auth.login"))

    viaje_activo = Viaje.query.filter(
        Viaje.id_conductor == perfil.id_conductor,
        Viaje.estado.in_(["activo", "alerta", "emergencia"]),
    ).first()

    rutas_programadas = []
    if viaje_activo is None:
        rutas_programadas = (
            Viaje.query.filter_by(id_conductor=perfil.id_conductor, estado="programado")
            .order_by(Viaje.eta)
            .all()
        )

    return render_template(
        "conductor/dashboard.html",
        conductor=perfil,
        viaje_activo=viaje_activo,
        rutas_programadas=rutas_programadas,
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


@conductor.route("/viajes/<int:id_viaje>/iniciar", methods=["POST"])
@conductor_required
def viajes_iniciar(id_viaje):
    """Inicia una ruta programada por el admin (RF-3.2): el conductor ya no
    arma su propio check-in, solo confirma con un clic el inicio de una ruta
    que ya le fue asignada (ver admin.viajes_programar).

    Revalida todo lo que en teoría ya se validó al programar, porque el
    tiempo entre programar e iniciar puede volver inválido lo que en su
    momento era correcto: licencia vencida mientras tanto (RF-6.2, nunca se
    confía en que ya se validó antes) o vehículo que dejó de estar
    disponible por otra causa.
    """
    perfil = current_user.conductor
    viaje = Viaje.query.get_or_404(id_viaje)

    if perfil is None or viaje.id_conductor != perfil.id_conductor:
        flash("No tienes permiso para iniciar ese viaje.", "error")
        return redirect(url_for("conductor.dashboard"))

    if viaje.estado != "programado":
        flash("Esa ruta ya no está pendiente de iniciar.", "error")
        return redirect(url_for("conductor.dashboard"))

    if not perfil.licencia_vigente():
        flash("No puedes iniciar un viaje: tu licencia está vencida.", "error")
        return redirect(url_for("conductor.dashboard"))

    # Un conductor no puede tener dos viajes sin cerrar a la vez (mismo
    # espíritu que antes tenía el check-in): si otra ruta suya ya está en
    # curso -por ejemplo iniciada desde otra pestaña-, bloquea esta.
    viaje_sin_cerrar = Viaje.query.filter(
        Viaje.id_conductor == perfil.id_conductor,
        Viaje.id_viaje != viaje.id_viaje,
        Viaje.estado.in_(["activo", "alerta", "emergencia"]),
    ).first()
    if viaje_sin_cerrar is not None:
        flash("Ya tienes un viaje sin cerrar. Confirma la llegada antes de iniciar uno nuevo.", "error")
        return redirect(url_for("conductor.dashboard"))

    if viaje.vehiculo.estado != "disponible":
        flash("El vehículo asignado ya no está disponible.", "error")
        return redirect(url_for("conductor.dashboard"))

    viaje.hora_salida = datetime.now()
    viaje.estado = "activo"
    viaje.vehiculo.estado = "en_ruta"

    bitacora = Bitacora(
        id_usuario=current_user.id_usuario,
        accion="ruta_iniciada",
        descripcion=(
            f"Conductor {perfil.nombre} inició el viaje #{viaje.id_viaje} "
            f"({viaje.origen} → {viaje.destino})."
        ),
        tabla_afectada="viajes",
        registro_id=viaje.id_viaje,
    )
    db.session.add(bitacora)

    # RF-3 (resolución automática): si esta ruta ya tenía una alerta de
    # 'ETA vencida sin iniciar' (ver scheduler.revisar_rutas_no_iniciadas),
    # el inicio tardío la resuelve sola — no hay pantalla de "atender"
    # dedicada para este tipo.
    alerta_ruta_no_iniciada = Alerta.query.filter_by(
        id_viaje=viaje.id_viaje, tipo="ruta_no_iniciada", atendida=False
    ).first()
    if alerta_ruta_no_iniciada is not None:
        alerta_ruta_no_iniciada.atendida = True
        alerta_ruta_no_iniciada.atendida_en = datetime.now()

    # RF-3.6 (regla de integridad): la BD protege con un índice único
    # parcial (idx_viaje_activo_unico) contra dos viajes 'activo' para el
    # mismo vehículo; última defensa ante una condición de carrera entre la
    # revalidación de arriba y este commit.
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("El vehículo asignado ya tiene un viaje activo.", "error")
        return redirect(url_for("conductor.dashboard"))

    flash(f"Viaje iniciado correctamente hacia '{viaje.destino}'.", "success")
    return redirect(url_for("conductor.dashboard"))


# Mapea la opción elegida en el selector del dashboard al tipo real de
# Alerta. 'mecanica' se comporta exactamente como el viejo
# reportar_problema_mecanico (visible para mecánico y admin, dispara el
# flujo de reporte de avería); 'trafico' es informativa y SOLO para el
# admin -mecanico.vehiculos_lista filtra explícitamente por
# tipo == 'asistencia_mecanica', así que 'incidencia_trafico' nunca aparece
# ahí ni dispara nada de ese flujo.
TIPOS_INCIDENCIA_CONDUCTOR = {
    "mecanica": "asistencia_mecanica",
    "trafico": "incidencia_trafico",
}


@conductor.route("/reportar-incidencia", methods=["POST"])
@conductor_required
def reportar_incidencia():
    """Registra una incidencia en ruta reportada por el conductor: falla
    mecánica (RF-5, gestión de flota) o tráfico/retraso (solo informativo
    para el admin). Reemplaza al antiguo reportar_problema_mecanico() -el
    conductor ahora elige el tipo antes de confirmar-, ver
    TIPOS_INCIDENCIA_CONDUCTOR para el mapeo.

    Distinto del aviso silencioso de emergencia.py: es visible y de un solo
    clic, y deja una Alerta real en el sistema en vez de solo facilitar una
    llamada externa. Solo aplica con un viaje 'activo' o 'alerta' -- si el
    viaje ya está en 'emergencia' no se ofrece esta opción (es un problema
    de seguridad, no mecánico/de tráfico), y como el filtro de abajo no
    incluye 'emergencia' entre los estados válidos, esa alerta nunca podría
    crearse aunque el formulario llegara a enviarse por algún medio
    distinto del botón del dashboard.
    """
    perfil = current_user.conductor
    if perfil is None:
        flash("Tu cuenta no tiene un perfil de conductor asociado.", "error")
        return redirect(url_for("conductor.dashboard"))

    tipo = TIPOS_INCIDENCIA_CONDUCTOR.get(request.form.get("tipo", ""))
    if tipo is None:
        flash("Selecciona un tipo de incidencia válido.", "error")
        return redirect(url_for("conductor.dashboard"))

    viaje = Viaje.query.filter(
        Viaje.id_conductor == perfil.id_conductor,
        Viaje.estado.in_(["activo", "alerta"]),
    ).first()
    if viaje is None:
        flash(
            "No tienes un viaje en curso al que reportarle una incidencia.",
            "error",
        )
        return redirect(url_for("conductor.dashboard"))

    descripcion = request.form.get("descripcion", "").strip()

    if tipo == "asistencia_mecanica":
        if descripcion:
            mensaje = f"{perfil.nombre} reportó un problema mecánico en ruta: {descripcion}"
        else:
            mensaje = f"{perfil.nombre} reportó un problema mecánico en ruta, sin más detalle."
        accion_bitacora = "reporte_problema_mecanico_conductor"
        descripcion_bitacora = (
            f"Conductor {perfil.nombre} reportó un problema mecánico en el viaje "
            f"#{viaje.id_viaje} ({viaje.origen} → {viaje.destino})."
        )
        mensaje_flash = "Problema mecánico reportado. El administrador fue notificado."
    else:
        if descripcion:
            mensaje = f"{perfil.nombre} reportó tráfico o retraso en ruta: {descripcion}"
        else:
            mensaje = f"{perfil.nombre} reportó tráfico o retraso en ruta, sin más detalle."
        accion_bitacora = "reporte_incidencia_trafico"
        descripcion_bitacora = (
            f"Conductor {perfil.nombre} reportó una incidencia de tráfico/retraso en el viaje "
            f"#{viaje.id_viaje} ({viaje.origen} → {viaje.destino})."
        )
        mensaje_flash = "Incidencia de tráfico reportada. El administrador fue notificado."

    alerta = Alerta(
        id_viaje=viaje.id_viaje,
        id_conductor=perfil.id_conductor,
        tipo=tipo,
        prioridad=2,
        mensaje=mensaje,
        atendida=False,
    )
    db.session.add(alerta)
    db.session.flush()  # asigna alerta.id_alerta antes de la Bitácora

    bitacora = Bitacora(
        id_usuario=current_user.id_usuario,
        accion=accion_bitacora,
        descripcion=descripcion_bitacora,
        tabla_afectada="alertas",
        registro_id=alerta.id_alerta,
    )
    db.session.add(bitacora)
    db.session.commit()

    flash(mensaje_flash, "success")
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
