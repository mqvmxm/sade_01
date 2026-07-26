# Blueprint del rol administrador (RF-1.4: el admin gestiona cuentas).
# Incluye el módulo de gestión de conductores (RF-2: Gestión de flota).

import csv
import io
import math
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app import db
from app.models.alerta import Alerta
from app.models.bitacora import Bitacora
from app.models.conductor import Conductor
from app.models.reporte_averia import ReporteAveria
from app.models.vehiculo import Vehiculo
from app.models.viaje import Viaje

VIAJE_ESTADOS_CERRABLES_POR_ADMIN = ("activo", "alerta", "emergencia")

# Historial de eventos: cada tipo normalizado con su etiqueta, color de badge
# (reutiliza el mismo sistema badge-status del resto del proyecto) y a qué
# lista existente apunta su link "Ver detalle". El proyecto no tiene vistas
# de detalle por registro individual, así que el link va a la lista general
# correspondiente: para Alertas eso significa que si la alerta ya está
# atendida no aparecerá ahí (esa lista solo muestra atendida=False), y para
# Viajes Activos significa que un viaje ya cerrado tampoco aparecerá (esa
# lista solo muestra activo/alerta/emergencia). Es una limitación conocida,
# no un bug: no hay a dónde más apuntar sin construir páginas de detalle
# nuevas, que quedan fuera del alcance pedido aquí.
TIPO_INFO_HISTORIAL = {
    "retraso": ("Alerta de retraso", "warning", "admin.alertas_lista"),
    "panico": ("Aviso de emergencia", "danger", "admin.alertas_lista"),
    "licencia_vencida": ("Licencia vencida", "danger", "admin.alertas_lista"),
    "averia": ("Avería en ruta", "warning", "admin.reportes_averia_lista"),
    "cerrado_forzado": ("Viaje cerrado (forzado)", "danger", "admin.viajes_lista"),
    "completado": ("Viaje completado", "success", "admin.viajes_lista"),
}
TAM_PAGINA_HISTORIAL = 20

admin = Blueprint("admin", __name__)


def admin_required(view_func):
    """Exige sesión iniciada y rol admin (RF-1.3), igual que hacía dashboard()."""

    @wraps(view_func)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.es_admin():
            flash("No tienes permiso para acceder a esa sección", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper


def _datos_conductor_desde_formulario():
    """Lee y valida los campos del formulario de conductor.

    Retorna un dict listo para crear/actualizar un Conductor, o None (y ya
    hizo flash del error) si la fecha de vencimiento no es válida.
    """
    fecha_texto = request.form.get("fecha_vencimiento_lic", "")
    try:
        fecha_vencimiento = datetime.strptime(fecha_texto, "%Y-%m-%d").date()
    except ValueError:
        flash("La fecha de vencimiento de la licencia no es válida.", "error")
        return None

    return {
        "nombre": request.form.get("nombre", "").strip(),
        "telefono": request.form.get("telefono", "").strip(),
        "num_licencia": request.form.get("num_licencia", "").strip(),
        "fecha_vencimiento_lic": fecha_vencimiento,
        "contacto_emergencia": request.form.get("contacto_emergencia", "").strip(),
        "tel_emergencia": request.form.get("tel_emergencia", "").strip(),
    }


def _conductor_para_formulario(conductor):
    """Convierte un Conductor de BD a dict apto para prellenar el formulario HTML."""
    return {
        "nombre": conductor.nombre,
        "telefono": conductor.telefono,
        "num_licencia": conductor.num_licencia,
        "fecha_vencimiento_lic": conductor.fecha_vencimiento_lic.isoformat(),
        "contacto_emergencia": conductor.contacto_emergencia,
        "tel_emergencia": conductor.tel_emergencia,
    }


def _datos_vehiculo_desde_formulario():
    """Lee y valida los campos comunes del formulario de vehículo.

    Retorna un dict listo para crear/actualizar un Vehiculo (sin 'estado', que
    se maneja aparte), o None (y ya hizo flash del error) si el año no es válido.
    """
    anio_texto = request.form.get("anio", "")
    try:
        anio = int(anio_texto)
    except ValueError:
        flash("El año del vehículo no es válido.", "error")
        return None

    return {
        "placas": request.form.get("placas", "").strip(),
        "num_unidad": request.form.get("num_unidad", "").strip(),
        "marca": request.form.get("marca", "").strip(),
        "modelo": request.form.get("modelo", "").strip(),
        "anio": anio,
        "num_serie": request.form.get("num_serie", "").strip(),
    }


def _vehiculo_para_formulario(vehiculo):
    """Convierte un Vehiculo de BD a dict apto para prellenar el formulario HTML."""
    return {
        "placas": vehiculo.placas,
        "num_unidad": vehiculo.num_unidad,
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "anio": vehiculo.anio,
        "num_serie": vehiculo.num_serie,
        "estado": vehiculo.estado,
    }


@admin.route("/dashboard")
@admin_required
def dashboard():
    """Muestra el panel de administrador."""
    return render_template("admin/dashboard.html")


@admin.route("/conductores")
@admin_required
def conductores_lista():
    """Lista todos los conductores con el estado de vigencia de su licencia (RF-2.3)."""
    conductores = Conductor.query.order_by(Conductor.nombre).all()
    return render_template("admin/conductores/lista.html", conductores=conductores)


@admin.route("/conductores/nuevo", methods=["GET", "POST"])
@admin_required
def conductores_nuevo():
    """Muestra el formulario de alta y crea el Conductor al enviarlo (RF-2.1)."""
    if request.method == "POST":
        datos = _datos_conductor_desde_formulario()
        if datos is None:
            return render_template(
                "admin/conductores/formulario.html", conductor=request.form, id_conductor=None
            )

        conductor = Conductor(**datos)
        try:
            db.session.add(conductor)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un conductor con el número de licencia '{datos['num_licencia']}'.",
                "error",
            )
            return render_template(
                "admin/conductores/formulario.html", conductor=request.form, id_conductor=None
            )

        flash(f"Conductor '{conductor.nombre}' registrado correctamente.", "success")
        return redirect(url_for("admin.conductores_lista"))

    return render_template("admin/conductores/formulario.html", conductor=None, id_conductor=None)


