# Tasks: CLI portátil Olympus — Slice A

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [contracts/cli.md](contracts/cli.md) y [quickstart.md](quickstart.md)  
**Documentation Mode**: New — tareas de implementación de la nueva feature  
**Baseline**: v0.4.9, tag remoto publicado resuelto a `c30a19dd410b1815f4591b204615cae0dd9e9a5f`

## Scope Rules

- Este archivo contiene trabajo de implementación **exclusivamente para Slice A / User Story 1**, más la reconciliación previa del gate R49 y documentación de uso de A. Conserva intactas las tres slices y la especificación.
- R49 se reconcilió previamente mediante la ejecución aislada documentada en [evidence/r49-20261014-c30a19d/report.md](evidence/r49-20261014-c30a19d/report.md); no se repitió. T002–T007 y T009 están completadas; T008 tiene integración local terminada y está `PENDING_CI_VALIDATION`. La generación original de tareas no ejecutó instalación.
- Slice B y Slice C no son dependencias de A y no generan tareas aquí. No incluir TOML Kit, edición de modelos, recuperación, aplicación instalada, instalación/desinstalación ni cambios a modelos, Core, adaptadores, permisos, manifests o archivos generados.
- Las rutas marcadas **NUEVO** son archivos propuestos por el plan dentro de directorios existentes; no se afirma que ya existan.
- T001 conserva su evidencia de R49. T002–T007 y T009 se marcan por implementación, pruebas y documentación registradas abajo; T008 permanece sin marcar hasta consumir el resultado Linux hosted. Este documento no confiere autoridad de publicación ni un gate de aprobación adicional.

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
- [ ] T008 [US1] Extender [`.github/workflows/fast.yml`](../../.github/workflows/fast.yml) con un único job Linux Python 3.11 que ejecute la misma selección mediante el intérprete configurado: `python -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a`; cubrir también la entrada, launcher `scripts/olympus`, JSON y cero mutaciones. Reutilizar acciones ya fijadas, conservar el job Windows actual y no añadir matrices, macOS, instaladores ni perfiles FAST/FULL/RUNTIME. Registrar el resultado del run Linux hospedado en la tabla de evidencia de [`specs/001-portable-olympus-cli/tasks.md`](tasks.md) cuando ocurra en el flujo CI autorizado.

### Cierre documental de Slice A

- [x] T009 Actualizar [README.md](../../README.md) y [`specs/001-portable-olympus-cli/quickstart.md`](quickstart.md) con prerrequisitos Python 3.11+, ejemplos copiables de help/version/list/status/check, contexto de origen, resultados esperados, comprobación de ausencia de escrituras y soporte comprobado Windows/Linux; indicar explícitamente que macOS no está verificado y no presentar edición o aplicación de B/C como capacidades disponibles.

## Dependencias y estrategia

Orden serial mínimo: `T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009`. T001/R49 conserva PASS y no se repitió. Tras T002–T006, se ejecutó T007, se integró el job T008 y se documentó el estado real en T009. T009 no requiere esperar una publicación no autorizada: informa Linux pendiente, sin declararlo aceptado. T008 sólo puede cerrarse después del resultado hosted de esta fuente. No hay dependencias de B/C ni agentes paralelos.

## Inventario de rutas y riesgos

| Tareas | Rutas previstas | Riesgo acotado |
|---|---|---|
| T001 | `specs/001-portable-olympus-cli/research.md` y `evidence/r49-20261014-c30a19d/` bajo la feature | R49 reconciliado; alcance Codex proyecto, sin afirmar runtime/agentes u otros scopes. |
| T002–T004 | `olympus/__init__.py`, `olympus/__main__.py`, `olympus/cli.py` (**NUEVOS**); lectura de `olympus/core/models.toml` y `scripts/render_harnesses.py` | Mantener la consulta sin imports/efectos laterales de B/C; no confundir fuente canónica con estado instalado ni convertir `check` en render. |
| T005 | `scripts/olympus_cli.py`, `scripts/olympus`, `scripts/olympus.cmd` (**NUEVOS**) | Quoting, resolución del checkout y propagación de salida deben ser equivalentes en Windows/Linux; launchers no instalan dependencias ni tocan PATH. |
| T006–T007 | `tests/harness-core/test_cli.py` (**NUEVO**) | Snapshots deben incluir caches y recursos consultados; preparar fixtures antes de capturar el estado para que el test mida sólo efectos de la CLI. |
| T008 | `.github/workflows/fast.yml` | Aislar job Linux dirigido a A y conservar el job Windows existente; un resultado aún no observado se queda `NOT RUN`. |
| T009 | `README.md`, `specs/001-portable-olympus-cli/quickstart.md` | Evitar prometer soporte macOS o funcionalidad de slices posteriores. |

