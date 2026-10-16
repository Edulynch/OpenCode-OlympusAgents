# Implementation Plan: Portable Olympus CLI

**Branch**: `001-portable-olympus-cli` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)  
**Documentation Mode**: New  
**Baseline**: `master` con PR #69 integrada, `b7f8404061847a58d5e8122e4baa2fa643b69a46`. Historial: producto v0.4.9 `c30a19dd410b1815f4591b204615cae0dd9e9a5f`; documentación post-PR #68 `1900da45250ddec817a6141396e0ec1268b2dfca`.

**Input**: Especificación, issue #64 y constitución 1.0.0. La planificación inicial, T001/R49 y el cierre preintegración A son históricos. Esta actualización documental incorpora las tres decisiones B aprobadas por el usuario y ajusta FR-009/FR-012; no genera tareas ni implementación.

**Registro histórico de cierre A anterior a PR #69**: T002–T009 completadas y T008 PASS por el [run Linux hosted](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38644271501/job/116127153113). Ese run usó `chmod`; entonces quedaba CI final para comprobar el permiso Git sin preparación. Estado de entonces: A READY_FOR_FINAL_CI, B CONDICIONADA, C BLOCKED. Este registro no reabre A, hoy SHIPPED con PR #69; no se reacredita CI ni R49 en esta sesión. macOS NOT VERIFIED.

**Estado vigente**: A **SHIPPED**, B **READY_FOR_TASKS** contractual, C y feature completa **BLOCKED**. Los experimentos del gate no acreditan implementación del lock; la validación integrada Windows/Linux es un prerrequisito para habilitar escrituras B.

## Summary

**Feasibility gate global: BLOCKED para la experiencia completa.** La inspección read-only previa al diseño identifica una vía mínima para A/B y para diagnóstico/delegación Windows de C. La aplicación instalada personalizada de C no tiene actualmente un contrato soportado de procedencia/verificación/recuperación. No se confunde ese bloqueo con falta de portabilidad del renderer ni se exige instalar en Linux para aceptar A/B. Evidencia, alternativas y decisión: [research.md](research.md).

Propuesta: Python 3.11+, `argparse` y stdlib; importar y componer el renderer existente sin moverlo ni duplicarlo. `tomllib` conserva validación semántica; TOML Kit es la única dependencia de edición justificada por preservación de formato. Entrada inicial `python -B -m olympus`; acceso final mediante launchers pequeños desde el checkout confiable en PATH, sin distribución binaria ni nueva UX sin checkout. Fuentes siguen siendo únicas y explícitas. B usa staging y recuperación acotada a un batch de archivos propios; C no obtiene un escritor Python de instalaciones.

**Registro histórico de gates tras T001 (2026-10-14)**: Slice A quedó **READY_FOR_IMPLEMENTATION** respecto de sus gates técnicos; B **CONDICIONADA** a validación de edición/preservación/recuperación; C **BLOCKED**. El gate global de entrega completa sigue BLOCKED y no es una dependencia de A. En ese momento las tareas A ya estaban generadas, y la ejecución T001 sólo resolvió R49; la implementación y el cierre actuales se registran aparte.

R49, prerrequisito de #64, está **PASS**: instalación de archivos y VerifyOnly desde el instalador remoto v0.4.9 y su adquisición normal, commit exacto verificado, en un Git temporal aislado, scope project/harness codex. Exit 0 en ambas operaciones, 12/12 recursos coincidentes y huellas sin cambios personales/desarrollo. [Evidencia de T001](evidence/r49-20261014-c30a19d/report.md). Al reconciliar T001, A dejó de estar retenida por R49 y podía implementarse independientemente de B/C; esa frase describe el estado de entonces, no el estado actual. R49 no acredita runtime de agentes ni instalación OpenCode/global/Linux.

## Technical Context

**Affected language/platform**: Python >=3.11 para A/B; PowerShell 7 y motores Windows existentes para operaciones nativas de C. Windows local y Linux CI para A/B; macOS NOT VERIFIED.  
**Dependencies and integrations**: stdlib Python (`argparse`, `tomllib`, `pathlib`, `hashlib`, `json`, `os`, `tempfile`, `subprocess`, `importlib`); sólo B carga `msvcrt` en Windows o `fcntl` en Linux para exclusión. TOML Kit 0.13.3 es dependencia candidata exclusiva de edición/preview B, sin Poetry runtime. Recovery no exige el editor; A sigue stdlib y no importa módulos B.\
**Data and storage**: `models.toml` sigue único mapping; outputs existentes y único scratch/registro temporal B; `.olympus-cli-edit.lock` es control vacío estable que permanece tras cleanup. No se crean esos recursos en esta revisión; manifests instalados fuera de B.\
**Existing test and verification tools**: `tests/harness-core/qualify.py --safe-root-read-only`, `tests/codex/validate_profile.py --mode static`, fixtures dual-harness/global/installer-ux; `unittest` para casos nuevos dentro de harness-core. En la baseline de planificación `.github/workflows/fast.yml` sólo tenía el job Windows; el job Linux enfocado se integró después y se documenta en [tasks.md](tasks.md).
**Constraints and compatibility**: preservar doce roles y diferencias Codex/OpenCode; sin APIs, daemons, WSL ni nuevo framework. No modificar modelos/outputs durante planificación. Los cambios futuros en renderer/instaladores protegidos requieren el plano de mantenimiento soportado; este plan no levanta DENY.  
**Scale or performance targets**: doce roles y treinta outputs del renderer baseline. Sin objetivo temporal/benchmark inventado.

