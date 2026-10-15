# Tasks: CLI portátil Olympus — Slice A

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [contracts/cli.md](contracts/cli.md) y [quickstart.md](quickstart.md)  
**Documentation Mode**: New — tareas de implementación de la nueva feature  
**Baseline**: v0.4.9, tag remoto publicado resuelto a `c30a19dd410b1815f4591b204615cae0dd9e9a5f`

## Scope Rules

- Este archivo contiene trabajo de implementación **exclusivamente para Slice A / User Story 1**, más la reconciliación previa del gate R49 y documentación de uso de A. Conserva intactas las tres slices y la especificación.
- R49 se reconcilió previamente mediante la ejecución aislada documentada en [evidence/r49-20261014-c30a19d/report.md](evidence/r49-20261014-c30a19d/report.md); no se repitió. T002–T009 están completadas, incluido T008 PASS en Linux hosted. La validación final del workflow actualizado, que confía en el permiso 100755 de Git, sigue pendiente.
- Slice B y Slice C no son dependencias de A y no generan tareas aquí. No incluir TOML Kit, edición de modelos, recuperación, aplicación instalada, instalación/desinstalación ni cambios a modelos, Core, adaptadores, permisos, manifests o archivos generados.
- La marca **NUEVO** refleja la propuesta original del plan; los archivos de A correspondientes a T002–T009 ya fueron creados, como registra la ejecución debajo. Las rutas B/C siguen siendo propuestas.
- T001 conserva su evidencia de R49. T002–T009 se marcan por implementación, pruebas y documentación registradas abajo. El run hosted consumido valida T008 para la fuente ejecutada; el nuevo comportamiento que elimina `chmod` necesita el CI final. Este documento no confiere autoridad de publicación ni un gate de aprobación adicional.

## Format

`- [ ] T001 [P?] [US1?] Descripción con ruta exacta del repositorio`

- **[P]** se omite: las tareas siguen dependencias explícitas y no requieren ownership paralelo.
- **[US1]** identifica el trabajo funcional de Slice A. El gate R49 y la documentación final no pertenecen a una historia de usuario.
- Ejecutar únicamente las comprobaciones enfocadas indicadas abajo. No correr perfiles FAST/FULL/RUNTIME, instalación real como parte de la generación, harnesses amplios ni matriz de sistemas operativos.

## Tasks

### Prerrequisito bloqueante de implementación — R49

- [x] T001 Reconciliar en [`specs/001-portable-olympus-cli/research.md`](research.md), **antes de cualquier cambio de código, pruebas, workflow o launcher**, instalación y `VerifyOnly` desde la fuente remota normal del tag inmutable `v0.4.9`, commit exacto `c30a19dd410b1815f4591b204615cae0dd9e9a5f`, en un proyecto Git temporal aislado, scope project/harness codex. Completada con exit 0 en ambas operaciones, 12/12 recursos coincidentes con manifest/release y snapshots personales/desarrollo/control idénticos; ver [evidence/r49-20261014-c30a19d/report.md](evidence/r49-20261014-c30a19d/report.md). No stubs, APIs/modelos, native runtime ni SourceRoot/SourceArchive; no acredita otros scopes/harnesses.

### Slice A — US1: consulta portable sin mutaciones

- **Goal**: La persona operadora puede consultar estado y asignaciones de los doce roles en Windows y Linux, recibe datos JSON equivalentes a la salida humana y completa las consultas sin diferencias de inventario ni de bytes en los archivos examinados.
- **Independent Test**: Ejecutar sólo pruebas `slice_a` y los entrypoints en Windows local y Linux hosted; contrastar los doce roles/ambos IDs, parsear el envelope JSON y comparar su contenido con la salida humana; capturar inventario y hashes antes/después de consultas válidas e inválidas y exigir cero diferencias.

