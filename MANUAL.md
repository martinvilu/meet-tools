# Manual de Uso y Referencia Técnica: meet-tools

> **MEET-TOOLS** — Sistema de control y monitoreo externo para Google Meet mediante WebExtensions y daemon concentrador.
> **Versión:** `1.1.0` · **CLI principal:** `meet-tools` · **Plugin Ripley:** `meet-tools`

---

## 1. Arquitectura y Propósito Pedagógico

`meet-tools` forma parte del ecosistema de herramientas de la cátedra de Programación 1 (UNRN). Su objetivo central es resolver de forma modular, determinista y automatizada las tareas asociadas a su dominio específico dentro del ciclo de desarrollo, evaluación y aprendizaje de software en C.

### Principios de Diseño
- **Enfoque Pedagógico:** Diagnósticos y mensajes en español rioplatense orientados a facilitar la comprensión de errores conceptuales.
- **Salida Estructurada Dual:** Soporte nativo para visualización enriquecida en terminal (Rich) y salida parseable para orquestadores (`--json`).
- **Integración Contractual:** Capacidad de emitir secciones de reporte para `dredd` (`dredd-section`) y actuar como satélite orquestado por `ripley`.
- **Idempotencia y Robustez:** Validación de precondiciones y comandos de autodiagnóstico (`doctor`) para verificación del entorno.

---

## 2. Instalación y Requisitos

