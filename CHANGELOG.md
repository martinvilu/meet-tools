# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versiones según [SemVer](https://semver.org/lang/es/).

## [1.3.0] - 2026-10-28

### Seguridad

- El daemon mandaba el PIN en el primer mensaje a cualquiera que se conectara, que con eso podía emparejarse: ahora el PIN y el QR sólo van a conexiones emparejadas o locales.
- Cualquier página web abierta en el navegador podía conectarse al daemon en 127.0.0.1: ahora responde 403 a los WebSocket con `Origin` de una página.
- La extensión podía probar PIN sin límite: comparte el límite de cinco intentos por minuto.
- PIN comparado en tiempo constante.

### Agregado

- Token de reconexión en `PAIRING_SUCCESS` (8 h, en memoria) que reemplaza al PIN en `PAIR_REQUEST`.
- `meet-tools atajos`: atajos de teclado globales (GNOME) para micrófono, cámara, mano, admitir y silenciar a todos; `--notificar` en esos comandos avisa los errores con una notificación.
- `meet-tools bandeja`: indicador de estado en la bandeja del sistema o notificaciones.
- Registro rotativo en `~/.local/state/p1/cast.log`.
- `MeetClient(pin=…)` y la variable `MEET_TOOLS_PIN` para un daemon de otro equipo.

### Corregido

- `meet-tools mic` (y los demás comandos) salían con `ERR_PAIRING_REQUIRED` con la configuración por omisión: el cliente nunca se emparejaba. Una conexión local ya no necesita PIN.
- `MeetClient.send_command` tomaba como respuesta el primer mensaje que llegara (podía ser un `STATE_SYNC`); ahora espera el ACK o el error.

## [1.2.0] - 2026-09-28

Primera versión con registro de cambios; lo anterior está en el historial de git.

### Agregado

- **cli**: cumplir el contrato de línea de comandos de LINEAMIENTOS §3.2 (N-ECO-04) (`81d7e5d`)

### Cambiado

- **daemon**: quitar el import de random, que quedó sin uso (N-MEET-02) (`42919fd`)

### Corregido

- **seguridad**: PIN de emparejamiento de 6 dígitos con secrets (N-MEET-02) (`0606c8f`)

### Documentación

- agregar el texto de la licencia GPL-3.0-or-later que declara pyproject (N-ECO-06) (`059cd94`)
- incorporar manual de uso integral y referencia tecnica (meet-tools) (`c646f2a`)

### Mantenimiento

- **calidad**: verificar errores de Python y dependencias vulnerables (N-ECO-08, N-ECO-13) (`69f8b1b`)
- **deps**: declarar cast-tools-common como dependencia en lugar de cargarla por sys.path (N-MEET-01) (`64b25ff`)