- [x] T002 [US1] Crear la entrada mínima Python 3.11+ con `argparse`, `--help`, `--version`, `--source` explícito y dispatch de comandos en archivos **NUEVOS** `olympus/__init__.py`, `olympus/__main__.py` y `olympus/cli.py`; admitir `python -B -m olympus`, evitar caches de importación también en procesos hijos y rechazar argumentos/comandos desconocidos sin importar ni crear módulos placeholder de B/C ni duplicar registros canónicos.
- [x] T003 [US1] Implementar `models list` y `config check` read-only en `olympus/cli.py`, leyendo `olympus/core/models.toml` con `tomllib` y reutilizando `checked_sources`, `role_model` y `outputs_for` de [`scripts/render_harnesses.py`](../../scripts/render_harnesses.py); presentar los doce roles, identidad, familia, esfuerzo y ambos IDs, reflejar a Kael como raíz de Codex y Aegis sin agente Codex, comparar outputs esperados en memoria sin ejecutar el renderer en modo escritura y emitir respuesta humana o JSON conforme al contrato aprobado con códigos de salida distinguibles.
- [x] T004 [US1] Implementar `status` de sólo lectura en `olympus/cli.py` para exponer el contexto y metadatos de instalación ya disponibles, incluidos estados ausentes, inválidos o contradictorios; marcarlos como reportados/no verificados, sin afirmar ownership, integridad ni capacidad C. No ejecutar `VerifyOnly`, `doctor`, discovery, subprocesses ni reparación, no inferir estado instalado desde la fuente y representar como desconocida o bloqueada cualquier ubicación global que el contrato actual no permita resolver sin operación C.
- [x] T005 [US1] Añadir launchers pequeños y ligados al checkout en archivos **NUEVOS** `scripts/olympus_cli.py`, `scripts/olympus` y `scripts/olympus.cmd`; invocar Python >=3.11 con bytecode desactivado, anclar rutas al checkout del launcher, preservar quoting para espacios y Unicode y propagar el código de salida, sin editar PATH ni instaladores.
- [x] T006 [US1] Añadir casos seleccionables `slice_a` al archivo **NUEVO** `tests/harness-core/test_cli.py`, dentro del directorio de pruebas existente y reutilizando sus helpers: éxito, help/version, argumentos inválidos, comandos B/C desconocidos, TOML malformado, roster discordante, drift y ausencia de outputs generados, estado sin instalación y metadata inválida; comprobar JSON parseable con stdout limpio, envelope y datos equivalentes a la salida humana, y códigos conforme al contrato aprobado. Comparar inventario y hashes antes/después de consultas válidas e inválidas, incluidos fuentes, outputs, manifests, destinos examinados, `__pycache__` y caches. Preparar fixtures fuera de la ventana de snapshot; no instalar, modificar modelos ni llamar APIs.
- [x] T007 [US1] Ejecutar en Windows local, con intérprete real Python 3.11+, exactamente `python3.11 -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a`; añadir smoke de `python3.11 -B -m olympus` y del launcher Windows `.cmd` desde rutas con espacios y caracteres no ASCII. Registrar comando, intérprete, resultado y límites en la tabla de evidencia de [`specs/001-portable-olympus-cli/tasks.md`](tasks.md); los casos están en `tests/harness-core/test_cli.py`.
- [x] T008 [US1] Integrar en [`.github/workflows/fast.yml`](../../.github/workflows/fast.yml) un job Linux Python 3.11 con la selección `python -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a`, launcher POSIX directo, JSON y cero mutaciones; conservar el job Windows y las acciones fijadas, sin nuevas suites/jobs. Linux hosted pasó en PR #69 (run y límites registrados abajo). El workflow final elimina `chmod` y comprueba el modo Git 100755; esa versión aún requiere CI final.

### Cierre documental de Slice A

- [x] T009 Actualizar [README.md](../../README.md) y [`specs/001-portable-olympus-cli/quickstart.md`](quickstart.md) con prerrequisitos Python 3.11+, ejemplos copiables de help/version/list/status/check, contexto de origen, resultados esperados, comprobación de ausencia de escrituras y soporte comprobado Windows/Linux; indicar explícitamente que macOS no está verificado y no presentar edición o aplicación de B/C como capacidades disponibles.

## Dependencias y estrategia

