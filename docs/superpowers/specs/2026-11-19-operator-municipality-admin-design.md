# Configuración de municipios por el super-admin — diseño

Cambio chico sobre la plataforma base (`2026-11-18-gobernar360-platform-design.md`). En el
código el super-admin se llama "operador de la plataforma" (`is_platform_operator`).

## Para qué

El super-admin da de alta cada municipio y tiene que poder manejar toda su configuración:
datos, tableros disponibles y usuarios. El administrador de un municipio maneja un
subconjunto: solo los usuarios y permisos del suyo. Ningún municipio ve datos de otro.

## Qué existe hoy

- Aislamiento por municipio con seguridad a nivel de fila en la base.
- El operador crea municipios, habilita tableros y crea un primer administrador.
- El administrador del municipio lista, agrega, modifica y quita usuarios del suyo.

## Qué falta (alcance)

1. El operador edita el nombre y el tipo de un municipio. El identificador (`slug`) no
   cambia.
2. El operador maneja los usuarios de cualquier municipio con las mismas operaciones y
   reglas que el administrador local: listar, agregar, cambiar permisos, dar o quitar el
   rol de administrador y quitar. Vale la regla de que el municipio conserva al menos un
   administrador una vez que tiene uno.
3. El operador puede poner una contraseña nueva a un usuario de un municipio; eso cierra
   todas las sesiones de esa cuenta. El alta de "primer administrador" se elimina: el
   primer administrador se crea como cualquier usuario, marcándolo administrador.
4. Cuentas que ya existen. Las cuentas son globales y la contraseña la eligió quien
   registró el email primero, que puede no ser su dueño. Por eso:
   - El administrador de un municipio no puede agregar un email que ya tiene cuenta; se
     le indica que lo pida al operador. (Antes podía, y eso permitía que quien había
     registrado el email entrara al municipio ajeno.)
   - El operador sí puede, y debe elegir: conservar la contraseña de la cuenta o
     reemplazarla por la que escribe, lo que cierra sus sesiones. El reemplazo queda en
     auditoría.

## Fuera de alcance

- Baja o suspensión de municipios.
- Que el administrador local cambie nombre, tipo o tableros de su municipio.
- Que el operador vea datos de los tableros: solo ve configuración. Para ver datos se
  agrega como usuario del municipio.
- Cuentas separadas por municipio: las cuentas siguen siendo globales. Quien intenta
  agregar un email ya registrado se entera de que existe una cuenta, nada más.
- Que el administrador local cambie contraseñas: como las cuentas son globales, le
  permitiría tomar la cuenta de alguien de otro municipio.

## Enfoques

1. **Mismas rutas de usuarios montadas dos veces (elegido).** Un único conjunto de rutas
   de usuarios, armado por una función que recibe de dónde sale el municipio: del
   municipio activo para el administrador (`/api/admin/...`) o de la dirección para el
   operador (`/api/platform/municipalities/{id}/...`). Las reglas no se pueden desalinear.
2. Rutas del operador escritas aparte. Descartado: duplica validaciones y reglas.
3. Que el operador "entre" al municipio como si fuera administrador. Descartado: le daría
   acceso a los datos de los tableros, que queda fuera de alcance.

## API

- `PATCH /api/platform/municipalities/{id}` — `name` y/o `kind`; cualquier otro campo se
  rechaza.
- `GET /api/platform/municipalities/{id}/dashboards` — tableros habilitados (ya existe el
  `PUT`).
- `GET/POST /api/platform/municipalities/{id}/users`
- `PATCH/DELETE /api/platform/municipalities/{id}/users/{membership_id}`
- `PUT /api/platform/municipalities/{id}/users/{membership_id}/password`
- Se elimina `POST /api/platform/municipalities/{id}/admins`.

Los cambios de usuarios que hace el operador quedan en el registro de auditoría del
municipio, a nombre del operador.

## Pantallas

- **Municipios** (`/platform`): lista con nombre, tipo e identificador, enlace a la
  configuración de cada uno y el formulario de alta.
- **Configuración de un municipio** (`/platform/municipalities/{id}`): datos (nombre y
  tipo), tableros habilitados y usuarios. La tabla de usuarios es la misma que usa el
  administrador local, más el botón para cambiar la contraseña.
