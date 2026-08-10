# Blueprint del rol mecánico: gestión de estado vehicular y reportes de
# avería (RF-5: Estado vehicular).

from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app import db
from app.models.alerta import Alerta
from app.models.bitacora import Bitacora
from app.controllers.perfil import procesar_perfil
from app.models.reporte_averia import ReporteAveria
from app.models.vehiculo import Vehiculo
from app.models.viaje import Viaje

mecanico = Blueprint("mecanico", __name__)

VIAJE_ESTADOS_CON_VEHICULO_EN_USO = ("activo", "alerta", "emergencia")

# Orden/agrupación de vehiculos_lista: "Falla reportada" siempre va primero
# (ver _clave_orden_vehiculo_mecanico) y no tiene entrada aquí porque no es
# un Vehiculo.estado real, sino un grupo derivado de tener una Alerta
# 'asistencia_mecanica' sin atender.
_ETIQUETA_GRUPO_VEHICULO = {
    "en_taller": "En taller",
    "en_ruta": "En ruta",
    "disponible": "Disponibles",
}
_PRIORIDAD_ESTADO_VEHICULO_MECANICO = {"en_taller": 0, "en_ruta": 1, "disponible": 2}


def _clave_orden_vehiculo_mecanico(vehiculo, alertas_mecanicas_por_vehiculo):
    """Orden de vehiculos_lista: "Falla reportada" primero -sin importar el
    Vehiculo.estado actual, ese grupo se "saca" de su lugar normal-, luego
    En taller, En ruta, Disponibles; alfabético por placa dentro de cada
    grupo (ya vienen ordenados así desde la query).
    """
    if vehiculo.id_vehiculo in alertas_mecanicas_por_vehiculo:
        prioridad = -1
    else:
        prioridad = _PRIORIDAD_ESTADO_VEHICULO_MECANICO.get(vehiculo.estado, 99)
    return (prioridad, vehiculo.placas)


