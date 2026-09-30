# Olympus → Codex: compatibility matrix

La matriz documenta el adapter Codex soportado desde Olympus Core, contra la
documentación oficial consultada el 2026-09-29 y la evidencia runtime previa
suministrada por el usuario para esta modularización. Los smokes aceptados no se
repitieron aquí. El proyecto mantiene un capability contract explícito; las
limitaciones de Codex no reducen garantías Core ni implican paridad con OpenCode.

## Clasificación

- `DIRECT_MAPPING`: primitive nativa con el mismo contrato operativo básico
  demostrado.
- `ADAPTABLE`: encaja si Kael mantiene explícitamente la policy Olympus.
- `PARTIAL`: hay soporte, pero enforcement, observabilidad, aislamiento o paridad
  no están demostrados.
- `GAP`: no se encontró un equivalente seguro demostrado; no se simula.
- `NOT_NEEDED`: Codex puede ofrecer la primitive, pero el flujo Olympus probado
  no depende de ella.

## Modelos por rol

| ROLE | OPENCODE MODEL | OPENCODE EFFORT | CODEX MODEL | CODEX EFFORT | STATUS |
|---|---|---|---|---|---|
| Kael | `gpt-6.1-sol` | `high` | `gpt-6.1-sol` | `high` | DIRECT_MAPPING |
| Veyra | `gpt-6-luna` | `max` | `gpt-6-luna` | `max` | DIRECT_MAPPING |
| Orin | `gpt-6-luna` | `max` | `gpt-6-luna` | `max` | DIRECT_MAPPING |
| Atlas | `gpt-6.1-sol` | `high` | `gpt-6.1-sol` | `high` | DIRECT_MAPPING |
| Kovan | `gpt-6-luna` | `max` | `gpt-6-luna` | `max` | DIRECT_MAPPING |
| Argus | `gpt-6.1-sol` | `high` | `gpt-6.1-sol` | `high` | DIRECT_MAPPING |
| Nox | `gpt-6-luna` | `max` | `gpt-6-luna` | `max` | DIRECT_MAPPING |
| Vera | `gpt-6-luna` | `max` | `gpt-6-luna` | `max` | DIRECT_MAPPING |
| Talos | `gpt-6.1-sol` | `high` | `gpt-6.1-sol` | `high` | DIRECT_MAPPING |
| Thales | `gpt-6.1-sol` | `xhigh` | `gpt-6.1-sol` | `xhigh` | DIRECT_MAPPING |
| Helios | `gpt-6.1-sol` | `high` | `gpt-6.1-sol` | `high` | DIRECT_MAPPING |
| Aegis | `gpt-6-luna` | `max` | — | — | GAP |

Los diez roles especialistas tienen archivos TOML separados bajo
`.codex/agents/`; Kael es la sesión root, no un custom agent adicional. Aegis no
existe en ese roster. El catálogo `codex debug models --bundled` pasó la
calificación estática: los modelos y esfuerzos configurados están disponibles
en esta CLI. No se promocionó ningún rol Luna a Sol. Los identificadores
OpenCode llevan provider (`openai/`); Codex usa el slug desnudo equivalente.

## Primitives Olympus

