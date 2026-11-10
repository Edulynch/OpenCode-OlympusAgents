# CLI portátil Olympus — quickstart (v0.5.0 candidate)

**Alcance del candidato**: Slice A (consulta) y B (edición canónica) aceptadas en Windows/Linux; C1–C6 para instalaciones **project** con preview de asignaciones también antes de `--execute`, doctor y routing de install/uninstall sólo donde estén cualificados; C7 para `status`, `doctor` y preview **global read-only**. Global `config apply --execute` y recovery no están soportados (seguimiento en [#122](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/122)). macOS **NOT VERIFIED**. No se declara cualificación genérica de instaladores ni runtime fuera de la matriz de [v0.5.0](../../docs/RELEASE-v0.5.0.md). [Evidencia histórica de A/B/C4](tasks.md).

## Requisitos y contexto

Python **3.11+ real**. Slice A usa sólo biblioteca estándar y no carga TOML Kit. Slice B requiere TOML Kit 0.13.3, opcional y sólo para preview/edición; se prepara explícitamente en el entorno elegido. `config recover` sigue siendo stdlib-only. No hay instalación automática. El intérprete Windows validado fue Python 3.11.17; usa un intérprete real, no un alias Microsoft Store.

Se necesita un checkout confiable de Olympus con fuentes y renderer. La CLI carga el renderer de ese origen; no ejecuta código encontrado en el destino. No requiere OpenCode/Codex, WSL, Docker, Node ni credenciales.

La entrada de módulo se usa desde el checkout con -B. Los launchers apuntan a su propio checkout y funcionan desde otro directorio. La opción global --source acepta otro origen **absoluto y confiable**, antes del subcomando; el cwd del destino no selecciona otra fuente automáticamente. `olympus --version` informa la release declarada por la fuente en `install.ps1`, actualmente `v0.4.12`: no certifica publicación ni integridad de la fuente. **No existe todavía una distribución standalone ni un comando `olympus` universal instalado.** La instalación pública de primer uso sin clonar se explica por separado en el [README](../../README.md#fast-install).

## Comandos disponibles

Desde el checkout, con el intérprete adecuado:

```text
python3.11 -B -m olympus --help
python3.11 -B -m olympus --version
python3.11 -B -m olympus models list
python3.11 -B -m olympus models list --json
python3.11 -B -m olympus config check
python3.11 -B -m olympus config check --harness codex --json
python3.11 -B -m olympus config apply --scope project --target /path/to/existing-project --harness opencode --dry-run
python3.11 -B -m olympus config apply --scope project --target /path/to/existing-project --harness opencode --execute
python3.11 -B -m olympus doctor --scope project --target /path/to/existing-project --harness all --json
```

El listado presenta los once roles canónicos, identidad, familia, esfuerzo y ambos IDs desde Core; Kael es el único orquestador. OpenCode representa los once roles; Codex representa Kael como raíz y los diez especialistas como agentes. Check compara outputs del renderer en memoria; `--harness` admite `opencode`, `codex` y `all` (default). No regenera ni repara archivos.

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

### Linux: launcher del checkout Git

El checkout Git conserva `scripts/olympus` como ejecutable (`100755`). Compruébalo sin cambiar permisos; la CLI no modifica el checkout. El job Linux de FAST exige el permiso antes y después de las consultas:

```sh
source_checkout="/path/to/Olympus checkout"
target_project="/path/to/Git project"
export OLYMPUS_PYTHON="$(command -v python3.11)"
test -x "$source_checkout/scripts/olympus"
cd "$target_project"
"$source_checkout/scripts/olympus" --help
"$source_checkout/scripts/olympus" --version
"$source_checkout/scripts/olympus" models list --json
"$source_checkout/scripts/olympus" config check --harness all
"$source_checkout/scripts/olympus" status --scope project --target "$target_project" --json
```

El run hosted de PR #69 pasó la suite, pero usó `chmod` antes de las consultas; no acredita el modo original del checkout. En el run final de GitHub Actions Linux [38857503366](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366/job/116832156025), `scripts/olympus` se comprobó ejecutable antes y después de las pruebas sin ejecutar `chmod`, y el control de Git confirmó un checkout limpio con `core.filemode=true`. El launcher permanece ligado al checkout; no se ofrece distribución standalone ni instalación sin clonar.

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

Históricamente Slice A devolvía BLOCKED/exit 3 para global. Slice C7 ahora informa manifests globales como metadatos reportados (o `absent`/exit 0), sin afirmar ownership, integridad, runtime o proveedor. Si no puede resolver una raíz segura, devuelve BLOCKED/exit 3. Check local no acredita disponibilidad/auth de modelos ni recarga de sesiones.

| Exit | Resultado de Slice A |
|---|---|
| 0 | Consulta válida, check coherente o ausencia informativa |
| 1 | Fuentes/metadatos inválidos, output ausente o drift |
| 2 | Argumentos/contexto inválidos; comandos no disponibles |
| 3 | Consulta bloqueada por ubicación global no verificable o capacidad no cualificada |

Slice A no tiene operación parcial que emita exit 4: sus consultas no modifican fuentes, outputs, configuraciones, manifests, permisos ni cachés. Usar -B en entradas Python; los launchers lo imponen. Scratch previo se informa sin reparar. La edición/recovery de Slice B se documenta aparte abajo.

### Diagnóstico read-only de proyecto (Slice C4)

`doctor` requiere `--scope project`, una raíz de worktree Git absoluta y
`--harness opencode|codex|all`. Lee el manifest y, para harnesses registrados,
usa `scripts/bootstrap.ps1 -VerifyOnly` desde el checkout local coherente. La
verificación profunda sólo se cualifica en Windows con PowerShell 7; en otras
plataformas o sin `pwsh` el comando informa `verification_unavailable` (exit 3)
sin afirmar integridad. No ejecuta runtime discovery ni consulta modelos.

Las asignaciones instaladas quedan `unknown`: el manifest no guarda IDs por rol
y el diagnóstico no los deduce de la fuente actual. El proceso PowerShell usa un
`USERPROFILE` temporal para contener su cache de inicio; se elimina al terminar.
No se cambia el proyecto ni se instalan/reparan recursos. Ejemplo Windows:

```powershell
& "$sourceCheckout\scripts\olympus.cmd" doctor --scope project --target $targetProject --harness all --json
$LASTEXITCODE
```

La aplicación C1/C3 sigue siendo una operación separada: `doctor` no deduce
asignaciones instaladas. El preview C6 las compara desde recursos administrados
verificados, y FR-008 también las muestra antes del `--execute` de proyecto.

### Install y uninstall mediante motores oficiales (Slice C5)

C5 sólo enruta a los motores ya existentes; no implementa un instalador paralelo.
Requiere Windows y PowerShell 7 (`pwsh`). Project exige un `--target` absoluto que
sea exactamente la raíz de un worktree Git existente y distinto del checkout de
fuente. Global rechaza `--target`; sus raíces sólo las resuelve el motor oficial.
El cwd heredado queda como contexto de sólo lectura para detectar overrides de
proyecto; nunca se usa como destino global ni se suplanta `USERPROFILE`.

`install --version` exige un tag exacto de release Olympus; es distinto de
`olympus --version`, que sólo informa la versión de la herramienta. El launcher
consulta metadata `releases/tags/<tag>`, exige que el tag devuelto coincida,
`immutable=true`, release publicado/no prerelease y la identidad del installer.
No se aceptan checkouts, archivos ni source overrides como origen de instalación.
Sustituye el tag de ejemplo sólo por un release oficial publicado:

```powershell
$sourceCheckout = (Get-Location).Path
$targetProject = 'D:\Repos\Sample Project'
$releaseTag = 'v0.4.11'
& "$sourceCheckout\scripts\olympus.cmd" install --scope project --target $targetProject --harness opencode --version $releaseTag --dry-run --json
$LASTEXITCODE
& "$sourceCheckout\scripts\olympus.cmd" install --scope project --target $targetProject --harness opencode --version $releaseTag --execute
$LASTEXITCODE
```

`--dry-run` y `--execute` son mutuamente excluyentes y requeridos. El preview usa
el `-DryRun` del installer; puede descargar el release a temp/cache, pero no
instala recursos en el target. No ejecutes el ejemplo de `--execute` salvo que
quieras cambiar ese target.

```powershell
# Global: no --target; el motor descubre las raíces oficiales.
& "$sourceCheckout\scripts\olympus.cmd" install --scope global --harness all --version $releaseTag --dry-run --json
& "$sourceCheckout\scripts\olympus.cmd" uninstall --scope global --harness all --dry-run --json

# Project uninstall usa el motor local y no consulta la red.
& "$sourceCheckout\scripts\olympus.cmd" uninstall --scope project --target $targetProject --harness opencode --execute --json
```

El uninstaller project no ofrece preview: `uninstall --scope project ...
--dry-run` se bloquea antes de arrancar PowerShell. En global, el preview nativo
lee manifests/hashes sin borrar recursos; `--harness all --execute` procesa ambos
roots secuencialmente y no es atómico. Los uninstallers sólo retiran recursos
manifest-owned intactos; drift o ownership inválido bloquea el motor. JSON es un
solo documento e incluye exit code/stdout/stderr nativos. Si una mutación falla,
se interrumpe o excede 300 s, el resultado es `unconfirmed`/exit 4 cuando no se
pueden descartar efectos parciales. No reintentes sin inspeccionar el destino.
La prueba de versión de `pwsh` está acotada a 10 s; el motor a 300 s. Linux y
macOS quedan bloqueados sin afirmar compatibilidad.

### Preview y aplicación explícita project (Slices C1/C3)

El preview requiere una instalación existente con un único manifest project válido,
el harness seleccionado ya instalado y todos los recursos administrados intactos
según sus hashes. Comprueba que la raíz indicada es exactamente una raíz Git,
que la fuente genera outputs coherentes y que no hay destinos OpenCode en conflicto.
Muestra archivos que cambiarían, archivos iguales y harnesses no seleccionados que
permanecerían intactos. Un manifest ausente/ambiguo, inventario no soportado, drift,
enlaces o conflicto bloquean el preview. No instala harnesses, no consulta runtimes
ni proveedores. `--dry-run` no crea lock, scratch ni escribe archivos o manifests.
`--execute` muestra el mismo plan, adquiere el lock compartido del target, vuelve a
validar ownership y drift bajo exclusión, y guarda un journal recuperable antes de
reemplazar recursos administrados y el manifest. Sólo actualiza harnesses seleccionados;
los demás y los archivos no administrados permanecen intactos. El manifest registra
la fuente como `installed_version=local` y `installed_from_commit=unknown`; no convierte
una fuente local en release oficial inmutable. Si una interrupción deja journal, los siguientes apply se bloquean
hasta recovery explícita. Recovery vuelve a validar el inventario con el renderer del checkout fuente que originó
el journal: usa ese mismo checkout (o su ruta explícita con `--source`) y conserva su renderer sin modificaciones
mientras exista `.olympus-cli-config-apply`. Una divergencia preserva evidencia y no se fuerza.

Ejemplo en PowerShell desde el checkout de Olympus, usando un proyecto existente:

```powershell
$sourceCheckout = (Get-Location).Path
$targetProject = 'D:\Repos\sample project'
$env:OLYMPUS_PYTHON = (Get-Command python3.11 -CommandType Application | Select-Object -First 1).Source
& "$sourceCheckout\scripts\olympus.cmd" config apply --scope project --target $targetProject --harness opencode --dry-run --json
$LASTEXITCODE
```

Para una instalación dual, selecciona `--harness all`; si un harness no figura en
el manifest, el preview se bloquea en vez de instalarlo. `--json` emite un único
documento con `changes`, `unchanged`, `preserved`, verificaciones y conflictos.
Un preview exitoso sólo describe el estado observado; no habilita ni ejecuta
aplicación. Para mutar, omite `--json` y usa explícitamente `--execute`; `--dry-run`
y `--execute` son mutuamente excluyentes. La ejecución muestra antes de escribir
las mismas asignaciones actuales/propuestas del preview, sin inferir familias
instaladas ni disponibilidad de proveedores. Después de una interrupción usa:

```powershell
& "$sourceCheckout\scripts\olympus.cmd" --source $sourceCheckout config recover --scope project --target $targetProject
```

### Estado, diagnóstico y preview global read-only (Slice C7)

OpenCode y Codex usan raíces globales distintas. `status` sólo reporta metadata del
manifest, incluso cuando existe; no certifica integridad. `doctor` valida
inventario/hashes y en Windows usa el motor oficial `global-install.ps1 -VerifyOnly`
con PowerShell 7; fuera de Windows la verificación nativa se declara no disponible.
El preview valida hashes y muestra las diferencias sin modificar ni adoptar recursos.

En una selección mixta instalada/ausente, `result=absent` y `selection_state=partial`
identifican la cobertura incompleta sin usar un resultado fuera del contrato; las
asignaciones conjuntas quedan `unknown`. La detección de drift managed devuelve
`failed`/exit 1; conflictos, versiones no reconocidas y verificaciones nativas
no disponibles bloquean con exit 3. `AGENTS.override.md` global de Codex tiene
mayor precedencia y bloquea el preview, sin leer ni modificar su contenido.

```powershell
cd 'D:\WORKSPACE\Personal\Tools\OpenCode-OlympusAgents'
git status --short --branch
git branch --show-current
python -B -m olympus status --scope global --harness all --json
python -B -m olympus doctor --scope global --harness codex --json
python -B -m olympus config apply --scope global --harness all --dry-run --json
```

Para probarlo sin leer tu instalación, prepara `OPENCODE_CONFIG_DIR` y `CODEX_HOME`
apuntando a fixtures globales aislados. No uses esas variables para una instalación
real sin revisar sus destinos. El preview marca `apply_available=false`; su
`--execute` y recovery global están bloqueados. OpenCode global no administra
`opencode.jsonc`; Codex registra a Kael en `olympus.config.toml`, no como
especialista. Familias actuales siguen `unknown`; formatos no verificables se
etiquetan `unsupported`. No se prueban proveedores, sesiones ni overrides.

## Evidencia enfocada y plataformas

```text
python3.11 -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a -v
```

La suite existente prepara fixtures antes de cada snapshot; compara inventarios, SHA-256, mtimes y modos en consultas exitosas/fallidas, incluidos fuentes, outputs, manifests simulados, destino y HOME/config/cache/temp aislados. No ejecuta instaladores ni agentes. Los manifests y marcas .git son fixtures; el smoke nativo de la CLI no acredita runtime OpenCode/Codex ni una instalación nueva.

| Plataforma/comprobación | Estado |
|---|---|
| Windows, Python 3.11.17, módulo y .cmd nativo desde cwd externo; espacios/ñ, JSON, exits y cero mutaciones | PASS: 19 casos, 1 POSIX omitido, exit 0 |
| Sintaxis POSIX revisada con Git Bash en Windows | PASS sólo de sintaxis; no evidencia Linux |
| Linux hosted, Python 3.11 y launcher ejecutado directamente | PASS en [run 38644271501](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38644271501/job/116127153113): 20 casos, 19 PASS, 1 Windows omitido, exit 0; usó `chmod`, así que no valida el bit preservado por checkout |
| Checkout Git con modo ejecutable 100755, sin preparación de permisos | PASS en GitHub Actions Linux [run 38857503366](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366/job/116832156025): `test -x scripts/olympus` antes y después de las pruebas, sin ejecutar `chmod`; checkout limpio según el control de Git con `core.filemode=true` |
| macOS | NOT VERIFIED |

Slice A está **SHIPPED**; los comandos y su evidencia anteriores se conservan sin cambios. No se ejecutaron FULL/RUNTIME ni se repitió R49. La reconciliación de B, C y macOS se detalla a continuación y en [tasks.md](tasks.md).

## Slice B — edición explícita de modelos en la fuente

Las familias iniciales son Sol (`openai/gpt-6.1-sol` en OpenCode; `gpt-6.1-sol` en Codex) y Luna (`openai/gpt-6-luna`; `gpt-6-luna`). Los identificadores son intención local: la CLI no consulta proveedores ni verifica disponibilidad/autenticación.

### Preparación opcional de TOML Kit

La edición/preview necesita `tomlkit==0.13.3`; no se instala automáticamente ni afecta a Slice A. Ejecuta ambos ejemplos siguientes desde la raíz del checkout confiable de OlympusAgents; crean un entorno fuera del checkout y usan su intérprete para `pip install -r requirements-cli.txt`.

```sh
python3.11 -m venv /absolute/path/to/olympus-cli-venv
/absolute/path/to/olympus-cli-venv/bin/python -m pip install -r requirements-cli.txt
```

En Windows PowerShell, la variante nativa es:

```powershell
python3.11 -m venv "$env:TEMP\olympus-cli-venv"
& "$env:TEMP\olympus-cli-venv\Scripts\python.exe" -m pip install -r requirements-cli.txt
```

Usa después ese mismo Python 3.11+ para los comandos B. La recuperación no necesita TOML Kit.

Define el ejecutable del entorno preparado para los siguientes ejemplos:

```powershell
$python = "$env:TEMP\olympus-cli-venv\Scripts\python.exe"
```

```sh
PYTHON=/absolute/path/to/olympus-cli-venv/bin/python
```

### Previews sin escritura

Desde el checkout confiable:

```powershell
& $python -B -m olympus models set-family sol --opencode openai/gpt-6.1-sol-example --codex gpt-6.1-sol-example --dry-run --json
& $python -B -m olympus agents set-model veyra --family luna --effort high --dry-run
```

```sh
"$PYTHON" -B -m olympus models set-family sol --opencode openai/gpt-6.1-sol-example --codex gpt-6.1-sol-example --dry-run --json
"$PYTHON" -B -m olympus agents set-model veyra --family luna --effort high --dry-run
```

`models set-family` requiere ambos IDs; `agents set-model` acepta `--family`, `--effort` o ambos. `--json` sólo se permite junto con `--dry-run`. Los previews no crean lock ni scratch.

### Edición explícita en una fuente aislada

La forma de edición es la misma orden sin `--dry-run`. Para evitar cambios accidentales, prepara primero un checkout/copia descartable con Core y renderer válidos y apunta `--source` a su ruta absoluta. No ejecutes ejemplos de edición contra una instalación ni sobre modelos/outputs personales:

```powershell
$source = 'C:\Temp\olympus-source-fixture' # copia aislada ya preparada
& $python -B -m olympus --source $source models set-family sol --opencode openai/gpt-6.1-sol-example --codex gpt-6.1-sol-example
& $python -B -m olympus --source $source agents set-model veyra --family luna --effort high
```

En Linux, asigna `source` a la ruta absoluta de una copia aislada y usa `--source "$source"` con la misma sintaxis y `"$PYTHON"` como intérprete. La operación muestra el preview antes de escribir. Sólo cambia la intención en `olympus/core/models.toml` y los outputs existentes que realmente cambian según el renderer; no modifica manifests ni despliega los cambios a instalaciones. La aplicación de destino es una operación separada y explícita: `config apply --execute`, documentada arriba.

### Lock estable, scratch y recuperación explícita

- `.olympus-cli-edit.lock` es un archivo vacío y estable que se conserva tras cleanup; no lo borres ni recrees para “liberar” una operación. Su existencia por sí sola no indica que haya un batch pendiente.
- `.olympus-cli-edit/` contiene el scratch/registro PREPARED o COMMITTED. Si existe scratch pendiente, las nuevas ediciones bloquean incluso con el lock libre; no hay reparación, reanudación ni retry automático.
- Sólo si hay un batch pendiente, solicita recovery explícita contra el mismo origen confiable. Recovery abre un lock existente y valida identidad, registro, hashes, read-set y backups antes de restaurar o limpiar:

```powershell
& $python -B -m olympus --source 'C:\Path\to\source-checkout' config recover
```

```sh
"$PYTHON" -B -m olympus --source /absolute/path/to/source-checkout config recover
```

Recovery no instala TOML Kit. Lock ausente/inseguro/ocupado, identidad divergente, terceros cambios, target ausente o backup inválido bloquean y preservan evidencia; no fuerces ni elimines scratch manualmente.

El protocolo coordina operaciones Olympus cooperantes y bloquea conflictos observables. No garantiza exclusión frente a escritores no cooperantes, atomicidad visible de varios archivos ni durabilidad absoluta ante pérdida eléctrica; una carrera posterior al último hash queda fuera de la garantía. Estos límites no autorizan a ignorar conflictos detectados.

### Evidencia y plataforma

| Gate | Resultado reconciliado |
|---|---|
| Windows, T019, CPython 3.11.17 | 55 PASS, 0 FAIL, 0 ERROR, 3 SKIPPED; exit 0. Los tres casos omitidos crean symlinks y Windows devolvió `WinError 1314`; no se cuentan como PASS Windows. |
| Linux hosted, T020, Ubuntu 24.04 / CPython 3.11.17 / TOML Kit 0.13.3 | 58 PASS, 0 FAIL, 0 SKIPPED; 37.350 s, exit 0. Los tres escenarios de symlink pasaron. Fuente: commit `539976812d14289696dbd3824f1ae706ac2f1947`, run [38857503366](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366), job [116832156025](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366/job/116832156025). |
| G2 / Slice B | **PASS Windows/Linux**. La prueba verificó snapshots, independencia de A, rollback/recovery, conflictos y los 15 límites del write-set. El checkout fuente quedó sin cambios. |
| C5 / Windows local | **PASS**: `python -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_c5 -v` ejecutó 8/8 sin skips; incluye project-uninstall real sobre Git fixtures aislados y global uninstall `--dry-run` real contra roots temporales `OPENCODE_CONFIG_DIR`/`CODEX_HOME` con manifests mínimos. Bytes/modos de roots y source quedaron iguales; probe y motor recibieron `PYTHONDONTWRITEBYTECODE=1`, y el motor mantuvo el `USERPROFILE` del fixture mientras el probe usó otro temporal. Los snapshots cubren roots/source, no temp/cache. Adquisición/API de release y ruta de instalación siguen con mocks; sin red, instalaciones reales ni CI remoto C5. |
| Launcher UX / Windows local | **PASS**: `pwsh -NoProfile -NonInteractive -File tests/installer-ux/qualify.ps1` terminó con `INSTALLER UX QUALIFICATION: PASS`; latest sigue igual y C5 valida endpoint exact-tag, mismatch, release mutable y forwarding de dry-run con API/installer mocks y raíces temporales. |
| macOS | **NOT VERIFIED**. |

FAST Windows y CodeQL también pasaron en el PR Draft #70. La evidencia C1 histórica fue Windows 6/6 **PASS** (local) y Linux 6/6 **PASS** en GitHub Actions [run 41310141414](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/41310141414), commit `a09cdeb934804f4a6c86d1e998f930ccb0be6f70`; no es validación de C3. El Linux CI inicial del Draft PR #110 pasó en [run 42392613719](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/42392613719) sobre el HEAD `2b23a26c92f2d7c014d92da96c2dafe7054ec8e4`, pero el filtro de entonces ejecutó 13 pruebas y excluyó `test_slice_c3_project_apply_uses_existing_target_writer_lock`. Tras ampliar el filtro, el job Linux [run 42401262655](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/42401262655/job/128489298237) pasó las 14 pruebas sin skips, incluida esa regresión C3, en el commit `4f1f5515faacec5aa2ed71d90d4081b44f9c333a`. FULL, runtime interactivo y operaciones de instalación/desinstalación sobre instalaciones reales **NOT_RUN**; no se afirma ejecución de CI remoto para C5. macOS **UNVERIFIED**.