def mecanico_required(view_func):
    """Exige sesión iniciada y rol mecánico (RF-1.3), igual que hacía dashboard()."""

    @wraps(view_func)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.es_mecanico():
            flash("No tienes permiso para acceder a esa sección", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper


def _viaje_activo_de(id_vehiculo):
    """Primer viaje 'activo'/'alerta'/'emergencia' de un vehículo, o None."""
    return Viaje.query.filter(
        Viaje.id_vehiculo == id_vehiculo,
        Viaje.estado.in_(VIAJE_ESTADOS_CON_VEHICULO_EN_USO),
    ).first()


def _tiempo_transcurrido(momento):
    """Antigüedad de `momento` en lenguaje natural relativo a datetime.now()
    (ej. 'hace 15 minutos', 'hace 2 horas'), para que el mecánico vea de un
    vistazo cuánto lleva esperando una falla reportada sin atenderse.

    Se calcula aquí en Python, no en el template, porque depende del
    momento en que se abre la página, no de una columna fija del registro.
    """
    segundos = (datetime.now() - momento).total_seconds()
    if segundos < 60:
        return "hace un momento"
    minutos = int(segundos // 60)
    if minutos < 60:
        return f"hace {minutos} minuto{'s' if minutos != 1 else ''}"
    horas = int(minutos // 60)
    if horas < 24:
        return f"hace {horas} hora{'s' if horas != 1 else ''}"
    dias = int(horas // 24)
    return f"hace {dias} día{'s' if dias != 1 else ''}"


def _alerta_mecanica_pendiente(id_viaje):
    """Alerta tipo='asistencia_mecanica' sin atender de ese viaje, o None.

    El reporte de avería (vehiculos_reportar_averia) es la ÚNICA forma en
    que un mecánico cierra este tipo de alerta: no existe una ruta aparte de
    "marcar como atendida" para este rol. Se resuelve automáticamente al
    completar el flujo de reporte de avería que ya existía.
    """
    return Alerta.query.filter_by(
        id_viaje=id_viaje, tipo="asistencia_mecanica", atendida=False
    ).first()


@mecanico.route("/perfil", methods=["GET", "POST"])
@mecanico_required
def perfil():
    """Pantalla "Mi perfil" del mecánico con sesión iniciada: edición de
    correo/teléfono y cambio de contraseña propia (RF-1). La lógica es
    compartida con admin.perfil (ver app/controllers/perfil.py).
    """
    return procesar_perfil("mecanico/perfil.html")


@mecanico.route("/dashboard")
@mecanico_required
def dashboard():
    """Ya no es el destino post-login del rol mecánico (ver
    auth._dashboard_redirect, que manda directo a vehiculos_lista): se
    conserva solo por si algún enlace viejo sigue apuntando aquí, y
    redirige de inmediato a la lista de vehículos en vez de mostrar un
    panel intermedio que no aportaba nada.
    """
    return redirect(url_for("mecanico.vehiculos_lista"))


@mecanico.route("/vehiculos")
@mecanico_required
def vehiculos_lista():
    """Lista todos los vehículos de la flota agrupados por sección: "Falla
    reportada" primero, luego En taller, En ruta y Disponibles (RF-5.1).
    """
    vehiculos = Vehiculo.query.order_by(Vehiculo.placas).all()

    viajes_en_uso = Viaje.query.filter(
        Viaje.estado.in_(VIAJE_ESTADOS_CON_VEHICULO_EN_USO)
    ).all()
    vehiculos_con_viaje_activo = {viaje.id_vehiculo for viaje in viajes_en_uso}

    # Alertas 'asistencia_mecanica' sin atender de TODA la flota, sin
    # restringir por el estado actual del viaje/vehículo: normalmente el
    # vehículo seguirá 'en_ruta' mientras la alerta esté pendiente, pero un
    # viaje cerrado por otra vía sin pasar por vehiculos_reportar_averia
    # podría dejarla pendiente igual, y el mecánico debe verla de todos
    # modos (RF-5). Se cierran solo al completar vehiculos_reportar_averia
    # (ver _alerta_mecanica_pendiente), no hay una ruta aparte para
    # atenderlas.
    alertas_mecanicas = (
        Alerta.query.options(joinedload(Alerta.conductor), joinedload(Alerta.viaje))
        .filter(Alerta.tipo == "asistencia_mecanica", Alerta.atendida.is_(False))
        .all()
    )
    alertas_mecanicas_por_vehiculo = {}
    for alerta in alertas_mecanicas:
        alertas_mecanicas_por_vehiculo.setdefault(alerta.viaje.id_vehiculo, alerta)

    antiguedad_por_alerta = {
        alerta.id_alerta: _tiempo_transcurrido(alerta.generada_en)
        for alerta in alertas_mecanicas_por_vehiculo.values()
    }

    # Vehículos con una ruta programada pendiente de iniciar (RF-3): aunque
    # su columna `estado` siga en 'disponible', ya están comprometidos con
    # esa ruta y no están realmente libres (ver admin._viajes_programados,
    # mismo criterio aplicado aquí para no duplicar consultas nuevas por
    # cada vehículo).
    viajes_programados = (
        Viaje.query.filter_by(estado="programado")
        .options(joinedload(Viaje.conductor))
        .all()
    )
    reserva_por_vehiculo = {}
    for viaje in viajes_programados:
        reserva_por_vehiculo.setdefault(viaje.id_vehiculo, viaje)

    # Reagrupa: "Falla reportada" se saca de su grupo de estado normal y va
    # primero, sin importar el Vehiculo.estado actual (ver
    # _clave_orden_vehiculo_mecanico) -así no aparece duplicado más abajo.
    vehiculos = sorted(
        vehiculos,
        key=lambda v: _clave_orden_vehiculo_mecanico(v, alertas_mecanicas_por_vehiculo),
    )
    grupo_vehiculo = {
        v.id_vehiculo: (
            "Falla reportada"
            if v.id_vehiculo in alertas_mecanicas_por_vehiculo
            else _ETIQUETA_GRUPO_VEHICULO.get(v.estado, "Otro")
        )
        for v in vehiculos
    }

    return render_template(
        "mecanico/vehiculos/lista.html",
        vehiculos=vehiculos,
        vehiculos_con_viaje_activo=vehiculos_con_viaje_activo,
        alertas_mecanicas_por_vehiculo=alertas_mecanicas_por_vehiculo,
        antiguedad_por_alerta=antiguedad_por_alerta,
        reserva_por_vehiculo=reserva_por_vehiculo,
        grupo_vehiculo=grupo_vehiculo,
    )


@mecanico.route("/alertas/<int:id_alerta>/marcar-vista", methods=["POST"])
@mecanico_required
def alertas_marcar_vista(id_alerta):
    """Marca una Alerta tipo='asistencia_mecanica' como vista (estado
    intermedio, distinto de 'atendida': ver _alerta_mecanica_pendiente).

    Solo aplica a este tipo de alerta -un mecánico no tiene por qué poder
    tocar una alerta de pánico o retraso-, así que cualquier otro tipo
    responde 404, igual que si la alerta no existiera.
    """
    alerta = Alerta.query.get_or_404(id_alerta)
    if alerta.tipo != "asistencia_mecanica":
        abort(404)

    if not alerta.vista:
        alerta.vista = True
        alerta.vista_en = datetime.now()

        bitacora = Bitacora(
            id_usuario=current_user.id_usuario,
            accion="alerta_mecanica_vista",
            descripcion=(
                f"{current_user.nombre} marcó como vista la alerta de problema "
                f"mecánico #{alerta.id_alerta}."
            ),
            tabla_afectada="alertas",
            registro_id=alerta.id_alerta,
        )
        db.session.add(bitacora)
        db.session.commit()

    flash("Alerta marcada como vista.", "success")
    return redirect(url_for("mecanico.vehiculos_lista"))


@mecanico.route("/alertas/<int:id_alerta>/detalle")
@mecanico_required
def alertas_detalle(id_alerta):
    """Detalle de una falla reportada: conductor (con teléfono), vehículo,
    descripción, antigüedad y ubicación geocodificada si existe (RF-5).

    Mismo criterio de seguridad que alertas_marcar_vista: solo aplica a
    Alerta tipo='asistencia_mecanica', cualquier otro tipo responde 404.
    """
    alerta = Alerta.query.options(
        joinedload(Alerta.conductor),
        joinedload(Alerta.viaje).joinedload(Viaje.vehiculo),
    ).get_or_404(id_alerta)
    if alerta.tipo != "asistencia_mecanica":
        abort(404)

    return render_template(
        "mecanico/alertas/detalle.html",
        alerta=alerta,
        vehiculo=alerta.viaje.vehiculo,
        antiguedad=_tiempo_transcurrido(alerta.generada_en),
    )


@mecanico.route("/vehiculos/<int:id_vehiculo>/estado", methods=["POST"])
@mecanico_required
def vehiculos_cambiar_estado(id_vehiculo):
    """Alterna el estado de un vehículo entre 'disponible' y 'en_taller' (RF-5.2).

    Misma protección que el formulario de edición del administrador: un
    vehículo 'en_ruta' no puede cambiar de estado por esta vía bajo ninguna
    circunstancia (se actualiza solo al finalizar su viaje activo).
    """
    vehiculo = Vehiculo.query.get_or_404(id_vehiculo)

    if vehiculo.estado == "en_ruta":
        flash(
            "No se puede modificar el estado de un vehículo en ruta; "
            "se actualizará automáticamente al finalizar el viaje activo.",
            "error",
        )
        return redirect(url_for("mecanico.vehiculos_lista"))

    nuevo_estado = request.form.get("estado", "")
    if nuevo_estado not in ("disponible", "en_taller"):
        flash("El estado seleccionado no es válido.", "error")
        return redirect(url_for("mecanico.vehiculos_lista"))

    estado_anterior = vehiculo.estado
    vehiculo.estado = nuevo_estado

    motivo = request.form.get("motivo", "").strip()
    descripcion = (
        f"Vehículo '{vehiculo.placas}' cambiado de '{estado_anterior}' a "
        f"'{nuevo_estado}' por {current_user.nombre}."
    )
    if motivo:
        descripcion += f" Motivo: {motivo}."

    bitacora = Bitacora(
        id_usuario=current_user.id_usuario,
        accion="cambio_estado_vehiculo",
        descripcion=descripcion,
        tabla_afectada="vehiculos",
        registro_id=vehiculo.id_vehiculo,
    )
    db.session.add(bitacora)
    db.session.commit()

    flash(f"Vehículo '{vehiculo.placas}' actualizado a '{nuevo_estado}'.", "success")
    return redirect(url_for("mecanico.vehiculos_lista"))


@mecanico.route("/vehiculos/<int:id_vehiculo>/reportar-averia", methods=["GET", "POST"])
@mecanico_required
def vehiculos_reportar_averia(id_vehiculo):
    """Muestra el formulario y registra un reporte de avería (RF-5.3).

    Solo aplica a un vehículo con un viaje 'activo'/'alerta'/'emergencia' en
    curso: el reporte se vincula a ese viaje (id_viaje es NOT NULL). Sin un
    viaje en curso no hay nada que reportar por esta vía, ni en GET ni en POST.
    """
    vehiculo = Vehiculo.query.get_or_404(id_vehiculo)
    viaje_activo = _viaje_activo_de(id_vehiculo)

    if viaje_activo is None:
        flash(
            f"El vehículo '{vehiculo.placas}' no tiene un viaje en curso; "
            "no se puede registrar un reporte de avería.",
            "error",
        )
        return redirect(url_for("mecanico.vehiculos_lista"))

    # Si el conductor ya reportó un problema mecánico para este mismo viaje,
    # se prellena la descripción con ese aviso (el mecánico puede editarlo
    # libremente) para que no tenga que volver a escribir lo mismo, y se usa
    # más abajo en el POST para cerrar esa alerta automáticamente.
    alerta_mecanica = _alerta_mecanica_pendiente(viaje_activo.id_viaje)

    if request.method == "POST":
        descripcion = request.form.get("descripcion", "").strip()
        if not descripcion:
            flash("Debes describir la falla del vehículo.", "error")
            return redirect(
                url_for("mecanico.vehiculos_reportar_averia", id_vehiculo=id_vehiculo)
            )

        cambiar_a_en_taller = request.form.get("cambiar_estado") is not None

        # Se guarda el estado del vehículo antes de tocar nada, para
        # conservar el estado real que tenía al momento del reporte.
        estado_vehiculo_prev = vehiculo.estado

        reporte = ReporteAveria(
            id_viaje=viaje_activo.id_viaje,
            id_vehiculo=vehiculo.id_vehiculo,
            id_usuario=current_user.id_usuario,
            descripcion=descripcion,
            estado_vehiculo_prev=estado_vehiculo_prev,
        )
        db.session.add(reporte)

        if cambiar_a_en_taller:
            # Excepción intencional a la protección de 'en_ruta' (RF-5.2): el
            # reporte de avería es justamente lo que retira al vehículo de
            # circulación, así que aquí SÍ se permite pasarlo a 'en_taller'
            # aunque esté 'en_ruta', y se cierra el viaje que lo justifica.
            vehiculo.estado = "en_taller"
            viaje_activo.estado = "cerrado_admin"
            viaje_activo.hora_llegada = datetime.now()

        if alerta_mecanica is not None:
            alerta_mecanica.atendida = True
            alerta_mecanica.atendida_en = datetime.now()

        db.session.flush()  # asigna reporte.id_reporte antes de la Bitácora

        bitacora = Bitacora(
            id_usuario=current_user.id_usuario,
            accion="reporte_averia",
            descripcion=(
                f"Reporte de avería registrado para el vehículo "
                f"'{vehiculo.placas}' por {current_user.nombre}."
            ),
            tabla_afectada="reportes_averia",
            registro_id=reporte.id_reporte,
        )
        db.session.add(bitacora)
        db.session.commit()

        flash("Reporte de avería registrado correctamente.", "success")
        return redirect(url_for("mecanico.vehiculos_lista"))

    return render_template(
        "mecanico/vehiculos/reportar_averia.html",
        vehiculo=vehiculo,
        viaje_activo=viaje_activo,
        alerta_mecanica=alerta_mecanica,
    )


@mecanico.route("/reportes-averia")
@mecanico_required
def reportes_averia_lista():
    """Historial de los reportes de avería creados por el mecánico en sesión
    (RF-5.4 desde la perspectiva del mecánico, no existía hasta ahora: solo
    admin.reportes_averia_lista mostraba todos los reportes del sistema).

    SEGURIDAD: filtra SIEMPRE por current_user.id_usuario. No se acepta
    ningún id de mecánico por query param ni ninguna otra vía -un mecánico
    jamás debe poder ver los reportes de otro.

    A diferencia de admin.reportes_averia_lista (que por default oculta los
    reportes archivados: son una lista *operativa* para seguimiento
    reciente, ver reportes_averia_archivar), esta vista SÍ incluye los
    archivados: es explícitamente un historial personal, no una lista de
    pendientes, así que archivar un reporte viejo desde el panel del admin
    no debe hacerlo desaparecer del propio historial del mecánico que lo
    registró.
    """
    reportes = (
        ReporteAveria.query.options(
            joinedload(ReporteAveria.vehiculo), joinedload(ReporteAveria.viaje)
        )
        .filter_by(id_usuario=current_user.id_usuario)
        .order_by(ReporteAveria.registrado_en.desc())
        .all()
    )
    return render_template("mecanico/reportes_averia.html", reportes=reportes)
