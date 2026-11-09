# Contrato propuesto de CLI

**Estado de esta rama**: A **SHIPPED**; B **ACEPTADA** (T019 Windows + T020 Linux, G2 PASS); C1 preview read-only, C3 apply explícito project, C4 doctor project, C5 install/uninstall routing y C6 asignaciones en preview project implementados. C6 tiene pruebas focalizadas locales, no cualificación hosted; la cualificación focal de C5 queda registrada por separado; macOS **NOT VERIFIED**.

## Entrada, contexto y soporte

- Inicial: `python -B -m olympus` desde el checkout confiable. Final: `olympus` mediante launcher anclado a ese checkout en PATH; Python >=3.11 explícito y sin escribir caches.
- Linux A: launcher y contrato entregados con PR #69; la observación del run anterior que usó `chmod` y su pendiente de entonces se conservan como historia en research.md. Esta reconciliación no cambia A. Linux B está acreditada por T020; macOS NOT VERIFIED.
- `--source <absolute-path>` es opción global anterior al subcomando; default de launcher es su checkout. No buscar automáticamente otro Core en el proyecto destino. Error si origen no existe, no contiene fuentes/renderer o es ambiguo.
- Proyecto: `--scope project --target <absolute-worktree-root>`. Global: `--scope global`, usando resolución segura del motor, sin interpretar un target de proyecto como destino global. Para contexto de override global, identificarlo explícitamente sin modificarlo.
- `--harness opencode|codex|all` selecciona representación/operación cuando aplique. Listado incluye ambos; check default all; mutaciones instaladas no usan un default silencioso.
- Sintaxis inválida/opciones incompatibles se rechazan antes de iniciar un motor nativo. No `--force`, bypass de drift, proveedor nuevo ni instalación automática.
- Consultas/preview no crean tempfiles, locks, backups, caches ni directorios, salvo las excepciones nativas explícitas. Excepción C4: PowerShell corre con `USERPROFILE` temporal para contener su cache de inicio; se elimina al salir y no persiste en source/target/perfil real. Excepción C5: el probe usa un perfil temporal y la adquisición oficial/ejecución nativa puede usar temp/cache, sin escribir recursos de instalación en preview. Un scratch previo se informa, no se repara. También propagar `PYTHONDONTWRITEBYTECODE=1` a hijos.

## Superficie de comandos

| Comando propuesto | Slice / semántica | Escritura / condición |
|---|---|---|
| `--version`, `--help` | A; versión de herramienta y ayuda | Ninguna |
| `models list [--json]` | A; once roles, familia/esfuerzo y IDs de ambos adaptadores | Ninguna |
| `status [--scope ... --target ... --harness ...] [--json]` | A; origen y estado local/manifest disponible, no Verify profundo propio | Ninguna; sin descubrir destinos arbitrarios |
| `config check [--harness ...] [--json]` | A; validación de fuentes y drift renderer | Ninguna; comparar expected en memoria |
| `models set-family <existing> --opencode <id> --codex <id> [--dry-run [--json]]` | B; editar los dos IDs de esa familia | Preview sin escribir; ejecución una orden explícita |
| `agents set-model <role> [--family <existing>] [--effort <canonical-value>] [--dry-run [--json]]` | B; al menos un valor solicitado | Otros roles inalterados; preview de resolución completa |
| `config recover` | B; rollback/cleanup de batch propio pendiente | Adquirir lock nativo estable existente antes de inspección del batch; sin dueño activo, identidad/estado/hashes/backups reconciliados; sin retry original |
| `doctor --scope project --target <absolute-worktree-root> --harness opencode|codex|all [--json]` | C4; diagnóstico read-only de instalación project existente | PowerShell 7 en Windows y fuente local coherente para VerifyOnly; otras plataformas/verificador no disponible quedan bloqueadas; no runtime discovery |
| `config apply --scope project --target <root> --harness ... --dry-run [--json]` | C1; preview read-only de recursos de una instalación existente | Exige manifiesto válido y hashes sin drift; no instala harnesses ausentes ni llama bootstrap/install |
| `config apply --scope project --target <root> --harness ... --execute` | C3; actualización explícita de recursos ya administrados | Exclusión estable del target, revalidación bajo lock y journal PREPARING/PREPARED/COMMITTED; sólo escritura humana, nunca `--force` |
| `config recover --scope project --target <root>` | C3; recuperación explícita del journal de apply project | Abre sólo el lock existente; PREPARED revierte estados new verificados y COMMITTED limpia evidencia; divergencias preservan journal y bloquean |
| `install --scope project|global [--target <root>] --harness ... --version <exact-tag> (--dry-run|--execute) [--json]` | C5; delegación de release oficial publicado e inmutable | Windows + PowerShell 7; el target sólo aplica a project; sin source/archive override |
| `uninstall --scope project|global [--target <root>] --harness ... (--dry-run|--execute) [--json]` | C5; delegación a los uninstallers existentes | Windows + PowerShell 7; project dry-run bloqueado, global dry-run soportado |

