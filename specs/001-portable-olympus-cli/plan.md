# Implementation Plan: Portable Olympus CLI

**Branch**: `001-portable-olympus-cli` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)  
**Documentation Mode**: New  
**Baseline**: producto v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`; documentación post-PR #68 en `1900da45250ddec817a6141396e0ec1268b2dfca`.

**Input**: Especificación `001-portable-olympus-cli`, issue #64, constitución 1.0.0. La planificación inicial y su actualización T001/R49 son registros históricos; el cierre actual de Slice A está al inicio y la ejecución detallada en [tasks.md](tasks.md). La especificación permanece intacta.

**Cierre actual de Slice A**: T002–T009 completadas y T008 PASS por el [run Linux hosted de PR #69](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38644271501/job/116127153113). Ese run usó `chmod`; el workflow actualizado elimina la preparación y comprueba el permiso 100755 de Git, pendiente de CI final. A está **READY_FOR_FINAL_CI**, macOS **NOT VERIFIED**, B **CONDICIONADA**, C **BLOCKED** y fuera del alcance de A. R49 conserva PASS y no se repitió.

## Summary

**Feasibility gate global: BLOCKED para la experiencia completa.** La inspección read-only previa al diseño identifica una vía mínima para A/B y para diagnóstico/delegación Windows de C. La aplicación instalada personalizada de C no tiene actualmente un contrato soportado de procedencia/verificación/recuperación. No se confunde ese bloqueo con falta de portabilidad del renderer ni se exige instalar en Linux para aceptar A/B. Evidencia, alternativas y decisión: [research.md](research.md).

Propuesta: Python 3.11+, `argparse` y stdlib; importar y componer el renderer existente sin moverlo ni duplicarlo. `tomllib` conserva validación semántica; TOML Kit es la única dependencia de edición justificada por preservación de formato. Entrada inicial `python -B -m olympus`; acceso final mediante launchers pequeños desde el checkout confiable en PATH, sin distribución binaria ni nueva UX sin checkout. Fuentes siguen siendo únicas y explícitas. B usa staging y recuperación acotada a un batch de archivos propios; C no obtiene un escritor Python de instalaciones.

**Registro histórico de gates tras T001 (2026-10-14)**: Slice A quedó **READY_FOR_IMPLEMENTATION** respecto de sus gates técnicos; B **CONDICIONADA** a validación de edición/preservación/recuperación; C **BLOCKED**. El gate global de entrega completa sigue BLOCKED y no es una dependencia de A. En ese momento las tareas A ya estaban generadas, y la ejecución T001 sólo resolvió R49; la implementación y el cierre actuales se registran aparte.

R49, prerrequisito de #64, está **PASS**: instalación de archivos y VerifyOnly desde el instalador remoto v0.4.9 y su adquisición normal, commit exacto verificado, en un Git temporal aislado, scope project/harness codex. Exit 0 en ambas operaciones, 12/12 recursos coincidentes y huellas sin cambios personales/desarrollo. [Evidencia de T001](evidence/r49-20261014-c30a19d/report.md). Al reconciliar T001, A dejó de estar retenida por R49 y podía implementarse independientemente de B/C; esa frase describe el estado de entonces, no el estado actual. R49 no acredita runtime de agentes ni instalación OpenCode/global/Linux.

## Technical Context

**Affected language/platform**: Python >=3.11 para A/B; PowerShell 7 y motores Windows existentes para operaciones nativas de C. Windows local y Linux CI para A/B; macOS NOT VERIFIED.  
**Dependencies and integrations**: `argparse`, `tomllib`, `pathlib`, `hashlib`, `json`, `os`, `tempfile`, `subprocess`, `importlib`; TOML Kit 0.13.3 como versión inicial explícitamente investigada, a cualificar antes de adoptar. No Poetry requerido en runtime.  
**Data and storage**: `olympus/core/models.toml` único mapping; outputs derivados existentes; metadatos temporales de recuperación de B, eliminables tras resultado reconciliado. Manifests instalados existentes no se modifican en A/B.  
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
| VI. Separación | Spec intacta; hechos, propuestas y pruebas futuras distinguidos | Al revisar el plan aún no había implementación ni tasks generadas; T002–T009 se completaron después, según [tasks.md](tasks.md) |
| VII. Alcance | A/B/C preservadas; #66/#67 excluidos; sin FAST/FULL/RUNTIME | Gate completo BLOCKED; no afirmar producto completo |

## Design

### Feasibility gate antes del diseño

Se leyeron spec/constitución, código del renderer, helpers/manifests/instaladores, suites y workflow; se consultó documentación primaria. Una investigación Veyra read-only del límite instalado fue recibida en estado terminal y reconciliada; no se ejecutaron scripts de producto. Sólo después se ejecutó `setup-plan.ps1 -Json` para copiar la plantilla activa.

| Área | Resultado | Evidencia / consecuencia |
|---|---|---|
| A: resolución/consulta portable | PASS de viabilidad estática; CLI validada en Windows y Linux hosted | T007 Windows PASS; T008 Linux hosted PASS con preparación histórica de permiso. CI final pendiente para validar checkout 100755 sin `chmod`. |
| B: edición y generación | CONDICIONADA | Candidate TOML y outputs en memoria propuestos; preservación y rollback aún no validados. Concurrencia no cooperante tiene límite explícito abajo |
| C: diagnóstico/routing Windows | PASS de reutilización estática, condicionado | `VerifyOnly`/uninstall existentes; offline/read-only exige fuente local y discovery seguro |
| C: aplicar personalización existente | BLOCKED | No contrato de origen personalizado ni recuperación; `-SourceRoot` sólo qualification; modelo fijo en bootstrap |
| Operaciones instaladoras Linux/macOS | BLOCKED / no cualificadas | Guards Windows en motores; no quitar guards ni portar instalador por esta feature |
| Gate R49 antes de código, común por secuenciación de #64 | PASS tras ejecución T001 | Instalador/archivo del tag remoto, identidad exacta, Codex proyecto aislado, install/VerifyOnly exit 0 y huellas idénticas; reporte enlazado |

En la tabla de factibilidad, PASS de viabilidad significa que existe un diseño respaldado por inspección; no representa por sí solo un smoke o aceptación ejecutada. Los resultados de ejecución actuales se enlazan en [tasks.md](tasks.md).

### Gates independientes y dependencias reales

| Gate | Estado de planificación | Dependencias reales | Condición pendiente / efecto |
|---|---|---|---|
| Global, experiencia completa A+B+C | BLOCKED | A/B/C aceptadas y garantías completas de spec | No declara la experiencia completa; no propaga C como dependencia de A |
| A, consulta/CLI | READY_FOR_FINAL_CI | Python >=3.11 stdlib, fuente/renderer, contexto read-only, Windows PASS, Linux hosted PASS (T008), R49 PASS | T002–T009 completadas; CI final pendiente para validar el modo 100755 de checkout sin `chmod`; macOS NOT VERIFIED |
| B, escritura de fuentes | CONDICIONADA | A y editor preservador cualificado; conjunto fijo fuente/outputs y recuperación | No habilitar escrituras hasta validar TOML/comments/newline, contenido ajeno, fallos y conflictos; contrato de concurrencia por resolver para esta garantía |
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

TOML Kit no exime pruebas de preservación: cargar bytes UTF-8, mantener LF/CRLF, exigir round-trip sin cambio idéntico, editar únicamente valores existentes, reparsear con `tomllib` y comparar estructura salvo los paths autorizados. Verificar que trivia/elementos ajenos no cambian; una forma no preservable se rechaza, no se normaliza. En outputs, comparar texto con el renderer y conservar convención de newline existente; sólo escribir los realmente afectados. Rechazar newline mixto ambiguo si impide mantener bytes ajenos.

Contrato local inicial: familias/roles existentes; IDs string no vacíos y sin controles/saltos, sin probar autenticación. Esfuerzos seleccionables son los valores ya presentes en la fuente canónica cargada (`high`, `xhigh`, `max` en baseline), derivados cada vez, sin enum competidor. No anunciar todos los valores de un proveedor. Si un esfuerzo deja de figurar, no es seleccionable por esta versión; ampliar esa UX requiere evidencia/decisión de contrato, no inventar catálogo. No llamar `codex debug models` ni discovery de OpenCode en previews. Check de catálogo existente queda fuera del acceptance offline inicial.

### Consistencia y recuperación de B

Una edición es un batch acotado y **no** una transacción atómica multiarquivo visible para cualquier lector.

Esta responsabilidad empieza sólo en B y permanece condicionada a sus pruebas. Implementarla como una función privada de edición de modelos con un conjunto fijo: `models.toml` más outputs cambiados que devuelve el renderer. Todos deben existir y estar coherentes antes de escribir; no admitir altas/bajas, paths arbitrarios, recursos instalados, callbacks o backends. No crear una API genérica `Transaction`/`Journal`, un motor compartido con C, eventos de reanudación o historial. Usar un único scratch, backups de archivos cambiados y hashes old/new: la información mínima persistida para una terminación abrupta. Recovery sólo revierte ese intento o limpia un intento ya confirmado; no puede continuar una edición ni orquestar operaciones instaladas.

1. Preflight read-only: fuentes/roster/output actual coherentes, paths regulares contenidos en origen, hashes de entradas renderer y recursos actuales; construir candidato/outputs completamente en memoria. Rechazar drift, missing outputs o cambios fuera de intención.
2. Al aceptar la orden real, crear exclusivamente el directorio `.olympus-cli-edit/` en origen como lock de operación; previews nunca lo crean. Un lock/registro previo bloquea nuevas escrituras; no se mata un PID ni se quita lock por edad.
3. Preparar backups originales y archivos nuevos del conjunto fijo existente, en el mismo filesystem. Registrar paths relativos acotados y hashes antes/después. Terminar staging y persistir registro antes de la primera sustitución; sin copias completas del árbol ni historial ilimitado.
4. Revalidar hashes de fuentes/outputs inmediatamente antes del batch y de cada reemplazo. Usar `os.replace` por archivo, conservar modo y newline. Hashes no iguales al snapshot bloquean; no elegir contenido de otras rutas ni hacer stash/reset/clean.
5. Confirmar que fuentes/outputs resultantes corresponden al candidato renderer. Sólo entonces marcar batch confirmado y retirar scratch; no tocar archivos iguales. Cualquier excepción atrapable intenta restaurar sólo archivos cuyo hash aún sea el escrito por este batch.
6. Si muere el proceso, las lecturas informan operación pendiente sin reparar. `config recover` es una orden humana explícita de rollback, no un scheduler: compara cada archivo con hash old/new; deja old, restaura new desde backup, bloquea cualquier tercer estado. Registro preparado sin escrituras se puede limpiar tras validar; registro confirmado sólo se limpia después de verificar estado new completo. No reanuda mutaciones ni fuerza archivos externos.

Los hashes y exclusión detectan conflictos cooperantes y cambios observables; **no garantizan** ausencia de carrera con un editor externo que ignora el lock entre última lectura y rename. Requisito operativo: un único escritor sobre recursos afectados durante commit/recovery, consistente con sesión única de #64. Si se exige garantía frente a escritores no cooperantes, B queda bloqueada para esa garantía: stdlib/locks advisory Linux no la satisfacen; no añadir locks nativos complejos silenciosamente ni modificar FR-012 sin decisión explícita. Dejar esa limitación visible y comprobar conflictos inyectados; no afirmar linearizabilidad universal o durabilidad frente a toda pérdida eléctrica.

Registro/estados: [data-model.md](data-model.md). Este mínimo existe por FR-012; backups en memoria solamente no cubren terminación abrupta. Si no se demuestra preservación/rollback con ese alcance fijo, mantener B condicionada; no añadir capas para poder declarar PASS. No presentar una condición de escritor único como prueba de que FR-012 excluye automáticamente terceros.

### Aplicación instalada: capacidad separada bloqueada

No implementar `config apply` usando `install.ps1 -SourceRoot` como contrato soportado. Tampoco Python debe abrir/agregar/modificar directamente `.opencode`, `.codex` o manifests del destino.

Hechos concretos: el motor consume outputs ya generados junto al script, valida hashes/ownership y preserva drift al rechazarlo. Sin embargo, registra versión/commit sin distinguir cambios locales, escribe antes de manifest sin recovery y bootstrap exige IDs fijos Sol/Luna para OpenCode. Linux tiene guards y rutas Windows; `all` global procesa dos harnesses independientemente.

La vía a investigar para desbloquear es **un delta pequeño en el mismo motor**: entrada explícita para aplicar configuración renderizada del checkout validado, procedencia personalizada verificable basada en digest de fuentes y release base, preflight completo antes de ambos harnesses, integración con verificador/uninstall y recuperación acotada a recursos propios. Los digests serían metadatos de procedencia, no otra copia de asignaciones. Debe conservar rechazo de drift, hashes, paths y scope. No decidir hoy campos definitivos ni parámetros sin esa prueba de compatibilidad; no modificar entrypoints de v0.4.9 para fingir un producto posterior.

C se conserva como tercera slice, con subcapacidad apply bloqueada, dentro de #64. No se crea otro issue ni se aprueba un split de release. El siguiente entregable para C sería evidencia de ese contrato y recuperación en motores existentes, antes de tareas de aplicación. Diagnóstico/install/uninstall Windows pueden planificarse como delegación; aplicación Linux se informa no soportada, sin reescritura PowerShell→Python.

### Slices y condiciones de avance

| Slice | Resultado verificable / reutilización | Archivos previstos | Dependencias | Riesgos / verificación enfocada | Bloqueo de avance |
|---|---|---|---|---|---|
| A — READY_FOR_FINAL_CI | Listado/JSON exacto, help/version/status/check sin escrituras; helpers renderer existentes | Entrada/cli.py, casos slice_a, job Linux y launchers | Python >=3.11, checkout confiable, renderer, R49 PASS; sin B/C | Consulta/JSON/cero mutación; Windows y Linux hosted pasaron en la evidencia registrada | T002–T009 completadas; CI final debe comprobar el permiso Git 100755 sin `chmod`; macOS NOT VERIFIED |
| B — CONDICIONADA | Edición familia/rol preservadora y generación coherente | `model_edit.py`, función privada de escritura/recovery, casos slice_b en mismo test | A y validación de TOML Kit/preservación/recuperación | TOML/comments/newline, fallo N y conflicto; ajenos idénticos | Validaciones no ejecutadas; contrato de concurrencia no resuelto para garantías más fuertes |
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
- Plataforma (registro histórico): el alias Microsoft Store no era el intérprete real; Python 3.11.17 devolvió exit 0. Usar un intérprete explícito y no instalarlo automáticamente. El run Linux hosted posterior pasó T008; la validación final del modo 100755 de checkout sigue pendiente.
- TOML: la elección de TOML Kit se basa en documentación/metadata; sus garantías de bytes deben verificarse sobre fixtures antes de habilitar edición. No instalar nada en esta sesión.
- Concurrencia: batch recuperable no ofrece snapshot multiarquivo a lectores externos ni exclusión de editores no cooperantes; requisito operativo y gate explícitos.
- Instalada: ausencia de contrato C no se resuelve omitiendo checks/version ni rebautizando local como release. Bloqueo separado conserva alcance del issue.
- Nativo: doctor global OpenCode llama discovery existente fuera del proyecto; cualquier escritura observada impide aceptar modo read-only y debe declararse BLOCKED, no envolverse como PASS.
- Autoridad: modificar en el futuro fuentes/entrypoints Olympus protegidos requiere su plano de mantenimiento soportado. El plan no autoriza a Codex a escalar.

## Validation Strategy

Riesgo TFR: A LOW (lectura/contexto); B MEDIUM (fuente/derivados); C HIGH (ownership/destinos). La CLI A tiene PASS Windows y PASS Linux hosted según [tasks.md](tasks.md); el modo real 100755 sin preparación requiere CI final. T001 añadió instalación real de archivos y VerifyOnly remotos aislados, PASS para R49; no pruebas de agentes ni runtime de agentes.

| Behavior / boundary | Check and reason | Class | Expected outcome | Executed status and evidence |
|---|---|---|---|---|
| A consulta/CLI/JSON | Casos `slice_a` en `test_cli.py`, dentro de harness-core; listado, ayuda/versión, estado, check, contexto inválido y JSON legible equivalente | Deterministic | Mismos doce roles/asignaciones del Core; errores útiles; ninguna operación B/C | PASS en T006/T007 y Linux hosted T008; CI final del modo checkout pendiente |
| A ausencia de mutación | Snapshot inventario/contenido antes/después de consultas válidas/inválidas, incluido caches/scratch; reuse helpers de snapshot existentes | Deterministic | Cero creación, modificación o borrado; sin renderer write/doctor/discovery | PASS en Windows y Linux hosted; CI final del modo checkout pendiente |
| B edición/preservación | Casos slice_b en mismo test, sin hacerlos prerrequisito A | Deterministic | Round-trip/comments/newlines, no-op y valores inválidos; ajenos idénticos | NOT RUN / CONDICIONADA |
| B renderer/cambio real | Mismo `test_cli.py`, fixture origen; familia/rol, Kael/Aegis, hashes de no afectados y comparación con helpers renderer | Deterministic | Preview coincide con resultado; sólo campos autorizados | NOT RUN |
| B rollback/concurrencia | Mismo test, fallo en sustitución N y proceso interrumpido; tercero hash distinto y lock activo | Simulated | Restauración propia o bloqueo sin overwrite; lectura sin reparación | NOT RUN |
| A compatibilidad Windows/Linux | Smoke entrada read-only/launcher, CLI/JSON y paths espacios/no ASCII; Windows Python real y un job Linux Python 3.11 | Real runtime | Misma consulta/config check y cero escrituras; sin preview de edición B ni instalador C | PASS T007 Windows y T008 Linux hosted; final CI de modo 100755 pendiente |
| C controles de integración | Si se desbloquea: fixtures existentes dual-harness/global; UX si cambia routing; compatibility sólo si cambia wrapper | Simulated | Drift/ownership/version/override/`all` preservados y resultados reconciliados | NOT RUN / apply BLOCKED |
| C nativo Windows | Tras desbloqueo/autorización: destino aislado, actualización personalizada y VerifyOnly/uninstall por motor | Real runtime | Procedencia distinguible y estado verificado, sin tocar usuario/otro scope | NOT RUN / apply BLOCKED |

Matriz OS mínima: Windows local (A/B + routing nativo cuando corresponda), Linux hosted Python 3.11 (A/B). No matriz combinatoria por versiones, modelos, twelve roles × OS ni macOS aspiracional. El job Linux llama sólo pruebas enfocadas; no `scripts/qualify.ps1` ni perfiles FAST/FULL/RUNTIME nuevos. El workflow actual valida el modo 100755 del checkout sin `chmod`; ese cambio requiere CI final. Mantener intacto el gate Windows CI existente.

Para A seleccionar sólo `unittest discover -s tests/harness-core -p test_cli.py -k slice_a`. No ejecutar su cualificador completo ni el validador de perfiles Codex como acceptance de A: conservarlos como checks de integración posteriores cuando se altere su frontera o un gate existente lo exija. No nuevos requisitos de pruebas de modelos/preservación/recuperación/instalación para desbloquear A. El job Linux filtra slice_a; B se añade después bajo su gate.

`qualify.py` contiene expectativas fijas de Sol/Luna/esfuerzos en líneas 239–242: se usa en baseline, no como test de fixture personalizado. Los casos CLI deben parametrizar el candidato usando renderer existente, sin rebajar esas expectativas del producto baseline ni agregar una copia del cualificador.

## Complexity Tracking

| Addition | Concrete need | Simpler option considered and evidence |
|---|---|---|
| TOML Kit, una dependencia B | FR-011 exige trivia/formato; tomllib sólo parser | Regex/serializer desde dict no cumplen preservación general; no escribir parser propio |
| Registro/backups de un batch B | FR-012 y recuperación tras terminación | Snapshot sólo en RAM pierde recovery; atomic rename aislado no cubre fuente + outputs |
| Dos launchers pequeños | Mismo comando con `-B`, quoting/exit sin compiler ni asociación | Entrada `-m` sola no UX final; wheel/zipapp ahora agregan distribución de datos/motores |

Sin servicio, clases de framework, engine nuevo ni matriz extensa. A sólo necesita entrada/parser/consultas, sin B/C ni placeholders. B conserva funciones privadas de edición/rollback; no generalizar. Recuperación instalada queda en C. Entrega completa sigue bloqueada; T002–T009 están completadas y A está READY_FOR_FINAL_CI con R49 PASS. La aceptación del permiso 100755 del checkout debe confirmarse en el próximo Linux CI; macOS NOT VERIFIED.