### Requisitos del Sistema
- **Python:** `>= 3.10` (recomendado Python 3.11 o 3.12).
- **Gestor de paquetes:** [`uv`](https://github.com/astral-sh/uv) (entorno estándar de cátedra).
- **Toolchain C (si aplica):** GCC / Clang, Make, GDB y bibliotecas estándar de desarrollo.

### Instalación en el Entorno de Usuario
Para instalar la herramienta de forma global y aislada en el sistema mediante `uv tool`:
```bash
uv tool install --editable /home/mrtin/dev/tools/meet-tools
```

### Verificación de Instalación
Ejecutá el comando `doctor` para constatar que todas las dependencias y binarios requeridos estén presentes y operativos:
```bash
meet-tools doctor
```

---

## 3. Guía Integral de Comandos (CLI)

| Comando | Descripción Breve |
| :--- | :--- |
| [`meet-tools daemon`](#daemon) | Inicia el daemon concentrador WebSocket en primer plano. |
| [`meet-tools status`](#status) | Consulta y muestra el estado actual consolidado de la sesión de Google Meet. |
| [`meet-tools mic`](#mic) | Conmuta el micrófono propio (TOGGLE_MIC). |
| [`meet-tools cam`](#cam) | Conmuta la cámara propia (TOGGLE_CAM). |
| [`meet-tools hand`](#hand) | Conmuta levantar/bajar la mano (TOGGLE_HAND). |
| [`meet-tools admit-all`](#admitall) | Acciona 'Admitir a todos' en la sala de espera (ADMIT_ALL). |
| [`meet-tools mute-all`](#muteall) | Acciona 'Silenciar a todos' los participantes (MUTE_ALL). |
| [`meet-tools leave`](#leave) | Abandona la reunión (LEAVE_CALL). |
| [`meet-tools monitor`](#monitor) | Escucha y muestra en tiempo real todos los eventos y telemetría de Meet. |
| [`meet-tools mock-tab`](#mocktab) | Simula una pestaña de Google Meet con la extensión para pruebas locales. |
| [`meet-tools pack`](#pack) | Empaqueta la extensión WebExtensions para Chrome (.zip) y Firefox (.xpi). |
| [`meet-tools sign`](#sign) | Valida y firma digitalmente el addon para Firefox utilizando Mozilla web-ext. |
| [`meet-tools qr`](#qr) | Muestra el código QR para emparejamiento directo con la app Android. |
| [`meet-tools doctor`](#doctor) | Verifica el estado del entorno de MEET-TOOLS (Python, web-ext opcional). |

### `meet-tools daemon`

Inicia el daemon concentrador WebSocket en primer plano.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--host`, `-h` | `<class 'str'>` | `127.0.0.1` | Dirección IP de escucha (127.0.0.1 por defecto; 0.0.0.0 para LAN y loopback) |
| `--port`, `-p` | `<class 'int'>` | `8765` | Puerto TCP para el servidor WebSocket |
| `--timeout`, `-t` | `<class 'float'>` | `2.5` | Timeout para ack de extensión (segundos) |
| `--pin` | `Optional[str]` | `None` | PIN de seguridad de 4 dígitos (si se omite, se genera aleatorio) |
| `--no-pin` | `<class 'bool'>` | `False` | Desactivar requerimiento de PIN (modo permisivo) |
| `--no-mdns` | `<class 'bool'>` | `False` | Desactivar anuncio mDNS en la red local |
| `--no-qr` | `<class 'bool'>` | `False` | Ocultar código QR en la consola al iniciar |

#### Ejemplo de Invocación
```bash
meet-tools daemon
```

### `meet-tools status`

Consulta y muestra el estado actual consolidado de la sesión de Google Meet.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | URI del daemon concentrador |
| `--json` | `<class 'bool'>` | `False` | Emitir el estado como JSON versionado (sin Rich). |

#### Ejemplo de Invocación
```bash
meet-tools status
```

### `meet-tools mic`

Conmuta el micrófono propio (TOGGLE_MIC).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | - |

#### Ejemplo de Invocación
```bash
meet-tools mic
```

### `meet-tools cam`

Conmuta la cámara propia (TOGGLE_CAM).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | - |

#### Ejemplo de Invocación
```bash
meet-tools cam
```

### `meet-tools hand`

Conmuta levantar/bajar la mano (TOGGLE_HAND).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | - |

#### Ejemplo de Invocación
```bash
meet-tools hand
```

### `meet-tools admit-all`

Acciona 'Admitir a todos' en la sala de espera (ADMIT_ALL).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | - |

#### Ejemplo de Invocación
```bash
meet-tools admit-all
```

### `meet-tools mute-all`

Acciona 'Silenciar a todos' los participantes (MUTE_ALL).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | - |

#### Ejemplo de Invocación
```bash
meet-tools mute-all
```

### `meet-tools leave`

Abandona la reunión (LEAVE_CALL).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--all`, `-a` | `<class 'bool'>` | `False` | Finalizar la llamada para todos (solo anfitriones) |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | - |

#### Ejemplo de Invocación
```bash
meet-tools leave
```

### `meet-tools monitor`

Escucha y muestra en tiempo real todos los eventos y telemetría de Meet.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | URI del daemon concentrador |
| `--json` | `<class 'bool'>` | `False` | Emitir cada evento como una línea JSON (NDJSON) versionada. |

#### Ejemplo de Invocación
```bash
meet-tools monitor
```

### `meet-tools mock-tab`

Simula una pestaña de Google Meet con la extensión para pruebas locales.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--tab-id`, `-t` | `<class 'str'>` | `tab_mock_1` | Identificador único de la pestaña simulada |
| `--in-call/--lobby` | `<class 'bool'>` | `True` | Estado inicial de llamada |
| `--host/--guest` | `<class 'bool'>` | `True` | Rol de anfitrión |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8765` | - |

#### Ejemplo de Invocación
```bash
meet-tools mock-tab
```

### `meet-tools pack`

Empaqueta la extensión WebExtensions para Chrome (.zip) y Firefox (.xpi).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--target`, `-t` | `<class 'str'>` | `both` | Navegador objetivo: chrome, firefox o both |
| `--out-dir`, `-o` | `<class 'str'>` | `dist` | Directorio de salida para los paquetes |

#### Ejemplo de Invocación
```bash
meet-tools pack
```

### `meet-tools sign`

Valida y firma digitalmente el addon para Firefox utilizando Mozilla web-ext.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--api-key`, `-k` | `Optional[str]` | `None` | API Key (JWT issuer) de Mozilla AMO |
| `--api-secret`, `-s` | `Optional[str]` | `None` | API Secret de Mozilla AMO |
| `--channel`, `-c` | `<class 'str'>` | `unlisted` | Canal de distribución: unlisted o listed |
| `--out-dir`, `-o` | `<class 'str'>` | `dist` | Directorio destino para el .xpi firmado |
| `--lint-only` | `<class 'bool'>` | `False` | Solo validar compatibilidad y manifiesto con web-ext lint |
| `--dry-run` | `<class 'bool'>` | `False` | Verificar manifiesto e imprimir el comando web-ext sign sin enviar |

#### Ejemplo de Invocación
```bash
meet-tools sign
```

### `meet-tools qr`

Muestra el código QR para emparejamiento directo con la app Android.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `pin` | `<class 'str'>` | PIN de emparejamiento |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--port`, `-p` | `<class 'int'>` | `8765` | Puerto TCP WebSocket |
| `--host`, `-h` | `Optional[str]` | `None` | IP anfitrión (si se omite, se detecta automáticamente) |

#### Ejemplo de Invocación
```bash
meet-tools qr <pin>
```

### `meet-tools doctor`

Verifica el estado del entorno de MEET-TOOLS (Python, web-ext opcional).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--json` | `<class 'bool'>` | `False` | Emitir diagnóstico en formato JSON estructurado. |

#### Ejemplo de Invocación
```bash
meet-tools doctor
```

---

## 4. Formatos de Salida e Integración con el Ecosistema

### Modo Interactivo / Terminal (Rich)
Por defecto, la herramienta renderiza paneles, árboles y tablas estilizadas para facilitar la lectura del estudiante y docente en terminales modernas con soporte ANSI.

### Modo Estructurado JSON (`--json`)
Para integración con pipelines de CI/CD, scripts de automatización u orquestadores externos, la opción `--json` emite un documento JSON estricto por la salida estándar (`stdout`), dirigiendo cualquier mensaje de logging a `stderr`:
```bash
meet-tools daemon --json
```

### Integración con Dredd (`dredd-section`)
Cuando la herramienta genera reportes de evaluación para entregas de alumnos, produce una sección Markdown estandarizada conforme al contrato de integración de Dredd (v1.0.0):
```markdown
<!-- dredd-section: meet-tools, tool=meet-tools, version=1.1.0, status=ok -->
```
Este encabezado garantiza la agregación determinista de los hallazgos en la rúbrica docente.

### Integración con Ripley
`meet-tools` está registrada en el catálogo de plugins satélites de Ripley (`SATELLITE_CATALOG`). Puede invocarse directamente a través del motor de evaluación de Ripley configurando el análisis en `ripley.toml`.

---

## 5. Diagnóstico y Códigos de Salida

### Códigos de Retorno (`exit code`)
| Código | Significado |
| :---: | :--- |
| `0` | Ejecución exitosa sin hallazgos críticos ni errores de sintaxis. |
| `1` | Hallazgos pedagógicos detectados, infracción de reglas o advertencias activas. |
| `2` | Error de sintaxis en argumentos CLI o archivo fuente no encontrado. |
| `>2` | Error no recuperable del sistema, fallo de memoria o excepción interna. |

### Diagnóstico del Entorno (`doctor`)
Ante comportamientos inesperados, verificá el estado operativo con:
```bash
meet-tools doctor
```
Comprueba la presencia de las dependencias requeridas y la integridad de los componentes del paquete.