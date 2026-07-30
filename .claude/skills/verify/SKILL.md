---
name: verify
description: Cómo levantar S.A.D.E. y verificar un cambio en caliente (no solo tests).
---

# Verificar S.A.D.E. en caliente

## Levantar el servidor

```bash
venv/Scripts/python run.py   # crea tablas si faltan (db.create_all) y sirve en :5000
```

Corre en foreground — lánzalo con `run_in_background` y lee el archivo de salida
para confirmar "Debugger is active!" antes de continuar. Detenlo con `TaskStop`
al terminar (no dejes el server ni el debugger huérfano).

`venv/Scripts/python seed.py` es idempotente: garantiza un usuario por rol.
Credenciales de prueba (fijas en seed.py): `agustin.coronel` / `sade2026` (admin),
`cesar.granados` / `sade2026` (conductor), `francisco.marroquin` / `sade2026` (mecánico).

## Superficie

App Flask con vistas Jinja + Bootstrap (server-rendered) y algunos endpoints JSON
(`/admin/dashboard/estado`, `/admin/vehiculos/placa-disponible`). La superficie real
es el navegador — usa `claude-in-chrome` para loguear y navegar, o `requests` en
Python (con manejo manual de `csrf_token` y cookies de sesión) para probar
endpoints/casos borde sin UI.

Patrón para pegarle a rutas protegidas con `requests`:

```python
import requests, re
s = requests.Session()
r = s.get('http://127.0.0.1:5000/login')
token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
s.post('http://127.0.0.1:5000/login', data={'csrf_token': token, 'nombre_usuario': '...', 'contrasena': '...'})
```

## Gotchas encontrados

- **Placas no se normalizan a mayúsculas al guardar** (`_datos_vehiculo_desde_formulario`
  en `app/controllers/admin.py`), y el `UNIQUE` de `Vehiculo.placas` en Postgres es
  case-sensitive por default. Un POST forzado con la misma placa en otro casing
  (`hgo-1206` vs `HGO-1206`) SÍ crea un vehículo duplicado real — el `IntegrityError`
  no lo detecta. El endpoint `/admin/vehiculos/placa-disponible` sí compara
  insensible a mayúsculas (usa `func.upper`), así que hay una brecha entre lo que la
  UX promete y lo que el backend realmente impide. Si tocas ese flujo, prueba
  explícitamente con un casing distinto al existente, no solo con la placa exacta.
- El scheduler (`revisar_viajes_activos`, cada 60s) puede generar alertas reales
  mientras el server está arriba para pruebas manuales — no asumas que las alertas
  nuevas que ves en el dashboard durante una verificación las creaste tú.
- Botones deshabilitados vía JS (ej. "Registrar vehículo" cuando hay placa
  duplicada) sí bloquean el submit del formulario incluso haciendo click con el
  mouse — confirmado que no navega ni envía.
