# Contrato de CLI — feature 001

**Estado histórico de la rama (2026-11-08)**: A **SHIPPED**; B **ACEPTADA** (T019 Windows + T020 Linux, G2 PASS); C1/C3 project, C4 doctor project, C5 install/uninstall routing y C6 asignaciones project ya integrados. C7 global read-only y C8 global OpenCode apply/recovery estaban implementados en esta rama, pendientes entonces de review/CI hosted y cualificación independiente. macOS nativo **NOT VERIFIED**. El límite vigente se define abajo.

## Límite vigente — 2026-11-16

OpenCode es el único runtime soportado. Esta enmienda sustituye las opciones
Codex/`all` y la instalación pública project/global que aparecen en la
propuesta original: no son rutas ni promesas de compatibilidad actuales.
Public install/update/uninstall se fija a global OpenCode y rechaza los antiguos
selectores scope/harness/target/version. Project-scoped OpenCode overrides,
config list/check/apply/recovery, status y read-only doctor permanecen como
operaciones distintas; ninguna instala recursos faltantes.

Los formatos actuales son explícitos y fallan cerrados si están incompletos o
no soportados. No hay conversión, adopción o eliminación automática de formatos
antiguos. Una instalación completa en formato actual sigue válida
independientemente de la release que la creó; para retirar una instalación
antigua no soportada, usa su release correspondiente.

## Entrada, contexto y soporte

- Inicial: `python -B -m olympus` desde el checkout confiable. Final: `olympus` mediante launcher anclado a ese checkout en PATH; Python >=3.11 explícito y sin escribir caches.
- Linux A: launcher y contrato entregados con PR #69; la observación del run anterior que usó `chmod` y su pendiente de entonces se conservan como historia en research.md. Esta reconciliación no cambia A. Linux B está acreditada por T020; macOS NOT VERIFIED.
- `--source <absolute-path>` es opción global anterior al subcomando; default de launcher es su checkout. No buscar automáticamente otro Core en el proyecto destino. Error si origen no existe, no contiene fuentes/renderer o es ambiguo.
- Las operaciones de configuración pueden seleccionar `--scope project --target <absolute-worktree-root>` o `--scope global`; para global se usa resolución segura del motor, nunca un target de proyecto.
- OpenCode es la única representación. `--harness opencode` es opcional donde se admite; OpenCode es el default. `codex` y `all` no son valores válidos ni aliases.
- Public install/update/uninstall no aceptan `--scope`, `--harness`, `--target` ni selector de versión; se fijan a global OpenCode. `--version` en la raíz sólo informa versión de la herramienta.
- Sintaxis inválida/opciones incompatibles se rechazan antes de iniciar un motor nativo. No `--force`, bypass de drift, proveedor nuevo ni instalación automática.
- Consultas/preview no crean tempfiles, locks, backups, caches ni directorios, salvo las excepciones nativas explícitas. Excepción C4: PowerShell corre con `USERPROFILE` temporal para contener su cache de inicio; se elimina al salir y no persiste en source/target/perfil real. Excepción C5: el probe usa un perfil temporal y la adquisición oficial/ejecución nativa puede usar temp/cache, sin escribir recursos de instalación en preview. Un scratch previo se informa, no se repara. También propagar `PYTHONDONTWRITEBYTECODE=1` a hijos.

## Superficie de comandos