### Routing de instalación y retiro — Slice C5

- `install --version` es distinto de la opción raíz `olympus --version`: requiere un tag Olympus exacto según el patrón release existente (`vMAJOR.MINOR.PATCH` con sufijo sintáctico opcional `alpha|beta|rc.N`); las banderas del release deben seguir calificándolo como estable (`prerelease=false`). Sólo se adquieren releases oficiales. El launcher solicita `releases/tags/<tag>` y exige tag devuelto idéntico, `immutable=true`, `draft=false`, `prerelease=false`, timestamp publicado válido e identidad coincidente del installer/archive. Omitir `Version` en los callers históricos conserva la selección `releases/latest`; la CLI siempre fija el tag solicitado. No `--SourceRoot`, `--SourceArchive` ni `--force` desde esta CLI.
- Project requiere `--target` absoluto, existente y exactamente raíz de un Git worktree, validada en read-only antes de PowerShell. Global rechaza `--target`: sus raíces sólo las descubre el motor oficial. El cwd heredado sigue siendo contexto de sólo lectura para comprobaciones de override del motor; no es el destino global ni se suplanta `USERPROFILE`.
- Instalar llama `scripts/launch-latest.ps1`, que conserva adquisición y validación del installer oficial; `--dry-run` se reenvía a `install.ps1`. Desinstalar project llama el `scripts/project-uninstall.ps1` local; global llama `scripts/global-install.ps1 -Uninstall`, sin descarga de release. `--dry-run` de project se bloquea con exit 3 antes de PowerShell porque ese motor no ofrece preview; global usa su `-DryRun`. `--harness all` global se ejecuta secuencialmente, no es atómico.
- Sólo Windows con PowerShell 7. Preflight de `pwsh` está acotado a 10 s y el motor a 300 s; los argumentos se pasan como argv, sin `shell` ni script interpolado. Los previews no escriben recursos target/global, pero la adquisición oficial, PowerShell y sus caches pueden usar temp/cache. No se cambia permisos de source/target ni se usa perfil real para la prueba de versión.
- JSON es un único documento stdout e incluye `native_exit_code`, `native_stdout` y `native_stderr`; la salida del motor no se mezcla fuera del documento. Dry-run nativo exitoso da `result=preview`, no `installed/removed`. Fallo nativo de una mutación, timeout o interrupción da exit 4/unconfirmed cuando no puede probarse ausencia de efectos; conserva código/salida nativa y nunca reintenta. Un error de preview read-only da exit 1. No se promete atomicidad de los motores oficiales.

`--json` de edición sólo se ofrece con `--dry-run` inicialmente; ejecución humana muestra preview antes de escribir y luego resumen. Esto evita mezclar varios documentos JSON en stdout sin introducir un protocolo de eventos. No se exige JSON de edición real por FR-004. Diagnóstico/listado/preview comparten datos equivalentes entre formatos.

`doctor` C4 sólo admite scope project y reutiliza bootstrap `-Target ... -Harness ... -SourceVersion ... -VerifyOnly` desde fuente local coherente, sin public wrapper que descargue archives. Manifest ausente se informa como ausencia; ownership/inventario inválido bloquea; drift de recursos administrados falla. La verificación se cualifica únicamente con PowerShell 7 en Windows; sin plataforma/verificador apto se informa `verification_unavailable` sin afirmar integridad. PowerShell recibe un `USERPROFILE` temporal para contener su cache de inicio, que se elimina al terminar. No suplantar la verificación con un hash checker Python ni ejecutar runtime discovery. Las asignaciones se informan `unknown`: el manifest no las registra y C4 no analiza recursos generados para inferirlas.

### Asignaciones instaladas en preview — Slice C6

