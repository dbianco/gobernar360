# Informe mensual y página pública — diseño

Tarea `docs/tasks/05-monthly-report-and-public-page.md`. Usa las fotos mensuales, el
catálogo y las metas de la tarea 02 (`2026-11-23-indicator-history-and-targets-design.md`).

## Para qué

Un municipio no puede entregar "el estado de la gestión de octubre" al concejo o a la
prensa, ni mostrar nada a los vecinos. Esta tarea agrega un informe mensual que se cierra
y se guarda, y una página pública donde el municipio decide qué mostrar.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** cerrar un mes y congelar su informe; reabrirlo solo explícitamente, con
  auditoría y una versión nueva; PDF generado en el servidor, legible en blanco y negro y
  determinístico; página pública opt-in en tres niveles (municipio, tablero, indicador),
  servida desde copias; enmascarar conteos chicos.
- **No objetivos:** temas por municipio, comentarios de vecinos, descargas masivas de datos
  abiertos, informes por área.
- **Anti-objetivos:** que una ruta pública lea tablas del municipio; que se publique un
  indicador que no es agregado, un texto reservado o un dato del padrón de personas; que un
  informe cerrado cambie al editar datos; que un municipio vea lo de otro.

## Informe mensual

- Lo cierra quien administra el municipio, para un mes ya terminado. Cada cierre es una
  versión (`monthly_reports`, dato del municipio con RLS) con su contenido congelado en
  JSON: semáforo de cada tablero, sus indicadores con valor al cierre del mes (foto de la
  tarea 02), variación contra el mes anterior, meta y serie de 12 meses, y las tablas que
  cada tablero aporte (Proyectos: hitos alcanzados y vencidos en el mes). Los nombres de
  tableros e indicadores también quedan congelados.
- Un comentario por tablero, escrito al cerrar.
- **Reabrir** marca la versión como reemplazada y crea la siguiente como borrador con los
  mismos comentarios; al cerrarla se congela de nuevo. Ambas cosas quedan en la auditoría.
- Los tableros aportan tablas por el contrato del registro (`report_tables`), así la
  plataforma no importa ningún tablero.

## PDF

- `fpdf2` con las fuentes base del PDF (sin archivos de fuente): el resultado no depende
  de la máquina. La fecha del documento es la del cierre, así el mismo informe da siempre
  los mismos bytes.
- A4, nombre del municipio, tabla resumen de semáforos, una sección por tablero con
  tabla de indicadores y minigráfico de 12 meses con la línea de meta, comentario y tablas
  del tablero. Números y fechas en formato argentino (`1.234,5`, `03/11/2026`).
- Cada semáforo lleva una marca dibujada (tilde, advertencia, cruz) y el nombre del estado:
  en blanco y negro se distingue igual.

## Publicación

- **Selección** (datos del municipio con RLS): `public_settings` (página activa, dirección
  pública, umbral de conteos chicos), `published_dashboards`, `published_indicators` y la
  marca `published` de cada informe.
- **Copias** (`public_sites`, `public_dashboards`, `public_indicators`, `public_reports`):
  se escriben al publicar, al cambiar la selección y en cada corrida de
  `snapshot-indicators`. Se leen sin municipio fijado; solo la API puede escribirlas y solo
  las filas de su propio municipio (política de RLS por comando).
- Despublicar, apagar la página o reabrir un informe borra las copias en el momento.
- Solo se pueden publicar indicadores declarados `aggregate` en el catálogo. Los conteos
  entre 1 y el umbral menos uno se muestran como "menos de N", también en su serie; su
  variación y desvío no se muestran.
- El PDF publicado es una versión aparte del informe, con los conteos chicos enmascarados.
  Antes de publicar un informe se revisa que sus comentarios no tengan nombres ni números de
  documento del padrón de personas.

## Página pública

- `/p/<dirección>` funciona sin sesión: semáforos e indicadores publicados con su evolución
  y la lista de informes para descargar.
- La sirven rutas `/api/public/...` que se conectan con un rol de base de datos propio
  (`gobernar360_public`) que solo puede leer las tablas de copias. Tienen límite de pedidos
  por minuto y se pueden cachear (`ETag`, revalidando siempre, así despublicar se ve en el
  momento).
- Una dirección inexistente, de una página apagada o un indicador no publicado responden
  404, sin distinguir entre los casos.

## Datos de ejemplo

Noetinger tiene informes cerrados de meses anteriores (no del mes pasado, para poder
cerrarlo a mano) y la página pública activa en `noetinger` con Proyectos y Social
publicados, sin indicadores ni informes publicados. Comuna Demo no tiene nada de esto.
