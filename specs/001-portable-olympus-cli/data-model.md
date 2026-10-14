# Data model: estado temporal de edición de fuentes

**Estado**: diseño B condicionado a validación, no implementado ni requerido por A. Recuperación de una edición de modelos, sin API transaccional genérica. No redefine modelos, identidades o manifests; sus schemas siguen en las fuentes de [spec.md](spec.md).

## Datos en memoria

- **Contexto**: origen confiable resuelto, operación, harnesses representados, scope/destino cuando aplica, versión y soporte observable.
- **Intención candidata**: copia transitoria del diccionario de modelos cargado desde la fuente canónica; sólo paths solicitados pueden diferir. Nunca persistir como `models.json` ni config de runtime.
- **Preview**: roles afectados, familia/esfuerzo/modelos anteriores y propuestos, ambos adaptadores y representaciones reales. Para Kael Codex, raíz; Aegis Codex, ausencia.
- **Batch fijo**: path relativo, hash/mode previos, bytes previos/candidatos y hash candidato. Sólo `models.toml` y outputs cambiados que el renderer devuelve. Todos deben existir y estar coherentes antes de la operación; no crear/eliminar recursos, aceptar paths arbitrarios ni incluir destinos instalados. Recursos iguales quedan fuera.
- **Read-set**: hashes de fuentes renderer leídas y outputs actuales; cambiar una entrada invalida el candidato, aunque esa entrada no fuese write target.

## Único registro temporal de B

Directorio propuesto `.olympus-cli-edit/` en origen; no forma parte del Core ni de instalación destino. Se crea sólo durante mutación B aceptada. Un directorio exclusivo evita dos writers CLI; su presencia bloquea otra edición hasta reconciliar. Una estructura concreta leída por funciones privadas, sin clase Journal/Transaction, backends, callbacks, log append, historial o migrador de schemas. Los dos estados sólo distinguen intento preparado y resultado confirmado para cleanup; no son un workflow extensible.

| Campo | Significado / validación |
|---|---|
| `schema_version` | 1; rechazar otro schema sin escribir |
| `operation_id` | Identificador único del batch; no reutilizar un resultado perdido |
| `source_root` | Origen resuelto original; recovery rechaza contexto distinto |
| `state` | PREPARED o COMMITTED; ausencia/registro incompleto no permite adivinar efectos |
| `read_set` | Paths relativos y SHA-256 del snapshot; validar contención antes de leer |
| `files` | Sólo recursos existentes del conjunto fijo autorizado, con old/new SHA-256, mode y backup/staged dentro del scratch |

Los originales y staged bytes se guardan como archivos de respaldo acotados, no dentro de un segundo mapping. Verificar su hash antes de rollback/commit. El registro se escribe por staging + replace antes de sustituir recursos; no necesita log append ni una tabla de progreso por cada rename. Tras muerte del proceso se determina progreso por hashes del filesystem.

El scratch nunca contiene referencias absolutas a recursos arbitrarios de destino. Rechazar paths fuera del origen, enlaces o recursos no regulares y cualquier backup cuyo digest no sea el esperado. No recuperar con un registro editado/conflictivo ni borrar lock de una operación posiblemente viva.

## Transiciones observables

| Estado observado | Lectura/preview | Mutación/recovery explícita |
|---|---|---|
| Sin operación | Consulta normal sin escrituras | Preflight; no-op no crea scratch |
| Scratch incompleto antes de PREPARED | Informar operación sin confirmar; no reparar | Sólo limpiar si puede demostrarse que no hubo sustitución; en otro caso BLOCKED |
| PREPARED con todos hashes old | Informar preparada/pendiente | Rollback no cambia recursos; limpieza propia validada |
| PREPARED con mezcla old/new | Informar parcial; no afirmar coherencia | Dejar old, restaurar new desde backup; confirmar conjunto previo y limpiar |
| PREPARED con todos new | Informar resultado sin confirmar | Política mínima: rollback, no asumir commit por coincidencia parcial de ejecución |
| COMMITTED con todos new | Informar cambio confirmado con cleanup pendiente | Validar estado y limpiar scratch, sin nueva mutación de modelos |
| Cualquier tercer hash/conflicto | Informar BLOCKED con recursos concretos | No sobrescribirlo; conservar respaldos y describir conflicto |

La restauración se hace únicamente cuando el recurso actual pertenece aún al estado new de este batch; no se restaura sobre contenido externo. Un proceso terminal debe acreditarse antes de recovery; no se infiere sólo por PID/edad. No existe retry automático del cambio original.

## Instalaciones

Se leen los manifests existentes sólo para contexto/diagnóstico según el motor soportado. El posible metadato de personalización de C **no tiene schema adoptado**: queda bloqueado hasta resolver compatibilidad, procedencia y verificación en ese motor. No usar el registro B como ownership de una instalación ni persistir assignments paralelas en manifests.

## Límite

Este registro permite recovery de recursos propios y conflictos detectables; no hace atómica una vista multiarquivo ni bloquea editores externos no cooperantes. Condiciones operativas y gate de esa garantía: [plan.md](plan.md).

Conservar únicamente este mínimo por necesidad de recuperación tras terminación abrupta. Si falla su validación, B sigue condicionada; no construir un engine instalado o un servicio para salvar el gate. A puede consultar sin importar el editor ni crear/modificar este estado.