@admin.route("/conductores/<int:id_conductor>/editar", methods=["GET", "POST"])
@admin_required
def conductores_editar(id_conductor):
    """Muestra el formulario prellenado y actualiza los datos del conductor (RF-2.1)."""
    conductor = Conductor.query.get_or_404(id_conductor)

    if request.method == "POST":
        datos = _datos_conductor_desde_formulario()
        if datos is None:
            return render_template(
                "admin/conductores/formulario.html",
                conductor=request.form,
                id_conductor=id_conductor,
            )

        for campo, valor in datos.items():
            setattr(conductor, campo, valor)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un conductor con el número de licencia '{datos['num_licencia']}'.",
                "error",
            )
            return render_template(
                "admin/conductores/formulario.html",
                conductor=request.form,
                id_conductor=id_conductor,
            )

        flash(f"Conductor '{conductor.nombre}' actualizado correctamente.", "success")
        return redirect(url_for("admin.conductores_lista"))

    return render_template(
        "admin/conductores/formulario.html",
        conductor=_conductor_para_formulario(conductor),
        id_conductor=id_conductor,
    )


@admin.route("/vehiculos")
@admin_required
def vehiculos_lista():
    """Lista todos los vehículos registrados con su estado actual (RF-2.3)."""
    vehiculos = Vehiculo.query.order_by(Vehiculo.placas).all()
    return render_template("admin/vehiculos/lista.html", vehiculos=vehiculos)


@admin.route("/vehiculos/nuevo", methods=["GET", "POST"])
@admin_required
def vehiculos_nuevo():
    """Muestra el formulario de alta y crea el Vehiculo al enviarlo (RF-2.2).

    El estado no se pide aquí: todo vehículo nuevo inicia en 'disponible'.
    """
    if request.method == "POST":
        datos = _datos_vehiculo_desde_formulario()
        if datos is None:
            return render_template(
                "admin/vehiculos/formulario.html", vehiculo=request.form, id_vehiculo=None
            )

        vehiculo = Vehiculo(**datos)
        try:
            db.session.add(vehiculo)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un vehículo con las placas '{datos['placas']}'.",
                "error",
            )
            return render_template(
                "admin/vehiculos/formulario.html", vehiculo=request.form, id_vehiculo=None
            )

        flash(f"Vehículo '{vehiculo.placas}' registrado correctamente.", "success")
        return redirect(url_for("admin.vehiculos_lista"))

    return render_template("admin/vehiculos/formulario.html", vehiculo=None, id_vehiculo=None)