## Constitution Check

Revisada antes y después del diseño: no se propone excepción constitucional. El bloqueo es de contrato/capacidad, no una autorización para omitir controles.

| Principle or constraint | Plan alignment and evidence | Open limitation |
|---|---|---|
| I. Core canónico | Resolver `checked_sources`/`role_model`; usar identidades y renderer; ningún mapping nuevo | Catálogo remoto no acreditado por configuración |
| II. Autoridad runtime | CLI humana; sin invocar Aegis ni cambiar permisos; reconocer Kael raíz/Aegis GAP Codex | Implementación en recursos protegidos por plano de mantenimiento, no por este plan |
| III. Simplicidad/evidencia | CLI directa, renderer sin migración, una dependencia pequeña y launchers acotados | Registro de recuperación sólo por batch, sin servicio/engine genérico |
| IV. TFR | Matriz enfocada, suites existentes; todas las pruebas futuras NOT RUN | Native apply no probado; fixtures no lo reemplazan |
| V. Integridad | Drift/hash/ownership centralizados en motores; C personalizada bloqueada | Procedencia personalizada y recuperación instalada ausentes |
| VI. Separación | FR-009/FR-012 actualizados por decisión explícita; hechos, decisiones y pruebas futuras distinguidos | Al revisar el plan aún no había implementación ni tasks generadas; T002–T009 se completaron después, según [tasks.md](tasks.md) |
| VII. Alcance | A/B/C preservadas; #66/#67 excluidos; sin FAST/FULL/RUNTIME | Gate completo BLOCKED; no afirmar producto completo |

## Design

### Feasibility gate antes del diseño — registro histórico

Se leyeron spec/constitución, código del renderer, helpers/manifests/instaladores, suites y workflow; se consultó documentación primaria. Una investigación Veyra read-only del límite instalado fue recibida en estado terminal y reconciliada; no se ejecutaron scripts de producto. Sólo después se ejecutó `setup-plan.ps1 -Json` para copiar la plantilla activa.

| Área | Resultado | Evidencia / consecuencia |
|---|---|---|
| A: resolución/consulta portable | PASS de viabilidad estática; CLI validada en Windows y Linux hosted | T007 Windows PASS; T008 Linux hosted PASS con preparación histórica de permiso. CI final pendiente para validar checkout 100755 sin `chmod`. |
| B: edición y generación | CONDICIONADA | Candidate TOML y outputs en memoria propuestos; preservación y rollback aún no validados. Concurrencia no cooperante tiene límite explícito abajo |
| C: diagnóstico/routing Windows | PASS de reutilización estática, condicionado | `VerifyOnly`/uninstall existentes; offline/read-only exige fuente local y discovery seguro |
| C: aplicar personalización existente | BLOCKED | No contrato de origen personalizado ni recuperación; `-SourceRoot` sólo qualification; modelo fijo en bootstrap |
| Operaciones instaladoras Linux/macOS | BLOCKED / no cualificadas | Guards Windows en motores; no quitar guards ni portar instalador por esta feature |
| Gate R49 antes de código, común por secuenciación de #64 | PASS tras ejecución T001 | Instalador/archivo del tag remoto, identidad exacta, Codex proyecto aislado, install/VerifyOnly exit 0 y huellas idénticas; reporte enlazado |

La tabla anterior conserva el gate inicial, supersedido para B por las decisiones aprobadas y el gate experimental registrado en research.md. En ella, PASS de viabilidad significa que existe un diseño respaldado por inspección; no representa por sí solo un smoke o aceptación ejecutada. Los resultados de ejecución actuales se enlazan en [tasks.md](tasks.md).

### Gates independientes y dependencias reales

