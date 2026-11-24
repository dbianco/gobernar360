# Historia de indicadores, metas e indicadores combinados — diseño

Tarea `docs/tasks/02-indicator-history-and-targets.md`. Cruza la plataforma
(`2026-11-18-gobernar360-platform-design.md`) y sus cinco tableros.

## Para qué

Los indicadores principales se calculan en el momento y no se guardan: se ve que hay 4
proyectos retrasados, pero no si es mejor o peor que el mes pasado ni cuánto falta para la
meta. El semáforo mensual no tiene números al lado.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** una foto mensual de cada indicador de cada tablero habilitado; un catálogo
  de indicadores que cada tablero declara; metas por indicador y año; evolución (valor
  actual, variación contra el mes anterior y contra el mismo mes del año anterior, serie
  de doce meses, línea de meta) en el resumen de cada tablero y en el general; números del
  mes junto a cada semáforo; indicadores que combinan tableros en el resumen general.
- **No objetivos:** pronósticos, avisos por correo (tarea 01), desagregar indicadores por
  área o eje, metas para los indicadores combinados, metas prorrateadas por mes.
- **Anti-objetivos:** que la plataforma importe un tablero; que un municipio vea o reciba
  fotos de otro; rellenar un mes pasado con el valor de hoy; mostrar un indicador combinado
  a quien no ve alguno de sus tableros.

## Catálogo

Cada `DashboardModule` declara `indicators`: clave, unidad (`None` = cantidad, `percent`,
`ratio`), si más alto es mejor, y si se puede **reconstruir** hacia atrás.
`get_summary(ctx, fecha)` sigue siendo la única función que calcula: devuelve los valores
"a esa fecha". Un indicador es reconstruible solo si sale de registros con fecha propia
(prestaciones, intervenciones y asignaciones del año hasta la fecha). Los que dependen del
estado actual (proyectos finalizados, actores cargados, trámites vigentes, metas
ambientales) no lo son.

## Fotos mensuales

- Tabla `indicator_snapshots` (dato del municipio, con RLS): municipio, tablero,
  indicador, año, mes, valor (puede ser nulo: "sin valor ese mes").
- `gobernar360 snapshot-indicators` recorre los municipios; cada uno en su propia
  transacción con el rol de la API y el municipio fijado. Guarda el **mes en curso** con
  todos los indicadores a la fecha de hoy; al correrlo cada día (o al menos el último día
  del mes) la fila del mes queda con el valor del cierre.
- `--from AAAA-MM` además recalcula los meses cerrados desde ese mes, al último día de
  cada uno, **solo para los indicadores reconstruibles**. Los otros no se tocan: si ya había
  una foto tomada en su momento queda, y si no, el mes queda vacío.
- Es idempotente: una fila por municipio, indicador y mes, escrita con `ON CONFLICT`.

## Metas

Tabla `indicator_targets` (con RLS y auditoría): municipio, tablero, indicador, año, valor.
La cambia quien administra el tablero, desde sus Parámetros. El desvío se calcula con el
sentido del indicador: positivo es mejor que la meta y negativo peor, así que "proyectos
retrasados" 6 con meta 4 da desvío −2 y "fuera de meta". La meta de un mes es la de su año.

## Evolución

Para cada indicador: valor actual (en vivo), valor y variación contra el cierre del mes
anterior y contra el mismo mes del año anterior, serie de los últimos doce meses (el último
es el valor actual) con la meta de cada mes, meta del año, desvío y si está en meta.

- Resumen de cada tablero: tarjetas con variación y minigráfico; al abrir una tarjeta, la
  serie con su línea de meta (y la misma información en tabla).
- La tira del semáforo muestra debajo de cada mes los números de ese mes.
- Resumen general: las mismas tarjetas por tablero y una sección de indicadores
  combinados.

## Indicadores combinados

Definidos en la plataforma como cociente de dos claves del catálogo, por ejemplo trámites en
línea por actor económico y prestaciones sociales del año por proyecto activo. Se muestran
solo si los dos tableros están habilitados y quien mira tiene acceso a ambos. Su historia
sale de las fotos de sus dos componentes.

## Datos de ejemplo

Noetinger recibe doce meses de historia de todos sus indicadores y metas del año actual y
del anterior; una base de ejemplo anterior la gana una sola vez.