Orden serial mínimo: `T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009`. T001/R49 conserva PASS y no se repitió. T002–T009 se completaron; el run hosted consumido cierra T008 PASS para la fuente que ejecutó. La actualización final que quita `chmod` necesita una ejecución CI posterior para comprobar el checkout con el modo real de Git. No hay dependencias de B/C ni agentes paralelos.

## Inventario de rutas y riesgos de la planificación

La tabla conserva las rutas previstas al generar tareas; T002–T009 están completadas según el estado y la evidencia que siguen.

| Tareas | Rutas previstas | Riesgo acotado |
|---|---|---|
| T001 | `specs/001-portable-olympus-cli/research.md` y `evidence/r49-20261014-c30a19d/` bajo la feature | R49 reconciliado; alcance Codex proyecto, sin afirmar runtime/agentes u otros scopes. |
| T002–T004 | `olympus/__init__.py`, `olympus/__main__.py`, `olympus/cli.py` (**NUEVOS**); lectura de `olympus/core/models.toml` y `scripts/render_harnesses.py` | Mantener la consulta sin imports/efectos laterales de B/C; no confundir fuente canónica con estado instalado ni convertir `check` en render. |
| T005 | `scripts/olympus_cli.py`, `scripts/olympus`, `scripts/olympus.cmd` (**NUEVOS**) | Quoting, resolución del checkout y propagación de salida deben ser equivalentes en Windows/Linux; launchers no instalan dependencias ni tocan PATH. |
| T006–T007 | `tests/harness-core/test_cli.py` (**NUEVO**) | Snapshots deben incluir caches y recursos consultados; preparar fixtures antes de capturar el estado para que el test mida sólo efectos de la CLI. |
| T008 | `.github/workflows/fast.yml` | Job Linux dirigido a A; el run consumido pasó. La revisión final exige CI con modo real de Git y sin `chmod`. |
| T009 | `README.md`, `specs/001-portable-olympus-cli/quickstart.md` | Evitar prometer soporte macOS o funcionalidad de slices posteriores. |

## Validation Evidence

La generación original no ejecutó operaciones. T001 instaló/verificó archivos en un destino aislado en una ejecución anterior. T002–T007 hicieron comprobaciones enfocadas de CLI; T008 cuenta con el run hosted PASS indicado abajo. El resultado se limita al contenido ejecutado y no prueba que el workflow posterior, ya sin `chmod`, detecte el bit 100755 del checkout.

