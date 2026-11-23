# Cuentas por email, avisos e inicio de sesión único — diseño

Tarea: `docs/tasks/01-email-accounts-and-notifications.md`. Cambia la plataforma
(`2026-11-18-gobernar360-platform-design.md`) y la administración de usuarios
(`2026-11-19-operator-municipality-admin-design.md`).

## Para qué

Hasta ahora quien agregaba un usuario le inventaba una contraseña y se la pasaba por otro
medio; nadie podía recuperar una contraseña olvidada y nadie se enteraba de lo que pedía
atención. Con correo saliente, cada persona elige su contraseña, la recupera sola y recibe
avisos. El centro del trabajo es que el envío sea confiable, no las pantallas.

## Objetivos, no objetivos y anti-objetivos

- **Objetivos:** bandeja de salida (outbox) con reintentos; invitaciones por enlace;
  recuperación de contraseña; avisos programados de hitos vencidos y de estado mensual
  faltante, que cada persona puede apagar; ingreso con un proveedor OpenID Connect.
- **No objetivos:** correos con diseño (HTML, plantillas de marketing); SMS; centro de
  notificaciones dentro de la aplicación; crear cuentas desde el proveedor de identidad;
  cerrar sesión en el proveedor al cerrarla en gobernar360.
- **Anti-objetivos:** que quien agrega a alguien pueda elegir, conocer o cambiar la
  contraseña de una cuenta; que una respuesta revele si un email tiene cuenta; que un
  correo se pierda o salga dos veces; que el enlace de un correo sirva más de una vez.

## Bandeja de salida

- Cada correo se escribe en `email_outbox` en la misma transacción que el cambio que lo
  causa: si el cambio se deshace no sale nada, y si se confirma el correo no se pierde.
- `gobernar360 send-email` los entrega por SMTP, uno por transacción: toma la fila con
  `FOR UPDATE SKIP LOCKED`, envía y la marca enviada en esa misma transacción. Dos
  procesos a la vez nunca mandan el mismo correo.
- Si falla, la fila sigue pendiente con el error y el próximo intento se demora 30 s, y
  el doble cada vez, hasta una hora. Si el servidor no responde, la corrida se corta (el
  resto fallaría igual). Un rechazo definitivo del destinatario (5xx) o 20 intentos
  fallidos la marcan `failed`; `--retry-failed` la vuelve a poner en cola.
- Corrido a mano, `send-email` manda todo lo pendiente sin esperar la demora: quien lo
  corre acaba de arreglar el servidor. Con `--watch` queda corriendo y respeta la demora;
  así se usa en producción.
- **Límite conocido:** si el proceso muere después de que el servidor SMTP aceptó el
  mensaje y antes de marcarlo enviado, se vuelve a mandar. Ninguna bandeja de salida
  cierra ese hueco con SMTP; el `Message-ID` es el mismo en cada intento
  (`<id-de-fila@dominio>`), lo que permite a los servidores reconocer el duplicado.

## Enlaces (invitación y recuperación)

- Un token aleatorio de 256 bits en el fragmento de la URL (`/set-password#token`), que
  el navegador no manda a ningún servidor ni en el `Referer`. Se guarda solo su SHA-256.
- Sirve una vez: la comprobación es un `UPDATE ... WHERE used_at IS NULL` que lo marca
  usado; de dos pedidos simultáneos, el segundo espera el bloqueo y ya no coincide.
- Vence: invitación a los 7 días, recuperación a la hora (configurables). Un enlace
  nuevo del mismo tipo anula el anterior; elegir contraseña, por cualquier vía, anula
  todos los pendientes y cierra todas las sesiones de la cuenta.
- Abrir el enlace solo consulta (`/auth/tokens/inspect`); recién guardar la contraseña
  lo usa. Así un antivirus que abre los enlaces de los correos no lo gasta.

## Agregar usuarios

- Ya no se pide contraseña. Email nuevo: se crea la cuenta sin contraseña y se manda una
  invitación. Email con cuenta: se agrega la membresía y se manda un aviso sin enlace.
  Cuenta que nunca eligió contraseña: se manda una invitación nueva (el enlace va a quien
  tiene el email, no a quien invita).
- La respuesta es la misma en los tres casos. Desaparecen el error `account_exists` y la
  opción del operador de conservar o reemplazar la contraseña de una cuenta existente: ya
  nadie elige contraseñas ajenas. El operador conserva "Cambiar contraseña" para casos
  excepcionales.
- "Reenviar invitación" en cada fila: manda un enlace nuevo si la cuenta todavía no tiene
  contraseña y nada en otro caso, con la misma respuesta.
- **Límite conocido:** después de agregarla, la lista de usuarios muestra el nombre con
  que la persona registró su cuenta, que puede no ser el que escribió quien la agregó.
  Es el nombre de alguien que ya es miembro del municipio; no se oculta.

## Recuperación de contraseña

- `POST /auth/password-reset` responde 204 haya o no cuenta, sin cookies ni cuerpo.
- Límite de 3 pedidos por dirección por hora, contado para cualquier dirección (exista o
  no), así el límite tampoco revela nada. La dirección se guarda solo como hash. Un
  bloqueo consultivo por dirección evita que pedidos simultáneos pasen el límite.

## Configuración del municipio

Decisiones posteriores del usuario: quién recibe los avisos, los textos de los correos y
el inicio de sesión único pasan a ser configuración de cada municipio, en una pestaña
"Configuración" junto a "Usuarios", para sus administradores. El operador de la
plataforma ve y cambia la misma configuración de cualquier municipio, desde la página de
ese municipio: lo que maneja el administrador es un subconjunto de lo que maneja el operador.

