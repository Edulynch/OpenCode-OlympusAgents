# Feature Specification: CLI portátil Olympus y configuración de modelos/agentes

**Feature Branch**: `001-portable-olympus-cli` (rama preexistente; esta sesión no crea ni cambia ramas)  
**Created**: 2026-10-14  
**Status**: Slice A SHIPPED; Slice B **ACEPTADA** (T019 Windows, T020 Linux, G2 PASS); Slice C y feature completa **BLOCKED**; macOS **NOT VERIFIED**.
**Documentation Mode**: New  
**Baseline**: `master` con Slice A integrada por PR [#69](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/69), commit `b7f8404061847a58d5e8122e4baa2fa643b69a46`. Baseline histórico: post-PR #68 `1900da45250ddec817a6141396e0ec1268b2dfca`; producto v0.4.9 `c30a19dd410b1815f4591b204615cae0dd9e9a5f`.\
**Restricciones de especificación inicial (históricas)**: Sólo especificación; sin implementación, planes, tareas, commits, push ni pruebas pesadas. Conservar fuentes, renderer, roles, diferencias de adaptadores y protecciones de instalación. Windows/Linux como objetivos; macOS sin cualificación acreditada. Excluir #66 y #67.\
**Evidence Reviewed**: Issue [#64](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/64) completo, incluidos aceptación y límites de ejecución; sin comentarios al consultar el 2026-10-14. Constitución [1.0.0](../../.specify/memory/constitution.md). Plantilla activa [spec-template](../../.specify/templates/overrides/spec-template.md), resuelta mediante el stack de Spec Kit. Fuentes y documentos del baseline: [models.toml](../../olympus/core/models.toml), [identities.toml](../../olympus/core/identities.toml), [capabilities.toml](../../olympus/harnesses/capabilities.toml), [renderer](../../scripts/render_harnesses.py), [bootstrap](../../scripts/bootstrap.ps1), [instalación global](../../scripts/global-install.ps1), [desinstalación de proyecto](../../scripts/project-uninstall.ps1), [entrypoint público](../../install.ps1), [desarrollo](../../docs/DEVELOPMENT.md), [release](../../docs/RELEASE-v0.4.9.md), [compatibilidad Codex](../../docs/CODEX-COMPATIBILITY.md) y retrospectivas [001](../retrospective/v0.4.9/001-core-and-adapters/spec.md), [006](../retrospective/v0.4.9/006-public-installation-ux/spec.md) y [007](../retrospective/v0.4.9/007-managed-installation/spec.md).

**Input**: Especificar `001-portable-olympus-cli`, primera nueva funcionalidad bajo Spec Kit, a partir del issue #64 y la constitución 1.0.0: consultar, configurar y aplicar asignaciones de modelos y agentes reutilizando la arquitectura existente.

## Reconciliación vigente de implementación — Slice B (2026-10-16)

T019 y T020 quedaron reconciliadas como PASS; G2 acredita la aceptación integrada de B en Windows y Linux. T019 Windows: 55 PASS, 0 FAIL, 0 ERROR, 3 SKIPPED por `WinError 1314` al crear fixtures symlink; los skips no cuentan como PASS Windows. T020 Linux hosted: 58 PASS, 0 FAIL, 0 SKIPPED, 37.350 s, exit 0, Ubuntu 24.04, CPython 3.11.17 y TOML Kit 0.13.3. Fuente exacta: commit `539976812d14289696dbd3824f1ae706ac2f1947`, PR Draft #70; run [38857503366](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366), job [116832156025](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366/job/116832156025). Los tres escenarios symlink omitidos en Windows pasaron en Linux. El run cubrió la selección integrada, incluyendo snapshots, independencia A, rollback/recovery, conflictos y 15 límites; confirmó checkout fuente sin cambios. FAST Windows y CodeQL también pasaron.

Esta aceptación documenta edición explícita de fuentes en B, no autorización permanente para escribir fuentes reales ni aplicación instalada. A permanece SHIPPED y sin cambios; `config apply`, Slice C y la feature completa siguen BLOCKED. Los límites cooperantes, atomicidad multiarquivo, durabilidad y macOS NOT VERIFIED permanecen vigentes. Los registros de diseño/planificación anteriores conservan su fecha y significado histórico; la reconciliación actual de tareas está en [tasks.md](tasks.md).

## Actualización contractual aprobada — Slice B (2026-10-14)

El usuario aprobó las tres decisiones posteriores al feasibility gate: alfabeto inicial de IDs, ajuste explícito de FR-012 a escritores cooperantes y exclusión nativa `msvcrt.locking`/`fcntl.flock`. En aquella revisión (2026-10-14), se actualizaron sólo estos cinco documentos, sin implementar, instalar dependencias ni generar tareas; entonces A estaba SHIPPED y C/global seguían BLOCKED. READY_FOR_TASKS habilitaba preparar tareas, no escrituras B hasta validar Windows/Linux. Ese estado contractual histórico quedó supersedido por la reconciliación de ejecución vigente al comienzo de este archivo.

El historial y los experimentos previos PASS se conservan en [research.md](research.md); no se repiten aquí. El protocolo y la identidad estable del lock se definen en [data-model.md](data-model.md). El renderer permanece sin modificaciones.

## Scope and Interpretation

La persona operadora necesita una única CLI ligera para conocer las asignaciones actuales, anticipar efectos, modificar la intención central y, mediante una operación distinta, actualizar un destino ya instalado. La configuración central ya existe; la funcionalidad agrega acceso y edición seguros.

### Baseline y delta autorizado

- `olympus/core/models.toml` contiene familias `sol` y `luna`, identificadores por adaptador y familia/esfuerzo de los doce roles. Identidades y definiciones de rol siguen en sus fuentes canónicas.
- El renderer valida fuentes y deriva outputs OpenCode/Codex; su comprobación de drift es de sólo lectura. No demuestra disponibilidad remota de modelos ni equivalencia semántica completa de políticas/prompts.
- OpenCode tiene doce agentes. Codex tiene diez especialistas, Kael como thread raíz y ninguna instancia de Aegis. Un identificador Codex en una familia canónica no crea soporte Codex para Aegis.
- Los motores existentes administran proyecto/global, manifests, ownership, hashes, verificación y desinstalación. Su cualificación documentada es Windows. No se acredita aquí un instalador Linux/macOS ni una aplicación segura de asignaciones personalizadas a destinos existentes como capacidad entregada.
- El delta es una interfaz de operador que reutiliza fuentes, generación y controles, con consulta/configuración portable y actualización instalada explícita cuando se demuestre segura para la plataforma y operación seleccionadas.

### Tres vertical slices del issue

| Slice | Resultado funcional | Límite de aceptación |
|---|---|---|
| A — Portable read-only CLI | Entrada, ayuda, versión, listado, resolución por modelo, estado y comprobación sin escrituras. | Consulta/comprobación Windows y Linux; evaluar acceso al comando instalado sin seleccionar aquí distribución. |
| B — Model editing | Preview y edición de familia o rol, validación, conservación de trabajo previo y regeneración canónica. | Una orden explícita por cambio; cero cambios ajenos a sus campos y representaciones derivadas. |
| C — Safe apply and operator UX | Selección proyecto/global, diagnóstico, preview/aplicación administrada, acceso a install/uninstall. | Actualización existente probada con manifests/ownership/verificación, o bloqueo concreto; delegación a motores existentes sólo en plataformas cualificadas. |

Se conserva A → B → C; esto define alcance y aceptación, no tareas. Completar B no acredita C. Si C no puede satisfacer la seguridad dentro de un alcance acotado, debe presentarse el bloqueo antes de decidir una separación de alcance/release; no declarar completa la experiencia de cambio de modelos.

### Incluido

- Consulta y diagnóstico local, salida legible y JSON opcional para listado, previews de asignaciones y diagnóstico.
- Edición de identificadores de una familia existente y familia/esfuerzo de un rol existente, sin reasignaciones implícitas.
- Distinción observable entre fuente canónica, outputs del repositorio y destino instalado.
- Aplicación explícita administrada, verificación y acceso a instalación/desinstalación con controles existentes.
- Ayuda y ejemplos copiables con dependencias, scopes y soporte acreditado por plataforma/operación.

### Excluido y restricciones

- No crear registros competidores, duplicar configuraciones por runtime, editar manualmente agentes generados ni rediseñar framework, prompts, permisos o políticas. Conservar Kael, Veyra, Orin, Atlas, Kovan, Argus, Nox, Vera, Talos, Thales, Helios y Aegis.
- No agregar proveedores, APIs de modelos/de pago, servicios residentes, agentes en segundo plano, dependencias pesadas ni un nuevo toolchain de compilación para esta feature.
- Python 3.11+ y biblioteca estándar son la opción inicial prioritaria por continuidad con el renderer. No se selecciona paquete, shim, launcher ni mecanismo definitivo de distribución; cualquier desviación requiere justificación técnica posterior.
- Consulta/configuración sin requerir Bun, Node, npm, WSL ni Docker. No reescribir a ciegas el instalador PowerShell ni rediseñar los dos entrypoints o pipeline de v0.4.9 para preparar esta funcionalidad.
- Excluir la UX `fast` sin checkout de #66 y la evaluación/publicación de Wiki de #67; no absorber otros gaps por asociación.
- Windows y Linux son objetivos de portabilidad CLI/configuración. macOS queda sin verificar y no recibe una promesa de soporte operativo por compartir lógica portable.
- La CLI es una herramienta de operador; no amplía autoridad de agentes, evita DENY ni activa Aegis automáticamente. Esta sesión sólo autoriza documentación, no mutaciones de Core o instalaciones.

## User Scenarios & Testing

### User Story 1 - Consultar asignaciones y estado sin cambios (Slice A; Priority: P1)

Una persona operadora consulta modelos/esfuerzos y comprende las diferencias OpenCode/Codex. Distingue las fuentes de una instalación y comprueba coherencia local sin escrituras ni conexión a proveedores.

**Why this priority**: Permite decidir qué cambiar y detectar límites antes de mutar.

**Independent Test**: Contrastar listado con Core y comparar inventario/contenido antes y después de consultas sobre fuentes y destinos aislados; ejecutar posteriormente flujos CLI en Windows y Linux, sin prompts a modelos.

**Acceptance Scenarios**:

1. **Given** fuentes válidas del baseline, **When** se listan asignaciones, **Then** aparecen exactamente doce roles, identidad, familia, esfuerzo y ambos IDs resueltos; se distingue Kael raíz Codex y Aegis sin agente Codex.
2. **Given** un mismo origen, **When** se pide listado legible o JSON, **Then** ambos describen las mismas asignaciones y contexto; JSON es procesable sin texto de presentación mezclado.
3. **Given** fuentes/outputs coherentes, **When** se comprueba configuración, **Then** se informa coherencia local y resultado satisfactorio sin afirmar disponibilidad de modelo ni actualización instalada.
4. **Given** TOML inválido, roster incongruente o drift de un output, **When** se comprueba, **Then** se identifica causa/recurso, termina sin éxito y no repara archivos.
5. **Given** un destino sin instalación, **When** se consulta estado, **Then** se informa ausencia sin crear manifest ni instalar.
6. **Given** Windows o Linux con prerrequisitos documentados y sin red, **When** se ejecutan ayuda, versión, listado y comprobación, **Then** se usa la misma semántica de resolución y se informa por separado el soporte nativo disponible.
7. **Given** una persona usuaria nueva, **When** consulta ayuda, **Then** puede copiar ejemplos para consulta, preview, edición y aplicación, identificar dependencias/contexto y corregir argumentos inválidos.

### User Story 2 - Editar una familia o un rol con preview (Slice B; Priority: P2)

Una persona que mantiene fuentes anticipa el efecto de un cambio y lo ejecuta con una orden explícita. Obtiene outputs coherentes preservando comentarios, trabajo previo y recursos ajenos; las instalaciones existentes aún no cambian.

**Why this priority**: Evita edición repetida, reasignaciones inesperadas y divergencia entre Core y adaptadores.

**Independent Test**: En origen aislado, contrastar previews con edición de familia/rol, comparar bytes no afectados y ejercitar rechazos, drift y fallos de generación mediante comprobaciones enfocadas.

**Acceptance Scenarios**:

1. **Given** roles asignados a una familia, **When** se previsualiza editar sus IDs, **Then** aparecen valores anteriores/propuestos de ambos runtimes y exactamente los roles afectados, manteniendo familia/esfuerzo, sin escribir.
2. **Given** cambio válido y origen coherente, **When** se edita la familia con una orden explícita, **Then** sólo cambian sus IDs y campos derivados por el renderer; roles de otras familias permanecen idénticos.
3. **Given** un rol existente, **When** se previsualiza y ejecuta su cambio de familia y/o esfuerzo, **Then** aparecen ambos IDs resueltos y esfuerzos anteriores/propuestos; sólo cambia el rol solicitado y sus representaciones aplicables.
4. **Given** una edición de Kael o Aegis, **When** se regenera, **Then** Kael conserva su representación raíz Codex y Aegis sólo cambia su salida OpenCode, sin crearse un agente Codex.
5. **Given** comentarios, TOML no relacionado y trabajo previo, **When** se edita, **Then** se conservan; identidades, permisos, cuerpos de prompts y outputs no afectados mantienen sus bytes.
6. **Given** rol/familia/esfuerzo inválido, IDs requeridos ausentes, flags incompatibles, origen ambiguo, drift o conflicto, **When** se solicita editar, **Then** se rechaza antes de escribir con una explicación útil.
7. **Given** fallo durante edición/regeneración bajo el contrato cooperante de FR-012, **When** termina o se recupera la operación, **Then** conserva o recupera coherencia propia sin sobrescribir conflictos externos detectados ni declarar render parcial exitoso. Un impedimento o resultado no acreditado se informa bloqueado o sin confirmar con estado real.
8. **Given** valores solicitados idénticos a los actuales, **When** se edita, **Then** se informa ausencia de cambios sin reescrituras.
9. **Given** instalaciones previas, **When** se editan fuentes, **Then** archivos y manifests instalados permanecen idénticos y se indica que requieren aplicación separada.

10. **Given** un ID que no coincide íntegramente con el alfabeto inicial de B, **When** se solicita preview o edición, **Then** se rechaza antes de staging o escritura, sin normalizarlo ni cambiar el renderer.
11. **Given** un dueño cooperante activo, **When** otra orden intenta commit o recovery, **Then** la adquisición nativa no bloqueante falla y la segunda orden informa bloqueo sin inspeccionar ni modificar recursos del batch ajeno.
12. **Given** una interrupción y scratch pendiente, **When** se solicita recovery explícito, **Then** adquiere el lock estable, valida identidad/registro/hashes/backups y sólo revierte recursos propios; un tercer estado bloquea, y una nueva interrupción conserva respaldos reutilizables.

### User Story 3 - Aplicar y operar sobre una instalación explícita (Slice C; Priority: P3)

Una persona operadora selecciona destino/harness, diagnostica, revisa y aplica intención preparada. La actualización conserva ownership y verificación; install/uninstall reutiliza el motor seguro donde está cualificado.

**Why this priority**: El cambio de fuentes sólo completa la experiencia cuando existe propagación segura y comprobable al destino.

**Independent Test**: En destinos aislados project/global, contrastar preview/resultado/verificador con manifests válidos y casos negativos; demostrar integración real en plataformas cualificadas distinguiéndola de fixtures, sin llamadas a modelos.

**Acceptance Scenarios**:

1. **Given** origen válido y destino administrado seleccionado, **When** se previsualiza aplicar, **Then** se muestran origen, scope, destino, harnesses, asignaciones antes/después, recursos/metadatos afectados y bloqueos, sin escribir ni instalar harnesses ausentes.
2. **Given** destino sin drift y ruta de actualización demostrada segura, **When** se aplica a un harness, **Then** recursos/manifest quedan coherentes y supera verificación; otro harness, configuración del usuario y otros proyectos permanecen idénticos.
3. **Given** selección de ambos harnesses, **When** completan actualización/verificación, **Then** se reporta cada resultado y sólo se declara éxito conjunto si ambos satisfacen controles; un resultado parcial no cuenta como aplicación completa.
4. **Given** drift, manifest ausente/inválido/incompatible, ownership no demostrable, versión/procedencia incoherente o ruta insegura, **When** se aplica, **Then** se bloquea antes de escribir, sin adoptar archivos ajenos, omitir hashes ni relabelar personalización como release inmutable.
5. **Given** fallo/interrupción durante actualización, **When** se informa o diagnostica el resultado disponible, **Then** se distingue aplicado, pendiente y sin confirmar, con recuperación segura disponible o bloqueo; no se repite ciegamente la mutación.
6. **Given** instalación y verificador soportado, **When** se diagnostica en formato legible/JSON, **Then** se reutiliza verificación existente y ambos informan el mismo scope/versión/integridad, sin reparar ni agregar discovery externo al modo de verificación.
7. **Given** plataforma no cualificada o prerrequisito ausente, **When** se solicita operación nativa, **Then** se explica el límite sin simular éxito ni usar controles menos protegidos.
8. **Given** instalación/desinstalación cualificada, **When** se invoca para scope/harness explícito, **Then** se delega al motor existente conservando controles, el otro harness y UX/pipeline v0.4.9.
9. **Given** estado instalado y metadatos ya coincidentes, **When** se aplica, **Then** se informa ausencia de cambios sin reescribir y se puede verificar el mismo estado.

### Edge Cases

- Orígenes o scopes coexistentes: consultas muestran contexto; las mutaciones requieren selección inequívoca sin elegir silenciosamente otro proyecto.
- Rol/familia desconocido, TOML duplicado/incompleto o roster discrepante: rechazo sin tablas reparadoras ni defaults que reasignen roles.
- Esfuerzo no validable localmente o ID nuevo sintácticamente válido: distinguir rechazo de contrato local de disponibilidad remota desconocida; no consultar proveedores.
- Familia con ID Codex y rol Aegis: mostrar traducción y ausencia de agente como conceptos distintos.
- Worktree con trabajo ajeno: preservarlo sin exigir limpieza global; drift/conflicto de recursos relevantes sí bloquea.
- Si se detecta un cambio de fuente/output/manifest entre inspección y escritura, invalidar antes de sobrescribir; si ya hay efectos, reconciliar sólo los propios y comunicar estado. En B rige FR-012: no se promete excluir cambios externos no cooperantes posteriores al último hash.
- Rutas con espacios/no ASCII, separadores, mayúsculas y enlaces/reparse points: conservar contención y portabilidad; bloquear traversal/escape sin debilitar controles por OS.
- Harness ausente, manifest legado o ownership ambiguo: distinguir ausencia, compatibilidad soportada y bloqueo. Aplicar no instala ni migra implícitamente.
- Actualización global con override de proyecto: conservarlo e informar que puede prevalecer; no afirmar recarga de sesiones activas.
- Un recurso/harness inseguro dentro de una selección múltiple: completar validación previa antes de escribir; si falla después, conservar resultados individuales observables.
- Permisos insuficientes, dependencia nativa ausente o interrupción: fallo/bloqueo útil sin elevación automática ni falsa atomicidad del motor existente.
- Personalización local divergente del release: mantener trazabilidad y diferencia explícita, sin presentarla como copia oficial idéntica.

## Requirements

### Functional Requirements

- **FR-001 (A/B/C)**: Toda intención de modelo/familia/esfuerzo DEBE resolverse exclusivamente desde `olympus/core/models.toml`, reutilizando identidades/roles y renderer existentes. No debe haber registros competidores ni mappings independientes por runtime.
- **FR-002 (A)**: La CLI DEBE ofrecer ayuda, versión, listado de asignaciones, estado y comprobación, identificando origen/contexto y fuente frente a instalación. Una instalación ausente debe informarse sin crearla.
- **FR-003 (A)**: El listado DEBE cubrir exactamente doce roles con identidad, familia, esfuerzo y modelos OpenCode/Codex, diferenciando representación real y límites del adaptador.
- **FR-004 (A/B/C)**: Listado, previews de familia/rol y diagnóstico DEBEN ofrecer salida legible y JSON opcional con datos equivalentes; JSON debe ser procesable sin mensajes de presentación mezclados.
- **FR-005 (A/B/C)**: Consulta, check, diagnóstico y cualquier preview/`dry-run` DEBEN ser de sólo lectura: cero creación, modificación o eliminación de archivos, manifests o configuración, incluidos caches y reparaciones.
- **FR-006 (B)**: Una orden explícita DEBE actualizar IDs de una familia existente, afectando exactamente sus roles actuales y conservando las asignaciones de familia y esfuerzo.
- **FR-007 (B)**: Una orden explícita DEBE cambiar familia y/o esfuerzo de un rol existente sin reasignar ningún otro rol.
- **FR-008 (B/C)**: Antes de mutar asignaciones DEBEN mostrarse origen, alcance, roles afectados, valores anteriores/propuestos, ambos IDs de runtime y esfuerzos. Preview y ejecución deben describir los mismos efectos si el estado no cambia; no se prescribe confirmación interactiva adicional.
- **FR-009 (B/C)**: Antes de cualquier staging o escritura DEBEN rechazarse roles/familias/esfuerzos fuera del contrato local soportado, IDs requeridos vacíos o inválidos, flags inválidos/incompatibles, contexto ambiguo y operaciones nativas no soportadas, indicando causa y corrección o límite concreto. En Slice B, cada ID existente que se use y cada ID propuesto DEBE coincidir por completo con `[A-Za-z0-9][A-Za-z0-9._:/-]*`, sin recortar ni normalizar; comillas, backslashes, controles, saltos y cualquier carácter fuera del alfabeto se rechazan. Es un contrato inicial de B, no una limitación universal de OpenCode/Codex ni prueba de disponibilidad o autenticación del proveedor.
- **FR-010 (A/B)**: Check y edición DEBEN validar coherencia mediante lógica existente. Drift/conflicto inesperado debe fallar/bloquear sin reparación o sobrescritura implícita.
- **FR-011 (B)**: La edición DEBE preservar comentarios, TOML no relacionado y trabajo previo. Sólo cambia valores solicitados y campos derivados; identidades, permisos, cuerpos de prompts y outputs ajenos mantienen sus bytes.
- **FR-012 (B)**: Olympus DEBE coordinar sus propias operaciones de commit y recovery mediante exclusión mutua nativa, detectar conflictos observables y recuperar únicamente recursos que continúen perteneciendo a la operación original, con hashes old/new y backups verificados. DEBE confirmar coherencia antes de declarar éxito; ante fallo recupera el estado previo propio o informa estado bloqueado o sin confirmar, sin presentar éxito parcial ni sobrescribir conflictos detectados. La recuperación adquiere exclusión antes de inspeccionar recursos del batch y puede repetirse tras interrupción sin destruir sus respaldos. No se garantiza protección absoluta frente a procesos externos que ignoran el lock, atomicidad multiarquivo visible para lectores concurrentes ni durabilidad absoluta ante pérdida de energía. No se permite sobrescritura automática de modificaciones externas; un hash previo a `os.replace` no es compare-and-swap.
- **FR-013 (B/C)**: Una petición idéntica al estado válido actual DEBE informar ausencia de cambios sin reescrituras innecesarias.
- **FR-014 (B/C)**: Edición de fuentes y aplicación instalada DEBEN ser operaciones separadas y explícitas. Editar deja intactos destinos; aplicar no cambia intención canónica, instala harnesses ausentes ni actualiza proyectos no seleccionados.
- **FR-015 (C)**: Aplicar DEBE identificar origen, scope project/global, destino y OpenCode/Codex/ambos inequívocamente, respetando raíz exacta de worktree en proyecto y resolución segura global, sin exigir limpieza del trabajo ajeno.
- **FR-016 (C)**: Preview DEBE enumerar recursos/metadatos afectados, asignaciones y bloqueos; ejecución debe validar antes de escribir manifests, ownership, hashes, contención, integridad y compatibilidad de versión/procedencia del conjunto seleccionado.
- **FR-017 (C)**: Aplicar DEBE usar flujo administrado que reutilice controles existentes, conserve archivos del usuario, overrides y harnesses no seleccionados, y mantenga manifests/hashes coherentes. No debe parchear agentes instalados al margen de ese flujo ni omitir verificaciones.
- **FR-018 (C)**: El estado instalado DEBE distinguir release base, origen y personalización para verificación posterior; una personalización no es contenido idéntico a un release oficial inmutable. Aquí no se decide esquema de metadatos.
- **FR-019 (C)**: Aplicar sólo DEBE declarar éxito tras actualización administrada y verificación del destino/harness. Para ambos debe reconciliar los dos resultados; efectos parciales/desconocidos requieren resultados confirmados/pendientes y recuperación segura o bloqueo explícito.
- **FR-020 (C)**: Diagnóstico DEBE reutilizar `VerifyOnly` o verificador existente donde esté soportado, informar scope/harness/versión/integridad y distinguir ausencia, drift, manifest inválido y verificación no disponible, sin reparación ni discovery externo nuevo.
- **FR-021 (C)**: Install/uninstall DEBEN delegar a motores/entrypoints existentes en plataformas cualificadas, conservando selección, manifests, ownership, hashes y protección contra drift. Operaciones no cualificadas terminan sin cambios ni falso éxito, explicando el límite.
- **FR-022 (A/B/C)**: DEBEN conservarse doce roles, doce agentes OpenCode, diez especialistas Codex, Kael raíz y Aegis ausente de Codex. Cambiar modelos no cambia permisos, gobernanza, límites de agentes ni instala proveedores.
- **FR-023 (A/B)**: Consulta, validación, preview y edición/regeneración DEBEN funcionar offline, sin APIs de modelos, procesos residentes ni dependencias pesadas, con igual semántica en Windows/Linux y sin WSL, Docker, Bun, Node o npm requeridos.
- **FR-024 (A/B/C)**: Soporte DEBE informarse por operación/plataforma y evidencia. Cualificación CLI/configuración no acredita instalación ni runtime; macOS sigue sin verificar hasta evidencia específica y no se reducen controles para ampliar compatibilidad.
- **FR-025 (A/C)**: El acceso final DEBE ofrecer un comando Olympus documentado y consistente con ejemplos copiables y prerrequisitos. La entrada Python de desarrollo puede aceptarse para A, pero no acredita UX instalada completa; distribución y spelling final se deciden después del análisis técnico.
- **FR-026 (A/B/C)**: Resultados DEBEN distinguir éxito, ausencia de cambios, fallo, bloqueo y estado sin confirmar; fallos/bloqueos terminan sin éxito. Validación local no afirma autenticación, disponibilidad de modelos, activación de runtime ni recarga de sesiones.

### Key Entities

- **Intención canónica**: familias, IDs por adaptador y familia/esfuerzo por rol en la fuente existente.
- **Rol/identidad**: uno de los doce roles Core; cambiar modelo no cambia responsabilidad o autoridad.
- **Representación de adaptador**: recursos derivados por renderer, con diferencias y gaps propios.
- **Preview**: valores anteriores/propuestos, roles, recursos y bloqueos; no es configuración alternativa.
- **Origen**: fuentes Core/adapter y outputs de un checkout; distinto del destino instalado.
- **Destino administrado**: instalación proyecto/global con harnesses, recursos propios y archivos ajenos preservados.
- **Manifest e identidad instalada**: ownership, hashes, harnesses, versión/procedencia y personalización verificable, preservando compatibilidad.
- **Estado de soporte/verificación**: resultado acotado a operación, plataforma y evidencia, sin inferir paridad.

## Success Criteria

### Measurable Outcomes

- **SC-001**: El 100% de los doce roles se consulta con asignaciones coincidentes con Core; cero roles adicionales e instancias Aegis Codex.
- **SC-002**: Salidas legible/JSON de listado, preview y diagnóstico describen el mismo estado y conjunto afectado; el 100% de las salidas JSON previstas es procesable.
- **SC-003**: Una orden explícita completa cada edición válida de familia/rol con representaciones coherentes; cero roles ajenos se reasignan y cero permisos, identidades o cuerpos de prompts se alteran.
- **SC-004**: El 100% de consultas/previews y rechazos previos conserva inventario/contenido; cero instalaciones cambian por editar fuentes.
- **SC-005**: El 100% de fallos de edición definidos dentro del contrato cooperante de FR-012 conserva/recupera coherencia propia o declara bloqueo/estado sin confirmar concreto, sin falso éxito ni sobrescritura de conflictos detectados. No se extiende a las garantías excluidas explícitamente por FR-012.
- **SC-006**: Cada combinación scope/harness anunciada como soportada permite actualizar una instalación existente personalizada y verificarla conservando ownership, procedencia y archivos ajenos; cero destinos no seleccionados cambian. Sin demostración segura se declara bloqueo y no cuenta como aceptación de C.
- **SC-007**: Cero resultados parciales/no confirmados se presentan como éxito conjunto; todo harness seleccionado tiene resultado reconciliado antes de afirmar aplicación completa.
- **SC-008**: Consulta/configuración alcanza aceptación en las dos plataformas objetivo sin red ni gasto en APIs; cada operación nativa anunciada tiene evidencia propia y ninguna afirmación operativa macOS precede su cualificación.
- **SC-009**: Una persona operadora puede seguir ejemplos para consultar, previsualizar, editar y aplicar al destino mediante la vía de comando soportada, sin editar outputs manualmente ni deducir scope, dependencias o límites.

## Dependencies and Risks

### Dependencies

- Constitución 1.0.0, Core y contratos citados; la especificación no los sustituye ni amplía autoridad.
- Renderer y fuentes de adaptadores; conservar su frontera actual sin inferir que consume todas las políticas/cuerpos de rol.
- Motores de bootstrap/global/install/uninstall, manifests, ownership, hashes y verificadores. La aplicación de personalizaciones depende de demostrar compatibilidad con ellos.
- Publicación/verificación v0.4.9 antes de código era el gate histórico de #64; T001/R49 lo reconciliaron con evidencia limitada a instalación/verificación de archivos Codex proyecto, conservada en research.md. No se repite ni se amplía su alcance por esta actualización B; metadata por sí sola no era esa evidencia.
- Windows local y Linux en CI alojada para cualificación posterior enfocada, sin WSL local; documentar prerrequisitos nativos según motor/plataforma sin extenderlos a consultas offline.
- Resolver acceso al comando instalado; entrada de desarrollo no resuelve por sí sola distribución y UX final.

### Risks

- Confundir edición con actualización instalada genera falsa propagación; los resultados deben separar estados.
- Personalización puede chocar con identidad inmutable de release y verificación: omitir controles compromete trazabilidad/desinstalación.
- Los motores baseline no acreditan transacción global/rollback completo; drift protection no demuestra recuperación.
- Reconstruir TOML indiscriminadamente puede perder comentarios/trabajo previo y violar FR-011.
- Diferencias de filesystem y operaciones Windows pueden limitar C sin impedir A/B Linux; no reducir protecciones para declarar soporte.
- Concurrencia, outputs compartidos y ambos harnesses pueden producir efectos parciales: requieren preflight/reconciliación honesta.
- Contrato local de esfuerzo/ID no demuestra aceptación remota; declarar límites sin APIs ni registros alternativos.

### Incertidumbres para planificación técnica

1. **Comando/distribución (incertidumbre inicial)**: plan.md registra la elección posterior de entrada/launchers ligados a checkout. A está SHIPPED; esta actualización B no cambia su contrato, distribución ni comportamiento, ni absorbe #66.
2. **TOML/recuperación de fuentes**: contrato B resuelto por las decisiones aprobadas; quedan pruebas de implementación previas a habilitar escrituras. Conservar experimentos de preservación/recuperación y cualificar el protocolo nativo completo Windows/Linux, sin motor transaccional general.
3. **Aplicación y metadatos**: demostrar flujo mínimo para proyecto/global y ambos harnesses compatible con ownership, hashes, versión y `VerifyOnly`, sin personalización presentada como release inmutable. Decidir si metadatos actuales bastan o se justifica un delta compatible; si exige debilitar controles, bloquear C y presentar decisión de alcance.
4. **Fallo parcial instalado**: establecer unidad segura, recuperación posible y comportamiento ante interrupción, especialmente con ambos harnesses. No asumir atomicidad baseline ni prometer rollback universal sin evidencia.
5. **Validación local de esfuerzos/IDs**: IDs de B restringidos por FR-009; esfuerzo seleccionable derivado de la fuente, sin catálogo adicional. El renderer sigue sin demostrar disponibilidad remota. Implementar y probar rechazo antes de staging, sin cambiar A ni renderer.
6. **Operaciones nativas Linux**: identificar reutilización real, límites OS y evidencia mínima por operación. A/B Linux no obliga a anunciar instalador Linux entregado; macOS permanece desconocido.
7. **Gate de release (reconciliado)**: T001/R49 resolvieron el prerequisito histórico con el alcance de evidencia documentado; no reacreditar ni acceder al entorno retenido en esta revisión.

No se identificó ambigüedad funcional material que impida iniciar planificación. Estas cuestiones requieren investigación técnica allí; viabilidad segura de C y gate de release condicionan implementación y cualquier declaración de producto completo.

## Verification Scope — registro de especificación inicial

En la sesión inicial sólo se revisaron documentación/fuentes. La tabla siguiente conserva ese historial previo a Slice A y al gate B; sus NOT RUN no describen el estado SHIPPED actual de A. Los checks expresaban aceptación futura conforme a TFR; no eran pruebas ejecutadas. Reutilizar suites pertinentes y ampliar sólo por evidencia insuficiente, riesgo o gates existentes.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Doce roles y diferencias de adaptador | Contrastar listado/JSON con Core y checks pertinentes harness-core/Codex | Deterministic | NOT RUN — funcionalidad nueva |
| Sólo lectura, rechazo y no-op | Inventario/contenido antes/después de consulta, preview y petición inválida | Deterministic | NOT RUN |
| Familia/rol y bytes no afectados | Contrastar preview, fuente y renderer; comentarios y trabajo previo | Deterministic | NOT RUN |
| Conflictos, concurrencia e interrupción | Escenarios aislados de render fallido y resultado parcial observable | Simulated | NOT RUN |
| Ownership/hashes/rutas/manifests/versiones | Checks existentes pertinentes y fixtures proyecto/global con drift/selección | Simulated | NOT RUN |
| CLI/configuración Windows/Linux | Flujos enfocados Windows local/Linux CI sin WSL ni APIs | Real runtime | NOT RUN |
| Apply/verify/install/uninstall por plataforma declarada | Destinos aislados mediante motor/verificador existentes; no sustituir por mocks | Real runtime | NOT RUN — integración pendiente |

No agregar tier ni imponer FULL/RUNTIME rutinarios. Mantener una sesión Olympus activa, sin procesos paralelos pesados/toolchains locales nuevos; no cambiar por ello el límite Core de hijos. Runtime de agentes/proveedores y soporte macOS no se acreditan por esta especificación.

## Verificación vigente de Slice B

El párrafo y los criterios históricos de planificación anteriores describían la fase preimplementación. La selección integrada final verificó en T019/T020 las rutas de edición/recovery, lock nativo, snapshots y conflictos en Windows/Linux; su fuente y límites están reconciliados en [tasks.md](tasks.md). G2 PASS no amplía Slice B a aplicación instalada ni cambia las exclusiones de FR-012.

## Assumptions

- `specs/001-portable-olympus-cli` es la primera feature nueva directa; numeración retrospectiva anidada no consume la secuencia.
- Actores humanos autorizados de fuentes/destinos; CLI no concede autoridad a Kael/Aegis/especialistas.
- Sólo familias/roles existentes; agregar/eliminar familias/roles, cambiar identidades y habilitar proveedores queda fuera.
- Seleccionar harness no habilita capacidades ausentes ni agrega otros harnesses.
- Trabajo ajeno se preserva sin limpieza global; conflictos se juzgan sobre recursos relevantes.
- Preview no reserva estado: debe revalidarse antes de escribir. Aplicar archivos no garantiza recarga de sesiones abiertas.
- Métricas de aceptación usan exactitud/preservación/finalización de flujos; no inventar objetivos de tiempo/consumo/rendimiento ausentes del issue.
