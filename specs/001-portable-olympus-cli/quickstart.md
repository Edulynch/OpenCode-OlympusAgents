# Slice A: CLI Olympus de sólo lectura

**Implementada en este checkout; Windows validado, Linux hosted pendiente.** Estado y evidencia en [tasks.md](tasks.md). R49 conserva PASS y no se repitió. Esta guía describe exclusivamente los comandos disponibles de A; B sigue condicionada y C bloqueada.

## Requisitos y contexto

Python **3.11+ real**, sólo biblioteca estándar. No TOML Kit ni instalación automática de dependencias. El intérprete Windows acreditado es C:/Users/BLAUTECH/.local/bin/python3.11.exe (3.11.17); un alias Microsoft Store no sustituye al intérprete.

Se necesita un checkout confiable de Olympus con fuentes y renderer. La CLI carga el renderer de ese origen; no ejecuta código encontrado en el destino. No requiere OpenCode/Codex, WSL, Docker, Node ni credenciales.

La entrada de módulo se usa desde el checkout con -B. Los launchers apuntan a su propio checkout y funcionan desde otro directorio. La opción global --source acepta otro origen **absoluto y confiable**, antes del subcomando; el cwd del destino no selecciona otra fuente automáticamente. --version informa la release declarada por la fuente en install.ps1, actualmente v0.4.9: no certifica publicación de los comandos nuevos ni integridad de la fuente.

## Comandos disponibles

Desde el checkout, con el intérprete adecuado:

```text
python3.11 -B -m olympus --help
python3.11 -B -m olympus --version
python3.11 -B -m olympus models list
python3.11 -B -m olympus models list --json
python3.11 -B -m olympus config check
python3.11 -B -m olympus config check --harness codex --json
```

El listado presenta doce roles, identidad, familia, esfuerzo y ambos IDs desde Core. OpenCode representa doce agentes; Codex tiene diez especialistas, Kael como raíz y Aegis ausente. Un ID Codex de Aegis no equivale a un agente instalado. Check compara outputs del renderer en memoria; --harness admite opencode, codex y all (default). No regenera ni repara archivos.

### Windows: launcher desde cualquier directorio

En PowerShell, empezando en el checkout confiable, seleccionar el intérprete disponible y un proyecto Git existente (sustituir la ruta de ejemplo):

```powershell
$sourceCheckout = (Get-Location).Path
$targetProject = 'D:\Repos\sample project'
$env:OLYMPUS_PYTHON = (Get-Command python3.11 -CommandType Application | Select-Object -First 1).Source
Set-Location -LiteralPath $targetProject
& "$sourceCheckout\scripts\olympus.cmd" --help
& "$sourceCheckout\scripts\olympus.cmd" --version
& "$sourceCheckout\scripts\olympus.cmd" models list --json
& "$sourceCheckout\scripts\olympus.cmd" config check --harness all
& "$sourceCheckout\scripts\olympus.cmd" status --scope project --target $targetProject --harness all
& "$sourceCheckout\scripts\olympus.cmd" status --scope project --target $targetProject --harness all --json
$LASTEXITCODE
```

OLYMPUS_PYTHON es una ruta/nombre de intérprete sin argumentos. No se modifica PATH ni se incorpora un instalador. La alternativa Python directa, también desde cwd externo, es:

```powershell
& $env:OLYMPUS_PYTHON -B "$sourceCheckout\scripts\olympus_cli.py" models list --json
& "$sourceCheckout\scripts\olympus.cmd" --source $sourceCheckout config check --json
```

El módulo requiere el contexto de importación del checkout; desde otros directorios se recomienda el launcher. Las pruebas externas del módulo usan PYTHONPATH explícito y aislado, sin discovery.

### Linux: uso previsto, pendiente de CI hosted

Seleccionar rutas reales de checkout/proyecto. El permiso ejecutable se prepara una vez **antes** de las consultas; la CLI nunca lo cambia. El job Linux de FAST hace la misma preparación:

```sh
source_checkout="/path/to/Olympus checkout"
target_project="/path/to/Git project"
export OLYMPUS_PYTHON="$(command -v python3.11)"
chmod +x "$source_checkout/scripts/olympus"
cd "$target_project"
"$source_checkout/scripts/olympus" --help
"$source_checkout/scripts/olympus" --version
"$source_checkout/scripts/olympus" models list --json
"$source_checkout/scripts/olympus" config check --harness all
"$source_checkout/scripts/olympus" status --scope project --target "$target_project" --json
```

