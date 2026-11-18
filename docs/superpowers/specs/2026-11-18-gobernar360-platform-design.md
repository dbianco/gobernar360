# gobernar360 — plataforma base + Tablero de Proyectos

## Contexto

gobernar360 será un producto para muchos gobiernos locales (municipios y comunas): un espacio de trabajo donde conviven tableros de gestión independientes (trámites, social, económico, proyectos, ambiental, superficie edificada) y un dashboard general que resume sus indicadores. Cada tablero se habilita por municipio y por rol.

Hoy el repo solo contiene `tableros-de-gestion-portal-ril.md` (relevamiento de los tableros de RIL, que sirve de referencia funcional). GeoMiner (`/Users/daniel/src/geominer`) es un pipeline de línea de comandos en Python + PostGIS, sin web, API ni usuarios, y con un solo municipio.

Son varios proyectos, no uno. **Este plan cubre el primero:** la plataforma base y el Tablero de Gestión de Proyectos encima, más una primera versión del dashboard general. Los demás tableros se diseñan y construyen de a uno después, sobre la misma base.

## Decisiones tomadas por el usuario

- Producto para muchos municipios: datos aislados por municipio desde el inicio.
- Primer tablero: Proyectos.
- Enfoque: API en Python (FastAPI) + aplicación web separada en React.

## Enfoques considerados

| Enfoque | Ventaja | Costo |
|---|---|---|
| A. Django modular, pantallas en servidor | Lo más rápido; usuarios, permisos y migraciones incluidos | Interfaz menos fluida |
| **B. FastAPI + React (elegido)** | Interfaz más rica; API lista para integraciones | Usuarios, permisos y formularios a mano; dos despliegues |
| C. Django + React puntual | Punto medio | Dos formas de hacer pantallas |

Descartado: un producto separado por tablero con login compartido (costo de operación sin beneficio hoy).

## Decisiones mías (corregibles)

- **Repositorio único** con `backend/` y `frontend/`.
- **Backend:** Python 3.12, uv, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, Pydantic v2, pytest, ruff. Mismas bases que GeoMiner (Python 3.12, uv, PostGIS 16-3.4) para integrarlo luego.
- **Frontend:** React + TypeScript + Vite, React Router, TanStack Query, Mantine (componentes y formularios), Recharts (gráficos), Vitest.
- **Idioma:** código en inglés (identificadores, comentarios, mensajes, tests). Los textos de interfaz en español viven en un archivo de traducciones (`frontend/src/locales/es-AR.json`).
- **Aislamiento por municipio:** una sola base PostgreSQL/PostGIS; toda tabla de datos lleva `municipality_id`; seguridad a nivel de fila en la base (RLS), con el municipio fijado por transacción (`SET LOCAL app.municipality_id`). La API se conecta con un rol de base que no es dueño de las tablas.
- **Acceso:** login propio con email y contraseña (argon2), sesión guardada en la base y cookie `httpOnly`. Sin proveedor externo por ahora.
- **Roles:**
  - Operador de la plataforma: crea municipios y habilita tableros por municipio.
  - Administrador del municipio: gestiona usuarios y permisos de su municipio.
  - Por tablero, cada usuario tiene un nivel: sin acceso, lectura, carga, administración (este último gestiona los parámetros del tablero).
  - Un usuario puede pertenecer a más de un municipio y cambiar entre ellos.
- **Independencia de tableros:** los módulos solo dependen de la base, nunca entre sí; un test lo verifica (import-linter). Tablas con prefijo por módulo (`projects_*`).
- **Dashboard general:** cada módulo publica una función de indicadores resumidos; el dashboard muestra solo los de los tableros que el usuario puede ver.
- **Auditoría:** registro de quién creó y modificó cada dato, desde el inicio (lo va a exigir el tablero social).

## Estructura