@admin.route("/vehiculos/<int:id_vehiculo>/editar", methods=["GET", "POST"])
@admin_required
def vehiculos_editar(id_vehiculo):
    """Muestra el formulario prellenado y actualiza los datos del vehículo (RF-2.2).

    El estado solo puede cambiarse aquí entre 'disponible' y 'en_taller'. Si el
    vehículo está actualmente 'en_ruta' (viaje activo, RF-5.5), el estado no es
    editable desde este formulario bajo ninguna circunstancia: cualquier POST que
    incluya el campo 'estado' se rechaza, sin importar su valor.
    """
    vehiculo = Vehiculo.query.get_or_404(id_vehiculo)

    if request.method == "POST":
        if vehiculo.estado == "en_ruta" and "estado" in request.form:
            flash(
                "No se puede modificar el estado de un vehículo en ruta; "
                "se actualizará automáticamente al finalizar el viaje activo.",
                "error",
            )
            return render_template(
                "admin/vehiculos/formulario.html",
                vehiculo=request.form,
                id_vehiculo=id_vehiculo,
            )

        datos = _datos_vehiculo_desde_formulario()
        if datos is None:
            return render_template(
                "admin/vehiculos/formulario.html",
                vehiculo=request.form,
                id_vehiculo=id_vehiculo,
            )

        if vehiculo.estado != "en_ruta":
            estado = request.form.get("estado", "")
            if estado not in ("disponible", "en_taller"):
                flash("El estado seleccionado no es válido.", "error")
                return render_template(
                    "admin/vehiculos/formulario.html",
                    vehiculo=request.form,
                    id_vehiculo=id_vehiculo,
                )
            datos["estado"] = estado

        for campo, valor in datos.items():
            setattr(vehiculo, campo, valor)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un vehículo con las placas '{datos['placas']}'.",
                "error",
            )
            return render_template(
                "admin/vehiculos/formulario.html",
                vehiculo=request.form,
                id_vehiculo=id_vehiculo,
            )

        flash(f"Vehículo '{vehiculo.placas}' actualizado correctamente.", "success")
        return redirect(url_for("admin.vehiculos_lista"))

    return render_template(
        "admin/vehiculos/formulario.html",
        vehiculo=_vehiculo_para_formulario(vehiculo),
        id_vehiculo=id_vehiculo,
    )


@admin.route("/viajes")
@admin_required
def viajes_lista():
    """Lista los viajes 'activo', 'alerta' o 'emergencia' para monitoreo del administrador (RF-3/RF-4).

    Las emergencias reales van siempre primero, sin importar su hora_salida:
    son lo más urgente y no deben poder quedar enterradas debajo de simples
    retrasos o viajes normales más recientes.
    """
    prioridad_estado = case(
        (Viaje.estado == "emergencia", 0),
        (Viaje.estado == "alerta", 1),
        else_=2,
    )
    viajes = (
        Viaje.query.filter(Viaje.estado.in_(["activo", "alerta", "emergencia"]))
        .order_by(prioridad_estado, Viaje.hora_salida)
        .all()
    )
    return render_template("admin/viajes/lista.html", viajes=viajes)


@admin.route("/viajes/<int:id_viaje>/confirmar-llegada-manual", methods=["POST"])
@admin_required
def viajes_confirmar_llegada_manual(id_viaje):
    """Confirma la llegada de un viaje en nombre del conductor (mismo efecto
    que conductor.viajes_confirmar_llegada). Pensada para cuando el
    conductor no puede confirmar él mismo pero el viaje sí terminó bien."""
    viaje = Viaje.query.get_or_404(id_viaje)

    if viaje.estado not in VIAJE_ESTADOS_CERRABLES_POR_ADMIN:
        flash("Ese viaje ya no está en curso.", "error")
        return redirect(url_for("admin.viajes_lista"))

    estado_anterior = viaje.estado
    viaje.hora_llegada = datetime.now()
    viaje.estado = "completado"
    viaje.vehiculo.estado = "disponible"

    bitacora = Bitacora(
        id_usuario=current_user.id_usuario,
        accion="confirmar_llegada_manual_admin",
        descripcion=(
            f"Llegada del viaje #{viaje.id_viaje} ({viaje.origen} → {viaje.destino}, "
            f"conductor {viaje.conductor.nombre}) confirmada manualmente por "
            f"{current_user.nombre} (estado previo: '{estado_anterior}')."
        ),
        tabla_afectada="viajes",
        registro_id=viaje.id_viaje,
    )
    db.session.add(bitacora)
    db.session.commit()

    flash(f"Llegada del viaje #{viaje.id_viaje} confirmada manualmente.", "success")
    return redirect(url_for("admin.viajes_lista"))


