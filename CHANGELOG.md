# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versiones según [SemVer](https://semver.org/lang/es/).

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
