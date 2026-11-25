# Gabinete: reuniones y compromisos — diseño

> Los compromisos pasaron después a la plataforma: ver
> `2026-11-24-commitments-and-notices-design.md`. Lo que sigue sobre quién los ve, quién los
> cambia y dónde se guardan queda reemplazado por ese documento.

Tarea: `docs/tasks/04-cabinet-commitments.md`. Sexto tablero (clave `cabinet`) y una pieza
nueva de la plataforma (`2026-11-18-gobernar360-platform-design.md`): los sujetos vinculables.

## Para qué

Los tableros dicen qué anda mal; no qué se acordó hacer, quién y para cuándo. El tablero
guarda las reuniones de gabinete y sus compromisos, y los muestra al lado de aquello de lo
que tratan: el semáforo de un mes o un proyecto.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** reuniones con temario, notas y acta; compromisos con responsable, fecha,
  estado, historial y cuenta de postergaciones; temario propuesto; vínculo con los demás
  tableros en los dos sentidos; seguimiento, resumen general y CSV.
- **No objetivos:** calendario, votaciones, adjuntos, avisos por correo de compromisos
  vencidos (los puede sumar `get_alerts` más adelante).
- **Anti-objetivos:** que `cabinet` importe otro tablero; vincular algo de otro municipio;
  que un vínculo revele qué es lo vinculado a quien no puede verlo; que un acta cambie.

## Sujetos vinculables (plataforma)

- Un sujeto es (tablero, clase, referencia). Todo tablero tiene la clase `month`, sin
  declarar nada: el mes y su semáforo (`2026-10`). Las demás las declara en el registro:
  `DashboardModule.linkable`, una tupla de `LinkableRecord(kind, search, describe,
  min_level)`: cómo buscarlas, cómo nombrarlas y quién las puede ver. Proyectos declara
  `project` en `dashboards/projects/subjects.py`.
- `platform/subjects.py` es el único que decide. Al escribir, `resolve` acepta solo lo que
  existe en el municipio y la persona puede ver; las dos fallas responden igual, así que
  probar referencias no revela nada. No hay clave foránea: sería de una tabla de otro
  tablero, y las claves foráneas no pasan por la seguridad por fila.
- Al leer, `present` muestra el sujeto solo a quien puede verlo. El resto recibe
  `access: restricted` y la clase, sin nombre, referencia, color ni si todavía existe. De
  un mes no se dice ni el tablero. Lo borrado dice `deleted`, solo a quien podía verlo.
- **Vista inversa:** un tablero puede dar `get_commitments` en el registro. `/api/subjects/...`
  junta los de todos y los muestran `StatusStrip` y `<SubjectCommitments>`, sin saber quién
  los guarda. Hace falta ver el sujeto **y** tener acceso al tablero que guarda los
  compromisos: lo que acuerda el gabinete no se publica a quien no tiene ese tablero. Sin
  ese acceso la respuesta es una lista vacía, no un error.
- Agregar algo vinculable: declarar `linkable` y, si se quiere, sus textos en
  `subjects.kinds|restricted|deleted.<tablero>.<clase>` (en los dos archivos de textos; sin
  ellos se usa «registro»). El tablero de gabinete no se toca.

## Reuniones

- Un municipio tiene **una sola reunión abierta** (índice único parcial) y ninguna se fecha
  antes de la última. Así «la anterior» y «la próxima» no son ambiguas.
- Crear la reunión acepta el temario y arrastra los compromisos abiertos. Ver la propuesta
  no cambia nada. Solo se acepta lo que se propone en ese momento: la API vuelve a calcular.
- Toda escritura carga la reunión con `FOR UPDATE`, así nada entra mientras se cierra.
- **Acta:** al cerrar se copia todo (`cabinet_meetings.minutes`), con el nombre de lo
  vinculado aunque quien cierra no lo vea. Se descarga como HTML listo para imprimir; qué
  nombres se leen se decide para cada lector al descargar.
- Una reunión abierta sin compromisos se puede descartar, y deja de contar como postergación.

## Temario propuesto

En orden: semáforos (rojo antes que amarillo), compromisos por fecha, y lo que quedó sin
tratar de la reunión anterior. Lo que ya aparece por sí mismo no se repite como arrastrado.

- **Semáforos:** el último de cada tablero, si es amarillo o rojo. Además, **el mes que
  acaba de terminar si cerró en rojo, aunque el mes en curso ya tenga verde**: el semáforo
  del mes en curso es provisorio y no resuelve uno que cerró mal. Solo los tableros a los
  que accede quien prepara; se dice cuántos no se miraron, sin decir cuáles.
- **Compromisos:** vencidos hoy, o con fecha anterior a la reunión.
- **Sin tratar:** puntos que nadie marcó como tratados. Escribir notas o tomar un
  compromiso lo marca solo.

## Compromisos

- Estados guardados: abierto, cumplido, descartado. «Vencido» se calcula de la fecha.
- **Postergado:** cada compromiso abierto al crear la reunión siguiente, cualquiera sea su
  fecha, gana una fila en `cabinet_carryovers`, única por compromiso y reunión. La cuenta es
  esas filas: ninguna reunión puede contar dos veces.
- Lo acordado (texto y vínculo) se corrige mientras la reunión está abierta; el responsable
  y la fecha también después, y quedan en el historial, que solo crece.
- Carga cambia el estado. Quien lo debe puede agregar notas aunque solo lea el tablero.
- **Cumplidos en término:** sobre los cumplidos y los vencidos. Los vencidos cuentan en
  contra: dejarlos afuera premiaría no cumplir. Se mide con la fecha vigente.
- El responsable es cualquier miembro activo; el formulario avisa si no accede al tablero.

## Queda a criterio de quien construye

Nombres de tablas y rutas, textos, ícono y datos de ejemplo.
