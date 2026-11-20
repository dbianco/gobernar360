# Semáforos, iconos y ayudas — diseño

Cambios que cruzan toda la plataforma (`2026-11-18-gobernar360-platform-design.md`) y sus
cuatro tableros. Se hacen antes del tablero Trámites para que nazca con ellos.

## Para qué

Quien conduce el municipio quiere ver de un vistazo cómo viene cada área. Los indicadores
no alcanzan: quien administra un tablero sabe cosas que los números no dicen. El semáforo
es su opinión, mes a mes. Los iconos y las ayudas hacen que la aplicación se lea más rápido.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** un icono por opción del menú; un semáforo mensual por tablero, cargado a
  mano por quien lo administra, visible en el resumen del tablero y en el resumen general;
  una ayuda en cada encabezado de tabla de los tableros; resumen general con los semáforos
  arriba y una sección colapsable por tablero.
- **No objetivos:** semáforo calculado a partir de indicadores; semáforo por indicador; un
  comentario que explique el color; ayudas en las tablas de administración de usuarios y
  municipios; avisos cuando falta cargar un mes.
- **Anti-objetivos:** que alguien vea el semáforo de un tablero al que no tiene acceso; que
  un municipio vea semáforos de otro; que el estado se comunique solo con color.

## Enfoques

1. **Semáforo en la plataforma (elegido).** Una sola tabla y una sola pantalla sirven a
   todos los tableros, presentes y futuros; el resumen general lo lee sin preguntar a cada
   tablero.
2. Semáforo dentro de cada tablero. Descartado: cinco copias de lo mismo.
3. Semáforo calculado con reglas sobre los indicadores. Descartado: el usuario lo pidió
   arbitrario.

Iconos: Tabler Icons (`@tabler/icons-react`), de línea y un solo color, para que el mismo
icono sirva en el menú y sobre el fondo de color del semáforo.

## Semáforo

- Un valor por municipio, tablero, año y mes: verde, amarillo o rojo. Un mes puede quedar
  sin color.
- Lo cambia quien tiene nivel de administración en ese tablero (el administrador del
  municipio lo tiene en todos). Lo ve quien tiene al menos lectura en ese tablero.
- Se pueden corregir meses pasados. No se puede cargar un mes posterior al actual.
- Cada cambio queda en el registro de auditoría.
- **Resumen de cada tablero:** una tira con los 12 meses del año que se está mirando, cada
  uno con su color o vacío. Con nivel de administración, cada mes se puede cambiar o
  vaciar desde ahí.
- **Resumen general:** arriba de todo, una tarjeta por tablero visible. Muestra en grande
  el icono del tablero sobre el color del último mes cargado, con el nombre del mes y del
  estado; al lado, en chico, los meses cargados entre los 5 anteriores a ese. Un tablero
  sin ningún mes cargado muestra el icono en gris y "Sin estado".
- Nombres de los estados: verde "En orden", amarillo "Con atención", rojo "Crítico".

## Iconos

Uno por opción del menú lateral: resumen general, cada tablero, usuarios y plataforma.

## Ayuda en encabezados

Cada encabezado con nombre de las tablas de los tableros lleva un icono de información; al
pasar el mouse, tocar o enfocarlo con teclado muestra una explicación corta. Quedan fuera
las columnas de acciones (sin nombre) y las que son solo un mes o un año. Los textos viven
en el archivo de textos, junto a los del tablero.

## Resumen general

Orden: semáforos; luego una sección por tablero con sus indicadores. Cada sección se
colapsa y se abre desde su título; empiezan abiertas y el navegador recuerda cuáles se
cerraron.

## Datos de ejemplo

Noetinger recibe semáforos de los últimos meses en sus cuatro tableros, con colores
variados. Una base de ejemplo anterior los gana una sola vez.

## Queda a criterio de quien construye

Nombres de tablas y rutas, forma de las respuestas, qué icono lleva cada opción, la
redacción de las ayudas y el aspecto exacto de la tira y las tarjetas.
