# Contrato propuesto de CLI

**Estado vigente (2026-10-14)**: A **SHIPPED** con PR #69 en master `b7f8404`; B **READY_FOR_TASKS** contractual por tres decisiones aprobadas, sin implementación; C y feature completa **BLOCKED**; macOS **NOT VERIFIED**. Evidencia histórica A/R49 y gate B en [research.md](../research.md). La revisión no cambia comandos A ni alcance C, no habilita apply/escrituras B ni declara implementado el lock. B sólo podrá escribir tras la validación enfocada Windows/Linux.

## Entrada, contexto y soporte

- Inicial: `python -B -m olympus` desde el checkout confiable. Final: `olympus` mediante launcher anclado a ese checkout en PATH; Python >=3.11 explícito y sin escribir caches.
- Linux A: launcher y contrato entregados con PR #69; la observación del run anterior que usó `chmod` y su pendiente de entonces se conservan como historia en research.md. Esta revisión no reacredita CI ni altera A. Linux B requiere validación propia; macOS NOT VERIFIED.
- `--source <absolute-path>` es opción global anterior al subcomando; default de launcher es su checkout. No buscar automáticamente otro Core en el proyecto destino. Error si origen no existe, no contiene fuentes/renderer o es ambiguo.
- Proyecto: `--scope project --target <absolute-worktree-root>`. Global: `--scope global`, usando resolución segura del motor, sin interpretar un target de proyecto como destino global. Para contexto de override global, identificarlo explícitamente sin modificarlo.
- `--harness opencode|codex|all` selecciona representación/operación cuando aplique. Listado incluye ambos; check default all; mutaciones instaladas no usan un default silencioso.
- Sintaxis inválida/opciones incompatibles se rechazan antes de cualquier escritura. No `--force`, bypass de drift, proveedor nuevo o modo automático Aegis.
- Consultas/preview no crean tempfiles, locks, backups, caches ni directorios. Un scratch previo se informa, no se repara. También propagar `PYTHONDONTWRITEBYTECODE=1` a hijos.

## Superficie de comandos

| Comando propuesto | Slice / semántica | Escritura / condición |
|---|---|---|
| `--version`, `--help` | A; versión de herramienta y ayuda | Ninguna |
| `models list [--json]` | A; doce roles, familia/esfuerzo y IDs de ambos adaptadores | Ninguna |
| `status [--scope ... --target ... --harness ...] [--json]` | A; origen y estado local/manifest disponible, no Verify profundo propio | Ninguna; sin descubrir destinos arbitrarios |
| `config check [--harness ...] [--json]` | A; validación de fuentes y drift renderer | Ninguna; comparar expected en memoria |
| `models set-family <existing> --opencode <id> --codex <id> [--dry-run [--json]]` | B; editar los dos IDs de esa familia | Preview sin escribir; ejecución una orden explícita |
| `agents set-model <role> [--family <existing>] [--effort <canonical-value>] [--dry-run [--json]]` | B; al menos un valor solicitado | Otros roles inalterados; preview de resolución completa |
| `config recover` | B; rollback/cleanup de batch propio pendiente | Adquirir lock nativo estable existente antes de inspección del batch; sin dueño activo, identidad/estado/hashes/backups reconciliados; sin retry original |
| `doctor --scope ... [--target ...] --harness ... [--json]` | C; verificar mediante motor existente | Windows cualificado, fuente local apta; read-only bloqueado si no se garantiza |
| `config apply --scope ... [--target ...] --harness ... [--dry-run] [--json]` | C; futura actualización administrada | BLOCKED para personalizado con baseline; no llama install override ni escribe destino |
| `install --scope ... [--target ...] --harness ... --version <release> [--dry-run]` | C; delegación de release oficial | Windows cualificado; no instala silenciosamente sources personalizados |
| `uninstall --scope ... [--target ...] --harness ...` | C; delegación de retiro administrado | Windows cualificado, ownership/hash del motor |

`--json` de edición sólo se ofrece con `--dry-run` inicialmente; ejecución humana muestra preview antes de escribir y luego resumen. Esto evita mezclar varios documentos JSON en stdout sin introducir un protocolo de eventos. No se exige JSON de edición real por FR-004. Diagnóstico/listado/preview comparten datos equivalentes entre formatos.

`doctor` usa bootstrap `-Target ... -Harness ... -SourceVersion ... -VerifyOnly` para proyecto y global-install `-Harness ... -SourceVersion ... -VerifyOnly` para global, desde fuente local coherente, sin public wrapper que descargue archives. Si la versión/candidate/procedencia no puede verificarse, informa límite/fallo. No suplantar la verificación con un hash checker Python. Global OpenCode discovery existente se evalúa por evidencia; si escribe, doctor permanece bloqueado como read-only.

### Identificadores — contrato inicial definitivo de Slice B

Todos los IDs existentes utilizados por el candidato y los IDs propuestos deben coincidir **por completo** con `[A-Za-z0-9][A-Za-z0-9._:/-]*`. No trim, normalización, matching parcial ni ancla que acepte un newline final. Primer carácter ASCII alfanumérico; los restantes sólo ASCII alfanuméricos, punto, underscore, dos puntos, slash o guion. Se aceptan los actuales conformes, incluidos `openai/gpt-6.1-sol` y `gpt-6-luna`.