| Comando propuesto | Slice / semántica | Escritura / condición |
|---|---|---|
| `--version`, `--help` | A; versión de herramienta y ayuda | Ninguna |
| `models list [--json]` | A; once roles, familia/esfuerzo e ID OpenCode | Ninguna |
| `agents list [--scope ... --target ...] [--json]` | CLI actual; valores efectivos OpenCode y su procedencia | Ninguna |
| `status [--scope project --target <root>\|--scope global] [--json]` | A/C7; estado local o metadatos del manifest seleccionado | Ninguna; global no certifica integridad |
| `config check [--harness opencode] [--json]` | A; validar fuentes y drift renderer OpenCode | Ninguna; comparar expected en memoria |
| `models set-family <existing> --opencode <id> [--dry-run [--json]]` | B; editar el ID OpenCode de esa familia | Preview sin escribir; ejecución es una orden explícita |
| `agents set-model <role> [--family <existing>] [--effort <canonical-value>] [--dry-run [--json]]` | B; al menos un valor solicitado | Otros roles inalterados; preview de resolución completa |
| `config recover` | B; rollback/cleanup de batch propio pendiente | Adquirir lock nativo estable existente antes de inspección del batch; sin dueño activo, identidad/estado/hashes/backups reconciliados; sin retry original |
| `doctor --scope project --target <root> [--harness opencode] [--json]` | C4; diagnóstico read-only de instalación OpenCode project existente | Windows + PowerShell 7 para VerifyOnly; no runtime discovery |
| `doctor --scope global [--harness opencode] [--json]` | C7; manifest/hashes y VerifyOnly global OpenCode | Windows + PowerShell 7 para verificación nativa; no repara |
| `config apply --scope project --target <root> [--harness opencode] --dry-run [--json]` | C1; preview read-only de OpenCode ya administrado | Manifest válido e hashes intactos; no instala recursos |
| `config apply --scope project --target <root> [--harness opencode] --execute` | C3; actualización explícita de recursos OpenCode ya administrados | Lock estable, revalidación y journal project schema 1; nunca `--force` |
| `config recover --scope project --target <root>` | C3; recuperación explícita del journal project | Abre sólo el lock existente; preserva evidencia ante divergencia |
| `status --scope global [--json]` | C7; metadata del manifest OpenCode global | Read-only; no certifica hashes ni runtime |
| `config apply --scope global [--harness opencode] --dry-run [--json]` | C7; preview OpenCode global | Sólo preview; no lock/journal ni escrituras |
| `config apply --scope global [--harness opencode] --execute [--json]` | C8 (#122); actualización de OpenCode global ya administrado | Lock estable, revalidación, journal global schema 2 y manifest al final |
| `config recover --scope global [--harness opencode]` | C8 (#122); recovery del journal OpenCode global | Abre sólo el lock existente; preserva evidencia ante estado ajeno |
| `install [--dry-run\|--execute] [--json]` | Instalación pública fija a global OpenCode | Sin scope/harness/target/version; Windows + PowerShell 7 |
| `update` | Actualización pública fija a global OpenCode | Sin alias `upgrade` ni selectores; Windows + PowerShell 7 |
| `uninstall [--dry-run] [--json]` | Retiro público fijo a global OpenCode | Sólo recursos intactos manifest-owned; Windows + PowerShell 7 |

### Instalación pública y contratos de formato vigentes

Install/update/uninstall públicos siempre seleccionan global OpenCode. No
aceptan `--scope`, `--harness`, `--target` o una versión explícita; `install`
puede usar `--dry-run` o `--execute`, `update` ejecuta la actualización y
`uninstall` puede ofrecer preview. `upgrade` ya no es un alias de `update`.
Las entradas de release eligen una release estable inmutable y validan la
identidad entre launcher, instalador y archivo; no hay fallback a ramas
mutables, versiones previas ni formatos alternativos. Operaciones nativas de
instalación siguen cualificadas sólo en Windows con PowerShell 7.

La configuración de proyecto/global no instala ni descarga recursos faltantes.
Project apply requiere un target absoluto que sea exactamente un worktree Git
existente y un manifest OpenCode actual; global descubre la raíz OpenCode y
rechaza `--target`. Preview es read-only. `--execute` actualiza sólo recursos
ya administrados con hashes válidos, bajo el lock estable, revalidación y
journal; recovery es una orden separada que preserva evidencia ante conflictos.
Doctor es read-only y reutiliza VerifyOnly donde la plataforma lo admite.

Los manifests actuales usan `schema_version=1`. Project requiere
`scope=project`, `installed_harnesses=["opencode"]`, `installed_version` y
`installed_from_commit` explícitos y no vacíos, y el inventario/hash actual de
15 rutas. Global requiere `scope=global`, sólo OpenCode,
`installed_version=local` o un release tag, `installed_from_commit` no vacío y
`default_agent_receipt` válido. Si la config global segura ya pertenece al
usuario, se administran 13 recursos y la config queda unowned con el receipt
del campo; si Olympus crea esa config, se administran 14. Ambas formas son
actuales. El guard de permisos requiere una
lista V2 válida con `external_directory * ASK` o `DENY` efectivo; no se parchea
la config del usuario para eludirla.

Los overrides usan schema 1 y un mapa `overrides`; archivo ausente significa
vacío y la precedencia es project > global > Core. Metadatos opcionales de
provenance/detección son opacos y nunca prueban ownership. No se rellenan
defaults ausentes ni se adopta un manifest antiguo. Formato incompleto o no
soportado se bloquea sin conversión ni eliminación; si hace falta retirar una
instalación anterior, usa su release correspondiente.

Source-edit journal B y project apply usan schema 1; el journal privado global
usa schema 2. Se mantienen los locks estables, la identidad/hash validation,
rollback acotado y protección de conflictos descritos en
[data-model.md](../data-model.md). Ningún preview escribe recursos de usuario;
ninguna operación afirma atomicidad multiarquivo frente a writers externos.

Las entradas de documentación detalladas para comandos públicos están en
[Installation](../../../docs/INSTALLATION.md); los comandos históricos C5 de
instalación project/Codex están reemplazados por esta frontera y no se deben
usar con releases actuales.

### Asignaciones instaladas en preview — Slice C6

- Tras validar inventario, ownership y hashes sin conflictos, `config apply --dry-run` agrega `data.assignments` en JSON y el mismo objeto serializado en salida humana. Las propuestas OpenCode provienen de `model_assignments`/renderer canónico. Para cada recurso instalado actual, sólo se extraen campos soportados de los bytes ya leídos en memoria y cuya SHA-256 coincide con el manifest; no se vuelve a leer el destino para este informe.
- `assignments.evidence=managed_hash_verified_bytes` indica únicamente bytes managed con hash coincidente, no configuración runtime efectiva, aceptación del proveedor ni disponibilidad remota. La familia instalada siempre es `unknown`: el manifest no contiene procedencia fiable para reconstruirla, aunque un ID coincida con Core.
- Las filas distinguen `selected` y `not_installed`; OpenCode muestra valores actuales y propuesta canónica. Reporta el modelo del agente Kael y el modelo de `opencode.jsonc` por separado.
- OpenCode acepta sólo la estructura de frontmatter generada con un campo `model` double-quoted sin escapes; todos los escalares bare, incluidos booleanos, nulls, números y palabras, quedan `unsupported` sin interpretación YAML. Un valor quoted como `"true"` sigue siendo una cadena de modelo. En el root JSONC se admite únicamente el envelope renderer-generado con su único modelo string cambiado. Estructuras, comillas/escapes no soportados, valores faltantes, anidados o de tipo incorrecto quedan `unsupported` sin valores actuales inferidos. Esta incertidumbre sólo anota el preview: no cambia disponibilidad, resultado, plan ni exits de C1/C3.
- Si falla la validación de manifest/inventario/hash, `assignments` queda explícitamente `unknown` con evidencia `not_verified`; no se exponen valores aparentemente verificados de una lectura bloqueada. C4 sigue informando `assignments: unknown` y no analiza recursos.

### Alcance global — Slice C7/C8

- `status --scope global` informa sólo metadata del manifest OpenCode, sin `VerifyOnly`, runtime ni introspección de proveedores. Rechaza rutas relativas, enlaces/reparse en ancestros y raíces inseguras; `--target` no está permitido.
- `doctor --scope global` y el preview validan el manifest OpenCode schema 1, inventario esperado, archivos regulares y hashes. En Windows, doctor llama a `global-install.ps1 -VerifyOnly` con raíz anclada, `USERPROFILE` temporal y PowerShell 7; otras plataformas informan `verification_unavailable`, no éxito simulado.
- Global preview informa bytes/hashes y propuestas de los once roles, sin lock/journal/escrituras. `apply_available=true` sólo señala la vía separada `--execute`; las asignaciones instaladas siguen `unknown` si no pueden acreditarse desde bytes manifest-owned con hash verificado.
- Global apply sólo actualiza una instalación OpenCode existente y validada. Preserva bytes de usuario no administrados y no adopta una configuración o manifest externos. Un guard inseguro, conflicto de precedencia, drift, manifest inválido o journal previo bloquea antes de escribir.
- Apply global comparte el `.olympus-cli-edit.lock`, revalida inventario/hash bajo lock y reemplaza el manifest al final. El journal privado `.olympus-cli-config-apply` es schema 2; el journal project conserva schema 1. PREPARED revierte sólo desde estados old/new acreditados; COMMITTED limpia evidencia verificada. `config recover --scope global --harness opencode` abre sólo el lock existente y preserva journal/bytes ante una tercera versión, identidad dudosa o evidencia inválida. No se promete atomicidad multiarquivo visible ni protección frente a writers externos no cooperantes.
- La ausencia de instalación es informativa; un manifest inválido, incompleto o de formato no soportado falla cerrado, sin defaults, adopción, conversión o eliminación automáticas. Formatos globales actuales son schema 1 con receipt válido y 13/14 recursos según ownership de la configuración, no un inventario histórico de 13 sin guard.
- Ninguna validación prueba el modelo efectivo del runtime, proveedor/autenticación ni overrides locales. La evidencia de implementación de esta feature no cualifica perfiles globales reales, Linux/macOS o runtime OpenCode.

### Identificadores — contrato inicial definitivo de Slice B

Los IDs existentes OpenCode utilizados por el candidato y los IDs propuestos deben coincidir **por completo** con `[A-Za-z0-9][A-Za-z0-9._:/-]*`. No trim, normalización, matching parcial ni ancla que acepte un newline final. Primer carácter ASCII alfanumérico; los restantes sólo ASCII alfanuméricos, punto, underscore, dos puntos, slash o guion. Se aceptan los actuales conformes, incluidos `openai/gpt-6.1-sol` y `openai/gpt-6-luna`.

Vacío, comillas, backslashes, espacios, controles, saltos, `#`, braces y cualquier carácter fuera del alfabeto se rechazan con exit 2 **antes de cualquier staging o escritura, incluida creación del lock**. Un ID existente no conforme rechaza la operación B con el mismo exit 2, sin repararlo; no modifica el comportamiento read-only de A. El renderer existente no cambia. Sintaxis válida no acredita disponibilidad, soporte live ni autenticación; no consultar proveedores. Es una restricción inicial de B, no una limitación universal de OpenCode.

Familias/roles de fuente. Esfuerzo inicial extraído del conjunto de esfuerzos presente en el documento canónico; no registry de esfuerzos/proveedor adicional. Kael es el único orquestador y la CLI no agrega roles.

### Exclusión y recovery — contrato de operador

- Commit y recovery B usan exclusión nativa no bloqueante sobre `.olympus-cli-edit.lock` en el origen canónico: `msvcrt.locking` Windows / `fcntl.flock` Linux. Un dueño activo devuelve blocked/exit 3 antes de inspeccionar su batch. El archivo de lock es estable y permanece vacío después del cleanup; su existencia no significa pendiente ni propietario vivo. Nunca eliminarlo/reemplazarlo/recrearlo para desbloquear.
- Preview no crea/adquiere lock ni scratch; no-op de edición válida y sin scratch pendiente tampoco los crea. Sólo la primera edición real aceptada puede crear el archivo estable. Recovery sólo abre el existente: si falta, es inseguro o su identidad no se acredita, blocked/exit 3 sin examinar registro/backups/targets. Con lock existente adquirido y sin scratch, no_changes/exit 0 sin escrituras.
- Scratch pendiente bloquea B en preflight incluso con lock libre o ausente, sin crear/recrear lock ni staging. `config recover` es orden humana separada; adquiere exclusión antes de leer el batch, valida identidad/registro/read-set/hashes/backups y mantiene el lock hasta rollback/cleanup o reporte de bloqueo. PID, timestamp y directorio no acreditan terminación; no auto-cleanup por antigüedad.
- PREPARING sólo se descarta si todos los targets siguen old; PREPARED deja old y restaura sólo new mediante copia staged de backup verificado (all-new también revierte); COMMITTED sólo limpia tras verificar todo new. Tercer estado, modo divergente, entrada externa modificada, backup necesario inválido o identidad distinta bloquean sin overwrite; conservar evidencia. Recovery interrumpido puede repetirse sin consumir respaldos. Protocolo completo: [data-model.md](../data-model.md).
- C3 project usa el mismo `.olympus-cli-edit.lock` del target que los escritores Python/PowerShell C2.3. El journal privado `.olympus-cli-config-apply` mantiene evidencia old/new; manifiesto se reemplaza al final. `--dry-run` no crea lock/scratch. La recuperación project exige `config recover --scope project --target ...`; no interpreta el journal B del source como estado del target. Recovery vuelve a validar con el renderer del checkout fuente original; conserva ese renderer sin modificaciones mientras el journal esté pendiente y usa ese mismo checkout mediante `--source`.
- C3 actualiza únicamente recursos OpenCode ya administrados y conserva otros bytes no seleccionados. Una fuente local se registra explícitamente como `installed_version=local` y con su valor `installed_from_commit`; `unknown` no acredita una revisión real. No se instala/adopta recurso ausente ni se migra un manifest.
- Coherencia y ownership acreditados permiten éxito; rollback confirmado de un cambio fallido sigue siendo fallo operacional/exit 1, no éxito de edición. Conflicto confirmado produce blocked/exit 3; efectos parciales o resultado no acreditado producen unconfirmed/exit 4 con recursos/estado concretos. Ningún resultado parcial se presenta como aplicado.
- Se excluyen protección absoluta contra procesos externos no cooperantes, atomicidad multiarquivo visible a lectores y durabilidad absoluta ante pérdida de energía. No hay sobrescritura automática de modificaciones externas; el hash previo a os.replace no es compare-and-swap. Estas exclusiones no habilitan ignorar conflictos detectados.

El Linux CI inicial del Draft PR #110 pasó en [run 42392613719](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/42392613719), pero ejecutó 13 pruebas con el filtro anterior `slice_c2_3` y no seleccionó la regresión C3. Con el filtro actualizado, el job Linux [run 42401262655](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/42401262655/job/128489298237) ejecutó las 14 pruebas sin skips y pasó, incluida `test_slice_c3_project_apply_uses_existing_target_writer_lock`.

T019 Windows y T020 Linux acreditaron la selección integrada y el protocolo lock/recovery en ambas plataformas antes de aceptar B. Windows omitió tres fixtures symlink por `WinError 1314`; Linux pasó los tres. Fuente T020: commit `539976812d14289696dbd3824f1ae706ac2f1947`, run [38857503366](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366), job [116832156025](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366/job/116832156025). Mantener un único scratch y registro, sin servicios ni segundo mapping; la evidencia no amplía garantías de FR-012 ni cualifica macOS.

## Salida y códigos

Salida humana concisa con origen/contexto, afectados, ID OpenCode y valores old/new antes de mutar. Errores nombran recurso/causa y corrección disponible; no emitir credenciales o logs nativos completos por defecto.

JSON de comando permitido es un documento único en stdout; diagnósticos de proceso/presentación van a stderr. Envoltorio `schema_version=1`, `operation`, `result`, `context`, `data`, `issues`. Los datos usan los mismos objetos del formato humano, sin segundo resolver. `result` puede ser `ok`, `no_changes`, `absent`, `preview` (C5: dry-run nativo completado, sin ejecutar instalación/retiro), `failed`, `blocked`, `unconfirmed`.

- Listado: `data.roles` con `role`, `identity`, `family`, `effort`, `models.opencode` y su representación OpenCode.
- Preview: affected roles, old/new intención/resolución, recursos cambiantes relativos y bloqueos; no tabla de mappings persistente.
- Estado/doctor: installed harnesses, scope, versión registrada, integridad y soporte/evidencia disponible. Cuando no puede conocerse una asignación instalada segura, informar unknown, no copiar la asignación del source como si estuviese aplicada.
- Preview C1: delta de archivos renderizados sólo después de validar raíz, manifiesto, inventario y hashes; conflictos bloquean el plan. El preview sigue read-only (`preview_only=true`); `apply_available=true` sólo indica que existe la vía separada `--execute`, que vuelve a previsualizar y revalida bajo lock. Nunca representa una escritura ya ejecutada.

| Exit | Significado |
|---|---|
| 0 | Consulta válida, éxito confirmado o no-op; ausencia informativa en status |
| 1 | Check/verificación fallida o fallo operacional confirmado |
| 2 | Argumentos/contexto/valores inválidos |
| 3 | Capacidad/entorno/contrato bloqueado, incluido apply C |
| 4 | Resultado parcial/sin confirmar que requiere reconciliación |

El código nativo y su salida relevante se conservan en datos del resultado; se traducen a estas categorías sin convertir error en éxito. Timeout de mutación nativa produce unconfirmed, no retry. No prometen atomicidad de install/uninstall oficiales sólo por routing.

## Protección de fronteras

Edición de source no acepta target instalado ni lo modifica. Apply no edita
models, instala recursos ausentes o migra manifests implícitamente;
`--execute` sólo reemplaza recursos OpenCode renderer-managed que constan en el
manifest y fueron seleccionados. No cambia permisos de acceso, autenticación ni
configuración de proveedores. Install oficial usa identidad immutable y motores
existentes. Soporte por operación/plataforma siempre explícito; macOS NOT
VERIFIED.
