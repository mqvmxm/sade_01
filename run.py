from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    print("Base de datos creada correctamente")

if __name__ == "__main__":
    print("S.A.D.E. iniciando en http://127.0.0.1:5000")
    app.run(debug=True)