| Capacidad | Mapping | Evidencia actual y límite |
|---|---|---|
| Instrucciones jerárquicas `AGENTS.md` | ADAPTABLE | Codex concatena instrucciones globales y de proyecto por directorio; `AGENTS.override.md`/`AGENTS.md` preceden a los nombres fallback. El experimento usa `project_doc_fallback_filenames = ["CODEX.md"]` para no añadir un `AGENTS.md` que también alteraría otros harnesses. Config local solo se carga en proyectos trusted. |
| Configuración local `.codex/config.toml` | DIRECT_MAPPING | Codex reconoce config por proyecto trusted. Aquí declara modelo root, aprobación, permission profiles, fallback `CODEX.md`, multi-agent y límite de threads. |
| Kael como root orchestrator | SUPPORTED | La sesión root representa al único Kael conceptual; no se crea un child `kael`. Root smoke previo: PASS. |
| Roles custom Veyra, Orin, Atlas, Kovan, Argus, Nox, Vera, Talos, Thales y Helios | SUPPORTED | Diez TOML generados desde el adapter. Runtime evidencia previa incluye Kael→Veyra y Kovan→Nox funcionales; no afirma smoke individual para cada rol. |
| Modelo y reasoning effort por role | SUPPORTED | Una fuente Core define familia/effort; el adapter traduce IDs a TOML/Codex. El catálogo bundled valida los slugs y efforts. |
| Multi-agent habilitado | SUPPORTED | `[agents].enabled = true`; fan-out/fan-in acotado de cuatro children tiene evidencia runtime PASS. |
| Delegación Kael → specialist | ADAPTABLE | Codex puede delegar cuando se pide o las instrucciones aplicables lo indican. Kael mantiene selección explícita; Codex no ofrece un allowlist Olympus que impida al root escoger otro agente. |
| Supresión de specialists no necesarios | ADAPTABLE | La policy de Kael prohíbe fan-out por disponibilidad. No delegar es una decisión de Kael, no una regla nativa Codex. |
| Trivial-task fast path | ADAPTABLE | `Kael → one writer → direct lightweight verification → DONE` está en `CODEX.md`; Codex puede seguirlo. No existe un fast path nativo que fuerce cero specialists para tareas pequeñas. |
| Máximo cuatro children | SUPPORTED | Cap nativo Codex = cuatro desde Core; fan-out/fan-in de 4 pasó y se observó concurrencia real de al menos 2. No se afirma equivalencia de scheduler más allá de esta evidencia. |
| Paralelismo acotado e independencia | SUPPORTED | Evidencia previa: fan-out/fan-in bounded PASS y concurrencia real ≥2. Kael conserva ownership de independencia y dependencias. |
| Delegación recursiva | DIRECT_MAPPING | Cada custom role pone `[agents].enabled = false`, deshabilitando sus herramientas multi-agent. La restricción estática existe; no se verificó invocación runtime. |
| Question barrier | PARTIAL | El prompt pide que children devuelvan `NEED_AUTHORITY` a Kael, pero Codex permite approval/permission requests originadas desde un thread hijo y la UI puede presentarlas directamente al usuario. No se garantiza que toda pregunta atraviese primero Kael. |
| Completion barrier | SUPPORTED | Bounded fan-out/fan-in de cuatro children pasó; Kael conserva obligación de no concluir con trabajo requerido desconocido o no consumido. |
| Result propagation | SUPPORTED | Child result delivery PASS en la evidencia runtime previa suministrada por el usuario. |
| Missing-result reconciliation | PARTIAL | App Server tiene `thread/read`, historial y filtros experimentales `parentThreadId`/`ancestorThreadId`. Recovery runtime de un resultado perdido no está demostrado; ausencia sigue siendo `COMPLETION_UNCONFIRMED`, no fracaso. |
| No blind retry | ADAPTABLE | `CODEX.md` prohíbe reemplazar/repetir sin reconciliar el child original y sus efectos. Es policy, no un mecanismo nativo que previene retries o duplicación de side effects. |
| ALLOW | SUPPORTED | `DIRECT_MAPPING` según evidencia runtime previa. El scope exacto y la autorización Olympus continúan siendo requisitos. |
| ASK | ADAPTABLE | Approval nativa confirmada por el usuario en la evidencia previa; no es autorización anticipada y una solicitud de child puede mostrarse fuera de Kael. |
| DENY | GAP | No hay equivalencia demostrada para protección hard Olympus. No reducir DENY Core ni tratar una aprobación ordinaria como elevación permitida. |
| `request_permissions` | PARTIAL | Codex tiene una herramienta para pedir un subconjunto de permisos de filesystem/network, con aprobación del cliente y scope por turno/sesión. No es una authority grant Olympus, ni se verificó su comportamiento frente a paths protegidos. |
| Sandbox, writable roots y shell | PARTIAL | Permission profiles beta gobiernan filesystem/network de comandos locales. `:workspace` protege `.codex` y `.git`; el perfil experimental hace read-only `.opencode`, `opencode.jsonc`, `CODEX.md` y entrypoints del installer/bootstrap. No equivale a ACL de herramientas por role ni restringe automáticamente MCP/connectors/UI. |
| `codex exec` non-interactive write | PARTIAL | En un fixture temporal, `codex exec --strict-config` sin `--sandbox` terminó `turn.completed` pero rechazó la edición como `read-only sandbox`; el archivo no cambió. La CLI puede salir 0 aunque la aceptación haya fallado. No prueba enforcement de `default_permissions`; añadir `--sandbox` selecciona el camino legacy y omite esos profiles. |
| Enforcement en Windows | PARTIAL | El proyecto fija `windows.sandbox = "elevated"`; documentación oficial señala que `unelevated` es más débil y puede no admitir carveouts split read/write. Config válida no prueba que el sandbox elevado esté instalado ni que deniegue cada path; no se calificó runtime. |
| Olympus-owned protection | PARTIAL | Config intenta proteger runtime OpenCode, instrucciones Codex, `.codex`, `.git` e entrypoints de instalación. Son límites del profile/sandbox y policy, no una primitive de ownership Olympus ni ACL de SO. No rebajar protección para obtener compatibilidad; probar enforcement antes de uso real. |
| Repos sibling / rutas externas | PARTIAL | Codex permite añadir roots/permisos, subjecto al runtime/approval. Olympus requiere scope exacto y decisión explícita del usuario; no se configuró un grant amplio ni se probó acceso cross-repository. |
| Aegis maintenance plane | GAP | No existe entrada Codex segura equivalente a usuario explícitamente `/maintain` → Aegis, inaccesible a Kael. No se instala ni inventa un Aegis Codex. |
| Lifecycle de child/result | PARTIAL | Ver tabla de lifecycle debajo. Codex tiene eventos nativos, pero no se observó un child en ejecución en este experimento y no se asume equivalencia con el problema upstream OpenCode `No tool output found`. |
| Continuation / resume | PARTIAL | `codex resume` y App Server `thread/resume` continúan threads guardados. Esto no prueba que un child perdido pueda reanudarse con identidad/resultado original ni que side effects se puedan repetir con seguridad. |
| Session/thread isolation | PARTIAL | Cada agent tiene thread identificable; `/agent` permite inspeccionar threads. Children heredan sandbox/runtime del parent. No hay evidencia de worktree/filesystem separado por child; `codex --worktree` aísla una sesión root, no establece aislamiento de cada child. |
| Activity visibility | PARTIAL | Codex usa visibilidad nativa de agentes/threads. No se recrea el Activity HUD OpenCode ni se reclama igual observabilidad agregada. |
| Installer / VerifyOnly project-local and global foundation | SUPPORTED project-local; FOUNDATION global, static qualification | `-Scope project` permanece default. `-Scope global -Harness codex` instala custom-agent TOML en el home Codex, el profile `olympus.config.toml` y root instructions globales `AGENTS.md`, con `scope=global` y hashes. Conserva la base `config.toml`; inicia el perfil con `codex --profile olympus`. Conflictos/detalles drift abortan, user-owned `AGENTS.md` nunca se pisa, subset VerifyOnly se soporta. Qualification usa `CODEX_HOME` temporal; no se afirma UI/runtime smoke global. |
| Config global/per-project | ADAPTABLE | Codex admite `~/.codex/agents/`, `.codex/agents/`, `AGENTS.md` jerárquico y perfiles `$CODEX_HOME/<name>.config.toml`, además de config local solo en proyectos trusted. Olympus global mantiene el profile aislado de config base; project-local overrides no se borran automáticamente y el estado se informa. |
| Shell tool | PARTIAL | Shell local es nativo y sandboxed según el modo/profile activo; el flujo normal puede ejecutar comandos. No hay equivalencia probada para permisos de shell por role como en OpenCode. |
| MCP | NOT_NEEDED | Codex soporta MCP global y project-local. El flujo Olympus base no requiere MCP y este perfil no agrega servers; filesystem sandbox no sustituye permisos específicos de MCP. |
| Skills | NOT_NEEDED | Codex soporta skills; los contratos actuales de roles son instrucciones breves y no dependen de skills. No se crea skill redundante. |
| Hooks | NOT_NEEDED | Codex soporta hooks incluyendo eventos de subagent, pero routing, permisos y completion no se delegan a hooks experimentales. Ningún hook fue instalado. |

