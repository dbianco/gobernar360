# Tablero Económico y padrón de personas — diseño

Tercer tablero sobre la plataforma (`2026-11-18-gobernar360-platform-design.md`). Basado en
la sección "Desarrollo económico" de `tableros-de-gestion-portal-ril.md`.

## Para qué

El área de desarrollo económico del municipio necesita saber a quién asiste y con qué:
qué empresas, comercios y emprendedores (actores) y qué personas tiene registrados, qué
herramientas ofrece (créditos, capacitaciones, programas) y a quién se las asignó.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** registrar actores, personas, herramientas y asignaciones; ver un resumen
  y reportes por año; descargar los datos.
- **No objetivos:** importación masiva (proyecto aparte); estado, monto o seguimiento de
  una asignación; que otros tableros usen todavía el padrón.
- **Anti-objetivos:** que un tablero muestre personas que no incorporó; que un municipio
  vea personas de otro; que una persona quede duplicada por tener el mismo DNI.

## Enfoques para las personas

1. **Padrón único por municipio en la plataforma (elegido por el usuario).** Los datos
   comunes de una persona viven una sola vez; cada tablero guarda aparte lo propio y solo
   lista a las personas que incorporó. El tablero Social va a reusar el mismo padrón.
2. Personas propias de cada tablero. Descartado: duplica personas entre Económico y Social.
3. Padrón único visible completo desde cualquier tablero. Descartado: un usuario del
   tablero Económico vería a todas las personas asistidas por Social.

## Padrón de personas (plataforma)

Tabla `people`, aislada por municipio como el resto de los datos.

- Datos comunes: nombre, apellido, DNI (opcional, único por municipio), fecha de
  nacimiento, teléfono, email, domicilio, barrio.
- El DNI se guarda solo con dígitos (se aceptan puntos y espacios al escribirlo), de 6 a
  9 dígitos.
- No tiene pantalla ni rutas propias: se llega siempre a través de un tablero.
- Un tablero puede buscar en el padrón solo por DNI exacto. Si la persona existe, la
  reusa; el formulario muestra sus datos antes de guardar.
- Los datos comunes los edita cualquier usuario con nivel de carga en un tablero que
  haya incorporado a esa persona.
- Al quitar a una persona de un tablero, si ningún otro registro la usa, se borra
  también del padrón: no quedan datos personales que nadie puede ver.

## Tablero Económico

Clave `economic`. Niveles: lectura ve y descarga; carga gestiona actores, personas y
asignaciones; administración gestiona herramientas y parámetros.

- **Parámetros** (listas del municipio): tipos de actor, sectores, categorías de
  herramienta y subcategorías dentro de cada categoría.
- **Herramientas:** nombre, descripción, categoría, subcategoría (opcional) y
  destinatarios: actores, personas o ambos.
- **Actores:** nombre, tipo y sector (opcionales), CUIT (11 dígitos, opcional),
  domicilio, teléfono, email, cantidad de empleados, notas. Personas vinculadas, cada
  una con un rol: titular, contacto o empleado.
- **Personas:** los datos del padrón más situación laboral (lista fija: sin datos,
  en relación de dependencia, independiente, desocupado, estudiante, jubilado, otra) y
  ocupación.
- **Asignaciones:** herramienta, un actor o una persona, fecha y nota. La herramienta
  tiene que admitir ese tipo de destinatario. Después de creada solo cambian fecha y nota.
- **Resumen** (por año): actores y personas registrados y cuántos recibieron alguna
  herramienta ese año; herramientas; asignaciones del año; dos tablas de asignaciones por
  herramienta, una para actores y otra para personas.
- **Reportes** (por año): actores por tipo y por sector, personas por situación laboral,
  asignaciones por categoría y por mes.
- **Descargas** CSV: actores, personas, asignaciones del año.
- **Resumen general:** actores, personas, herramientas y asignaciones del año.

Reglas:

- Las listas de actores, personas y asignaciones se paginan (50 por página) y se buscan
  por texto: nombre o CUIT, y nombre, apellido o DNI.
- No se puede borrar un parámetro o una herramienta en uso, ni un actor o una persona
  con asignaciones. Borrar un actor o una persona quita sus vínculos.
- Agregar una persona con un DNI que ya está en el padrón la reusa y actualiza sus datos
  comunes con los enviados; si ya estaba en el tablero, se rechaza.

## Pantallas

Pestañas: Resumen, Actores, Personas, Asignaciones, Reportes, Parámetros (solo
administración). Actores y Personas son lista más ficha; desde la ficha se vinculan
personas y se cargan asignaciones.

## Datos de ejemplo

Noetinger recibe actores, personas, herramientas y asignaciones de este año y del
anterior. Comuna Demo queda con el tablero habilitado y vacío. Como con Ambiental, una
base de ejemplo anterior gana el tablero una sola vez sin tocar lo demás.

## Queda a criterio de quien construye

Nombres de tablas y rutas, forma exacta de las respuestas, textos de interfaz y el
contenido de los datos de ejemplo.