## Validation Evidence

La generación original no ejecutó operaciones. T001 instaló/verificó archivos en un destino aislado en una ejecución anterior. T002–T006 y T007 sólo hicieron comprobaciones enfocadas de CLI en fixtures; no repitieron R49 ni tocaron su entorno retenido. T007 está PASS; el job Linux de T008 está integrado pero hosted sigue NOT RUN.

| Check | Class | Result | Evidence / limitation |
|---|---|---|---|
| Identidad del tag publicado v0.4.9 | Deterministic | PASS (evidencia previa) | [`research.md`](research.md) registra el tag remoto resuelto a `c30a19dd410b1815f4591b204615cae0dd9e9a5f`; esto por sí solo no satisface R49. |
| Instalación del tag remoto en un Git desechable y VerifyOnly posterior | Real runtime | PASS | Una ejecución de cada operación de instalación de archivos, exit 0, scope project/harness codex; [reporte R49](evidence/r49-20261014-c30a19d/report.md). No es runtime de agentes. |
| Slice A: casos funcionales `slice_a`, errores, salida JSON y snapshot sin mutaciones | Deterministic | PASS (T006; Windows local) | 17 casos PASS y 1 POSIX SKIPPED; fallo inicial de formato de ayuda corregido y sólo ese caso repetido, PASS. Inventarios/hash/mtime sin diferencias en cada consulta. Comandos y límites abajo. |
| Slice A: CLI, JSON y ausencia de mutaciones en Windows | Real runtime (CLI) | PASS (T007) | Suite de 20 casos: 19 PASS, 1 POSIX SKIPPED, exit 0; incluye módulo desde cwd externo y launcher .cmd nativo, espacios/ñ, ambos formatos y exits 0/1/2/3. No es runtime OpenCode/Codex. |
| Slice A: sintaxis POSIX en Windows | Deterministic | PASS, límite de sintaxis | Git Bash --noprofile --norc -n scripts/olympus, exit 0; LF sin CR. No establece compatibilidad Linux. |
| Slice A: CLI, launcher, JSON y ausencia de mutaciones en Linux hosted | Real runtime | PENDING_CI_VALIDATION / NOT RUN | Job slice-a-linux agregado a FAST; Python 3.11, permiso ejecutable previo, invocación directa en suite y checkout sin cambios. Fuente local sin publicar: no hay ejecución hosted de estos cambios. |
| Documentación de capacidades disponibles | Deterministic | PASS (T009) | README breve y quickstart actualizado: sólo A, metadata vs integridad, Windows comprobado/Linux pendiente/macOS no verificado. |

Completar tareas no autoriza commits, push, PR, publicación ni cambios fuera del alcance indicado.

### Ejecución autorizada T002–T006 — 2026-10-14

- Archivos nuevos: `olympus/__init__.py`, `olympus/__main__.py`, `olympus/cli.py`, `scripts/olympus_cli.py`, `scripts/olympus`, `scripts/olympus.cmd`, `tests/harness-core/test_cli.py`. Único documento actualizado: este archivo. Sin dependencias nuevas, cambios de instaladores, Core, adaptadores, permisos, manifests ni outputs del repositorio.
- Contratos A implementados: ayuda/versión/origen explícito, `models list`, `config check` por harness y `status` de metadatos. JSON único con envelope versión 1 y datos comunes con presentación humana. Exit 0 para consulta/ausencia, 1 para configuración/drift/metadatos fallidos, 2 para argumentos/contexto inválidos y 3 para capacidad bloqueada. No se implementa una operación parcial que requiera exit 4.
- `status` no verifica ownership, integridad o asignaciones instaladas; los marca unverified/unknown. Global queda BLOCKED sin discovery; manifest legado se identifica, ambos manifests coexistentes se bloquean. Scratch existente se informa sin reparar. No subprocesses ni red en los comandos.
- Python observado: `C:/Users/BLAUTECH/.local/bin/python3.11.exe` (3.11.17). Ejecutado: `& 'C:/Users/BLAUTECH/.local/bin/python3.11.exe' -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a -v`. Resultado inicial: 18 casos, 16 PASS, 1 FAIL por ejemplo de ayuda partido entre líneas, 1 SKIPPED POSIX; exit 1, 67.429 s. Se corrigió únicamente el formato de ayuda para conservar ejemplos copiables.
- Repetición acotada: el mismo comando con `-k slice_a_help_version -v`: 1 caso PASS, exit 0, 2.170 s. No se repitieron los 16 casos que ya habían pasado. Resultado reconciliado T006: 17 PASS / 1 SKIPPED; no se afirma un nuevo run completo con exit 0.
- Cada consulta válida/inválida compara inventario de archivos/directorios y SHA-256/mtime mediante el helper existente `snapshot_outputs`. El sandbox incluye fuentes, todos los outputs, manifests de fixture, destino simulado, HOME/config/cache/temp y cualquier `__pycache__`. Preparación de fixtures fuera de la ventana de snapshot; cero diferencias observadas. Los manifests y la marca `.git` son fixtures, no instalación ni runtime real.
- Comprobación de alcance: 343 archivos preexistentes versionados/de la feature (excluido este documento de progreso) conservaron SHA-256; incluye spec/plan/research/contratos/constitución y evidencia R49. No aparecieron `.pyc` bajo `olympus`, `scripts` o `tests/harness-core`. No se accedió al entorno R49 retenido ni se intentó su cleanup.
- La entrada Python del launcher se probó desde cwd ajeno al checkout y rutas con espacios/ñ. El smoke nativo Windows `.cmd`, la ejecución/permiso ejecutable del launcher POSIX y Linux hosted quedan pendientes de T007/T008; no se declara macOS validado. Sin FAST/FULL/RUNTIME, APIs/modelos, instalación, commit, push o PR.