- Tras validar inventario, ownership y hashes sin conflictos, `config apply --dry-run` agrega `data.assignments` en JSON y el mismo objeto serializado en salida humana. Las propuestas de harness seleccionado provienen de `model_assignments`/renderer canónico. Para cada recurso instalado actual, sólo se extraen campos soportados de los bytes ya leídos en memoria y cuya SHA-256 coincide con el manifest; no se vuelve a leer el destino para este informe.
- `assignments.evidence=managed_hash_verified_bytes` indica únicamente bytes managed con hash coincidente, no configuración runtime efectiva, aceptación del proveedor ni disponibilidad remota. La familia instalada siempre es `unknown`: el manifest no contiene procedencia fiable para reconstruirla, aunque un ID coincida con Core.
- Las filas distinguen `selected`, `preserved` y `not_installed`. Harness seleccionado muestra `current` y propuesta canónica; el no seleccionado conserva `current` y no presenta propuesta. OpenCode reporta el modelo del agente Kael y el modelo de `opencode.jsonc` de forma independiente. Codex informa a Kael sólo en `roots.codex`, nunca como agente especialista.
- OpenCode acepta sólo la estructura de frontmatter generada con un campo `model` double-quoted sin escapes; todos los escalares bare, incluidos booleanos, nulls, números y palabras, quedan `unsupported` sin interpretación YAML. Un valor quoted como `"true"` sigue siendo una cadena de modelo. En el root JSONC se admite únicamente el envelope renderer-generado con su único modelo string cambiado. Codex usa `tomllib` y exige `model`/`model_reasoning_effort` top-level de tipo string en el archivo de rol/root conocido. Estructuras, comillas/escapes no soportados, TOML malformado/duplicado, valores faltantes, anidados o de tipo incorrecto quedan `unsupported` sin valores actuales inferidos. Esta incertidumbre sólo anota el preview: no cambia disponibilidad, resultado, plan ni exits de C1/C3.
- Si falla la validación de manifest/inventario/hash, `assignments` queda explícitamente `unknown` con evidencia `not_verified`; no se exponen valores aparentemente verificados de una lectura bloqueada. C4 sigue informando `assignments: unknown` y no analiza recursos.

### Identificadores — contrato inicial definitivo de Slice B

Todos los IDs existentes utilizados por el candidato y los IDs propuestos deben coincidir **por completo** con `[A-Za-z0-9][A-Za-z0-9._:/-]*`. No trim, normalización, matching parcial ni ancla que acepte un newline final. Primer carácter ASCII alfanumérico; los restantes sólo ASCII alfanuméricos, punto, underscore, dos puntos, slash o guion. Se aceptan los actuales conformes, incluidos `openai/gpt-6.1-sol` y `gpt-6-luna`.

Vacío, comillas, backslashes, espacios, controles, saltos, `#`, braces y cualquier carácter fuera del alfabeto se rechazan con exit 2 **antes de cualquier staging o escritura, incluida creación del lock**. Un ID existente no conforme rechaza la operación B con el mismo exit 2, sin repararlo; no modifica el comportamiento read-only de A. El renderer existente no cambia. Sintaxis válida no acredita disponibilidad, soporte live ni autenticación; no consultar proveedores. Es una restricción inicial de B, no una limitación universal de OpenCode o Codex.

Familias/roles de fuente. Esfuerzo inicial extraído del conjunto de esfuerzos presente en el documento canónico; no registry de esfuerzos/proveedor adicional. Kael es el único orquestador y la CLI no agrega roles.

### Exclusión y recovery — contrato de operador