@admin.route("/viajes/<int:id_viaje>/cerrar-forzado", methods=["POST"])
@admin_required
def viajes_cerrar_forzado(id_viaje):
    """Cierra un viaje atorado o con datos inconsistentes que no se puede
    resolver de otra forma. A diferencia de la confirmación (normal o
    manual), el estado queda en 'cerrado_admin' -no 'completado'- para dejar
    constancia de que el cierre fue anómalo, no una llegada real."""
    viaje = Viaje.query.get_or_404(id_viaje)

    if viaje.estado not in VIAJE_ESTADOS_CERRABLES_POR_ADMIN:
        flash("Ese viaje ya no está en curso.", "error")
        return redirect(url_for("admin.viajes_lista"))

    estado_anterior = viaje.estado
    viaje.hora_llegada = datetime.now()
    viaje.estado = "cerrado_admin"
    viaje.vehiculo.estado = "disponible"

    bitacora = Bitacora(
        id_usuario=current_user.id_usuario,
        accion="cerrar_viaje_forzado_admin",
        descripcion=(
            f"Viaje #{viaje.id_viaje} ({viaje.origen} → {viaje.destino}, "
            f"conductor {viaje.conductor.nombre}) cerrado de forma forzada por "
            f"{current_user.nombre} (estado previo: '{estado_anterior}')."
        ),
        tabla_afectada="viajes",
        registro_id=viaje.id_viaje,
    )
    db.session.add(bitacora)
    db.session.commit()

    flash(f"Viaje #{viaje.id_viaje} cerrado de forma forzada.", "success")
    return redirect(url_for("admin.viajes_lista"))


@admin.route("/alertas")
@admin_required
def alertas_lista():
    """Lista las alertas sin atender, más recientes primero (RF-3.5)."""
    alertas = (
        Alerta.query.filter_by(atendida=False)
        .order_by(Alerta.generada_en.desc())
        .all()
    )
    return render_template("admin/alertas/lista.html", alertas=alertas)


@admin.route("/reportes-averia")
@admin_required
def reportes_averia_lista():
    """Lista todos los reportes de avería registrados por mecánica (RF-5.4).

    No hay infraestructura de tiempo real: esta vista simplemente consulta la
    BD en cada carga, igual que Vehículos y Viajes activos.
    """
    reportes = (
        ReporteAveria.query.options(
            joinedload(ReporteAveria.vehiculo),
            joinedload(ReporteAveria.viaje),
            joinedload(ReporteAveria.usuario),
        )
        .order_by(ReporteAveria.registrado_en.desc())
        .all()
    )
    return render_template("admin/reportes_averia/lista.html", reportes=reportes)


def _tipo_y_cierre_de_viaje_cerrado(viaje, reportes_por_viaje, forzado_por_viaje, manual_por_viaje):
    """Deriva (slug_tipo, cierre) para un Viaje ya cerrado ('completado' o
    'cerrado_admin'), revisando en orden de prioridad:

    1. Si el mecánico registró un ReporteAveria para ese viaje (con el
       checkbox de "cambiar a en_taller" marcado, cerró el viaje) -> avería.
       Se revisa PRIMERO porque ese cierre también deja estado='cerrado_admin',
       igual que el cierre forzado del admin, y hay que distinguirlos.
    2. Si hay Bitácora de cerrar_viaje_forzado_admin para ese viaje -> forzado.
    3. Si hay Bitácora de confirmar_llegada_manual_admin para ese viaje -> manual.
    4. Si no aplica ninguna de las anteriores -> cierre normal del conductor
       (viajes_confirmar_llegada en conductor.py no deja registro en Bitácora).
    """
    if viaje.id_viaje in reportes_por_viaje:
        return "averia", "Mecánico"
    if viaje.id_viaje in forzado_por_viaje:
        return "cerrado_forzado", "Manual (admin)"
    if viaje.id_viaje in manual_por_viaje:
        return "completado", "Manual (admin)"
    return "completado", "Conductor"