Vacío, comillas, backslashes, espacios, controles, saltos, `#`, braces y cualquier carácter fuera del alfabeto se rechazan con exit 2 **antes de cualquier staging o escritura, incluida creación del lock**. Un ID existente no conforme rechaza la operación B con el mismo exit 2, sin repararlo; no modifica el comportamiento read-only de A. El renderer existente no cambia. Sintaxis válida no acredita disponibilidad, soporte live ni autenticación; no consultar proveedores. Es una restricción inicial de B, no una limitación universal de OpenCode o Codex.

Familias/roles de fuente. Esfuerzo inicial extraído del conjunto de esfuerzos presente en el documento canónico; no registry de esfuerzos/proveedor adicional. Aegis se puede configurar en Core, pero sólo materializa OpenCode.

### Exclusión y recovery — contrato de operador

- Commit y recovery B usan exclusión nativa no bloqueante sobre `.olympus-cli-edit.lock` en el origen canónico: `msvcrt.locking` Windows / `fcntl.flock` Linux. Un dueño activo devuelve blocked/exit 3 antes de inspeccionar su batch. El archivo de lock es estable y permanece vacío después del cleanup; su existencia no significa pendiente ni propietario vivo. Nunca eliminarlo/reemplazarlo/recrearlo para desbloquear.
- Preview no crea/adquiere lock ni scratch; no-op de edición válida y sin scratch pendiente tampoco los crea. Sólo la primera edición real aceptada puede crear el archivo estable. Recovery sólo abre el existente: si falta, es inseguro o su identidad no se acredita, blocked/exit 3 sin examinar registro/backups/targets. Con lock existente adquirido y sin scratch, no_changes/exit 0 sin escrituras.
- Scratch pendiente bloquea B en preflight incluso con lock libre o ausente, sin crear/recrear lock ni staging. `config recover` es orden humana separada; adquiere exclusión antes de leer el batch, valida identidad/registro/read-set/hashes/backups y mantiene el lock hasta rollback/cleanup o reporte de bloqueo. PID, timestamp y directorio no acreditan terminación; no auto-cleanup por antigüedad.
- PREPARED: dejar old, restaurar sólo new mediante copia staged de backup verificado; all-new también revierte. COMMITTED: sólo limpiar tras verificar todo new. Tercer estado, modo divergente, entrada externa modificada, backup necesario inválido o identidad distinta bloquean sin overwrite; conservar evidencia. Recovery interrumpido puede repetirse sin consumir respaldos. Protocolo completo: [data-model.md](../data-model.md).
- Coherencia y ownership acreditados permiten éxito; rollback confirmado de un cambio fallido sigue siendo fallo operacional/exit 1, no éxito de edición. Conflicto confirmado produce blocked/exit 3; efectos parciales o resultado no acreditado producen unconfirmed/exit 4 con recursos/estado concretos. Ningún resultado parcial se presenta como aplicado.
- Se excluyen protección absoluta contra procesos externos no cooperantes, atomicidad multiarquivo visible a lectores y durabilidad absoluta ante pérdida de energía. No hay sobrescritura automática de modificaciones externas; el hash previo a os.replace no es compare-and-swap. Estas exclusiones no habilitan ignorar conflictos detectados.

La liberación por terminación abrupta y la identidad/cleanup del lock deben verificarse en ambas plataformas antes de habilitar escrituras. La documentación y el PASS previo de una primitiva Windows no prueban la implementación. El protocolo integrado y su liberación en Windows/Linux siguen **NOT RUN**. Mantener un único scratch y registro, sin servicios ni segundo mapping.

## Salida y códigos

Salida humana concisa con origen/contexto, afectados, ambos IDs y valores old/new antes de mutar. Errores nombran recurso/causa y corrección disponible; no emitir credenciales o logs nativos completos por defecto.

JSON de comando permitido es un documento único en stdout; diagnósticos de proceso/presentación van a stderr. Envoltorio `schema_version=1`, `operation`, `result`, `context`, `data`, `issues`. Los datos usan los mismos objetos del formato humano, sin segundo resolver. `result` puede ser `ok`, `no_changes`, `absent`, `failed`, `blocked`, `unconfirmed`.

- Listado: `data.roles` con `role`, `identity`, `family`, `effort`, `models.opencode`, `models.codex`, y representación de cada harness (`agent`, `root`, `absent`).
- Preview: affected roles, old/new intención/resolución, recursos cambiantes relativos y bloqueos; no tabla de mappings persistente.
- Estado/doctor: installed harnesses, scope, versión registrada, integridad y soporte/evidencia disponible. Cuando no puede conocerse una asignación instalada segura, informar unknown, no copiar la asignación del source como si estuviese aplicada.
- Bloqueo apply: contexto solicitado y razones, plan de escritura ausente; no simular un preview de actualización que el motor aún no soporta.

| Exit | Significado |
|---|---|
| 0 | Consulta válida, éxito confirmado o no-op; ausencia informativa en status |
| 1 | Check/verificación fallida o fallo operacional confirmado |
| 2 | Argumentos/contexto/valores inválidos |
| 3 | Capacidad/entorno/contrato bloqueado, incluido apply C |
| 4 | Resultado parcial/sin confirmar que requiere reconciliación |

El código nativo y su salida relevante se conservan en datos del resultado; se traducen a estas categorías sin convertir error en éxito. Timeout de mutación nativa produce unconfirmed, no retry. No prometen atomicidad de install/uninstall oficiales sólo por routing.

## Protección de fronteras

Edición de source no acepta target instalado ni lo modifica. Apply no edita models, instala harness ausente o migra manifests implícitamente. Install oficial usa identidad immutable y motores existentes. Ningún comando cambia permisos/agentes/proveedores ni cierra gaps de Codex. Soporte por operación/plataforma siempre explícito; macOS NOT VERIFIED.