```
backend/
  pyproject.toml, alembic.ini, migrations/
  src/gobernar360/
    main.py                  # app factory, registers dashboard modules
    core/                    # config, db session + RLS context, security
    platform/                # municipalities, users, sessions, memberships,
                             # dashboard grants, audit, summary registry
    dashboards/
      registry.py            # DashboardModule: key, router, summary provider
      projects/              # models, schemas, service, router, summary, export
  tests/
frontend/
  src/
    platform/                # shell, login, municipality switcher, user admin
    dashboards/
      registry.ts            # lazy routes + nav entries per dashboard key
      projects/
      overview/              # general dashboard
    locales/es-AR.json
docker-compose.yml           # postgis/postgis:16-3.4, api, web
docs/superpowers/specs/      # design doc
```

Contrato de un tablero (backend): `DashboardModule(key, router, get_summary(session) -> list[SummaryIndicator])`. Una dependencia de FastAPI `require_dashboard(key, level)` protege cada ruta. Sumar un tablero es crear una carpeta en `dashboards/` de cada lado y registrarla.

## Tablero de Proyectos — alcance v1

Basado en la sección 4 del relevamiento de RIL.

- **Gestiones** (períodos de gobierno) con opción de cambiar la gestión activa.
- **Parámetros** (los administra el municipio): ejes, objetivos (por eje), dependencias, programas, responsables. Fijos: prioridades (A+, A, B, C) y los 17 ODS.
- **Proyectos:** nombre, descripción, eje, objetivo, dependencia, responsable, programa, prioridad, año, fechas, presupuesto planificado y ejecutado, ODS asociados.
- **Hitos** por proyecto: fecha comprometida y estado; "en alerta" si venció sin finalizar.
- **Indicadores estratégicos** por objetivo: unidad, línea de base, meta, valor actual.
- **Resumen:** proyectos por estado, presupuesto (total, % planificado, % ejecutado), activos y finalizados, avance promedio, hitos finalizados/total y en alerta, distribución por dependencia, responsable, programa y ODS. Filtros: año, eje, dependencia, responsable, prioridad.
- **Exportación** a CSV de proyectos e indicadores.

Reglas que defino yo:
- Estado guardado: sin iniciar, en implementación, finalizado. "Retrasado" se calcula: fecha de fin vencida sin finalizar, o algún hito en alerta.
- Avance: porcentaje de hitos finalizados; si no hay hitos, se carga a mano.

**Fuera de alcance en esta etapa:** los otros tableros, la integración de GeoMiner, importación masiva, login con proveedor externo, vistas públicas, facturación.

## Etapas

1. **Arranque del repo:** `git init`, guardar el diseño en `docs/superpowers/specs/2026-11-18-gobernar360-platform-design.md`, esqueleto de `backend/` y `frontend/`, `docker-compose.yml`, ruff, pytest, vitest.
2. **Base, backend:** municipios, usuarios, sesiones, pertenencias, permisos por tablero, RLS, auditoría, API de administración, comando para crear el operador y un municipio de ejemplo.
3. **Base, frontend:** login, selector de municipio, navegación que muestra solo los tableros permitidos, administración de usuarios y permisos.
4. **Proyectos, backend:** modelo, migraciones, API, cálculo de resumen, exportación.
5. **Proyectos, frontend:** resumen con filtros y gráficos, listados y formularios de proyectos, hitos, indicadores y parámetros.
6. **Dashboard general:** registro de indicadores resumidos y pantalla de inicio.
7. **Datos de ejemplo y verificación de punta a punta.**

Cada etapa se desarrolla con tests primero. Antes de implementar, el detalle tarea por tarea se escribe con `superpowers:writing-plans` a partir del documento de diseño.

## Verificación

- `docker compose up` levanta base, API y web.
- `uv run pytest` en `backend/`, contra PostGIS real. Incluye tests de aislamiento: un usuario del municipio A no puede leer ni modificar datos del municipio B, ni siquiera con una consulta sin filtro (lo impide RLS); y tests de permisos por nivel en cada ruta.
- `npm test` en `frontend/`.
- Recorrido en navegador (Playwright) con datos de ejemplo: el operador crea dos municipios; en uno, un usuario de carga crea un proyecto con hitos y ve el resumen actualizado; un usuario de lectura no puede editar; un usuario sin permiso no ve el tablero en la navegación; el dashboard general muestra los indicadores de Proyectos; el usuario del segundo municipio no ve nada del primero.
- Test que falla si un módulo de tablero importa a otro.
