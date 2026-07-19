from datetime import date

from app import create_app, db
from app.models.conductor import Conductor
from app.models.usuario import Usuario

app = create_app()


def crear_usuario(nombre, nombre_usuario, password, rol, id_conductor=None):
    if Usuario.query.filter_by(nombre_usuario=nombre_usuario).first():
        print(f"Usuario '{nombre_usuario}' ya existe, se omite.")
        return

    usuario = Usuario(
        nombre=nombre,
        nombre_usuario=nombre_usuario,
        rol=rol,
        id_conductor=id_conductor,
    )
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    print(f"Usuario creado: {usuario.nombre_usuario} (rol: {usuario.rol})")


with app.app_context():
    crear_usuario("Agustín Coronel", "agustin.coronel", "sade2026", "admin")

    conductor = Conductor.query.filter_by(num_licencia="GRAC-850312-H").first()
    if not conductor:
        conductor = Conductor(
            nombre="César Granados",
            telefono="771 234 5678",
            num_licencia="GRAC-850312-H",
            fecha_vencimiento_lic=date(2027, 3, 15),
            contacto_emergencia="Agustín Coronel",
            tel_emergencia="771 100 0000",
        )
        db.session.add(conductor)
        db.session.commit()

    crear_usuario(
        "César Granados",
        "cesar.granados",
        "sade2026",
        "conductor",
        id_conductor=conductor.id_conductor,
    )

    crear_usuario("Francisco Marroquín", "francisco.marroquin", "sade2026", "mecanico")