- Commit y recovery B usan exclusión nativa no bloqueante sobre `.olympus-cli-edit.lock` en el origen canónico: `msvcrt.locking` Windows / `fcntl.flock` Linux. Un dueño activo devuelve blocked/exit 3 antes de inspeccionar su batch. El archivo de lock es estable y permanece vacío después del cleanup; su existencia no significa pendiente ni propietario vivo. Nunca eliminarlo/reemplazarlo/recrearlo para desbloquear.
- Preview no crea/adquiere lock ni scratch; no-op de edición válida y sin scratch pendiente tampoco los crea. Sólo la primera edición real aceptada puede crear el archivo estable. Recovery sólo abre el existente: si falta, es inseguro o su identidad no se acredita, blocked/exit 3 sin examinar registro/backups/targets. Con lock existente adquirido y sin scratch, no_changes/exit 0 sin escrituras.
- Scratch pendiente bloquea B en preflight incluso con lock libre o ausente, sin crear/recrear lock ni staging. `config recover` es orden humana separada; adquiere exclusión antes de leer el batch, valida identidad/registro/read-set/hashes/backups y mantiene el lock hasta rollback/cleanup o reporte de bloqueo. PID, timestamp y directorio no acreditan terminación; no auto-cleanup por antigüedad.
- PREPARING sólo se descarta si todos los targets siguen old; PREPARED deja old y restaura sólo new mediante copia staged de backup verificado (all-new también revierte); COMMITTED sólo limpia tras verificar todo new. Tercer estado, modo divergente, entrada externa modificada, backup necesario inválido o identidad distinta bloquean sin overwrite; conservar evidencia. Recovery interrumpido puede repetirse sin consumir respaldos. Protocolo completo: [data-model.md](../data-model.md).
- C3 project usa el mismo `.olympus-cli-edit.lock` del target que los escritores Python/PowerShell C2.3. El journal privado `.olympus-cli-config-apply` mantiene evidencia old/new; manifiesto se reemplaza al final. `--dry-run` no crea lock/scratch. La recuperación project exige `config recover --scope project --target ...`; no interpreta el journal B del source como estado del target. Recovery vuelve a validar con el renderer del checkout fuente original; conserva ese renderer sin modificaciones mientras el journal esté pendiente y usa ese mismo checkout mediante `--source`.
- C3 cambia sólo hashes de harnesses seleccionados y conserva los no seleccionados; conserva provenance opaca sólo para harnesses no seleccionados. La fuente local se registra como `installed_version=local` y `installed_from_commit=unknown`, nunca como release oficial inmutable. No se instala/adopta harness ausente ni se migran manifests.
- Coherencia y ownership acreditados permiten éxito; rollback confirmado de un cambio fallido sigue siendo fallo operacional/exit 1, no éxito de edición. Conflicto confirmado produce blocked/exit 3; efectos parciales o resultado no acreditado producen unconfirmed/exit 4 con recursos/estado concretos. Ningún resultado parcial se presenta como aplicado.
- Se excluyen protección absoluta contra procesos externos no cooperantes, atomicidad multiarquivo visible a lectores y durabilidad absoluta ante pérdida de energía. No hay sobrescritura automática de modificaciones externas; el hash previo a os.replace no es compare-and-swap. Estas exclusiones no habilitan ignorar conflictos detectados.

El Linux CI inicial del Draft PR #110 pasó en [run 42392613719](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/42392613719), pero ejecutó 13 pruebas con el filtro anterior `slice_c2_3` y no seleccionó la regresión C3. Con el filtro actualizado, el job Linux [run 42401262655](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/42401262655/job/128489298237) ejecutó las 14 pruebas sin skips y pasó, incluida `test_slice_c3_project_apply_uses_existing_target_writer_lock`.

T019 Windows y T020 Linux acreditaron la selección integrada y el protocolo lock/recovery en ambas plataformas antes de aceptar B. Windows omitió tres fixtures symlink por `WinError 1314`; Linux pasó los tres. Fuente T020: commit `539976812d14289696dbd3824f1ae706ac2f1947`, run [38857503366](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366), job [116832156025](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366/job/116832156025). Mantener un único scratch y registro, sin servicios ni segundo mapping; la evidencia no amplía garantías de FR-012 ni cualifica macOS.

## Salida y códigos

Salida humana concisa con origen/contexto, afectados, ambos IDs y valores old/new antes de mutar. Errores nombran recurso/causa y corrección disponible; no emitir credenciales o logs nativos completos por defecto.

JSON de comando permitido es un documento único en stdout; diagnósticos de proceso/presentación van a stderr. Envoltorio `schema_version=1`, `operation`, `result`, `context`, `data`, `issues`. Los datos usan los mismos objetos del formato humano, sin segundo resolver. `result` puede ser `ok`, `no_changes`, `absent`, `preview` (C5: dry-run nativo completado, sin ejecutar instalación/retiro), `failed`, `blocked`, `unconfirmed`.

- Listado: `data.roles` con `role`, `identity`, `family`, `effort`, `models.opencode`, `models.codex`, y representación de cada harness (`agent`, `root`, `absent`).
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

Edición de source no acepta target instalado ni lo modifica. Apply no edita models, instala harness ausente o migra manifests implícitamente; `--execute` sólo reemplaza recursos renderer-managed que constan en el manifest y fueron seleccionados. No cambia permisos de acceso, autenticación ni configuración de proveedores. Install oficial usa identidad immutable y motores existentes. Ningún comando cierra gaps de Codex. Soporte por operación/plataforma siempre explícito; macOS NOT VERIFIED.