## Lifecycle observado/documentado

Esto separa los nombres conceptuales Olympus de los estados nativos Codex. No se
declara que una ejecución de tarea exitosa solo porque un thread terminó.

| Olympus | Evidencia/estado Codex | Interpretación segura |
|---|---|---|
| `RUNNING` | `turn/started` / `turn.status = inProgress`; thread runtime `active` (puede incluir `waitingOnApproval`) | Trabajo aún activo. |
| `TERMINAL` | `turn/completed` con `status = completed`, `failed` o `interrupted` | El turno terminó; inspeccionar el item y salida original antes de consumirlo. `interrupted` es el estado al interrumpir, no un estado llamado `cancelled`. |
| Child successful | Turn `completed`, más resultado en el child/response parent | `completed` solo es terminalidad, no prueba que la aceptación de la tarea se cumpla. |
| Child failed | Turn `failed` y error/evento correspondiente | Conservar error y resultado; no iniciar sustituto automáticamente. |
| Child cancelled | `turn/interrupt` conduce a `interrupted` | Codex no denomina este estado `cancelled`; efecto funcional requiere inspección. |
| `RESULT_PENDING` | No hay un estado nativo documentado con este nombre. Codex dice que el parent espera los resultados solicitados antes de responder consolidado. | Usar la etiqueta Olympus mientras no se haya inspeccionado/consumido el resultado del child. |
| `RESULT_VISIBLE` | Mensaje consolidado visible para root; historial/items disponibles vía App Server `thread/read` cuando se conoce el ID | Marcarlo solo tras validar los hechos requeridos. El campo `collabToolCall.status` existe, pero la guía no define aquí su enum como un contrato de éxito Olympus. |
| `COMPLETION_UNCONFIRMED` | No hay un estado nativo equivalente; los threads exponen estados `notLoaded`, `idle`, `systemError`, `active` y eventos de turno/items | Ausencia de item/salida no es fracaso ni permiso para retry. Reconciliar el thread/resultado original; si no hay evidencia, reportar unknown. |
| Continuation | `codex resume`; App Server `thread/resume` por `threadId`; `thread/read` inspecciona sin reanudar | Reanudar una conversación root está documentado. No se asume recovery de un child/resultado no disponible. |