| Gate | Estado de planificación | Dependencias reales | Condición pendiente / efecto |
|---|---|---|---|
| Global, experiencia completa A+B+C | BLOCKED | A/B/C aceptadas y garantías completas de spec | No declara la experiencia completa; no propaga C como dependencia de A |
| A, consulta/CLI | SHIPPED | PR #69 integrada en master; Python >=3.11 stdlib y renderer | No cambiar comportamiento ni repetir su cualificación por esta actualización B; macOS NOT VERIFIED |
| B, escritura de fuentes | READY_FOR_TASKS contractual | A SHIPPED, editor exclusivo B, contrato de IDs y lock nativo estable | Implementación NOT RUN; completar pruebas enfocadas Windows/Linux antes de habilitar escrituras |
| C, operación instalada completa | BLOCKED | A/B, motor existente y contrato explícito de actualización personalizada | Demostrar procedencia, ownership, manifests/versiones/hash/verificador y recuperación segura; Linux nativo no cualificado |
| R49, comenzar implementación | PASS | Requisito expreso de #64 y proceso release existente | Evidencia directa en Git desechable scope project/harness codex, sin runtime/stub ni source override; no atribuir cualificación a otros scopes |

A no depende de TOML Kit, registro de recuperación, cambios en instaladores, schema de personalización, verificación instalada de C ni portabilidad de instaladores. `status` A lee contexto/metadata disponible sin ejecutar doctor/discovery; `config check` compara en memoria sin render de escritura. A no importa módulos B/C ni crea su scratch. El acceso final por launchers y setup se documenta, pero la entrada de desarrollo admitida en A no requiere distribuir el producto completo antes de planificarla.

La revisión inicial encontró publicación/notas/CI pero no el paso remoto requerido. Ese bloqueo quedó superado por la ejecución posterior autorizada de T001: identidad pública y 274 blobs del archive comparados con el commit, instalador tagged intacto, adquisición REMOTE_ARCHIVE en install y VerifyOnly, 12 recursos de Codex proyecto con versión v0.4.9, dos exits 0 y snapshots sin contaminación. No se usó FULL ni prompt a modelo, ni se exigió Linux installer. El manifest registra commit unknown por ausencia de .git en el archive: la identidad se acredita externamente, no se reescribe. Alcance completo de evidencia y límites: [reporte R49](evidence/r49-20261014-c30a19d/report.md).

### Arquitectura mínima

1. `olympus.__main__`/`olympus.cli`: parser, validación de contexto, presentación/JSON, dispatch directo a funciones. Sin contenedor de servicios, clases manager ni plugin framework.
2. `olympus.cli` carga **el único** `scripts/render_harnesses.py` desde el checkout seleccionado mediante `importlib.util`, con bytecode deshabilitado. Se requiere checkout confiable: no se descubre ni ejecuta código de proyectos destino.
3. Para listado/check, reutiliza `checked_sources`, `role_model` y `outputs_for`. Para candidatos, obtiene fuentes con `checked_sources`, copia únicamente el diccionario de modelos y compone `opencode_outputs`/`codex_outputs`/`capability_doc` existentes. No llama `run(..., 'render', ...)` para preview ni commit de B.
4. `olympus.model_edit`: reemplaza sólo escalares solicitados en documento TOML preservador, revalida con `tomllib`, comprueba equivalencia semántica del resto y preservación textual. Candidato y previews permanecen en memoria.
5. `olympus.source_edit`: batch pequeño de modelos + outputs efectivamente cambiados, staging/backup/hash/recovery. No escribe instalaciones ni importa las reglas de ownership del instalador.
6. `olympus.native_ops`: routing Windows y traducción de resultado de verificadores/entrypoints existentes mediante `subprocess` con argumentos separados, timeout y captura. Linux informa limitación; no hay segundo motor de instalación.

El origen default de launchers es el checkout al que pertenecen; `--source` permite otro checkout explícito confiable. Mutaciones exigen origen inequívoco; el destino no se infiere del directorio actual. Referencia de comando/JSON/exit: [contracts/cli.md](contracts/cli.md).

### Distribución elegida y experiencia final

- Inicial: `python -B -m olympus` desde checkout. `-B` y `PYTHONDONTWRITEBYTECODE=1` evitan caches de import en modos de sólo lectura y subprocesses.
- Final acotada: launchers `scripts/olympus` para Linux y `scripts/olympus.cmd` para Windows llaman `scripts/olympus_cli.py` con Python >=3.11 y `-B`, anclado al directorio del launcher y sin cambiar cwd. La persona usuaria añade ese directorio a PATH según la guía; no se modifica PATH automáticamente. Se verifica quoting y exit code en ambos OS. No se requiere asociación `.pyz` ni compiler.
- Python y TOML Kit se preparan una vez en entorno elegido; la ejecución de comandos no instala dependencias ni accede a red. El launcher permite seleccionar intérprete explícito al preparar el entorno; no contiene modelos/familias. Venv opcional, no obligatorio para A.
- Es una experiencia de comando instalado **ligada a checkout**, documentada como tal. Mover/borrar el checkout exige actualizar PATH y entorno; no se promete una distribución standalone ni el flujo sin checkout de #66.
- Wheel/`console_scripts` sigue siendo alternativa ligera futura si distribuir sin checkout se vuelve requisito propio: ahora añade backend/build/data placement sin resolver fuentes ni motores. `.pyz` tampoco resuelve edición de fuentes externas ni comandos Windows por sí sola. No agregar ambos canales.

