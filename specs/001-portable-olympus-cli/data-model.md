# Data model: estado temporal de edición de fuentes

**Estado vigente (2026-10-16)**: B ACEPTADA por T019 Windows + T020 Linux, G2 PASS; A SHIPPED; C y feature completa BLOCKED; macOS NOT VERIFIED. El protocolo documentado fue validado en la selección integrada sin ampliar sus garantías cooperantes. Recuperación acotada de una edición, sin API transaccional ni schemas de modelos/manifests alternativos. Historial del diseño anterior y experimentos: [research.md](research.md) y [tasks.md](tasks.md).

## Datos en memoria

- **Contexto**: origen confiable canónico resuelto; operación e identidad de filesystem del lock. No ejecutar código de destinos instalados.
- **Intención candidata**: copia transitoria de modelos, sólo paths solicitados distintos. IDs efectivos coinciden completamente con `[A-Za-z0-9][A-Za-z0-9._:/-]*`; sin normalización ni catálogo remoto.
- **Preview**: afectados, familia/esfuerzo e IDs old/new de ambos adaptadores; Kael raíz y Aegis ausente en Codex. No crea/adquiere lock ni scratch.
- **Batch fijo**: path relativo, bytes/hashes old/new y modo previo; sólo `models.toml` y outputs existentes que realmente cambian. No altas/bajas, recursos instalados ni paths arbitrarios. No-op de edición sobre estado válido y sin scratch pendiente no crea lock/scratch.
- **Read-set**: hashes de entradas renderer, inventario relevante y outputs actuales. Un cambio observable invalida el candidato; durante recovery los write targets sólo admiten los hashes old/new registrados, mientras entradas ajenas al write-set deben coincidir con el snapshot.

## Lock nativo estable — protocolo de Slice B

El origen canónico usa exactamente `source_root/.olympus-cli-edit.lock`, fuera del único scratch `source_root/.olympus-cli-edit/`. El archivo de lock es vacío y permanente: no contiene estado, modelos, PID ni segundo registro. La presencia del archivo no significa operación pendiente o dueño activo. Después de una operación puede permanecer como único artefacto de control; las consultas nunca lo crean ni modifican y no lo confunden con drift o scratch pendiente.

1. La edición real valida petición/candidato y ausencia de scratch pendiente antes de cualquier escritura. Si hay scratch, bloquear sin crear/recrear el archivo de lock. Abre el archivo sin truncar: creación exclusiva si falta; si otro proceso ganó la creación, abre el existente y sigue el mismo protocolo. Una vez establecido, ninguna operación cooperante lo elimina, renombra, reemplaza, trunca ni recrea para liberar el lock. No se almacena dentro de un directorio que cleanup vaya a eliminar; no usar `.git` ni un path instalado.
2. Windows: descriptor binario sobre archivo regular, posición 0 y `msvcrt.locking(..., LK_NBLCK, 1)`; la región puede extender EOF del archivo vacío. Linux: `fcntl.flock(..., LOCK_EX | LOCK_NB)` sobre el descriptor. No esperar en bucle ni usar polling. Si está ocupado, BLOCKED; no inspeccionar registro/backups/targets del dueño activo.
3. Verificar contención, path regular sin symlink/reparse/hardlink e identidad descriptor/path: `(st_dev, st_ino)`, obtenida mediante fstat/stat y verificada en la plataforma. Si el filesystem no proporciona identidad estable verificable, BLOCKED. Guardar la identidad en el único registro de operación. El descriptor es privado y no heredable; no duplicarlo ni transferirlo a hijos. Mantenerlo abierto y la exclusión durante staging, commit, rollback y cleanup; comprobar de nuevo identidad antes de mutaciones. Liberar al finalizar o por terminación del proceso, cuya conducta deberá probarse en ambos OS.
4. `config recover` **sólo abre el archivo existente**. Lock ausente/inseguro/ocupado o identidad no acreditable: BLOCKED sin abrir registro, backups ni targets del batch. No recrear un lock faltante para recuperar. Tras adquirirlo, validar registro y coincidencia exacta de identidad/contexto antes de inspeccionar recursos. Con lock existente y sin scratch, recovery informa no_changes y libera exclusión sin escrituras.
5. La adquisición acredita exclusión entre operaciones conformes que mantienen ese descriptor toda su vida; no prueba éxito, ausencia de efectos o autenticidad del registro. PID/timestamp/directorio no acreditan terminación. El descriptor se mantiene también ante excepciones hasta terminar rollback o informar bloqueo. Scratch pendiente bloquea una nueva edición incluso con lock libre.

En POSIX, unlink de un archivo bloqueado deja vivo su inode y permite crear otro en el mismo path. Este protocolo evita esa bifurcación entre operaciones **cooperantes** al mantener el archivo estable fuera del cleanup. La comparación descriptor/path/registro detecta sustituciones observables y bloquea; no impide absolutamente la eliminación por un proceso externo que ignora el protocolo. No resolver conflictos recreando silenciosamente el lock. Cambiar/mover el origen con operación pendiente o identidad inconsistente bloquea recovery.

## Único registro temporal de B

Scratch creado sólo después de adquirir exclusión y revalidar una edición real aceptada. Una estructura concreta para funciones privadas, sin Journal/Transaction, backends, callbacks, log append, historial o migrador. PREPARED/COMMITTED sólo distinguen intento recuperable de resultado confirmado para cleanup.