La guía oficial de subagents dice que el main thread espera a que sus resultados
solicitados estén disponibles y los combina. App Server ofrece `turn/completed`,
items `collabToolCall`, historial persistido y status de thread; los filtros de
children por parent/ancestor son experimentales. No se observó el fallo upstream
OpenCode `No tool output found` ni un fallo equivalente Codex; tampoco se hizo un
smoke que permita concluir que Codex está libre de una clase equivalente.

## Authority y permisos

- **ALLOW**: dentro del task/write scope autorizado y permitido por el profile
  activo. El profile root usa `. = "write"` dentro del workspace; specialist
  profiles son read-only por defecto.
- **ASK**: una aprobación nativa elegible bajo `approval_policy = "on-request"`
  o una solicitud explícita `request_permissions`. La UI/runtime decide; una
  petición del child puede aparecer al usuario sin pasar primero por Kael.
- **DENY**: boundary Olympus que el prompt no puede conceder. Los paths protegidos
  están configurados read-only/deny y `.codex`/`.git` heredan protecciones de
  `:workspace`, pero no se ha demostrado que todos los flows de aprobación,
  overrides de sesión y sandbox Windows respeten invariablemente cada boundary.
  No codificar `DENY` como “se puede elevar con approval”; si la política runtime
  ofrece un grant ambiguo, detenerse y conservar el límite.

Los permission profiles son controles del shell/local command execution y de
filesystem/network compatibles; no reemplazan ACL del SO ni restringen
automáticamente MCP, browser, connectors u otras herramientas. La documentación
de subagents además dice que children heredan sandbox/permission mode actual del
parent y que overrides runtime del parent se reaplican al spawn incluso si el
custom agent declaró otros defaults. Por tanto, `default_permissions` por role
no es una garantía de ACL inmutable. La selección `elevated` se configura solo en
el proyecto experimental; no cambia el config global ni autoriza un fallback
`unelevated`. El smoke no-interactivo no calificó el perfil: su read-only denial
no debe etiquetarse como Olympus `DENY`, y el sandbox legacy de `--sandbox` no
es evidencia de `default_permissions`. La UI interactiva aún debe probar ALLOW,
ASK y DENY solo en fixtures sintéticos.

## Fuentes oficiales consultadas

Markdown actual de OpenAI/Codex, recuperado el 2026-09-29:

- [Instrucciones AGENTS.md](https://developers.openai.com/codex/agent-configuration/agents-md.md)
  — precedencia y jerarquía, `project_doc_fallback_filenames`.
- [Subagents](https://developers.openai.com/codex/agent-configuration/subagents.md)
  — custom agent TOML, modelos/effort, concurrencia, herencia de permisos,
  inspección y colección de resultados.
- [Configuration Reference](https://developers.openai.com/codex/config-file/config-reference.md)
  — config trusted por proyecto, aprobación, profiles, sandbox, agents, shell.
- [Permissions](https://developers.openai.com/codex/permissions.md)
  — filesystem/network profiles, writable roots y enforcement Windows.
- [Agent approvals & security](https://developers.openai.com/codex/agent-approvals-security.md)
  — aprobación, `request_permissions`, sandbox y protected paths.
- [Models](https://developers.openai.com/codex/models.md) y
  [model selection](https://developers.openai.com/codex/model-selection.md)
  — modelos actuales y reasoning effort.
- [Codex App Server](https://developers.openai.com/codex/app-server.md)
  — thread/turn/item lifecycle, status, children, approval, continuation/resume.
- [CLI](https://developers.openai.com/codex/cli.md),
  [MCP](https://developers.openai.com/codex/extend/mcp.md),
  [Skills](https://developers.openai.com/codex/build-skills.md),
  [Hooks](https://developers.openai.com/codex/hooks.md) y
  [Worktrees](https://developers.openai.com/codex/environments/git-worktrees.md)
  — primitives adyacentes y sus superficies.