### Ejecución autorizada T007–T009 — 2026-10-14

- **T007 PASS**. Intérprete Python 3.11.17 acreditado: `C:/Users/BLAUTECH/.local/bin/python3.11.exe`. Ejecutado `& 'C:/Users/BLAUTECH/.local/bin/python3.11.exe' -B -m unittest discover -s tests/harness-core -p test_cli.py -k slice_a -v`: 20 casos, 19 PASS, 1 SKIPPED POSIX, exit 0, 93.052 s. Sin fallos ni necesidad de repetir pruebas o corregir código de producto.
- Se ampliaron los tests existentes con smoke del módulo desde cwd externo (PYTHONPATH confiable explícito) y `.cmd` nativo mediante cmd.exe /d /s /c, deshabilitando AutoRun. Source/target y ruta del launcher contienen espacios y ñ. Ambos ejecutan help/version, list/check/status humanos y JSON, origen explícito/default anclado, scope project y propagación de exits 0/1/2/3. Snapshots de inventario/hash/mtime/modo sin diferencias, incluidos HOME/config/cache/temp aislados. Metadatos y marca .git son fixtures; no se instaló ni cargó ningún runtime de agentes.
- **T008 PENDING_CI_VALIDATION**. Un job Linux Ubuntu 24.04/Python 3.11 agregado al workflow FAST existente; acciones reutilizadas con sus pins, job Windows y triggers intactos. No se creó workflow ni harness. Preparación explícita `chmod +x scripts/olympus` antes de consultas; test de permiso/sintaxis, suite slice_a con invocación POSIX directa y snapshot de modos, verificación de checkout que incluye archivos ignorados/cachés. La comprobación Git descuenta sólo el bit ejecutable preparado; la suite compara modos durante consultas y el job exige launcher ejecutable antes/después.
- Comprobación local POSIX limitada: `C:/Program Files/Git/bin/bash.exe --noprofile --norc -n scripts/olympus`, exit 0; archivo LF, 0 bytes CR. Revisión estática del diff/YAML simple y `git diff --check` PASS, sin afirmar ejecución Actions ni parseo YAML por herramienta dedicada. Linux hosted permanece NOT RUN: publicar esta fuente/ejecutar el job exige operaciones Git excluidas de la autorización. No se instaló WSL/Docker ni se simuló PASS Linux.
- **T009 PASS**. README agrega una sección breve de CLI desde checkout; quickstart describe exclusivamente capacidades A, selección de intérprete/origen, ejemplos humanos/JSON, códigos y límites de metadata. No presenta edición/aplicación como disponibles ni agrega UX de instalación sin clonar de #66.
- Archivos modificados: `tests/harness-core/test_cli.py`, `.github/workflows/fast.yml`, `README.md`, `specs/001-portable-olympus-cli/quickstart.md` y este `tasks.md`. Sin cambios a los launchers ni al código CLI; no hubo defectos de producto demostrados.
- Protección: 346 archivos preexistentes protegidos, incluidos Core/modelos/identidades/adaptadores/instaladores/manifests/outputs, código CLI/launchers, spec/plan/research/contratos/constitución y evidencia R49, conservan SHA-256. Entorno R49 no accedido. Sin llamadas a modelos, instalaciones, FAST/FULL/RUNTIME, commits, push, PR o release.

**Estado documental de Slice A**: `WINDOWS_VALIDATED / PENDING_CI_VALIDATION`. T001–T007 y T009 completas; T008 pendiente exclusivamente de resultado hosted de los cambios. B condicionada y C BLOCKED. Spec y sus tres slices intactas; no se declara A aceptada en ambos sistemas ni la feature completa.