- Se guarda en `municipality_settings` (destinatarios, inicio de sesión único) y
  `email_templates` (texto propio de cada correo). Son tablas de plataforma, como las
  membresías: el ingreso y la recuperación de contraseña las leen antes de elegir
  municipio. Las rutas filtran por el municipio activo y cada cambio queda auditado.
- **Destinatarios de los avisos:** una lista de direcciones separadas por comas. Reciben
  todos los avisos del municipio. Si la lista está vacía, cada aviso va a quienes
  administran su tablero (como antes), para que un municipio que no configuró nada siga
  recibiendo avisos.
- **Textos de los correos:** cada correo (acceso nuevo, acceso a una cuenta existente,
  recuperar contraseña y cada tipo de aviso) tiene asunto y texto HTML editables con un
  editor de texto enriquecido (Tiptap). Lo guardado se limpia a un conjunto chico de
  etiquetas (párrafos, títulos, listas, negrita, cursiva, subrayado, tachado, enlaces),
  solo puede usar las variables de ese correo y debe conservar las obligatorias (sin
  `{{link}}` una invitación no sirve). Los valores se escapan al reemplazarse. Se puede
  volver al texto por defecto y enviarse una prueba con datos de ejemplo, sin guardar.
  La recuperación de contraseña usa el texto del municipio si la cuenta pertenece a uno
  solo; si no, el de por defecto (no hay forma de saber "de qué municipio" es el pedido).
- **Inicio de sesión único:** el proveedor (emisor, cliente, secreto) sigue siendo de la
  plataforma, en variables de entorno: si un administrador de municipio pudiera elegir
  el proveedor, podría ingresar con cualquier cuenta, y las cuentas son compartidas entre
  municipios. Cada municipio decide si lo permite (apagado por defecto). La sesión
  recuerda cómo se abrió: una abierta por inicio de sesión único solo llega a los
  municipios que lo permiten (se revisa en cada pedido, así que apagarlo corta esas
  sesiones) y nunca opera la plataforma. El botón del ingreso aparece cuando hay
  proveedor y al menos un municipio lo permite.

## Avisos

- `gobernar360 notify`, corrido por un programador de tareas (por ejemplo una vez por
  día), recorre cada municipio en su propia transacción con la seguridad por filas
  puesta en ese municipio.
- Tipos: `status_light_missing` (de la plataforma: un tablero habilitado sin estado del
  mes que terminó) y los que declara cada tablero con `DashboardModule.alert_kinds` y
  `get_alerts`; Proyectos declara `milestone_overdue` (la misma regla que marca el hito
  en la pantalla del proyecto).
- Destinatarios: la lista del municipio (ver Configuración) o, si está vacía, quienes
  tienen nivel de administración en el tablero del aviso, con la cuenta activa. Una
  dirección cuya cuenta apagó el tipo no lo recibe.
- Una sola vez por dirección y evento: `notifications_sent` (única por municipio,
  dirección, tipo y clave del evento) se reclama con `INSERT ... ON CONFLICT DO NOTHING` en la misma
  transacción que el correo. Clave del hito: id y fecha de vencimiento (si se le pone una
  fecha nueva y también pasa, es otro evento). Clave del estado: tablero y mes.
- Un correo por dirección, municipio y tipo en cada corrida, con la lista de eventos nuevos.
- Apagar un tipo en "Mi cuenta" lo saltea sin registrarlo: al volver a encenderlo llegan
  los eventos todavía vigentes.

## Inicio de sesión único

- OpenID Connect con código de autorización y PKCE (S256). El proveedor se descubre con
  `/.well-known/openid-configuration` y se configura con `GOBERNAR360_OIDC_ISSUER`,
  `_CLIENT_ID` y `_CLIENT_SECRET`; sin emisor no se ofrece. Por defecto está apagado: un
  valor por defecto que apunte a un proveedor local sería peligroso en producción.
- `/auth/sso/start` guarda el intento (hash del `state`, `nonce`, verificador PKCE, diez
  minutos) y deja el `state` en una cookie `HttpOnly`, `SameSite=Lax`, solo para
  `/api/auth/sso`. `/auth/sso/callback` exige que el `state` recibido sea el de la cookie
  de ese navegador (impide terminar un ingreso en el navegador de otro), gasta el intento
  pase lo que pase, canjea el código y valida el ID token: firma con las claves
  publicadas (solo algoritmos asimétricos), emisor, audiencia, `azp`, vencimiento y
  `nonce`. Si el token no trae el email, se lee de `userinfo` y su `sub` debe coincidir.
- Entra solo una cuenta existente y activa cuyo email el proveedor declare verificado
  (`email_verified`). Nunca se crea una cuenta. Los errores vuelven a `/login` con un
  código que la pantalla explica.
- Proveedor local para desarrollo: `dev/oidc-provider` (oidc-provider, implementación
  certificada por OpenID), con las cuentas demo, una con el email sin verificar y otra
  sin cuenta en gobernar360.

## Textos

Todo texto para personas sigue en español. Los textos por defecto de los correos están en
`backend/src/gobernar360/locales/es-AR.json` (asunto y HTML, con la misma sintaxis
`{{nombre}}` que la aplicación web) y cada municipio puede reemplazarlos. Cada correo sale
en HTML con una copia en texto plano generada a partir del HTML.