### Edición TOML y validación

`tomllib` no escribe ni conserva trivia como modelo editable; no reconstruir TOML desde su dict. Evaluado stdlib-first: patch de líneas sirve al formato actual, pero necesita reconocer strings multilínea, escapes, keys dotted/quoted y comentarios para no confundir contenido ajeno. Un parser propio para cubrirlos cuesta más que una dependencia pequeña, y un regex amplio es inseguro. Elegir TOML Kit sólo para B y para sus previews; A sigue siendo stdlib. La dependencia ausente bloquea B antes de escribir, sin instalación automática.

TOML Kit 0.13.3 sigue siendo dependencia candidata exclusiva de edición/preview B; se importa sólo al despachar esas operaciones. Recovery usa backups y stdlib, sin exigir editor ni instalación de dependencias. Los experimentos PASS no eximen las pruebas de la implementación: cargar bytes UTF-8, mantener LF/CRLF, exigir round-trip sin cambio idéntico, editar únicamente valores existentes, reparsear con `tomllib` y comparar estructura salvo los paths autorizados. Usar fábrica de strings explícita para conservar comillas literales/multilínea cuando corresponda y comparar bytes con sólo los escalares autorizados enmascarados; verificar que trivia/elementos ajenos no cambian. Una forma no preservable se rechaza, no se normaliza. En outputs, comparar texto con el renderer y conservar convención de newline existente; sólo escribir los realmente afectados. Rechazar newline mixto ambiguo si impide mantener bytes ajenos.

Contrato local inicial B: familias/roles existentes; todos los IDs utilizados del candidato y los solicitados deben coincidir completamente con `[A-Za-z0-9][A-Za-z0-9._:/-]*`, sin trim ni normalización, antes de staging o cualquier escritura, incluida creación del lock. IDs existentes conformes se aceptan; los no conformes bloquean B sin repararlos ni cambiar A. No modificar el renderer ni afirmar disponibilidad/autenticación; este alfabeto no limita universalmente OpenCode/Codex. Esfuerzos seleccionables son los valores ya presentes en la fuente canónica cargada (`high`, `xhigh`, `max` en baseline), derivados cada vez, sin enum competidor. No anunciar todos los valores de un proveedor. Si un esfuerzo deja de figurar, no es seleccionable por esta versión; ampliar esa UX requiere evidencia/decisión de contrato, no inventar catálogo. No llamar `codex debug models` ni discovery de OpenCode en previews. Check de catálogo existente queda fuera del acceptance offline inicial.

### Consistencia y recuperación de B — decisiones aprobadas

B mantiene una función privada sobre `models.toml` y los outputs existentes que realmente cambian. No hay altas/bajas de outputs, paths arbitrarios, recursos instalados, callbacks, backends, API Transaction/Journal ni motor compartido con C. Máximo observado en baseline: 14 archivos para cambiar ambos IDs de sol; otros cambios usan el subconjunto que calcula el renderer.

El único scratch `.olympus-cli-edit/` guarda un registro PREPARED/COMMITTED y backups/staged del intento. El archivo estable `.olympus-cli-edit.lock`, junto al scratch en el origen canónico resuelto, es sólo infraestructura de exclusión; permanece después del cleanup, vacío, sin mapping ni historial. No forma parte del batch canónico ni se instala en destinos. Nunca se elimina, reemplaza, trunca o recrea como forma de liberar o renovar un lock. El protocolo detallado y la identidad están en [data-model.md](data-model.md).

