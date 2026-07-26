# Blueprint del rol mecánico: gestión de estado vehicular y reportes de
# avería (RF-5: Estado vehicular).

from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models.bitacora import Bitacora
from app.models.reporte_averia import ReporteAveria
from app.models.vehiculo import Vehiculo
from app.models.viaje import Viaje

mecanico = Blueprint("mecanico", __name__)

VIAJE_ESTADOS_CON_VEHICULO_EN_USO = ("activo", "alerta", "emergencia")


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


@mecanico.route("/dashboard")
@mecanico_required
def dashboard():
    """Muestra el panel de mecánico, verificando el rol en backend (RF-1.3)."""
    return render_template("mecanico/dashboard.html")


@mecanico.route("/vehiculos")
@mecanico_required
def vehiculos_lista():
    """Lista todos los vehículos de la flota con su estado actual (RF-5.1)."""
    vehiculos = Vehiculo.query.order_by(Vehiculo.placas).all()

    viajes_en_uso = Viaje.query.filter(
        Viaje.estado.in_(VIAJE_ESTADOS_CON_VEHICULO_EN_USO)
    ).all()
    vehiculos_con_viaje_activo = {viaje.id_vehiculo for viaje in viajes_en_uso}

    return render_template(
        "mecanico/vehiculos/lista.html",
        vehiculos=vehiculos,
        vehiculos_con_viaje_activo=vehiculos_con_viaje_activo,
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
    )