| Campo | Significado / validación |
|---|---|
| `schema_version` | 1; otro schema bloquea sin modificar recursos |
| `operation_id` | Identificador único del intento; no reutilizar resultado perdido |
| `source_root` | Origen canónico original; contexto distinto bloquea recovery |
| `lock_identity` | Path relativo fijo `.olympus-cli-edit.lock` y `(st_dev, st_ino)` del descriptor adquirido; debe coincidir con path y registro |
| `state` | PREPARED o COMMITTED; ausencia/incompleto no permite adivinar efectos |
| `read_set` | Inventario/paths relativos y SHA-256 del snapshot; validar contención antes de leer |
| `files` | Recursos existentes del conjunto fijo, hashes old/new, modo, backup/staged dentro del scratch; sin duplicados ni paths arbitrarios |

Originales y candidatos son archivos acotados, no otra configuración. Completar staging, verificar hashes y persistir PREPARED por staging + replace antes del primer reemplazo de targets; vaciar buffers de archivos según plataforma sin prometer durabilidad absoluta frente a pérdida eléctrica. No hay tabla de progreso por rename: se reconstruye progreso desde hashes bajo exclusión. COMMITTED sólo se persiste tras verificación final de bytes/read-set/coherencia renderer.

Rechazar traversal, escapes, enlaces/reparse/hardlinks, recursos no regulares, cross-filesystem y registros conflictivos. Recovery usa stdlib/renderer y backups, sin instalar/importar el editor TOML. Validar schema/contexto/identidad, todos los hashes de targets old/new y sus modos esperados, read-set no escrito y todos los backups necesarios antes del primer restore. Los staged todavía presentes también deben coincidir con su hash new. Los staged consumidos por replace pueden estar ausentes; no inventar contenido a partir de esa ausencia.

## Transiciones observables

Toda inspección de recovery en esta tabla ocurre **después** de adquirir exclusión nativa y validar identidad. Consultas/preview sólo informan scratch pendiente, sin repararlo ni crear locks/caches; su lectura no es un snapshot multiarquivo reservado.

| Estado observado | Lectura/preview | Mutación/recovery explícita |
|---|---|---|
| Sin operación | Consulta normal, sin escrituras | Edición válida: preflight; no-op sin lock/scratch. Recovery con lock existente: no_changes |
| Lock activo | Consulta sin reservar estado | Otro commit/recovery: BLOCKED antes de inspección del batch |
| Lock ausente/inseguro/identidad distinta | Informar contexto no acreditado cuando se observe | Recovery BLOCKED; no recrear ni asumir terminación |
| Scratch incompleto antes de PREPARED | Informar operación sin confirmar; no reparar | Tras adquirir lock, BLOCKED si no puede acreditarse ausencia de sustituciones; no limpiar por antigüedad |
| PREPARED con todos old | Informar pendiente | Validar estado old/read-set/coherencia y limpiar sólo temporales propios |
| PREPARED con mezcla old/new | Informar parcial, sin éxito | Validar conjunto y backups necesarios; dejar old, restaurar new, verificar old coherente y limpiar |
| PREPARED con todos new | Informar resultado sin confirmar | Rollback; no inferir commit por coincidencia de hashes |
| COMMITTED con todos new | Informar cambio confirmado con cleanup pendiente | Validar estado new/read-set y limpiar, sin rollback ni nueva edición |
| Tercer hash, modo distinto, missing target, backup inválido o read-set externo distinto | Informar conflicto concreto | BLOCKED antes de restore; preservar contenido externo, registro y respaldos disponibles |

## Recovery repetible y cleanup

Antes de cada restore revalidar identidad/hash new y modo esperado del target, y hash old del backup. Un modo externo divergente también bloquea; no cambiarlo automáticamente. Crear **otra copia staged** del backup, verificarla, conservar modo y sustituir mediante os.replace; nunca mover/consumir el respaldo original. Mantener todos los backups hasta que el conjunto esté old y coherente. Una interrupción deja mezcla old/new clasificable para otro recovery exclusivo, sin retry de la edición original.

Cleanup bajo el mismo lock elimina únicamente temporales enumerados y propios; registro al final, scratch al final, **nunca el archivo estable del lock**. Si se interrumpe cleanup, PREPARED all-old o COMMITTED all-new permite repetirlo tras revalidar targets/read-set/coherencia; backups/staged ya retirados no se requieren para una restauración que no se hará. Si falta un backup todavía necesario, bloquear. Scratch sin registro suficiente queda bloqueado con evidencia disponible; no deducir ownership por edad, PID ni nombre.

Hash old/new acredita pertenencia al estado del intento dentro del contrato local; no demuestra autoría frente a un tercero que escribe bytes idénticos. Un hash previo a os.replace no es compare-and-swap. La carrera con un proceso externo no cooperante tras la última comprobación está fuera de garantía; cualquier conflicto observable impide overwrite automático y obliga a reportar bloqueo o estado sin confirmar.

## Instalaciones y límites

B no modifica manifests ni destinos instalados y no reutiliza este registro como ownership de C. El schema de personalización instalada sigue no adoptado; C BLOCKED sin cambios de alcance.

FR-012 excluye protección absoluta frente a procesos no cooperantes, atomicidad multiarquivo visible para lectores concurrentes y durabilidad absoluta ante pérdida de energía. No permite sobrescritura automática de trabajo externo ni éxito parcial. T019/T020 acreditan el protocolo integrado, lock vacío/identidad/recovery en Windows/Linux; tres fixtures symlink omitidos en Windows (`WinError 1314`) pasaron en Linux. La evidencia exacta es T019/T020 en [tasks.md](tasks.md) y el run T020 [38857503366 / job 116832156025](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38857503366/job/116832156025). No resolver fallos añadiendo servicio, SQLite, polling permanente, gestores transaccionales o agentes. macOS sigue NOT VERIFIED.
