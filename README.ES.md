<div align="center">

# 🏛️ Olympus Agents

<img src="docs/assets/olympus-cover.png" alt="El equipo de Olympus Agents en el monte Olimpo" width="100%">

**Tu equipo de programación con IA. Una instrucción, nueve roles. Tú tienes el control.**

🌐 **[English](README.md) · Español**

[![Última versión](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![Windows validado](https://img.shields.io/badge/Windows-validado-2563eb?style=flat-square)](docs/HARNESSES.md) [![Linux (WSL 2)](https://img.shields.io/badge/Linux-WSL%202-2563eb?style=flat-square)](docs/INSTALLATION.md#linux-sh-entrypoint) [![OpenCode v2.4.1](https://img.shields.io/badge/OpenCode-v2.4.1-2563eb?style=flat-square)](https://github.com/anomalyco/opencode/releases/tag/v2.4.1) [![Licencia MIT](https://img.shields.io/badge/Licencia-MIT-f59e0b?style=flat-square)](LICENSE)

**[🎯 Pruébalo](#your-first-task) · [⚡ Instala](#fast-install) · [👥 Equipo](#the-team) · [🧭 Comandos](#task-parallelism) · [🛠️ CLI](#portable-cli) · [📚 Guías](#guides)**

</div>

<a id="your-first-task"></a>

## 🎯 Tu primera tarea

Después de [instalar Olympus](#fast-install), abre OpenCode en tu proyecto y dile a Kael qué quieres hacer:

> 📱 **Crea:** Haz una app en Flutter para registrar hábitos, con almacenamiento local y una primera pantalla sencilla.

> 🐛 **Corrige:** Averigua por qué falla esta API, corrige la causa y ejecuta las pruebas relevantes.

**🧭 Empieza con Kael.** Se encarga de sumar especialistas cuando aportan algo. No tienes que elegir un agente para cada paso.

Kael conserva la evidencia de validación aplicable durante la implementación, los pull requests, CI y las etapas de publicación, así que no hace falta repetir pruebas solo porque cambió la etapa. Si queda un criterio de aceptación sin validar, solicita la comprobación mínima necesaria; las revisiones y los controles de publicación obligatorios siguen vigentes.

¿Quieres trabajar en paralelo o evaluar el rendimiento? Consulta los [comandos de OpenCode](#task-parallelism).

<a id="fast-install"></a>

## ⚡ Instala o actualiza

### Windows

**Requisitos:** PowerShell 7 (`pwsh`), OpenCode V2 y Python 3.11+.

```powershell
& ([scriptblock]::Create((irm 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1')))
```

✅ **Después de instalar:** abre una nueva ventana de PowerShell 7 y ejecuta `olympus version`.

### Linux

**Requisitos:** `curl`, `sh`, OpenCode V2 y Python 3.11+.

La [última versión estable](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) incluye el instalador para Linux:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh
```

Validado en Ubuntu 24.04 con WSL 2. [Configuración y verificación en Linux (en inglés) →](docs/INSTALLATION.md#linux-sh-entrypoint)

🔄 **¿Ya lo tienes instalado?** Ejecuta `olympus update` y luego `olympus doctor --scope global`.

🛡️ **Alcance:** la instalación es **global para tu usuario y solo para OpenCode**. Selecciona una versión publicada e inmutable y configura a Kael como agente global predeterminado. [Detalles de instalación y seguridad (en inglés) →](docs/INSTALLATION.md)

## 📌 Instala una versión específica

Elige un tag estable publicado y sustituye `vX.Y.Z` por ese tag exacto.

**Windows:**

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/vX.Y.Z/install.ps1')))
```

**Linux:** usa el mismo tag estable seleccionado si admite la instalación en Linux:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh -s -- vX.Y.Z
```

<a id="the-team"></a>

## 👥 Conoce al equipo

| Primario | Responsabilidad |
| --- | --- |
| 🧭 **Kael** | Decide y coordina la ejecución, reconcilia la evidencia, evalúa la aceptación y cierra la tarea. No inspecciona repositorios, investiga, ejecuta shell/Git/pruebas ni edita archivos. |
| 🗺️ **Atlas** | Primario independiente de análisis y planificación de solo lectura. Entrega un plan acotado a Kael; no ejecuta ni acepta el trabajo. |

**Los siete especialistas de Kael**

| Agente | Cuándo te ayuda |
| --- | --- |
| 🔎 **Veyra** | Encuentra código, documentación y evidencia relevante. |
| 💻 **Kovan** | Implementa cambios acotados y realiza el trabajo Git normal autorizado. |
| 🧪 **Nox** | Ejecuta pruebas y comprueba qué pasó realmente. |
| ⚖️ **Vera** | Revisa cambios de forma independiente para detectar errores y regresiones. |
| 🛡️ **Talos** | Diagnostica fallas de seguridad y evalúa su impacto. |
| 🧠 **Thales** | Ayuda a resolver fallas técnicas difíciles cuando la evidencia acotada no basta. |
| 🚀 **Helios** | Evalúa si una mejora de rendimiento justifica su costo y riesgo. |

Atlas no es un agente hijo de Kael. Orin y Argus están retirados y no forman parte del equipo actual de nueve roles.

🧠 **Modelos predeterminados:** los roles Sol usan GPT‑6.2 Sol. Los roles Luna y los modelos que elegiste explícitamente no cambian. [Configuración de modelos (en inglés) →](docs/INSTALLATION.md#olympus-cli)

<a id="task-parallelism"></a>

## 🧭 Comandos de OpenCode

⚡ **`/olympus.ultra <prompt>`** — busca trabajo listo e independiente hasta el límite de instrucciones (de 1 a 8) de la sesión actual de Kael o Atlas. El límite no es una meta y no se añade ningún scheduler.

> `/olympus.ultra Revisa estos módulos independientes y resume las pruebas.`

📈 **`/olympus.performance <prompt>`** — expresa una intención explícita de optimizar. Usa el método de Helios cuando aporte valor y requiere aprobación de una dirección concreta aún no resuelta antes de implementarla. La validación compara antes/después/delta/meta y comprueba la corrección.

> `/olympus.performance Evalúa cómo reducir el tiempo de respuesta de este endpoint sin cambiar su comportamiento.`

🚀 **`/olympus.performance-ultra <prompt>`** — combina una intención explícita de optimización con la admisión Ultra; no autoriza la implementación ni evita ninguna de las dos barreras.

💬 **Los tres comandos se ejecutan desde un primario Kael o Atlas y necesitan una instrucción.** Con argumentos vacíos o solo espacios, muestran el uso; desde un primario no compatible, indican el primario permitido. Ninguno invoca herramientas ni agentes en esos casos. No hay alias simples. [Detalles de uso (en inglés) →](docs/WORKFLOWS.md#native-task-commands)

<a id="portable-cli"></a>

## 🛠️ Olympus CLI

| Comando | Para qué sirve |
| --- | --- |
| `olympus --help` | Consulta los comandos más usados y sus ejemplos. |
| `olympus update` | Busca una versión estable más reciente. |
| `olympus agents list` | Consulta los modelos y el nivel de razonamiento de los agentes. |
| `olympus config set-max-parallel 6` | Guarda el límite compartido de instrucciones (1–8) para los agentes hijos directos de Kael o Atlas en cada sesión principal. |
| `olympus doctor --scope global` | Revisa la instalación global sin modificarla. |

🔍 **¿Necesitas más detalles?** Prueba `olympus update --help` para ver la ayuda del comando o agrega `--verbose` para ver qué se ejecutó. Para automatizar, usa `--json` en los comandos que lo admiten. [Todos los comandos y opciones avanzadas (en inglés) →](docs/INSTALLATION.md#olympus-cli)

<a id="fast-uninstall"></a>

## 🗑️ Desinstala

```powershell
olympus uninstall
```

Elimina los recursos administrados por Olympus que no se hayan modificado y su entrada en el PATH de Windows. Conserva los archivos ajenos a Olympus y los cambios posteriores al agente predeterminado. [Detalles de desinstalación (en inglés) →](docs/INSTALLATION.md)

<a id="guides"></a>

## 📚 Guías

La documentación técnica está en inglés.

| Tema | Dónde encontrarlo |
| --- | --- |
| ⚡ **Instalación y desinstalación** | [Alcance, opciones y solución de problemas](docs/INSTALLATION.md) |
| 🎯 **Cómo usar Olympus** | [Comandos y ejemplos](docs/WORKFLOWS.md) |
| 🛠️ **CLI** | [Configuración y diagnósticos](docs/INSTALLATION.md#olympus-cli) |
| 🧩 **Soporte de OpenCode** | [Funciones compatibles y sus límites](docs/HARNESS-CAPABILITIES.md) |
| 🛡️ **Seguridad** | [Reporta un problema de seguridad](SECURITY.md) |
| 🧑‍💻 **Contribuye** | [Desarrollo](docs/DEVELOPMENT.md) · [Hoja de ruta](docs/ROADMAP.md) · [Árboles de trabajo](docs/WORKTREES.md) |
| 📦 **Versiones** | [Última versión estable](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) · [Todas las versiones](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) · [Registro de cambios](CHANGELOG.md) |
| 📖 **Toda la documentación** | [Índice de guías](docs/README.md) · [Licencia](LICENSE) |

## 🔗 Menciones

- [XERJ Corpus Hub](https://hub.xerj.org/corpus/edulynch--opencode-olympusagents) — un catálogo de proyectos de código abierto que da más contexto a las herramientas de IA.

## ⚖️ Uso y responsabilidad

Los agentes pueden modificar archivos y ejecutar comandos según los permisos que les concedas. Empieza en una rama de prueba, comprueba que los permisos correspondan a la tarea y revisa los cambios propuestos antes de aplicarlos o integrarlos. Ejecuta las comprobaciones pertinentes y confirma los resultados antes de confiar en ellos.

Olympus se proporciona «tal cual», sin garantías. Consulta la [licencia MIT](LICENSE) para conocer los términos completos, incluida la limitación de responsabilidad.