def _cierre_para_panico(alerta, reportes_por_viaje, forzado_por_viaje, manual_por_viaje):
    """Cierre de una Alerta tipo='panico', derivado del cierre de su Viaje
    asociado con la misma prioridad de _tipo_y_cierre_de_viaje_cerrado().

    Si el viaje de la emergencia todavía no se cerró (sigue
    activo/alerta/emergencia), no hay nada que derivar todavía: se reporta
    'Pendiente' en vez de adivinar un cierre que no ha ocurrido.
    """
    viaje = alerta.viaje
    if viaje is None or viaje.estado not in ("completado", "cerrado_admin"):
        return "Pendiente"
    _, cierre = _tipo_y_cierre_de_viaje_cerrado(viaje, reportes_por_viaje, forzado_por_viaje, manual_por_viaje)
    return cierre


def _construir_eventos_historial():
    """Arma la lista normalizada del Historial (RF de auditoría): une
    Alertas (retraso/pánico/licencia_vencida) y Viajes cerrados
    (completado/cerrado_admin) en un solo tipo de evento, ordenada por
    fecha descendente. No hay hoy ninguna Alerta tipo='licencia_vencida'
    real en el sistema (el check-in solo bloquea con un flash, RF-6.2, sin
    crear fila); el código la contempla por si alguna vez existe, pero su
    ausencia no debe romper ni vaciar el resto del historial.
    """
    reportes_por_viaje = {r.id_viaje: r for r in ReporteAveria.query.all()}
    forzado_por_viaje = {
        b.registro_id: b
        for b in Bitacora.query.filter_by(accion="cerrar_viaje_forzado_admin", tabla_afectada="viajes").all()
    }
    manual_por_viaje = {
        b.registro_id: b
        for b in Bitacora.query.filter_by(accion="confirmar_llegada_manual_admin", tabla_afectada="viajes").all()
    }

    eventos = []

    alertas = (
        Alerta.query.options(joinedload(Alerta.conductor), joinedload(Alerta.viaje))
        .filter(Alerta.tipo.in_(["retraso", "panico", "licencia_vencida"]))
        .all()
    )
    for alerta in alertas:
        if alerta.tipo == "retraso":
            slug, cierre = "retraso", "Automático"
            ruta = f"{alerta.viaje.origen} → {alerta.viaje.destino}" if alerta.viaje else "—"
            id_vehiculo = alerta.viaje.id_vehiculo if alerta.viaje else None
        elif alerta.tipo == "panico":
            slug = "panico"
            cierre = _cierre_para_panico(alerta, reportes_por_viaje, forzado_por_viaje, manual_por_viaje)
            ruta = f"{alerta.viaje.origen} → {alerta.viaje.destino}" if alerta.viaje else "—"
            id_vehiculo = alerta.viaje.id_vehiculo if alerta.viaje else None
        else:  # licencia_vencida (contemplado por esquema; hoy nunca se genera)
            slug, cierre = "licencia_vencida", "Sistema"
            ruta = "—"
            id_vehiculo = None

        eventos.append(
            {
                "fecha": alerta.generada_en,
                "tipo_slug": slug,
                "conductor": alerta.conductor.nombre,
                "id_conductor": alerta.id_conductor,
                "ruta": ruta,
                "id_vehiculo": id_vehiculo,
                "cierre": cierre,
            }
        )

    viajes_cerrados = (
        Viaje.query.options(joinedload(Viaje.conductor), joinedload(Viaje.vehiculo))
        .filter(Viaje.estado.in_(["completado", "cerrado_admin"]))
        .all()
    )
    for viaje in viajes_cerrados:
        slug, cierre = _tipo_y_cierre_de_viaje_cerrado(viaje, reportes_por_viaje, forzado_por_viaje, manual_por_viaje)
        eventos.append(
            {
                "fecha": viaje.hora_llegada,
                "tipo_slug": slug,
                "conductor": viaje.conductor.nombre,
                "id_conductor": viaje.id_conductor,
                "ruta": f"{viaje.origen} → {viaje.destino}",
                "id_vehiculo": viaje.id_vehiculo,
                "cierre": cierre,
            }
        )

    # Ordena por fecha descendente. En teoria hora_llegada siempre esta
    # presente para un viaje 'completado'/'cerrado_admin' (todas las rutas
    # que producen esos estados la fijan), pero no hay una restriccion de BD
    # que lo garantice y ya existen filas reales mas viejas sin ese dato:
    # se tratan como la fecha mas antigua posible en vez de romper el orden.
    eventos.sort(key=lambda e: e["fecha"] or datetime.min, reverse=True)
    for evento in eventos:
        etiqueta, badge, endpoint = TIPO_INFO_HISTORIAL[evento["tipo_slug"]]
        evento["tipo_etiqueta"] = etiqueta
        evento["badge"] = badge
        evento["url_detalle"] = url_for(endpoint)
    return eventos


