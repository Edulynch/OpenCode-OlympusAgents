# Revisión final de integración — Slice A / PR #69

Revisión documental y estática del 2026-10-14 sobre el head
`6e1076dd68427e3e2e1814f594adaa7fda3dbee4` del
[PR #69](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/69).
No se repitieron Windows ni R49, ni se accedió al árbol temporal retenido.
Los originales de `evidence/r49-20261014-c30a19d/` permanecen intactos.

## Evidencia Linux consumida

[Slice A / Linux, job 116127153113](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38644271501/job/116127153113)
terminó SUCCESS el `2026-10-14T21:58:31Z`: Ubuntu 24.04,
CPython 3.11.17, 20 casos en 5.129 s, 19 PASS y 1 SKIPPED de Windows,
exit 0; launcher POSIX directo, JSON y snapshots sin mutaciones.
Actions probó `refs/pull/69/merge`, commit abreviado `6704b1e`, que integra
el head indicado con base `1900da45250ddec817a6141396e0ec1268b2dfca`.

Ese run preparó el ejecutable mediante `chmod`. Acredita T008 PASS para
la ejecución funcional Linux histórica; no acredita el bit del checkout
original. El operador preparó después `scripts/olympus` en `100755`.
La revisión retira la reparación del workflow y conserva `test -x` antes y
después de la suite y la comprobación final de Git con `core.filemode=true`.
El test existente `test_slice_a_posix_launcher` comprueba `os.access(...,
os.X_OK)` sobre el checkout real y la copia de fixture creada con `copy2`,
sin `chmod`; luego ejecuta el launcher directamente. No hace falta otra suite.
El CI final de estos cambios sigue NOT RUN.

## Auditoría de la evidencia R49 publicada

Se revisaron los 29 archivos del diff del PR y los 12 archivos versionados
de su carpeta R49. La búsqueda estática de claves privadas, tokens GitHub,
claves de proveedor y asignaciones literales de credenciales no encontró
coincidencias. Es una revisión acotada de contenido, no una garantía de
ausencia de todo dato sensible ni una ejecución de R49.

| Hallazgo | Ubicación | Evaluación |
|---|---|---|
| Usuario local y rutas absolutas de HOME, configuración, cachés y temporal | `environment.json`, `operations.json`, `preflight-start-failure.json`, `report.md`, `result.json`, `snapshots-before.json` | Metadatos personales identificables; no son necesarios literalmente para explicar aislamiento. No se reproducen aquí. |
| Rutas a archivos de autenticación | `snapshots-before.json`, `personal_locations` | Se publican nombres/rutas, no su contenido ni credenciales; evitar duplicarlos en guías. |
| Ruta personal del intérprete | `tasks.md`, `plan.md`, `research.md`; antes también quickstart | Evidencia histórica de Python real. La guía de uso puede conservar versión y remitir al registro sin repetir la ruta. |
| Repetición de contadores, hashes y resultados | `report.md`, `result.json`, `snapshots-before.json`, resúmenes de plan/research/tasks | Parte es trazabilidad: el snapshot previo se contrasta con el resultado posterior. Centralizar resúmenes futuros, sin borrar los registros originales. |
| Inventario de 274 blobs | `acquisition.json`, 60 339 bytes en copia local | Es la mayor parte del volumen, pero sostiene la comparación del archive con el commit. Recortarlo a 12 recursos perdería evidencia del alcance declarado. |
| Hashes de manifest y de comprobación | `installed-manifest.json`, `managed-files.json`, `acquisition.json` | Repetición útil: permite contrastar tres procedencias; conservarla. |

### Referencias locales no publicadas

El reporte y `evidence-sha256.json` nombran diez logs que no están en el PR:
`git-init.stdout.log`, `git-init.stderr.log`, `git-root.stdout.log`,
`git-root.stderr.log`, `isolation-preflight.stdout.log`,
`isolation-preflight.stderr.log`, `install.stdout.log`, `install.stderr.log`,
`verify-only.stdout.log`, `verify-only.stderr.log`. El patrón `*.log` de
`.gitignore` explica su exclusión. `cleanup.json` tampoco está versionado:
ya era un archivo local untracked al iniciar esta revisión.

Existen copias de esos once archivos **en la carpeta de evidencia del
repositorio**; sus hashes coinciden con el índice histórico. No se siguió
ninguna ruta al temporal ni a configuraciones personales. Existencia local
no equivale a publicación. Los enlaces relativos del reporte no son
evidencia accesible para quien consulte sólo el PR; en particular, los logs
REMOTE_ARCHIVE y el detalle del rechazo de cleanup no son verificables allí
como archivos originales. El reporte y los JSON publicados registran esos
resultados, pero no sustituyen los logs ausentes.

### Integridad y comprobaciones estáticas

Los 22 hashes enumerados coinciden con las copias locales en la carpeta de
evidencia. Diez JSON originales usan CRLF; sus blobs Git se normalizaron a
LF y por ello **no coinciden byte a byte** con esos hashes históricos.
Se comprobó que la única diferencia es CRLF → LF. `report.md` coincide
directamente. El índice no contiene su propio hash. No se cambió ningún
hash histórico para ocultar la diferencia de representación.

Los 12 hashes instalados coinciden entre manifest, `managed-files.json` y
los recursos correspondientes de `acquisition.json`; los 274 registros
de adquisición concuerdan en cantidad con el resultado. Los pares de
huellas antes/después de desarrollo, personal y control son iguales;
también coinciden las huellas del target antes/después de VerifyOnly.
Esto comprueba consistencia de registros conservados, no reejecuta ni
reconstruye los snapshots o la instalación original.

## Reducción mínima propuesta, sin aplicarla a originales

1. Usar `tasks.md` como registro de aceptación A y el reporte R49 como
   registro histórico de T001. README/quickstart/contrato sólo necesitan
   estado, límites y enlaces; retirar de la guía y del resumen de plataforma
   la ruta personal repetida del intérprete, conservando Python 3.11.17 y
   su procedencia histórica en tasks/research y Git.
2. Conservar los doce originales y el índice histórico, incluidos fallos
   de preflight, `installed_from_commit=unknown`, contadores y los 274 blobs.
   La actualización de estados actuales en plan/research/tasks no debe
   reescribir los resultados históricos del reporte R49.
3. Para una futura copia pública reducida, sustituir consistentemente
   sólo prefijos personales por marcadores (`<USER_HOME>`, `<R49_ROOT>`)
   en **derivados identificados**, manteniendo sufijos, relaciones de
   contención, argumentos, versiones, timestamps y resultados. Registrar
   hashes de original/derivado y cada sustitución; no reemplazar ni
   recalcular silenciosamente el índice original. La anonimización del
   estado actual no borraría datos ya publicados en el historial Git.
4. Registrar explícitamente los once archivos locales como no publicados
   antes de considerar su publicación. Si se desea acceso público a esos
   originales, revisar y publicar sólo las copias conservadas bajo la
   carpeta de evidencia; nunca obtenerlos del temporal bloqueado ni
   inventar un artefacto/enlace faltante. No eliminar ni consolidar logs
   originales para disimular los enlaces rotos. Un índice suplementario
   distinguiría hashes CRLF originales, blobs Git LF y derivados.

Las rutas personales, la falta de publicación y la representación de
hashes son limitaciones documentales registradas, no nuevos resultados
FAIL de R49. Esta propuesta no exige limpieza, reejecución, reescritura
del historial ni publicación en esta revisión.

## Límites del cierre

Riesgo de este delta: LOW, limitado a workflow y documentación. Se usó
comprobación estática del cambio exacto en lugar de ejecutar suites.

| Comprobación de esta revisión | Resultado |
|---|---|
| Diff exacto del workflow, jobs/triggers/pins y job Windows preservados | PASS; sólo se retira el paso `chmod` y se detecta drift de modo |
| Sintaxis Bash del launcher y de los dos bloques Linux del workflow | PASS con `bash --noprofile --norc -n`; sin ejecutar comandos CLI |
| Inspección AST de la suite existente | PASS; 20 casos, comprobación ejecutable sobre ROOT, copia sin `chmod`, ejecución directa y snapshots |
| Integridad de registros R49 conservados y hashes cruzados de 12 recursos | PASS estático, con límites CRLF/LF y archivos no publicados descritos arriba |
| Índice Git del launcher | PASS; `100755`, blob `3720c09ca2bd4447becd1adb7fb3bf64751b943a`; único cambio staged, 0 líneas de contenido cambiadas |
| Diff/documentación | PASS; `git diff --check`, nuevos enlaces locales válidos, T001–T009 marcadas completas con estado actual y evidencia enlazada |

El chequeo de enlaces requirió corregir la decodificación del propio
script a UTF-8 y repetirlo: PASS. No se usó parser YAML dedicado; el
workflow se contrastó contra el original permitiendo sólo el delta exacto
descrito y se comprobó la sintaxis de sus bloques Bash. `.specify/extensions.yml`
no existe en las comprobaciones previa/posterior; no hay hooks registrados.

macOS permanece **NOT VERIFIED**; B/C quedan fuera del alcance, con sus
gates previos. La entrega completa A+B+C sigue bloqueada por sus requisitos
restantes. No se ejecutaron suites de producto, FAST/FULL/RUNTIME,
instaladores ni llamadas a modelos en esta revisión. No hubo commit,
push ni merge. El estado preparado del launcher y el diff final se
comprueban antes del cierre; la ejecución Linux sin reparación corresponde
al CI final autorizado posterior.
