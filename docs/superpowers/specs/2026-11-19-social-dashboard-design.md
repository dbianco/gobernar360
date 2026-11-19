# Tablero Social — diseño

Cuarto tablero sobre la plataforma (`2026-11-18-gobernar360-platform-design.md`). Reusa el
padrón de personas de `2026-11-19-economic-dashboard-design.md`. Basado en la sección
"Desarrollo social" de `tableros-de-gestion-portal-ril.md`.

## Para qué

El área social registra a quién asiste y cómo: personas, sus grupos familiares, lo que se
les entrega (prestaciones) y lo que el equipo hace con ellas (intervenciones). El valor
está en ver en un solo lugar todo lo hecho con una persona o una familia.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** registrar personas, grupos familiares, entregas de prestaciones e
  intervenciones; ver la historia de una persona y de un grupo; resumen y reportes por
  año; descargar los datos.
- **No objetivos:** stock de prestaciones ("disponibles por categoría" en la referencia);
  áreas del municipio con datos separados dentro del tablero; importación masiva; turnos
  o seguimiento de casos con estados.
- **Anti-objetivos:** que el nivel de lectura vea el texto de una intervención; que el
  tablero muestre personas que no incorporó (por ejemplo las de Económico); que un
  municipio vea datos de otro; que una persona quede duplicada por DNI.

## Enfoques

1. **Mismo patrón que Económico (elegido).** Las personas entran por una tabla propia del
   tablero que apunta al padrón; todo lo demás apunta a esa tabla. El grupo familiar se
   guarda en esa misma fila, porque una persona está en un solo grupo.
2. Grupo familiar en el padrón, compartido entre tableros. Descartado: Económico vería con
   quién vive una persona asistida por Social.
3. Pertenencia a varios grupos con una tabla intermedia. Descartado: nadie lo pidió y
   complica la ficha y los conteos.

Para el texto de las intervenciones el usuario eligió: lo leen solo quienes tienen nivel
de carga o administración.

## Datos

Clave `social`. Niveles: lectura ve y descarga; carga gestiona personas, grupos, entregas
e intervenciones; administración gestiona los catálogos.

- **Catálogos del municipio:** categorías de prestación; prestaciones (categoría, nombre,
  descripción); tipos de intervención.
- **Personas:** los datos del padrón. Lo propio del tablero es el grupo familiar y el
  parentesco.
- **Grupos familiares:** nombre, domicilio, barrio. Integrantes: personas del tablero,
  cada una con un parentesco de una lista fija: referente, cónyuge o pareja, hijo/a,
  padre o madre, hermano/a, abuelo/a, nieto/a, otro familiar, no familiar.
- **Entregas:** prestación, persona, fecha, cantidad (entero, 1 o más; por defecto 1) y
  nota. Después de creada cambian fecha, cantidad y nota.
- **Intervenciones:** tipo, persona, fecha, descripción y quién la hizo (texto libre).
  Después de creada cambian fecha, descripción y quién la hizo.

Reglas:

- Un grupo tiene a lo sumo un referente. Una persona está en un solo grupo: para pasarla
  a otro hay que quitarla primero del actual.
- Borrar un grupo deja a sus integrantes sin grupo; no borra personas.
- No se borra un catálogo en uso, ni una persona con entregas o intervenciones.
- Quitar una persona del tablero la quita de su grupo y, si nadie más la usa, del padrón.
- Agregar una persona con un DNI que ya está en el padrón la reusa, igual que en Económico.
- Las listas de personas, grupos, entregas e intervenciones se paginan (50 por página).
  Personas se busca por nombre, apellido o DNI y se filtra por barrio; grupos, por nombre
  o domicilio.
- **Texto reservado:** con nivel de lectura, la descripción de una intervención no sale
  de la API: ni en listas, ni en la ficha, ni en la descarga (la columna no existe). Se
  ve que hubo una intervención, su tipo, fecha y quién la hizo.

## Resumen, reportes y descargas

- **Resumen** (por año): personas y grupos registrados; personas que recibieron alguna
  prestación en el año; entregas del año y unidades entregadas; intervenciones del año;
  tabla de prestaciones (categoría, entregas, unidades) y tabla de intervenciones por tipo.
- **Reportes** (por año): entregas por categoría y por mes, intervenciones por tipo y por
  mes, personas por barrio y entregas por barrio (el barrio es el de la persona; sin
  barrio se agrupa aparte).
- **Descargas** CSV: personas (con grupo y parentesco), grupos, entregas del año,
  intervenciones del año.
- **Resumen general:** personas, grupos, entregas del año, intervenciones del año.

## Pantallas

Pestañas: Resumen, Personas, Grupos familiares, Prestaciones, Intervenciones, Reportes,
Parámetros (solo administración).

- **Ficha de persona:** datos, grupo y parentesco, historia de entregas e intervenciones,
  con alta desde ahí.
- **Ficha de grupo:** datos, integrantes (agregar buscando entre las personas del tablero,
  cambiar parentesco, quitar) y la historia de entregas e intervenciones de todos.
- **Prestaciones** e **Intervenciones:** listas del año con filtros y alta eligiendo la
  persona.
- Con nivel de lectura, donde iría la descripción se lee "Reservado".

## Datos de ejemplo

Noetinger recibe catálogos, personas (algunas compartidas con Económico por DNI), grupos,
entregas e intervenciones de este año y del anterior. Comuna Demo queda con el tablero
habilitado y vacío. Una base de ejemplo anterior gana el tablero una sola vez.

## Queda a criterio de quien construye

Nombres de tablas y rutas, forma exacta de las respuestas, textos de interfaz y el
contenido de los datos de ejemplo.
