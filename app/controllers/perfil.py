# Lógica de la pantalla "Mi perfil", compartida por los blueprints de admin
# y mecánico (RF-1). No es un blueprint propio -no expone rutas- porque el
# patrón del proyecto es "un blueprint por rol": cada blueprint de rol
# expone su propia ruta /perfil (admin.perfil, mecanico.perfil) y delega
# aquí la lógica, para no duplicarla entre ambos.

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.models.bitacora import Bitacora


def procesar_perfil(template_name):
    """Muestra y procesa la pantalla "Mi perfil" de la cuenta con sesión
    iniciada: datos editables (correo, teléfono) y cambio de contraseña,
    cada uno en su propio <form> (distinguidos por el campo oculto
    'formulario') dentro de la misma página.
    """
    usuario = current_user

    if request.method == "POST":
        formulario = request.form.get("formulario", "")

        if formulario == "datos":
            email = request.form.get("email", "").strip()
            telefono = request.form.get("telefono", "").strip()

            cambios = []
            if email != (usuario.email or ""):
                cambios.append("correo")
            if telefono != (usuario.telefono or ""):
                cambios.append("teléfono")

            usuario.email = email or None
            usuario.telefono = telefono or None

            if cambios:
                bitacora = Bitacora(
                    id_usuario=usuario.id_usuario,
                    accion="edicion_perfil_propio",
                    descripcion=(
                        f"{usuario.nombre} actualizó su perfil ({', '.join(cambios)})."
                    ),
                    tabla_afectada="usuarios",
                    registro_id=usuario.id_usuario,
                )
                db.session.add(bitacora)

            db.session.commit()
            flash("Tus datos se actualizaron correctamente.", "success")
            return redirect(url_for(request.endpoint))

        if formulario == "contrasena":
            actual = request.form.get("contrasena_actual", "")
            nueva = request.form.get("nueva_contrasena", "")
            confirmar = request.form.get("confirmar_contrasena", "")

            if not usuario.check_password(actual):
                flash("La contraseña actual no es correcta.", "error")
                return redirect(url_for(request.endpoint))

            if len(nueva) < 8:
                flash("La nueva contraseña debe tener al menos 8 caracteres.", "error")
                return redirect(url_for(request.endpoint))

            if nueva != confirmar:
                flash("Las contraseñas nuevas no coinciden.", "error")
                return redirect(url_for(request.endpoint))

            usuario.set_password(nueva)

            bitacora = Bitacora(
                id_usuario=usuario.id_usuario,
                accion="cambio_contrasena_propia",
                descripcion=f"{usuario.nombre} cambió su propia contraseña.",
                tabla_afectada="usuarios",
                registro_id=usuario.id_usuario,
            )
            db.session.add(bitacora)
            db.session.commit()

            flash("Tu contraseña se actualizó correctamente.", "success")
            return redirect(url_for(request.endpoint))

    return render_template(template_name, usuario=usuario)