1. Preflight read-only: validar argumentos/contexto, dependencia de edición, todos los IDs efectivos, fuentes/roster/drift, contención, archivos regulares sin enlaces/reparse/hardlinks y filesystem común. Scratch pendiente bloquea B antes de crear lock/staging, incluso si falta el archivo de lock; no recrearlo para desbloquear. Construir candidato/outputs completamente en memoria; conservar LF/CRLF por archivo y rechazar outputs con newline mixto no preservable. Preview no crea ni adquiere lock; edición idéntica sobre estado válido y sin scratch pendiente informa no_changes sin crear lock ni scratch.
2. Para cambio real, abrir el lock estable sin truncar, creándolo exclusivamente sólo si todavía no existe. Adquirir exclusión no bloqueante: Windows `msvcrt.locking` sobre byte 0, longitud 1 (incluso archivo vacío); Linux `fcntl.flock` exclusivo no bloqueante. Un dueño activo produce BLOCKED sin esperar, polling o inspección de su batch. Comprobar identidad del descriptor frente al path; mantenerlo abierto y bloqueado hasta finalizar commit/rollback/cleanup.
3. Bajo exclusión, revalidar snapshot/read-set completo y ausencia de scratch previo. Scratch pendiente bloquea una nueva edición aunque el lock esté libre: exige recovery explícito. Preparar backups y candidatos del conjunto fijo en el mismo filesystem, conservar modos y terminar staging antes de persistir PREPARED por staging + replace. Registrar identidad estable del lock y hashes old/new.
4. Antes del batch y de cada sustitución, comprobar identidades/modos y hashes: entradas fuera del write-set deben seguir en snapshot, el target a sustituir aún old y los ya sustituidos por el intento new. Sólo después usar `os.replace` por archivo. Los hashes detectan cambios observables; **no son compare-and-swap** ni excluyen la carrera con un escritor externo que ignora el lock.
5. Verificar bytes esperados, read-set y coherencia con el renderer antes de persistir COMMITTED. Mantener exclusión durante cleanup; retirar sólo recursos temporales propios, nunca el lock estable. Fallo atrapable mantiene exclusión e intenta rollback sólo tras validar ownership/hashes/backups; ningún resultado parcial se presenta como éxito. Si no puede reconciliarse, retener evidencia y reportar blocked/unconfirmed.
6. `config recover` abre el lock existente, sin crearlo ni reemplazarlo. Si falta o no puede acreditarse su identidad, BLOCKED sin examinar registro/backups/recursos del batch. Tras adquirir exclusión valida identidad/registro y clasifica todos los recursos; tercero hash, recurso ausente, backup inválido o read-set externo modificado bloquean antes de restaurar. Un lock libre, PID, timestamp o directorio no prueba éxito previo: el estado se determina sólo por registro y hashes validados.
7. PREPARED deja old y restaura new mediante una nueva copia staged del backup; nunca consume el respaldo original durante rollback. PREPARED all-new también revierte. COMMITTED sólo limpia tras validar estado new completo. Confirmar estado old coherente antes de cleanup del rollback y permitir repetir recovery interrumpido; sin reanudar la edición original ni retry automático. Scratch incompleto o evidencia insuficiente queda bloqueado, nunca se retira por antigüedad.

El escritor único es cooperante: commit y recovery Olympus comparten exclusión nativa. La liberación por terminación abrupta y la identidad/ubicación estable deben verificarse **en Windows y Linux antes de habilitar escrituras**. La primitiva Windows pasó un experimento previo; protocolo integrado y variante Linux siguen NOT RUN. Ningún PID/edad sustituye la adquisición del lock. La exclusión sobre el archivo de control no bloquea editores externos de modelos/outputs.

Limitaciones aprobadas de FR-012: sin protección absoluta contra procesos no cooperantes, vista atómica multiarquivo ni durabilidad absoluta ante pérdida de energía. No sobrescribir automáticamente modificaciones externas ni conflictos detectados. Si un tercero modifica un recurso después de la última comprobación, esa carrera queda fuera de garantía; no afirmar linearizabilidad universal. Mantener estado bloqueado o sin confirmar cuando no se pueda recuperar coherencia propia. Estas limitaciones sustituyen el bloqueo contractual anterior; los checks de implementación pendientes son gates previos a escrituras, no excepciones para omitirlos.

### Aplicación instalada: capacidad separada bloqueada

No implementar `config apply` usando `install.ps1 -SourceRoot` como contrato soportado. Tampoco Python debe abrir/agregar/modificar directamente `.opencode`, `.codex` o manifests del destino.

Hechos concretos: el motor consume outputs ya generados junto al script, valida hashes/ownership y preserva drift al rechazarlo. Sin embargo, registra versión/commit sin distinguir cambios locales, escribe antes de manifest sin recovery y bootstrap exige IDs fijos Sol/Luna para OpenCode. Linux tiene guards y rutas Windows; `all` global procesa dos harnesses independientemente.

La vía a investigar para desbloquear es **un delta pequeño en el mismo motor**: entrada explícita para aplicar configuración renderizada del checkout validado, procedencia personalizada verificable basada en digest de fuentes y release base, preflight completo antes de ambos harnesses, integración con verificador/uninstall y recuperación acotada a recursos propios. Los digests serían metadatos de procedencia, no otra copia de asignaciones. Debe conservar rechazo de drift, hashes, paths y scope. No decidir hoy campos definitivos ni parámetros sin esa prueba de compatibilidad; no modificar entrypoints de v0.4.9 para fingir un producto posterior.