| Check | Class | Result | Evidence / limitation |
|---|---|---|---|
| Identidad del tag publicado v0.4.9 | Deterministic | PASS (evidencia previa) | [`research.md`](research.md) registra el tag remoto resuelto a `c30a19dd410b1815f4591b204615cae0dd9e9a5f`; esto por sí solo no satisface R49. |
| Instalación del tag remoto en un Git desechable y VerifyOnly posterior | Real runtime | PASS | Una ejecución de cada operación de instalación de archivos, exit 0, scope project/harness codex; [reporte R49](evidence/r49-20261014-c30a19d/report.md). No es runtime de agentes. |
| Slice A: casos funcionales `slice_a`, errores, salida JSON y snapshot sin mutaciones | Deterministic | PASS (T006; Windows local) | 17 casos PASS y 1 POSIX SKIPPED; fallo inicial de formato de ayuda corregido y sólo ese caso repetido, PASS. Inventarios/hash/mtime sin diferencias en cada consulta. Comandos y límites abajo. |
| Slice A: CLI, JSON y ausencia de mutaciones en Windows | Real runtime (CLI) | PASS (T007) | Suite de 20 casos: 19 PASS, 1 POSIX SKIPPED, exit 0; incluye módulo desde cwd externo y launcher .cmd nativo, espacios/ñ, ambos formatos y exits 0/1/2/3. No es runtime OpenCode/Codex. |
| Slice A: sintaxis POSIX en Windows | Deterministic | PASS, límite de sintaxis | Git Bash --noprofile --norc -n scripts/olympus, exit 0; LF sin CR. No establece compatibilidad Linux. |
| Slice A: CLI, launcher, JSON y ausencia de mutaciones en Linux hosted | Real runtime | PASS (T008, PR #69) | [Run 38644271501, job 116127153113](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38644271501/job/116127153113), success `2026-10-14T21:58:31Z`; Ubuntu 24.04 / CPython 3.11.17; 20 casos, 19 PASS, 1 omitido por Windows, 5.129 s, exit 0. El run preparó el launcher con `chmod`; no valida que 100755 sobreviva al checkout sin preparación. |
| Checkout Git conserva el modo ejecutable en CI final | Static workflow review; hosted CI pendiente | PENDING final CI | El workflow actual quita `chmod`, exige `test -x` antes/después y usa `core.filemode=true` al comprobar cambios. |
| Documentación de capacidades disponibles | Deterministic | PASS (T009 actualizado) | README y quickstart describen A, los resultados Windows/Linux y límites: modo de checkout pendiente de CI final, macOS NOT VERIFIED; B condicionada y C fuera del alcance de A. |

Completar tareas no autoriza commits, push, PR, publicación ni cambios fuera del alcance indicado.

### Ejecución autorizada T002–T006 — 2026-10-14 (registro histórico)

- Archivos nuevos: `olympus/__init__.py`, `olympus/__main__.py`, `olympus/cli.py`, `scripts/olympus_cli.py`, `scripts/olympus`, `scripts/olympus.cmd`, `tests/harness-core/test_cli.py`. Único documento actualizado: este archivo. Sin dependencias nuevas, cambios de instaladores, Core, adaptadores, permisos, manifests ni outputs del repositorio.
- Contratos A implementados: ayuda/versión/origen explícito, `models list`, `config check` por harness y `status` de metadatos. JSON único con envelope versión 1 y datos comunes con presentación humana. Exit 0 para consulta/ausencia, 1 para configuración/drift/metadatos fallidos, 2 para argumentos/contexto inválidos y 3 para capacidad bloqueada. No se implementa una operación parcial que requiera exit 4.
- `status` no verifica ownership, integridad o asignaciones instaladas; los marca unverified/unknown. Global queda BLOCKED sin discovery; manifest legado se identifica, ambos manifests coexistentes se bloquean. Scratch existente se informa sin reparar. No subprocesses ni red en los comandos.
- Python observado: `C:/Users/BLAUTECH/.local/bin/python3.11.exe` (3.11.17). Ejecutado: `& 'C:/Users/BLAUTECH/.local/bin/python3.11.exe' -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a -v`. Resultado inicial: 18 casos, 16 PASS, 1 FAIL por ejemplo de ayuda partido entre líneas, 1 SKIPPED POSIX; exit 1, 67.429 s. Se corrigió únicamente el formato de ayuda para conservar ejemplos copiables.
- Repetición acotada: el mismo comando con `-k slice_a_help_version -v`: 1 caso PASS, exit 0, 2.170 s. No se repitieron los 16 casos que ya habían pasado. Resultado reconciliado T006: 17 PASS / 1 SKIPPED; no se afirma un nuevo run completo con exit 0.
- Cada consulta válida/inválida compara inventario de archivos/directorios y SHA-256/mtime mediante el helper existente `snapshot_outputs`. El sandbox incluye fuentes, todos los outputs, manifests de fixture, destino simulado, HOME/config/cache/temp y cualquier `__pycache__`. Preparación de fixtures fuera de la ventana de snapshot; cero diferencias observadas. Los manifests y la marca `.git` son fixtures, no instalación ni runtime real.
- Comprobación de alcance: 343 archivos preexistentes versionados/de la feature (excluido este documento de progreso) conservaron SHA-256; incluye spec/plan/research/contratos/constitución y evidencia R49. No aparecieron `.pyc` bajo `olympus`, `scripts` o `tests/harness-core`. No se accedió al entorno R49 retenido ni se intentó su cleanup.
- La entrada Python del launcher se probó desde cwd ajeno al checkout y rutas con espacios/ñ. El smoke nativo Windows `.cmd`, la ejecución/permiso ejecutable del launcher POSIX y Linux hosted quedan pendientes de T007/T008; no se declara macOS validado. Sin FAST/FULL/RUNTIME, APIs/modelos, instalación, commit, push o PR.

### Ejecución autorizada T007–T009 — 2026-10-14 (registro histórico del workflow previo)

- **T007 PASS**. Intérprete Python 3.11.17 acreditado: `C:/Users/BLAUTECH/.local/bin/python3.11.exe`. Ejecutado `& 'C:/Users/BLAUTECH/.local/bin/python3.11.exe' -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a -v`: 20 casos, 19 PASS, 1 SKIPPED POSIX, exit 0, 93.052 s. Sin fallos ni necesidad de repetir pruebas o corregir código de producto.
- Se ampliaron los tests existentes con smoke del módulo desde cwd externo (PYTHONPATH confiable explícito) y `.cmd` nativo mediante cmd.exe /d /s /c, deshabilitando AutoRun. Source/target y ruta del launcher contienen espacios y ñ. Ambos ejecutan help/version, list/check/status humanos y JSON, origen explícito/default anclado, scope project y propagación de exits 0/1/2/3. Snapshots de inventario/hash/mtime/modo sin diferencias, incluidos HOME/config/cache/temp aislados. Metadatos y marca .git son fixtures; no se instaló ni cargó ningún runtime de agentes.
- **T008 aún sin resultado hosted en ese momento**. El job Linux Ubuntu 24.04/Python 3.11 estaba agregado al workflow FAST existente; acciones reutilizadas con sus pins, job Windows y triggers intactos. No se creó workflow ni harness. El flujo de entonces preparaba `chmod +x scripts/olympus` antes de consultas; comprobaba permiso/sintaxis, ejecutaba suite slice_a con invocación POSIX directa y snapshot de modos, y verificaba checkout incluyendo ignorados/cachés. Git ignoraba el bit ejecutable preparado (`core.filemode=false`); la suite comparaba modos durante consultas y el job exigía launcher ejecutable antes/después.
- Comprobación local POSIX limitada: `C:/Program Files/Git/bin/bash.exe --noprofile --norc -n scripts/olympus`, exit 0; archivo LF, 0 bytes CR. Revisión estática del diff/YAML simple y `git diff --check` PASS, sin afirmar ejecución Actions ni parseo YAML por herramienta dedicada. En ese registro el Linux hosted estaba NOT RUN; el resultado posterior se consume en el cierre de integración siguiente. No se instaló WSL/Docker ni se simuló PASS Linux.
- **T009 PASS**. README agrega una sección breve de CLI desde checkout; quickstart describe exclusivamente capacidades A, selección de intérprete/origen, ejemplos humanos/JSON, códigos y límites de metadata. No presenta edición/aplicación como disponibles ni agrega UX de instalación sin clonar de #66.
- Archivos modificados: `tests/harness-core/test_cli.py`, `.github/workflows/fast.yml`, `README.md`, `specs/001-portable-olympus-cli/quickstart.md` y este `tasks.md`. Sin cambios a los launchers ni al código CLI; no hubo defectos de producto demostrados.
- Protección: 346 archivos preexistentes protegidos, incluidos Core/modelos/identidades/adaptadores/instaladores/manifests/outputs, código CLI/launchers, spec/plan/research/contratos/constitución y evidencia R49, conservan SHA-256. Entorno R49 no accedido. Sin llamadas a modelos, instalaciones, FAST/FULL/RUNTIME, commits, push, PR o release.

**Estado histórico al cerrar T009**: `WINDOWS_VALIDATED / PENDING_CI_VALIDATION`. La reconciliación actual de T008 se registra a continuación; B sigue condicionada y C BLOCKED.

### Cierre de integración Slice A — PR #69

- **T008 PASS** por el run Linux hosted [38644271501, job 116127153113](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38644271501/job/116127153113), success `2026-10-14T21:58:31Z`. PR #69 head `6e1076dd68427e3e2e1814f594adaa7fda3dbee4`; ejecutó el merge ref con prefijo `6704b1e` y base `1900da4` (el SHA completo del merge ref no se registró). Ubuntu 24.04, CPython 3.11.17, 20 tests: 19 PASS, 1 omitido por Windows, 5.129 s, exit 0.
- Ese run ejecutó la preparación `chmod +x` y no comprobó el modo original del checkout. Por eso acredita el resultado hosted de T008, pero no el requisito final de modo real de Git.
- El workflow actualizado elimina ese paso, conserva `test -x scripts/olympus` antes y después de la suite y usa `core.filemode=true` para detectar drift de contenido y permiso. **El CI final de esa revisión está pendiente.**
- **Estado actual de Slice A: READY_FOR_FINAL_CI.** macOS NOT VERIFIED; B CONDICIONADA; C fuera del alcance de A y BLOCKED para la experiencia completa. No se repitieron Windows ni R49.
- Auditoría documental de evidencia R49, referencias locales no publicadas, rutas personales y reducción mínima propuesta: [integration-review.md](integration-review.md). Los originales permanecen intactos.


---

### Reconciliación de mantenimiento T010–T012 (2026-10-14)

Este resultado supersede el bloqueo histórico anterior para el trabajo autorizado en esta sesión. Sólo se ejecutaron T010–T012; no se avanzó a otras tareas de Slice B.

- **T010: PASS.** Añadidos únicamente los helpers privados en `olympus/source_edit.py` y los casos `slice_b_lock` en `tests/harness-core/test_cli.py`. La adquisición de edición crea exclusivamente un archivo vacío; recovery sólo abre uno existente. Windows usa `msvcrt.locking` (`LK_NBLCK`, byte 0, longitud 1), Linux usa `fcntl.flock` (`LOCK_EX | LOCK_NB`). El descriptor es no heredable. Se valida archivo regular/vacío, ausencia de enlaces/reparse/hardlinks y concordancia `(st_dev, st_ino)` descriptor/path; no se elimina ni recrea automáticamente.
- **T011: PASS Windows local.** Fuente base `HEAD b7f8404061847a58d5e8122e4baa2fa643b69a46`; cambios locales sin commit. Intérprete real `Python 3.11.17` (`python3.11`). Comando exacto: `python3.11 -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_b_lock -v`; resultado final `Ran 10 tests ... OK (skipped=1)`, exit 0 (9 casos pasaron; un fixture se omitió). SHA-256 de `olympus/source_edit.py`: `08E66033AA27CFDFDBD72C6549EABBE582858E2834F2CCBAA47463A354434245`; `tests/harness-core/test_cli.py`: `6AB1BF93E0AC795EDF01A20DC7B7706D3EF3B8230EE3144077E8612C364EB61E`.
- Evidencia Windows: exclusión entre procesos para edit/edit, edit/recovery y recovery/recovery mediante helpers productivos y locking del kernel; recovery contendiente no crea/inspecciona su marcador mientras el dueño mantiene el lock; identidad y archivo vacío permanecen; liberación tras `finally` por excepción y terminación abrupta con `kill()` real. Las pruebas usan exclusivamente fixtures temporales con espacios/Unicode. La prueba de enlace simbólico se omitió porque Windows devolvió `WinError 1314` (privilegio requerido); rechazo de hardlink sí pasó. No se probó explícitamente un archivo reparse point en Windows.
- **T012: PENDING_CI.** Añadido un solo paso `Slice B lock (native Linux)` al job Linux existente en `.github/workflows/fast.yml`, después del paso A y antes del control de checkout; no se alteraron las acciones fijadas, el job Windows ni los controles A. SHA-256 del workflow: `14434858E0070768B0B0AD91C42C3580D27ACAB665C97CA22AAF492F84705772`. No existe resultado hosted consumido para este contenido porque conseguirlo requeriría publicar/cambiar el remoto, acciones no autorizadas. No se usó WSL/Docker ni CI distinto.
- `git diff --check`: exit 0. No hay `.olympus-cli-edit.lock` ni `.olympus-cli-edit/` en el checkout; las pruebas limpiaron sus fixtures. No se cambió código producto de Slice A ni se implementó T013–T021.

**G1: PENDING_CI (NOT PASS).** Windows está acreditado con la limitación de symlink indicada; Linux requiere CI hosted del contenido identificado. No se inicia T013–T021. Sin acceso a R49, FULL/RUNTIME, commit, push, PR o merge.
