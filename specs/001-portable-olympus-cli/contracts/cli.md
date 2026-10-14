# Contrato propuesto de CLI

**Estado**: diseño, ninguna orden nueva existe todavía. [Plan](../plan.md) separa gates: A READY_FOR_IMPLEMENTATION tras R49 PASS, B condicionada y C BLOCKED; global BLOCKED para entrega completa. [R49](../evidence/r49-20261014-c30a19d/report.md) sólo acredita distribución/instalación de archivos Codex proyecto, no nuevos comandos ni runtime. T002–T009 no se ejecutaron. A no importa editor/recovery/native_ops ni ejecuta B/C; este contrato no habilita apply ni cambia spec.

## Entrada, contexto y soporte

- Inicial: `python -B -m olympus` desde el checkout confiable. Final: `olympus` mediante launcher anclado a ese checkout en PATH; Python >=3.11 explícito y sin escribir caches.
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
| `config recover` | B; rollback/cleanup de batch propio pendiente | Orden humana separada, con estado/ownership reconciliado; sin retry original |
| `doctor --scope ... [--target ...] --harness ... [--json]` | C; verificar mediante motor existente | Windows cualificado, fuente local apta; read-only bloqueado si no se garantiza |
| `config apply --scope ... [--target ...] --harness ... [--dry-run] [--json]` | C; futura actualización administrada | BLOCKED para personalizado con baseline; no llama install override ni escribe destino |
| `install --scope ... [--target ...] --harness ... --version <release> [--dry-run]` | C; delegación de release oficial | Windows cualificado; no instala silenciosamente sources personalizados |
| `uninstall --scope ... [--target ...] --harness ...` | C; delegación de retiro administrado | Windows cualificado, ownership/hash del motor |

`--json` de edición sólo se ofrece con `--dry-run` inicialmente; ejecución humana muestra preview antes de escribir y luego resumen. Esto evita mezclar varios documentos JSON en stdout sin introducir un protocolo de eventos. No se exige JSON de edición real por FR-004. Diagnóstico/listado/preview comparten datos equivalentes entre formatos.

`doctor` usa bootstrap `-Target ... -Harness ... -SourceVersion ... -VerifyOnly` para proyecto y global-install `-Harness ... -SourceVersion ... -VerifyOnly` para global, desde fuente local coherente, sin public wrapper que descargue archives. Si la versión/candidate/procedencia no puede verificarse, informa límite/fallo. No suplantar la verificación con un hash checker Python. Global OpenCode discovery existente se evalúa por evidencia; si escribe, doctor permanece bloqueado como read-only.

IDs son strings sin controles ni saltos y no vacíos; no asumir disponibilidad/auth. Familias/roles de fuente. Esfuerzo inicial extraído del conjunto de esfuerzos presente en el documento canónico; no registry de esfuerzos/proveedor adicional. Aegis se puede configurar en Core, pero sólo materializa OpenCode.

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