C se conserva como tercera slice, con subcapacidad apply bloqueada, dentro de #64. No se crea otro issue ni se aprueba un split de release. El siguiente entregable para C sería evidencia de ese contrato y recuperación en motores existentes, antes de tareas de aplicación. Diagnóstico/install/uninstall Windows pueden planificarse como delegación; aplicación Linux se informa no soportada, sin reescritura PowerShell→Python.

### Slices y condiciones de avance

| Slice | Resultado verificable / reutilización | Archivos previstos | Dependencias | Riesgos / verificación enfocada | Bloqueo de avance |
|---|---|---|---|---|---|
| A — SHIPPED | Consulta entregada mediante PR #69 | Archivos A existentes, sin cambios ahora | Baseline master | Evidencia A histórica conservada | No reabrir ni cambiar A por B |
| B — READY_FOR_TASKS | Contratos de IDs, exclusión y recovery aprobados; renderer existente | `model_edit.py`, función privada de escritura/recovery y casos slice_b futuros | A SHIPPED y contratos actualizados | Validación enfocada integrada Windows/Linux previa a escrituras | Implementación NOT RUN; no habilitar B hasta reconciliar esos resultados |
| C — BLOCKED | Doctor/routing reutilizables; apply no habilitado | Native routing y suites existentes; delta motor sólo después de desbloqueo | A/B, procedencia, ownership/manifests/versiones/verificador y recuperación segura | Drift/parcial all/overrides; fixtures y smoke posterior | Contrato instalado y recuperación aún no demostrados; sin éxito completo |

## Project Structure

Inventario de rutas previsto durante la planificación. Los archivos de A asignados a T002–T009 ya fueron creados; B/C y otros elementos futuros siguen siendo propuestas, según el estado detallado en [tasks.md](tasks.md):

```text
olympus/core/models.toml                  fuente canónica; sin modificar ahora
olympus/core/identities.toml              reutilizada, sin cambios
olympus/harnesses/                        templates/capacidades existentes
scripts/render_harnesses.py               importado; sin copia ni migración
olympus/__init__.py                       NUEVO: paquete/entrada, sin mappings
olympus/__main__.py                       NUEVO: entrada módulo
olympus/cli.py                            NUEVO: parser, resolución, consultas/presentación
olympus/model_edit.py                     NUEVO: edición preservadora en memoria
olympus/source_edit.py                    NUEVO: batch/recovery sólo de fuente
.olympus-cli-edit.lock                    FUTURO: archivo estable de exclusión, nunca cleanup
.olympus-cli-edit/                        FUTURO: único scratch de operación y registro
olympus/native_ops.py                     NUEVO: delegación de motores, no writer instalado
scripts/olympus_cli.py                    NUEVO: entrada anclada al checkout
scripts/olympus                           NUEVO: launcher Linux
scripts/olympus.cmd                       NUEVO: launcher Windows
requirements-cli.txt                     NUEVO: una dependencia pequeña B, sin framework
tests/harness-core/test_cli.py            NUEVO: unittest dentro del área existente
.github/workflows/fast.yml                job Linux enfocado integrado en FAST; revisión final elimina chmod
tests/harness-core/qualify.py              baseline existente reutilizado en modo seguro
tests/codex/validate_profile.py            estático existente
tests/release/dual-harness-installer.ps1    reutilizar para C si se desbloquea
tests/global-installer/qualify.ps1         reutilizar para C si se desbloquea
tests/installer-ux/qualify.ps1              routing/uninstall existente
scripts/bootstrap.ps1                     posible delta C BLOQUEADO
scripts/global-install.ps1                posible delta C BLOQUEADO
scripts/project-uninstall.ps1             compatibilidad/verificación del eventual delta
install.ps1                              routing oficial; no convertir qualification en apply
README.md                                ejemplos/dependencias/soporte, futura actualización
```

**Structure decision**: Usar el árbol actual; no `src/`, nuevo harness, engine portable de instalación ni registro modelo alternativo. Los módulos separan cuatro responsabilidades concretas; si `native_ops` sólo tiene dos llamadas al empezar C, puede permanecer como funciones en `cli.py` hasta justificar extracción. No tocar outputs protegidos directamente.

### Supporting Design Artifacts

- [research.md](research.md): evidencia del gate y comparación de alternativas.
- [data-model.md](data-model.md): sólo batch temporal/estados, necesario para recuperación; no copia el schema Core.
- [contracts/cli.md](contracts/cli.md): contexto, salidas, exits y límites de comando; material para separar fuente/destino y bloqueo C.
- [quickstart.md](quickstart.md): guía futura ejecutable de validación enfocada; ninguna orden se ejecutó en esta planificación.

## Dependencies and Risks

