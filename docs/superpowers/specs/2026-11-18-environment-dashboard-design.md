# Tablero de Gestión Ambiental — diseño

Segundo tablero de gobernar360. Se construye sobre la plataforma base descripta en
`2026-11-18-gobernar360-platform-design.md` y sigue el mismo contrato de módulo que el
Tablero de Proyectos. Referencia funcional: sección 5 y nota de +Comunidad en
`tableros-de-gestion-portal-ril.md`.

## Para qué

Que el municipio reúna en un solo lugar las variables de su agenda ambiental, las cargue
con frecuencia mensual o anual, y vea cuánto le falta para sus metas y qué datos todavía no
está relevando.

## Objetivos

- Definir variables propias dentro de siete categorías fijas.
- Cargar valores por período con el menor esfuerzo posible.
- Ver por categoría el valor del año contra la meta y el avance de la carga.
- Seguir la evolución de una variable en el tiempo.
- Aportar indicadores al dashboard general.

## Fuera de alcance en esta versión

- Desglose de una variable por punto de medición o dependencia: cada punto se carga como
  una variable propia ("Calidad del agua — punto X").
- Importación automática desde fuentes externas: todo se carga a mano.
- Metas distintas por año: cada variable tiene una sola meta anual.

Sería un fracaso que cargar los valores del mes lleve más tiempo que la planilla que el
municipio usa hoy.

## Enfoques

1. **Módulo propio con variables definidas por el municipio (elegido).** Categorías fijas,
   subcategorías y variables configurables, valores por período. Es lo que muestra RIL y
   encaja en el contrato de tableros existente.
2. Reusar los "indicadores estratégicos" de Proyectos. Descartado: esos indicadores tienen
   un único valor actual, sin historia por período, y los tableros no pueden depender uno
   de otro.
3. Catálogo fijo de variables igual para todos los municipios. Descartado: RIL deja que
   cada municipio configure las suyas, y los pilotos destacan justamente descubrir qué
   datos tiene y cuáles le faltan a cada uno.

## Modelo

Clave del tablero: `environment`. Tablas con prefijo `environment_`, todas con
`municipality_id` y seguridad a nivel de fila.

- **Categorías** (fijas, en código): `energy`, `waste`, `water`, `air`, `mobility`,
  `biodiversity`, `governance`.
- **Subcategoría**: categoría + nombre.
- **Variable**: subcategoría, nombre, unidad, frecuencia (`monthly` | `annual`), meta anual
  opcional, sentido (`higher_is_better` | `lower_is_better`), fuente (`municipal` |
  `external`) y forma de resumir el año (`sum` | `average` | `last`). La frecuencia no se
  puede cambiar después de crear la variable.
- **Valor**: variable, año, período (`0` = año completo, `1`–`12` = mes) y número. Uno por
  variable y período. Las variables anuales solo aceptan período 0 y las mensuales 1–12.

## Reglas

- **Valor del año:** para una variable anual, su valor. Para una mensual, la suma, el
  promedio o el último mes cargado, según la variable. Sin cargas no hay valor.
- **Cumplimiento:** con sentido "más es mejor", valor ÷ meta. Con "menos es mejor",
  meta ÷ valor (100 % si el valor es 0). Sin meta, sin valor o con meta 0 en "más es
  mejor", no se calcula.
- **Meta cumplida:** valor ≥ meta ("más es mejor") o valor ≤ meta ("menos es mejor").
- **Cargas:** cargadas sobre esperadas en el año: 12 por variable mensual, 1 por anual.
- No se puede borrar una subcategoría con variables ni una variable con valores.

## Permisos

Igual que Proyectos: lectura ve todo y descarga; carga además registra valores;
administración además gestiona subcategorías y variables.

## API (`/api/dashboards/environment`)

- `GET/POST /subcategories`, `PATCH/DELETE /subcategories/{id}`
- `GET/POST /variables`, `PATCH/DELETE /variables/{id}`
- `GET /values?year=` y `PUT /values` (guarda un valor; `null` lo borra)
- `GET /summary?year=` — por categoría y por variable: valor del año, meta, cumplimiento,
  cargas
- `GET /variables/{id}/series?year=` — meses del año elegido y valor anual de cada año con
  datos
- `GET /export/values.csv?year=`

## Pantallas

- **Resumen:** selector de año; tarjetas con variables, cargas del año, metas cumplidas y
  no cumplidas; una tabla por categoría con valor / meta, cumplimiento y cargas.
- **Seguimiento:** filtros de categoría, subcategoría, variable y año; vista mensual o
  anual; gráfico de línea con la meta como referencia y opción de ver como tabla.
- **Carga:** grilla del año, una fila por variable y una columna por mes (o una sola para
  las anuales); cada celda se guarda al salir de ella.
- **Parámetros:** por categoría, subcategorías y variables.

## Dashboard general

Para el año en curso: cantidad de variables, avance de la carga, metas cumplidas y metas
no cumplidas.

## Cambios en la base compartida

- Las utilidades que Proyectos tenía y ahora usan dos tableros pasan a la plataforma:
  tipos de esquemas comunes, respuesta CSV y la lista editable de la web.
- Al listar usuarios se ocultan los permisos sobre tableros que el municipio ya no tiene
  habilitados; hasta ahora esos permisos viejos impedían editar al usuario. Con un solo
  tablero no podía ocurrir.
- Los datos de ejemplo suman el tablero ambiental y se pueden agregar a una base ya
  cargada sin borrarla.
