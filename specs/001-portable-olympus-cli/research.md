# Research: feasibility gate y decisiones

**Fecha**: 2026-10-14. **Baseline**: v0.4.9 `c30a19d…`. La investigación inicial fue read-only y luego comprobó Python/renderer/notas. **Actualización T001**: instalación normal remota y VerifyOnly de archivos Codex proyecto en Git temporal aislado, PASS; sin pruebas de CLI nueva ni agentes. Global **BLOCKED**, A **READY_FOR_IMPLEMENTATION** por R49 PASS, B **CONDICIONADA**, C **BLOCKED**.

## Evidencia del gate

| ID | Fuente / ubicación | Hecho observado |
|---|---|---|
| E1 | [renderer](../../scripts/render_harnesses.py), `checked_sources` 63–105, `role_model` 108–116 | Configuración/roster canónicos validados; helpers trabajan con dicts |
| E2 | Renderer, `opencode_outputs` 188–269, `codex_outputs` 272–319, `outputs_for` 346–355 | Generación en memoria; Kael raíz y sin Aegis Codex; reutilizable sin copiar renderer |
| E3 | Renderer, `run` 358–383 | Check compara; render escribe secuencialmente, sin rollback exterior |
| E4 | [bootstrap](../../scripts/bootstrap.ps1), 15, 136–162, 297–375, 519–533, 651–690 | Consume outputs del checkout junto al script, ownership/hash/conflicto, manifest versión/commit y VerifyOnly |
| E5 | [global-install](../../scripts/global-install.ps1), 98–156, 171–203, 237–299 | Outputs locales, rutas/manifests/hashes, overrides preservados, escrituras antes de manifest |
| E6 | [install](../../install.ps1), 14–40, 146–157, 160–192 | SourceRoot qualification-only, identidad textual SemVer; Windows-only. No digest de personalización |
| E7 | Bootstrap 739–750; global-install 310–320; [project-uninstall](../../scripts/project-uninstall.ps1) 118–120 | Discovery con IDs Sol/Luna fijos; límites Windows; global all puede ser parcial |
| E8 | [harness-core](../../tests/harness-core/qualify.py) 239–242/300–352; [Codex validator](../../tests/codex/validate_profile.py) 26–56 | Expectations de baseline y modo safe-root; catálogo Codex separado del check estático |
| E9 | [workflow](../../.github/workflows/fast.yml); [ledger](../retrospective/v0.4.9/EVIDENCE.md), E000 | CI Windows actual; tag y SHA identificados. Publicación/FAST no acreditan gate remoto release |
| E10 | [dual-harness](../../tests/release/dual-harness-installer.ps1), [global](../../tests/global-installer/qualify.ps1), [UX](../../tests/installer-ux/qualify.ps1) | Suites existentes para drift, ownership, verify y conservación; no corridas en esta sesión |
| E11 | `C:/Users/BLAUTECH/.local/bin/python3.11.exe -B --version`; renderer `check --harness all` | Ejecutados en revisión: Python 3.11.17, exit 0; HARNESS_RENDER_CHECK PASS, 30 outputs y read-only. El alias `python.exe` Microsoft Store no proporciona intérprete |
| E12 | [check de notas](../../tests/release/github-release-notes.ps1) con `-Version v0.4.9` sin ReleaseBody fixture | Ejecutado en revisión: GITHUB_RELEASE_NOTES v0.4.9 PASS, exit 0; body real de GitHub, sin escritura/instalación |

Investigación Veyra previa limitada a instalación recibida y reconciliada en estado terminal. Esta revisión no activó agentes ni otra sesión Olympus. Ningún hallazgo otorga autoridad de escritura sobre los archivos anteriores.

## 1. Distribución y acceso al comando