- Release: R49 aceptado con evidencia directa limitada a instalación de archivos Codex proyecto. No sustituir esa evidencia por FAST histórico ni ampliar su alcance a OpenCode/global/runtime de agentes.
- Plataforma: A SHIPPED con PR #69; conservar evidencia preintegración Python/T008/mode en research.md sin convertir su pendiente histórico en gate actual. B requiere validación propia Windows/Linux; no instalar intérprete ni depender del alias Microsoft Store.
- TOML: conservar experimentos PASS del gate para 0.13.3; pruebas de integración/preservación del producto B NOT RUN antes de habilitar edición. No instalar dependencias ni repetir experimentos en esta revisión.
- Concurrencia: FR-012 ajustado por aprobación explícita; lock nativo cooperante estable y recovery bajo exclusión. Sin snapshot multiarquivo, protección absoluta contra terceros no cooperantes ni durabilidad absoluta ante pérdida eléctrica. Identidad y liberación Windows/Linux son gates de implementación.
- Instalada: ausencia de contrato C no se resuelve omitiendo checks/version ni rebautizando local como release. Bloqueo separado conserva alcance del issue.
- Nativo: doctor global OpenCode llama discovery existente fuera del proyecto; cualquier escritura observada impide aceptar modo read-only y debe declararse BLOCKED, no envolverse como PASS.
- Autoridad: modificar en el futuro fuentes/entrypoints Olympus protegidos requiere su plano de mantenimiento soportado. El plan no autoriza a Codex a escalar.

## Validation Strategy

Riesgo TFR: A LOW (lectura/contexto); B MEDIUM (fuente/derivados); C HIGH (ownership/destinos). A está SHIPPED en master con PR #69. Las observaciones de CI/permiso anteriores a esa integración se conservan como historia en research.md; no se reacreditan ni modifican flujos A aquí. T001 añadió instalación real de archivos y VerifyOnly remotos aislados, PASS para R49; no pruebas de agentes ni runtime de agentes.

| Behavior / boundary | Check and reason | Class | Expected outcome | Executed status and evidence |
|---|---|---|---|---|
| A consulta/CLI/JSON | Casos `slice_a` en `test_cli.py`, dentro de harness-core; listado, ayuda/versión, estado, check, contexto inválido y JSON legible equivalente | Deterministic | Mismos doce roles/asignaciones del Core; errores útiles; ninguna operación B/C | PASS histórico T006/T007 y T008; pendiente preintegración conservado en research.md. A SHIPPED, sin nuevo gate aquí |
| A ausencia de mutación | Snapshot inventario/contenido antes/después de consultas válidas/inválidas, incluido caches/scratch; reuse helpers de snapshot existentes | Deterministic | Cero creación, modificación o borrado; sin renderer write/doctor/discovery | PASS histórico Windows/Linux; A SHIPPED, sin nuevo gate aquí |
| B edición/preservación | Casos slice_b en mismo test: fullmatch IDs, round-trip, máscaras, fábrica string, LF/CRLF/newline mixto, no-op y dependencia ausente | Deterministic | Rechazo previo a cualquier escritura; bytes ajenos idénticos; no-op sin lock/scratch | Experimentos de gate PASS según research.md; implementación NOT RUN |
| B renderer/cambio real | Mismo `test_cli.py`, fixture origen; familia/rol, Kael/Aegis, hashes de no afectados y comparación con helpers renderer | Deterministic | Preview coincide con resultado; sólo campos autorizados | NOT RUN |
| B rollback/concurrencia | Fallo en sustitución N/interrupción, PREPARED old/mixed/new, COMMITTED cleanup parcial, terceros hashes/read-set y backups corruptos; recovery interrumpido/repetido | Simulated | Restauración propia validada o bloqueo sin overwrite; preservar respaldos y evitar éxito parcial | Experimentos acotados PASS; implementación NOT RUN |
| A compatibilidad Windows/Linux | Smoke entrada read-only/launcher, CLI/JSON y paths espacios/no ASCII; Windows Python real y un job Linux Python 3.11 | Real runtime | Misma consulta/config check y cero escrituras; sin preview de edición B ni instalador C | PASS histórico T007/T008; A SHIPPED tras PR #69, sin reacreditar CI |
| C controles de integración | Si se desbloquea: fixtures existentes dual-harness/global; UX si cambia routing; compatibility sólo si cambia wrapper | Simulated | Drift/ownership/version/override/`all` preservados y resultados reconciliados | NOT RUN / apply BLOCKED |
| C nativo Windows | Tras desbloqueo/autorización: destino aislado, actualización personalizada y VerifyOnly/uninstall por motor | Real runtime | Procedencia distinguible y estado verificado, sin tocar usuario/otro scope | NOT RUN / apply BLOCKED |

### Gate de implementación previo a habilitar escrituras B

Añadir casos slice_b al `tests/harness-core/test_cli.py` existente, reutilizando snapshots/helpers; sin otro harness ni nuevas pruebas A por hábito. Ejecutar serialmente en Windows local y Linux hosted:

