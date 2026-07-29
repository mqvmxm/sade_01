# S.A.D.E. — Sistema de Administración de Disponibilidad y Emergencias

Aplicación web (Flask) para administrar una flota de vehículos: registra viajes de
conductores, vigila que no se retrasen sobre su hora estimada de llegada, permite reportar
averías de vehículos y ofrece un aviso silencioso de emergencia que notifica por WhatsApp y
SMS con la ubicación del conductor.

## Problema que resuelve

Una flota sin monitoreo depende de que el conductor avise por su cuenta si algo sale mal — un
retraso, una avería, una emergencia en carretera. S.A.D.E. centraliza esa información: valida
que la licencia del conductor esté vigente antes de dejarlo salir a ruta, revisa
automáticamente cada minuto si algún viaje activo ya superó su hora estimada de llegada, y le
da al conductor una forma discreta de pedir ayuda sin tener que hablar ni sacar el teléfono a
la vista, mientras el administrador ve todo desde un panel central.

## Roles

La aplicación tiene tres roles, cada uno con su propio panel:

- **Administrador** — gestiona conductores, vehículos y cuentas de mecánico; da de alta
  cuentas de conductor y mecánico; monitorea viajes activos, alertas y emergencias en tiempo
  real; puede cerrar viajes manualmente o de forma forzada; consulta el Historial de eventos y
  la Bitácora de auditoría.
- **Conductor** — hace check-in de un viaje (origen, destino, hora estimada de llegada),
  confirma su llegada, y cuenta con el aviso silencioso de emergencia. No puede iniciar un
  viaje si su licencia está vencida.
- **Mecánico** — consulta el estado de los vehículos de la flota, cambia su estado entre
  disponible y en taller, y registra reportes de avería sobre el vehículo de un viaje en curso.

La cuenta de administrador **no se crea desde el navegador**: es intencional, para no exponer
esa superficie de ataque. Se crea desde la terminal del servidor con `flask crear-admin` (ver
más abajo).

## Stack tecnológico

- **Backend**: Flask, Flask-Login (sesiones y roles), Flask-SQLAlchemy (ORM)
- **Base de datos**: PostgreSQL (vía `psycopg2-binary`)
- **Notificaciones**: Twilio (WhatsApp y SMS) para el aviso de emergencia
- **Tareas periódicas**: APScheduler, revisa cada 60 segundos los viajes activos que ya
  superaron su hora estimada de llegada
- **Frontend**: Jinja2 + Bootstrap 5 (sin build step ni framework de JS)
- **Config**: variables de entorno vía `python-dotenv` (`.env`)

No hay una herramienta de migraciones (ni Alembic ni Flask-Migrate): los cambios de esquema se
hacen editando los modelos y volviendo a correr `db.create_all()`, que solo crea las tablas que
falten — **no altera** tablas ya existentes. Un cambio de columna sobre una tabla que ya existe
requiere un `ALTER TABLE` manual.

## Instalación desde cero

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd sade
```

### 2. Crear y activar el entorno virtual

```bash
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Windows (Git Bash)
venv/Scripts/activate

# Linux/macOS
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Crear la base de datos

Necesitas una instancia de PostgreSQL corriendo, y una base de datos vacía creada de antemano
(la app no la crea por ti, solo crea las tablas dentro de ella):

```sql
CREATE DATABASE sade_db;
```

### 5. Configurar las variables de entorno

Copia `.env.example` a `.env` y completa los valores:

```bash
cp .env.example .env
```

Como mínimo, ajusta `SECRET_KEY` (una clave propia, no la de ejemplo) y los datos de conexión a
tu base de datos (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, o bien un único
`DATABASE_URL`). El resto de variables (Twilio, correo) pueden dejarse vacías mientras
`SIMULATE_TWILIO` y `EMAIL_SIMULATE` estén en `True` — ver la sección siguiente.

### 6. Crear las tablas y levantar el servidor

```bash
python run.py
```

Esto crea las tablas que falten en la base de datos configurada e inicia el servidor de
desarrollo en `http://0.0.0.0:5000`.

### 7. Crear la cuenta de administrador

En otra terminal, con el entorno virtual activado:

```bash
flask --app run.py crear-admin
```

El comando pide nombre, nombre de usuario, correo y contraseña de forma interactiva, y crea la
cuenta directamente en la base de datos.

### (Opcional) Datos de prueba

`seed.py` crea de forma idempotente un usuario de cada rol (admin, conductor, mecánico) para
poder probar el login de los tres sin registrar cuentas manualmente:

```bash
python seed.py
```

Las contraseñas que genera son de ejemplo y quedan visibles en el propio script — úsalo solo en
un entorno de desarrollo, nunca contra una base de datos real.

## Modos simulados (SIMULATE_TWILIO / EMAIL_SIMULATE)

Por defecto (`SIMULATE_TWILIO=True`, `EMAIL_SIMULATE=True` en `.env`), la aplicación **no** se
conecta a Twilio ni a un servidor SMTP real: el envío de WhatsApp, SMS y correo de recuperación
de contraseña se simula imprimiendo el mensaje en la consola del servidor. Esto permite
desarrollar y probar los flujos completos (aviso de emergencia, "olvidé mi contraseña") sin
necesidad de credenciales reales.

La simulación reemplaza únicamente la llamada al proveedor externo — la validación del
destinatario (número de teléfono o correo con formato inválido) falla igual en modo simulado
que en modo real.

Para usar credenciales reales, pon `SIMULATE_TWILIO=False` / `EMAIL_SIMULATE=False` en `.env` y
completa las variables correspondientes (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_WHATSAPP_FROM`, `TWILIO_SMS_FROM`, `ADMIN_PHONE_NUMBER`, `EMAIL_HOST`, `EMAIL_PORT`,
`EMAIL_USER`, `EMAIL_PASSWORD`, `EMAIL_FROM`).