**Decision**: stdlib Python >=3.11; inicial `python -B -m olympus`; final mínimo launchers Windows/Linux anclados a checkout confiable, ubicado en PATH de usuario. No publicar paquete o binario en esta sesión. Instalar prerrequisitos es preparación explícita, no parte de cada orden CLI; comandos de modelos trabajan offline.

**Rationale**: Renderer/engine necesitan árbol fuente real y outputs; separar ejecutable de fuentes mediante un paquete exige resolver resource placement o un checkout externo. Checkout + launchers usa el contrato ya existente, conserva movilidad y no introduce el flujo sin checkout de #66. El usuario sabe que el comando depende de Python y del checkout.

| Opción | Ventaja | Coste/límite | Resolución |
|---|---|---|---|
| Python stdlib y `-m` | Sin framework/build inicial; código portable | Python requerido; por sí solo no instala nombre de comando | Entrada A |
| Launchers `.cmd`/POSIX shell | Nombre `olympus`, fuerza `-B`, apunta al único árbol; sin compiler | PATH/setup documentado y quoting a cualificar; ligado al checkout | Elegida para acceso final acotado |
| Wheel + console_scripts en venv/pipx | Wrappers generados e integración estándar | Backend/build adicional; fuentes/renderer externo y datos aún a resolver; pipx no imprescindible | Alternativa futura, no segundo canal ahora |
| Stdlib zipapp | Archivo transportable con Python presente | No hace mutable el Core empaquetado; recursos/installer externos; Windows resolución de comando requiere wrapper/asociación | No aporta ventaja para este alcance |
| Ejecutable congelado/runtime embebido | Reduce prerequisite Python | Artefactos por OS/arquitectura, toolchain y mantenimiento mayores | Descartado inicial |
| PowerShell-only / Node/TUI framework | Otras interfaces posibles | No cumple simplicidad/objetivos sin costo injustificado | Descartado |