- Exclusión nativa no bloqueante con archivo vacío: edit/edit, edit/recover y recover/recover; dueño activo bloquea al segundo antes de examinar el batch. Probar liberación tras excepción y terminación abrupta real del proceso en **ambas** plataformas; no sólo fixtures/PID.
- Identidad estable: resolver alias del origen, comparar descriptor/path/registro y rechazar enlaces/reparse/hardlinks o identidad no verificable; cleanup no elimina ni reemplaza el lock. Simular intento de unlink/recreate/path sustituido y comprobar detección observable y ausencia de recuperación sobre otra identidad. No prometer exclusión frente al actor externo no cooperante que elimina el archivo de control.
- Fallos antes de PREPARED y en cada límite del batch máximo; comprobar estados old/new, rollback exacto, backup inválido/registro incompleto, read-set cambiado, modo divergente y tercer hash. Antes del primer restore validar todo el conjunto y respaldos necesarios. Interrumpir recovery y repetirlo sin consumir backups; probar cleanup parcial PREPARED all-old/COMMITTED all-new y conservar el lock estable.
- Snapshots de contenido/inventario/modos/mtimes: previews y rechazos de entrada no crean lock/scratch/caches; no-op de edición tampoco. Tras operación aceptada, sólo varían targets efectivos y control B documentado. Instalaciones/manifests/sentinels ajenos permanecen idénticos. Slice A sigue stdlib y no importa B/editor; edición/preview sin TOML Kit bloquea antes de escritura, recovery no depende de ella.
- Reconstruir expected con el renderer único, verificar prompts/permisos/identidades/no afectados y representación Kael/Aegis. Probar IDs existentes conformes y rechazo de comillas, backslash, controles, saltos, espacios y otros caracteres, sin normalización ni APIs.

Todos estos checks integrados siguen **NOT RUN**. READY_FOR_TASKS no los convierte en PASS: deberán ejecutarse y reconciliarse antes de habilitar escrituras en cada plataforma soportada. Un fallo conserva ese gate bloqueado y se corrige/proporciona evidencia enfocada; no se amplía a FULL/RUNTIME por defecto. Los experimentos previos no se repiten sin cambio material del supuesto que acreditaron.

Matriz OS mínima: Windows local (A/B + routing nativo cuando corresponda), Linux hosted Python 3.11 (A/B). No matriz combinatoria por versiones, modelos, twelve roles × OS ni macOS aspiracional. El job Linux llama sólo pruebas enfocadas; no `scripts/qualify.ps1` ni perfiles FAST/FULL/RUNTIME nuevos. El requisito histórico del workflow A sobre modo 100755 se conserva; A está SHIPPED y esta revisión no altera su workflow ni requiere repetir su cualificación. Mantener intacto el gate Windows CI existente.

Para A seleccionar sólo `unittest discover -s tests/harness-core -p test_cli.py -k slice_a`. No ejecutar su cualificador completo ni el validador de perfiles Codex como acceptance de A: conservarlos como checks de integración posteriores cuando se altere su frontera o un gate existente lo exija. No nuevos requisitos de pruebas de modelos/preservación/recuperación/instalación para desbloquear A. El job Linux filtra slice_a; B se añade después bajo su gate.

`qualify.py` contiene expectativas fijas de Sol/Luna/esfuerzos en líneas 239–242: se usa en baseline, no como test de fixture personalizado. Los casos CLI deben parametrizar el candidato usando renderer existente, sin rebajar esas expectativas del producto baseline ni agregar una copia del cualificador.

## Complexity Tracking

| Addition | Concrete need | Simpler option considered and evidence |
|---|---|---|
| TOML Kit, una dependencia B | FR-011 exige trivia/formato; tomllib sólo parser | Regex/serializer desde dict no cumplen preservación general; no escribir parser propio |
| Registro/backups de un batch B | FR-012 y recuperación tras terminación | Snapshot RAM no cubre muerte del proceso; conservar backups durante rollback repetible |
| Lock estable + primitivas stdlib | Exclusión commit/recovery sin dos inodes cooperantes tras cleanup | Directorio/PID/edad no acreditan dueño terminal; sentinel vacío persistente sin nuevo registro |
| Dos launchers pequeños | Mismo comando con `-B`, quoting/exit sin compiler ni asociación | Entrada `-m` sola no UX final; wheel/zipapp ahora agregan distribución de datos/motores |

Sin servicio, clases de framework, engine nuevo ni matriz extensa. A SHIPPED permanece sin cambios; B READY_FOR_TASKS contractual conserva funciones privadas y requiere PASS integrado Windows/Linux antes de escrituras. C y entrega completa siguen BLOCKED. macOS NOT VERIFIED; no generar tasks.md ni implementar nada en esta actualización.
