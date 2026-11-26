# Compromisos de todos y notificaciones — diseño

Amplía `2026-11-24-cabinet-commitments-design.md`: los compromisos pasan del tablero Gabinete
a la plataforma, para que cualquiera pueda asignar uno a otro o a sí mismo, salga o no de una
reunión, y sumar a quienes quieran enterarse cuando se cumple.

## Qué pidió el usuario

1. Lo usa **todo usuario** del municipio, sin necesidad de permisos de tablero.
2. Un compromiso de reunión lo ven los miembros de Gabinete, más el responsable y los agregados.
3. Cualquiera asigna a cualquiera del mismo municipio.
4. El responsable lo marca cumplido y puede cambiar la fecha y el responsable.
5. Se avisa dentro de la aplicación: íconos junto al nombre, con vista previa al pasar el
   mouse y la lista al hacer clic.
6. Los informales no cuentan en Gabinete.
7. Las listas de nombres se filtran escribiendo.

## Lo que quedaba sin decir

Se resolvió por lo más acotado y **el usuario lo confirmó**: quién ve los informales, qué puede
quien los asignó, que no haya correo, que el cumplimiento en término use la fecha vigente (lo
reemplazó F1 de la revisión del 2026-11-25: usa la fecha acordada) y quién sigue viendo un compromiso que pasó a otro.

- **Informales:** los ven solo quien los asignó, el responsable y los agregados. Ni los
  administradores ni Gabinete; para los demás no existen (404).
- **Quien asignó uno informal** corrige el texto y el vínculo, cambia fecha, responsable y
  agregados, lo descarta o lo reabre. Cumplido lo dice el responsable.
- **De reunión:** quien edita Gabinete conserva lo que podía. El texto se cambia solo desde la
  reunión. Quien no tiene Gabinete ve el compromiso y no la reunión.
- **Agregados:** leen; no cambian nada. Los elige quien puede cambiar la fecha.
- **Pasarlo a otro** deja de mostrarlo a quien lo pasó, salvo que lo haya creado, que lo vea
  por Gabinete o que quede agregado.
- **Cumplidos en término** (Gabinete) usa la fecha acordada en la reunión, aunque el
  responsable la haya movido después. El historial conserva cada cambio.
- **Si el responsable deja el municipio** (F2), quien lo quita recibe la lista de lo que debía
  y puede ver (lo de reuniones) y cuántos más hay. A quien asignó uno informal se le avisa y es
  quien lo reasigna: los administradores siguen sin verlos.
- **Avisos:** «te lo asignó» al responsable; «lo cumplió» a los agregados y a quien asignó uno
  informal. A nadie de lo que hizo él mismo. Reabrir, descartar o reasignar retira los avisos
  no leídos que dejaron de ser ciertos. **No se manda correo.**

## Estructura

- `platform/commitments.py` decide quién ve, quién cambia y a quién se avisa. Tablas en
  `platform/commitment_models.py`: `commitments`, `commitment_followers`, `commitment_entries`
  (historial) y `commitment_notices`. `Commitment.source` es el tablero que lo registró, o nada
  si es informal.
- Gabinete guarda solo en qué punto se tomó cada uno (`cabinet_taken`) y las postergaciones.
  Todo lo suyo (resumen, CSV, temario, acta) parte de `present.taken()`.
- La plataforma no conoce Gabinete: le pregunta por el registro de dónde viene un compromiso
  (`DashboardModule.get_commitment_origins`) y muestra la reunión solo a quien accede al tablero.
- La vista inversa (tira de estado, ficha de proyecto) suma los informales, a quienes los ven.
- La migración 0018 renombra las tablas, sin copiar filas.

## Pantallas

- **Compromisos** (menú, todos): A mi cargo, Los que asigné, Los que sigo; alta y ficha.
- **Notificaciones:** los propios abiertos y los ajenos que se siguen, con estado, fecha y
  enlace. Un cumplido queda hasta marcarlo como leído; abrir la ficha también lo marca.
- **Encabezado:** pendientes propios (rojo si hay vencidos) y novedades. Se consulta cada minuto.
- `<PersonSelect>` y `<PeopleSelect>` reemplazan toda lista de nombres.
- «Mis compromisos» de Gabinete desaparece: la sección nueva los reúne a todos.