Los wrappers de `console_scripts` son generados por instaladores de paquetes y PATH sigue siendo responsabilidad de setup; esa opción no resuelve automáticamente distribución del Core. [PyPA entry points](https://packaging.python.org/en/latest/specifications/entry-points/#use-for-scripts).

Zipapp requiere un intérprete adecuado y su extensión no proporciona por sí sola un comando Windows sin limitaciones; empaquetar no elimina la necesidad de árbol fuente mutable. [Python zipapp](https://docs.python.org/3.11/library/zipapp.html).

## 2. Arquitectura y generación reutilizada

**Decision**: parser `argparse` + funciones directas; carga del renderer del source confiable; consultas usan E1/E2. Preview de B compone helpers con modelos candidatos en memoria. Sin refactor/migración del renderer, servicio o motor nuevo.

**Rationale**: `checked_sources` ya valida roster/identidades/capacidades, y los builders aceptan modelos explícitos. `outputs_for` lee disco; para preview no escribir un TOML temporal ni llamar render. B coordina escrituras fuera de `run('render')`, porque éste es secuencial y no proporciona recovery.

**Alternatives considered**: copiar lógica de rendering produce divergencia; cambiar renderer entero para empaquetar adelanta mantenimiento innecesario; subprocess render preview viola sólo lectura. No ejecutar código desde un destino instalado como si fuera fuente confiable.

## 3. TOML preservador

**Decision**: `tomllib` para semántica; TOML Kit sólo para editar/preview B, versión inicial investigada 0.13.3. No instalarla en esta sesión; fijar/cualificar su versión en implementación. No Poetry ni sus dependencias dev en runtime.

**Rationale**: Python documenta que tomllib no escribe y recomienda un editor preservador para documentos existentes. [Python tomllib](https://docs.python.org/3.11/library/tomllib.html). TOML Kit conserva comentarios, espacios, indentación y orden según su documentación; esa capacidad requiere tests de byte-preservation del proyecto, no un PASS por la descripción. [TOML Kit](https://tomlkit.readthedocs.io/en/latest/). La metadata versionada 0.13.3 sólo declara Python como dependencia runtime; Poetry es build backend, no runtime obligatorio. [Metadata 0.13.3](https://raw.githubusercontent.com/python-poetry/tomlkit/0.13.3/pyproject.toml).

**Alternatives considered**: dict→serializer pierde comentarios/formato; patch de regex limitado funciona en baseline pero confunde strings multilínea/dotted keys/unrelated contents; cubrir TOML completo a mano sería más código y riesgo que una dependencia pequeña. No agregar framework CLI por esta decisión.

**Límite**: preservar bytes/trivia fuera de valores solicitados debe comprobarse; rechazo antes de escribir si round-trip/diff no lo demuestra. No prometer toda forma TOML sin cualificación. A sigue sólo stdlib; B sin dependencia disponible termina BLOCKED.

## 4. Consistencia, staging y recuperación

**Decision**: B condicionada a demostrar preservación/recuperación. Función privada limitada a `models.toml` + outputs cambiados del renderer que ya existen, candidatos en memoria, backups/staging de ese conjunto y un registro temporal old/new. Verificación final y rollback propio; recuperación explícita tras interrupción, sin reanudar ni auto-repair. No API genérica transaccional, recursos arbitrarios, log de eventos, backends ni reutilización como actualizador instalado C. A no requiere ni importa nada de esto.

**Rationale**: un edit de models seguido de render puede fallar entre múltiples archivos. Backups en RAM sólo cubren excepciones atrapables. `os.replace` evita una escritura fragmentada de un archivo, pero no crea transacción para treinta; usar staging del mismo filesystem y cualificar Windows. [Python os.replace](https://docs.python.org/3.11/library/os.html#os.replace).

**Alternatives considered**: copiar todo repositorio o git stash/reset destruye aislamiento; SQLite/WAL/servicio transaccional no justifican coste; simple render posterior sin backup viola recuperación. No rollback sobre recursos con hash de terceros.

**Límite de concurrencia**: hash preflight + lock entre CLI no excluye editores no cooperantes; no hay garantía universal con stdlib/Linux advisory locking. Un único escritor sobre paths afectados es condición de commit. Si la interpretación de FR-012 exige excluir cualquier escritor externo simultáneo, registrar B BLOCKED para esa garantía y resolver alcance antes de tareas B, sin editar spec silenciosamente.

## 5. Aplicación a instalaciones: bloqueo concreto

**Decision**: C personalizada BLOCKED con baseline; no implementar writer alternativo ni usar override qualification como contrato. Mantener doctor/routing Windows como integración separable dentro de C.

**Rationale**: E4–E7 prueban reutilización de outputs y controles, pero no una ruta soportada de personalización trazable/recuperable. Un source personalizado con marcadores v0.4.9 puede pasar identidad textual, quedando manifest con versión/commit que no describen cambios locales. Fallar a mitad puede dejar hashes nuevos con manifest viejo y posteriores operaciones bloqueadas por drift. Bootstrap además descubre IDs fijos, no derivados de la intención nueva. Nada de esto es evidencia de pérdida reproducida; son límites observados en flujo/código.

**Alternatives considered**: patch directo del destino, `SourceVersion=local` para esquivar mismatch, eliminar hashes o marcar una personalización como oficial incumplen la especificación. Envolver el motor con snapshots de todo destino duplica preflight/seguridad y no arregla procedencia ni unidades globales `all`.

**Vía acotada de desbloqueo**: extender el mismo motor con contrato explícito de fuente personalizada validada, provenance de release/digest y verificación posterior compatible, recuperación de recursos propios y prueba de guards. Digests de procedencia no son otra configuración de modelos. Validar project/global y ambos harnesses antes de decidir parámetros/campos definitivos. Si ese delta no es acotado, proponer split explícito al usuario; no crearlo ni declarar C completada ahora.

## 6. Portabilidad y operaciones nativas

**Decision**: A/B Python compartido Windows/Linux; launchers OS mínimos. Native_ops llama motores Windows sólo donde cualificados. Linux native apply/install/uninstall no soportados; macOS NOT VERIFIED. No quitar platform guards ni repetir framework en Python.

**Rationale**: E6/E7 y dependencia `fsutil` en reparse handling impiden asumir installer portable. Filesystem paths/unicode/newlines se prueban sobre core CLI; eso no acredita Aegis/DENY/runtime discovery.

**Alternatives considered**: portar todo PowerShell ahora, WSL local, Docker y matriz macOS por aspiración contradicen alcance/economía.

## 7. Pruebas y gates

**Decision**: un archivo unittest nuevo en harness-core, con casos seleccionables slice_a/slice_b. A sólo consulta, CLI, JSON, cero mutaciones y compatibilidad Windows/Linux; job Linux inicial filtra slice_a. B añade edición/recuperación cuando su gate lo permita; C reutiliza suites instaladoras al desbloquearse. Los cualificadores amplios baseline no son requisito de aceptación A. Sin nuevos tiers ni FAST/FULL/RUNTIME.

**Rationale**: E8 fija baseline y por defecto renderiza; no usarlo como aceptación de modelos arbitrarios. Parametrizar casos CLI en fixtures sin debilitar checks del producto. TFR exige native smoke únicamente para integración que se anuncie, no para afirmar disponibilidad de modelos.

**Alternatives considered**: matriz todas las familias/roles/esfuerzos/OS, duplicar harness o ejecutar FULL por defecto aporta coste sin cubrir mejor los fallos relevantes.

**Release gate**: R49 se mantiene separado de la viabilidad de cada slice. La ejecución posterior autorizada de T001 acreditó la verificación remota limitada a archivos Codex proyecto; ya no retiene A. No cambia aceptación de la funcionalidad nueva ni de C.

## Revisión de R49 y gates independientes (2026-10-14)

**Registro histórico anterior a T001**: documenta el bloqueo encontrado durante planificación. Fue resuelto por la ejecución posterior de R49 descrita más abajo; no representa el estado actual del gate.

Se consultaron release real, PR #65 y sus comentarios/reviews, PR #63/#68, comentarios del issue #61 y #64, runs del SHA exacto y artifacts del run FAST, además de docs/scripts locales. La búsqueda de referencias `v0.4.9` identificó esas fuentes; no se interpretaron #66/#67 como requisitos ni se mezcló su trabajo.

| Comprobación | Resultado observado | Qué establece |
|---|---|---|
| Publicación | PASS: no draft, `2026-10-14T05:29:18Z`, tag v0.4.9 | Release existente, no aceptación instalada |
| Identidad tag | PASS: tag peeled `c30a19dd410b1815f4591b204615cae0dd9e9a5f` | Baseline exacto |
| Notas reales | PASS ejecutado por script existente, exit 0 | Body/tag/comandos de notas conformes; admite comandos locales, no prueba install remoto |
| CI SHA exacto | FAST run 38516290563 y CodeQL 38516290529 success; artifacts FAST=0 | Checks históricos acotados. `Invoke-FastSlice` es offline; no ejecuta aceptación remota |
| Instalación + VerifyOnly desde tag remoto | Evidencia no encontrada; no ejecutados ahora | R49 BLOCKED para comenzar implementación |

La [release publicada](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.4.9) distingue checks remotos de fixtures locales. El [PR #65](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/65) reporta OpenCode stubbed y deja validación del tag como gate; no tiene comentarios/reviews que lo reconcilien. [CI FAST exacto](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38516290563) y [CodeQL](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38516290529) no sustituyen esa prueba. Las fuentes revisadas no prueban que nunca se ejecutó; prueban que no se encontró un resultado trazable suficiente.

**Falta exacta en esa revisión, ahora resuelta por T001**: evidencia del paso 3 de [DEVELOPMENT](../../docs/DEVELOPMENT.md): fuente/URL del tag remoto inmutable v0.4.9, instalación en Git desechable y VerifyOnly posterior, con origen/versión/harness/resultados trazables. Los sustitutos locales/notas/CI no bastaban; la ejecución remota posterior aporta esa evidencia sin añadir FULL/RUNTIME, modelos o Linux installer.

**Dependencias de A resueltas para tareas**: runtime Python local concreto, stdlib, fuente/renderer coherentes por E11, funciones de resolución existentes, contrato de consulta/JSON y vía Linux CI definida en plan. Tener que implementar el job/smoke no es una dependencia de arquitectura sin resolver; su ejecución es acceptance futura. A no requiere validación de TOML Kit, rollback o manifests personalizados. A **READY_FOR_TASKS** significa tareas sólo de consulta/read-only, no implementación autorizada ni acceptance Windows/Linux completada. R49 pertenece a inicio de código y el gate global pertenece a entrega completa.

## Ejecución autorizada de T001: resolución R49

**R49: PASS**, cierre del bloqueo anterior. [Reporte y evidencia](evidence/r49-20261014-c30a19d/report.md), [resultados](evidence/r49-20261014-c30a19d/result.json), [operaciones](evidence/r49-20261014-c30a19d/operations.json).

- Release no draft, v0.4.9 publicada `2026-10-14T05:29:18Z`; tag anotado `a9c76fb47ae7826df57f2319a29be1397e8ff97f` resuelve a `c30a19dd410b1815f4591b204615cae0dd9e9a5f`, revalidado después.
- Instalador raw del tag ejecutado sin cambios, adquisición normal `REMOTE_ARCHIVE` en install y VerifyOnly, sin fuentes locales/overrides/master/latest. Referencia remota de 274 blobs validada contra el commit; no se usó como input local.
- Una instalación real de archivos en un Git temporal, scope project/harness codex, exit 0; VerifyOnly con nueva adquisición del mismo tag, exit 0. Manifest schema 1/version v0.4.9/codex, 12/12 recursos coincidentes con manifest y release.
- Entorno del proceso limpiado, HOME/config/cache/temp/Git aislados y runtimes/credenciales ausentes en PATH/env; preflight pasó antes de instalación. Sin stubs, modelos, agentes, prompts ni scope global.
- Verificación no modificó target: 25 registros idénticos. Repositorio de desarrollo (13.874 registros), configuraciones/cachés personales seleccionadas (95) y control ajeno (2), iguales antes/después. Logs/databases personales activos no se incluyeron ni se tocaron.
- Archive sin .git produce `installed_from_commit=unknown`; no se alteró ese campo ni se presentó como prueba. Identidad exacta acreditada por tag/commit y hashes de los blobs y archivos entregados.
- Se conservaron dos fallos de preparación anteriores a la instalación: snapshot sobre log activo y selección múltiple de PowerShell. Se corrigió sólo el preflight; instalación y VerifyOnly se ejecutaron una vez cada una. Evidencia conservada; limpieza del árbol temporal pendiente por rechazo automático «blocked by policy», sin ejecución del comando de borrado ni intento de eludirlo.

Este resultado satisface el gate solicitado de adquisición/instalación/verificación remota en destino aislado. No afirma runtime Codex/OpenCode, instalación OpenCode/global/Linux ni aceptación de A/B/C. La tabla de revisión anterior registra el estado histórico de evidencia faltante y queda supersedida únicamente para R49 por este cierre.

## Conclusión y decisiones pendientes

**A READY_FOR_IMPLEMENTATION** respecto de sus gates técnicos: R49 PASS y tareas A ya generadas, sin esperar B/C. T002–T009 siguen sin ejecutar. **B CONDICIONADA**, **C BLOCKED** y **global BLOCKED** mantienen sus requisitos completos. Resolver T001 no implementa funcionalidades ni concede autorización de publicación o de cambios fuera del encargo.
