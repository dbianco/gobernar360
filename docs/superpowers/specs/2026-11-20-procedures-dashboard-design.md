# Tablero Trámites — diseño

Quinto tablero sobre la plataforma (`2026-11-18-gobernar360-platform-design.md`). Nace con
semáforo, icono y ayudas (`2026-11-20-status-lights-and-ui-design.md`). Basado en la
descripción de "Trámites" de `tableros-de-gestion-portal-ril.md`; el tablero de referencia
no tiene vista previa, así que el alcance lo acordó el usuario.

## Para qué

El municipio quiere saber qué trámites ofrece, qué le pide al vecino en cada uno y quién
tiene ya ese dato. Con eso decide qué sistemas conviene conectar primero: los que evitan
pedir más veces lo que el Estado ya sabe.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** inventario único de trámites cargado por las áreas; lista común de
  requisitos con su fuente; reporte de oportunidades de interoperabilidad; resumen y
  descargas.
- **No objetivos:** seguimiento de solicitudes de vecinos; permisos por área (el área es un
  dato del trámite); historial de versiones; importación masiva; datos personales.
- **Anti-objetivos:** que un municipio vea datos de otro; que un trámite dado de baja
  infle los números; que el mismo trámite cuente dos veces en el volumen de una fuente.

## Enfoques

1. **Lista común de requisitos y catálogo de fuentes (elegido).** Un requisito se carga una
   vez y se reusa en muchos trámites; la fuente es un dato del requisito. Así "en cuántos
   trámites se pide el libre deuda" es una cuenta y no una comparación de textos.
2. Requisitos como texto libre dentro de cada trámite. Descartado: no se puede agrupar.
3. Seguimiento de solicitudes. Descartado por el usuario: es otro producto.

## Datos

Clave `procedures`. Niveles: lectura ve y descarga; carga gestiona trámites y requisitos;
administración además gestiona áreas y fuentes.

- **Áreas:** nombre.
- **Fuentes:** nombre y nivel (municipal, provincial, nacional, otro). Una fuente municipal
  puede indicar su área; las demás no.
- **Requisitos:** nombre, descripción y fuente. Sin fuente significa que lo aporta el vecino.
- **Trámites:** nombre, descripción, área responsable, a quién está dirigido (personas,
  organizaciones, ambos), canal (presencial, en línea, ambos), enlace, gratuito o costo,
  plazo estimado en días, cantidad estimada por año, vigente o no.
- **Requisitos de un trámite:** un requisito de la lista, si es obligatorio, cómo se pide
  hoy (papel o digital) y una nota. Un requisito figura una sola vez por trámite.

Reglas:

- No se borra un área con trámites o fuentes, una fuente con requisitos, ni un requisito
  usado en algún trámite. Borrar un trámite borra sus requisitos asociados.
- Un trámite gratuito no lleva costo.
- Resumen, oportunidades y resumen general cuentan solo trámites vigentes.
- La lista de trámites se pagina (50), se busca por nombre y se filtra por área, canal y
  vigencia.

## Resumen, oportunidades y descargas

- **Resumen:** trámites vigentes; cuántos tienen canal en línea; promedio de requisitos por
  trámite; requisitos y fuentes cargados; trámites por área y por canal; los diez
  requisitos más pedidos con su fuente.
- **Oportunidades:** por cada fuente usada, cuántos de sus requisitos se piden, en cuántos
  trámites distintos y cuántas gestiones por año suman esos trámites (cada trámite una sola
  vez). Orden: nivel municipal primero, luego provincial, nacional y otro; dentro de cada
  nivel, por gestiones y luego por trámites. Aparte, la misma cuenta para los requisitos
  sin fuente.
- **Descargas** CSV: trámites, requisitos por trámite, oportunidades.
- **Resumen general:** trámites vigentes, porcentaje con canal en línea, requisitos, fuentes.

## Pantallas

Pestañas: Resumen, Trámites, Requisitos, Oportunidades, Parámetros (solo administración).
Ficha de trámite con sus datos y la tabla de requisitos (agregar, cambiar, quitar). El
semáforo va arriba del resumen con sus propias flechas de año, porque el inventario no
tiene año.

## Datos de ejemplo

Noetinger recibe áreas, fuentes, requisitos y una docena de trámites con requisitos
compartidos. Comuna Demo queda con el tablero habilitado y vacío. Una base de ejemplo
anterior gana el tablero una sola vez, con su semáforo.

## Queda a criterio de quien construye

Nombres de tablas y rutas, forma de las respuestas, textos de interfaz y de ayuda, icono y
contenido de los datos de ejemplo.