def _exportar_historial_csv(eventos):
    """Genera el CSV de descarga con las mismas columnas visibles en la tabla."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(["Tipo de evento", "Conductor", "Ruta", "Fecha y hora", "Cierre"])
    for evento in eventos:
        escritor.writerow(
            [
                evento["tipo_etiqueta"],
                evento["conductor"],
                evento["ruta"],
                evento["fecha"].strftime("%d/%m/%Y %H:%M") if evento["fecha"] else "",
                evento["cierre"],
            ]
        )

    respuesta = Response(buffer.getvalue(), mimetype="text/csv")
    respuesta.headers["Content-Disposition"] = "attachment; filename=historial_sade.csv"
    return respuesta


@admin.route("/historial")
@admin_required
def historial():
    """Historial de eventos: une Alertas y Viajes cerrados en una sola
    lista normalizada, con filtros opcionales, exportación a CSV y
    paginación (ver _construir_eventos_historial() para el detalle de cómo
    se normaliza y deriva cada tipo/cierre).
    """
    eventos = _construir_eventos_historial()

    tipo_filtro = request.args.get("tipo", "").strip()
    conductor_filtro = request.args.get("conductor", "").strip()
    vehiculo_filtro = request.args.get("vehiculo", "").strip()
    desde_texto = request.args.get("desde", "").strip()
    hasta_texto = request.args.get("hasta", "").strip()

    if tipo_filtro:
        eventos = [e for e in eventos if e["tipo_slug"] == tipo_filtro]
    if conductor_filtro:
        eventos = [e for e in eventos if str(e["id_conductor"]) == conductor_filtro]
    if vehiculo_filtro:
        eventos = [e for e in eventos if str(e["id_vehiculo"]) == vehiculo_filtro]

    if desde_texto:
        try:
            desde_fecha = datetime.strptime(desde_texto, "%Y-%m-%d")
            # Un evento sin fecha conocida (ver nota en _construir_eventos_historial)
            # no puede afirmarse que caiga dentro del rango: se excluye.
            eventos = [e for e in eventos if e["fecha"] is not None and e["fecha"] >= desde_fecha]
        except ValueError:
            flash("La fecha 'desde' no es válida.", "error")
            desde_texto = ""

    if hasta_texto:
        try:
            # +1 día para que 'hasta' incluya todo ese día completo.
            hasta_fecha = datetime.strptime(hasta_texto, "%Y-%m-%d") + timedelta(days=1)
            eventos = [e for e in eventos if e["fecha"] is not None and e["fecha"] < hasta_fecha]
        except ValueError:
            flash("La fecha 'hasta' no es válida.", "error")
            hasta_texto = ""

    if request.args.get("formato") == "csv":
        return _exportar_historial_csv(eventos)

    filtros_actuales = {
        clave: valor
        for clave, valor in {
            "tipo": tipo_filtro,
            "conductor": conductor_filtro,
            "vehiculo": vehiculo_filtro,
            "desde": desde_texto,
            "hasta": hasta_texto,
        }.items()
        if valor
    }

    total_eventos = len(eventos)
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1
    total_paginas = max(1, math.ceil(total_eventos / TAM_PAGINA_HISTORIAL))
    pagina = min(pagina, total_paginas)
    inicio = (pagina - 1) * TAM_PAGINA_HISTORIAL
    eventos_pagina = eventos[inicio : inicio + TAM_PAGINA_HISTORIAL]

    return render_template(
        "admin/historial/lista.html",
        eventos=eventos_pagina,
        tipos_evento=TIPO_INFO_HISTORIAL,
        conductores=Conductor.query.order_by(Conductor.nombre).all(),
        vehiculos=Vehiculo.query.order_by(Vehiculo.placas).all(),
        filtros_actuales=filtros_actuales,
        pagina=pagina,
        total_paginas=total_paginas,
        total_eventos=total_eventos,
    )


@admin.route("/alertas/<int:id_alerta>/atender", methods=["POST"])
@admin_required
def alertas_atender(id_alerta):
    """Marca una alerta como atendida (RF-3.5)."""
    alerta = Alerta.query.get_or_404(id_alerta)
    alerta.atendida = True
    alerta.atendida_en = datetime.now()
    db.session.commit()

    flash("Alerta marcada como atendida.", "success")
    return redirect(url_for("admin.alertas_lista"))
