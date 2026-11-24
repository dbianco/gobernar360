# Tablero Reclamos — diseño

Sexto tablero sobre la plataforma (`2026-11-18-gobernar360-platform-design.md`), con semáforo,
icono y ayudas (`2026-11-20-status-lights-and-ui-design.md`). Pedido en
`docs/tasks/03-complaints-dashboard.md`.

## Para qué

Trámites es un inventario. Reclamos sigue cada caso que hace un vecino (una luminaria
apagada, residuos sin recolectar, un bache) desde que entra hasta que se resuelve, y mide
con honestidad cuánto tardó.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** ciclo de vida explícito con historial; reloj de servicio en días hábiles con
  calendario propio del municipio; bandejas por área; vecino del padrón o anónimo; zona;
  análisis, descargas y resumen general.
- **No objetivos:** formulario público para vecinos, avisos al vecino, adjuntos, mapa (si se
  hace la capa geográfica, la zona pasa a ser un polígono), asignación a personas dentro del
  área.
- **Anti-objetivos:** que un municipio vea o referencie reclamos, tipos, áreas o zonas de otro;
  que un reclamo reabierto "resetee" su tiempo; que se pueda fechar hacia atrás un cambio de
  estado; que el reloj corra mientras se espera al vecino.

## Datos

Clave `complaints`. Niveles: lectura ve y descarga; carga registra reclamos, cambia estados,
reasigna y agrega notas; administración además gestiona áreas, zonas, tipos y calendario.

- **Áreas** y **zonas:** nombre. No se borran si algo las usa.
- **Tipos:** nombre, área a la que se derivan por defecto, plazo objetivo en días hábiles
  (1 a 365) y si está vigente (los no vigentes no se ofrecen para reclamos nuevos pero siguen
  en los números).
- **Calendario:** días de la semana hábiles (lunes a viernes si no se cambió) y feriados
  (fecha y nombre, uno por fecha).
- **Reclamos:** número correlativo del municipio, tipo, área responsable, zona, dirección,
  descripción, vecino (del padrón, por DNI, o anónimo), estado, plazo objetivo copiado del
  tipo al registrarlo y momento de recepción (siempre el del servidor).
- **Historial:** cada reclamo guarda eventos en orden: alta, cambio de estado, reasignación,
  cambio de tipo y nota. Cada uno con quién, cuándo y nota. Nada se borra; un reclamo tampoco.

El vecino se busca en el padrón del municipio solo por DNI exacto (la misma búsqueda de la
plataforma que usan Económico y Social). Si no está se lo agrega al padrón desde el reclamo.
El reclamo apunta a la persona del padrón, así que quitarla de otro tablero no la borra
mientras tenga reclamos.

## Ciclo de vida

| Desde | Hacia |
|---|---|
| Recibido | Asignado, Rechazado |
| Asignado | En curso, Esperando al vecino, Resuelto, Rechazado |
| En curso | Esperando al vecino, Resuelto, Rechazado |
| Esperando al vecino | En curso, Rechazado |
| Resuelto | Cerrado, Reabierto |
| Reabierto | En curso, Esperando al vecino, Resuelto, Rechazado |
| Cerrado, Rechazado | — |

Cualquier otro paso se rechaza (409 `invalid_transition`). Rechazar y reabrir piden nota.
Reasignar, cambiar el tipo o los datos solo se puede con el reclamo abierto (recibido,
asignado, en curso, esperando o reabierto). Cambiar el tipo copia el plazo del tipo nuevo.

## Reloj de servicio

- Se cuenta en días hábiles del calendario del municipio, con fechas de Argentina. Un tramo
  desde el día A hasta el día B cuenta los días hábiles después de A y hasta B inclusive: el
  día en que entra el reclamo no se cuenta, como en los plazos administrativos.
- El reloj corre desde la recepción. Se detiene al pasar a Esperando al vecino y vuelve a
  correr el día en que sale de esa espera: los días hábiles después del día en que empezó
  la espera, hasta el día en que termina inclusive, no se cuentan. Se detiene al resolver
  o rechazar.
- Reabrir retoma el reloj desde el día en que se lo había dado por resuelto: los días que
  estuvo mal resuelto cuentan, porque el problema seguía.
- Usado = días hábiles contados; restante = plazo − usado; vencimiento = el día hábil en que
  el usado llega al plazo (si está en espera, suponiendo que se retoma hoy).
- Situación de un reclamo abierto: vencido si el restante es negativo; en riesgo si quedan
  como mucho un cuarto del plazo (redondeado hacia arriba, mínimo un día); si no, en plazo.
  Uno resuelto o cerrado quedó en plazo o vencido según su usado al resolverse.
- El reloj se calcula al leer, con el calendario vigente: cargar un feriado olvidado corrige
  también los casos anteriores.

## Bandejas

Cada área tiene su bandeja con sus reclamos abiertos, primero los más cerca de vencer (menos
días restantes; a igual restante, los que corren antes que los pausados y luego los más
antiguos). Un resumen por área muestra abiertos, en riesgo, vencidos y en pausa.

## Análisis y descargas

El período se elige por fecha de recepción (por defecto, los últimos doce meses contando el
mes actual). Con los reclamos recibidos en el período:

- recibidos por mes contra resueltos por mes (estos por fecha de resolución);
- cuántos se resolvieron, parte resuelta en plazo, mediana y percentil 90 de días hábiles
  hasta resolverse (interpolación lineal, como PERCENTIL.INC de una planilla), por tipo y
  por área;
- reclamos repetidos: mismo tipo y misma dirección (sin distinguir mayúsculas, acentos ni
  espacios), cada uno a no más de N días del anterior (30 por defecto);
- zonas y tipos con más reclamos.

Sin importar el período, hoy: abiertos por estado, por situación y por antigüedad en días
corridos desde la recepción.

Descargas CSV con el mismo período: reclamos (uno por fila, con días hábiles hasta la
resolución, así la mediana por tipo sale igual en una planilla) e informe por área.

Resumen general: abiertos, vencidos, parte resuelta en plazo y mediana de resolución de los
últimos doce meses.

## Pantallas

Pestañas: Resumen, Reclamos, Bandejas, Parámetros (solo administración). Ficha del reclamo con
sus datos, el reloj, las acciones que el estado permite (solo las válidas, y solo a quien
carga) y el historial completo.

## Datos de ejemplo

Noetinger recibe áreas, zonas, tipos, feriados nacionales y varios cientos de reclamos
inventados de los últimos doce meses, con vecinos del padrón y anónimos, casos reabiertos,
esperas y repetidos, y su semáforo. El tablero **no** queda habilitado en Noetinger: lo
habilita el operador. Comuna Demo lo tiene habilitado con unos pocos reclamos propios.