Estos ejemplos no son evidencia Linux. El launcher permanece ligado al checkout; no se ofrece distribución standalone ni instalación sin clonar.

## Salidas y límites

Salida humana: operación/resultado, origen/contexto y datos legibles. Un destino sin manifest informa status: absent, installed_harnesses: [] e integrity: "unverified"; termina con exit 0 sin instalar nada.

Con --json, stdout contiene un único documento con schema_version=1, operation, result, context, data e issues. Ejemplo completo de ausencia, con rutas ilustrativas:

```json
{
  "schema_version": 1,
  "operation": "status",
  "result": "absent",
  "context": {
    "source": "D:/Repos/Olympus",
    "kind": "installation_metadata",
    "scope": "project",
    "harness": "all",
    "target": "D:/Repos/sample project"
  },
  "data": {
    "installed_harnesses": [],
    "integrity": "unverified",
    "ownership": "unverified",
    "assignments": "unknown",
    "runtime_validation": "not_performed",
    "evidence": "none",
    "installation_state": "absent"
  },
  "issues": []
}
```

Los datos humanos y JSON proceden del mismo objeto. El listado usa data.roles; check informa coherent y número de outputs. Errores JSON permanecen en issues, sin texto humano mezclado; diagnósticos de presentación humana van a stderr.

Status project exige --target absoluto con una marca .git de raíz de worktree; leer esa marca no verifica el repositorio. Sólo lee manifests: versión/origen e inventario **reportados**, nunca ownership/hash/asignaciones instaladas acreditadas. No abre archivos enumerados por el manifest ni copia modelos del source como instalados. Metadatos inválidos fallan; manifests simultáneos o contradicciones de scope/ubicación bloquean. Metadatos legados se identifican sin migrar. Un harness seleccionado fuera del inventario se informa ausente.

```text
python3.11 -B -m olympus status --scope global --json
```

Esta consulta global devuelve BLOCKED/exit 3: A no realiza discovery ni consulta configuraciones personales. No ejecuta VerifyOnly, runtimes ni modelos. Check local no acredita disponibilidad/auth de modelos ni recarga de sesiones.

| Exit | Resultado de Slice A |
|---|---|
| 0 | Consulta válida, check coherente o ausencia informativa |
| 1 | Fuentes/metadatos inválidos, output ausente o drift |
| 2 | Argumentos/contexto inválidos; comandos no disponibles |
| 3 | Consulta bloqueada, incluida ubicación global sin discovery |

No hay operación parcial en A que emita exit 4. Las consultas no modifican fuentes, outputs, configuraciones, manifests, permisos ni cachés. Usar -B en entradas Python; los launchers lo imponen. Scratch previo se informa sin reparar. Edición, recuperación y aplicación no se exponen en la ayuda ni se aceptan.

## Evidencia enfocada y plataformas

```text
python3.11 -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a -v
```

La suite existente prepara fixtures antes de cada snapshot; compara inventarios, SHA-256, mtimes y modos en consultas exitosas/fallidas, incluidos fuentes, outputs, manifests simulados, destino y HOME/config/cache/temp aislados. No ejecuta instaladores ni agentes. Los manifests y marcas .git son fixtures; el smoke nativo de la CLI no acredita runtime OpenCode/Codex ni una instalación nueva.

| Plataforma/comprobación | Estado |
|---|---|
| Windows, Python 3.11.17, módulo y .cmd nativo desde cwd externo; espacios/ñ, JSON, exits y cero mutaciones | PASS: 19 casos, 1 POSIX omitido, exit 0 |
| Sintaxis POSIX revisada con Git Bash en Windows | PASS sólo de sintaxis; no evidencia Linux |
| Linux hosted, Python 3.11 y launcher ejecutado directamente | PENDING_CI_VALIDATION: job slice-a-linux agregado al workflow FAST, no publicado/ejecutado |
| macOS | NOT VERIFIED |

No se ejecutaron FAST/FULL/RUNTIME ni se repitió R49. La aceptación completa de A queda pendiente de Linux hosted. [Plan](plan.md), [research](research.md) y [contrato](contracts/cli.md) conservan el diseño de las tres slices; la ejecución actual está en [tasks.md](tasks.md).
