# Script de arranque de S.A.D.E.: crea la app, asegura que existan las
# tablas de BD (no aplica migraciones sobre tablas ya existentes) y
# levanta el servidor de desarrollo de Flask.

from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    print("Base de datos creada correctamente")

if __name__ == "__main__":
    print("S.A.D.E. iniciando en http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)