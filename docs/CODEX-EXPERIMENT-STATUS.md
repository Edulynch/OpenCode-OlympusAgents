# Estado del experimento Olympus → Codex

**OLYMPUS_CODEX_EXPERIMENT: PARTIAL**

El perfil experimental y sus qualifications estáticas están implementados. Ya
hay evidencia previa de dos tareas root-only en fixtures, una PASS y otra
PARTIAL; una invocation adicional `codex exec` terminó sin cumplir la edición
porque su sandbox era read-only. Faltan gates runtime importantes: uso de roles,
paralelismo, approvals interactivos, enforcement real de permisos Windows y
lifecycle de child/results. No se declara ganador entre runtimes.

## WHAT WORKS

- Branch `experiment/codex-compat` parte del baseline `c11d4f59370871a5c0978daab2512ea39c0928c0`; el perfil nuevo permanece fuera de master/beta.3.
- `.codex/config.toml`, `CODEX.md` y diez custom roles especialistas ya existían como trabajo parcial. Fueron auditados y reutilizados; no hay `aegis.toml` ni se duplicó Kael como child.
- Codex CLI instalado: `0.159.1`; OpenCode CLI: `v2.0.20`.
- `python tests/codex/validate_profile.py`: PASS. Python/TOML validó config y los 10 TOML; el catálogo local `codex debug models --bundled` confirmó modelos/esfuerzos; referencias Codex, ausencia de Aegis, cap 4, roster/modelos/efforts OpenCode y ausencia de cambios OpenCode contra el baseline pasaron.
- La tabla ROLE conserva Kael/Sol `gpt-6.1-sol high`, especialistas Sol en Sol con effort original, Luna en `gpt-6-luna max`; Thales continúa `xhigh`. No queda `gpt-6-sol` funcional en perfiles Codex/OpenCode. Literales de esa forma en tests de migración/detección son fixtures negativos, no configuración runtime.
- Evidencia previa auditada: Codex root-only completó una edición trivial de fixture en 109.9 s con verificación directa, 0 children y una revalidación segura después de un intento read-only que no cumplió aceptación. No valida Kovan ni permission profile normal.
- Evidencia previa auditada: Codex root-only cambió la función del fixture de calculadora en 69.7 s. Su comando unittest falló en el sandbox por no encontrar `python`; Aegis ejecutó host-side los mismos 2 tests en el fixture temporal y pasaron. El caso sigue PARTIAL y no cuenta como Kovan→Nox.
- Smoke adicional de esta continuación: `codex exec --strict-config --json` en
  un Git root desechable terminó con exit 0 y evento `turn.completed` en 16 s;
  el root intentó la edición pero Codex la rechazó por `read-only sandbox`.
  `target.md` siguió `Status: pending`, no cambió ningún archivo y el resultado
  terminal se consumió. Fueron 26,859 input tokens (20,480 cached) y 178 output;
  costo no disponible. `agents.enabled=false` se pasó como override para que
  esta prueba no lanzara children. No califica el fast path Olympus ni el
  enforcement del profile.
- Mapeo estático de OpenCode actual: 12 roles; config declara Kael como default y el runtime model esperado. La qualification nueva compara los modelos/efforts del roster con la tabla y verifica que `.opencode/**` y `opencode.jsonc` sigan idénticos al baseline.
- Research oficial actual de OpenAI/Codex recuperado el 2026-09-29 para instrucciones, custom agents, config, permissions, approvals, modelos, App Server, CLI, MCP, skills y hooks. Context7 no estuvo disponible; se consultaron directamente endpoints Markdown oficiales.

## STATIC ONLY

- TOML/config syntax, custom role roster y nombres se parsean estáticamente; no se demostró spawn/discovery runtime de los 10 roles.
- El modelo/effort aparece en el catálogo bundled; no se inspeccionó en runtime el modelo seleccionado para un child.
- Codex documenta `CODEX.md` mediante `project_doc_fallback_filenames`, instrucciones jerárquicas y project config en proyectos trusted. Un registro previo informó que Codex cargó `CODEX.md`; la inspección `debug prompt-input` de esta continuación no expuso el texto/path del root, así que ese load no se vuelve a declarar como gate runtime reproducido. `codex exec --strict-config` terminó sin error de configuración, pero usó sandbox read-only y no demuestra por sí solo qué permission profile fue efectivo. `--strict-config` no es aceptado por `codex debug`; el CLI no tiene `codex debug agents`. `codex agents` es un browser de sesiones de agente del App Server, no una prueba de descubrimiento del catálogo de roles.
- `agents.max_concurrent_threads_per_session = 4`, suppress-recursion por role, routing selectivo, trivial fast path, permission profiles y boundaries son configuración/policy estática. No se midieron con children.
- No se probó enforcement de `olympus-project`/`olympus-readonly`, `windows.sandbox = "elevated"`, ALLOW/ASK/DENY, request_permissions, approvals o paths protegidos en runtime. El rechazo read-only del CLI no-interactivo no cuenta como Olympus DENY.
- OpenCode: este host reporta `v2.0.20`; la salida de shell recolectada tras el restart en esta continuación muestra `opencode debug config` exit 0 y `opencode debug agents` exit 0 con Kael. El stdout crudo no se guardó como archivo de repo; un registro previo de `debug agents` fue `[]`, por lo que el discovery dinámico no se toma como gate resuelto. Qualification estática verifica 12 fuentes/roles, modelos y ausencia de cambios contra baseline; no hubo TUI/prompt conversacional.
- Las filas experimentales OpenCode no se ejecutaron; el benchmark comparable está incompleto.

## GAPS

- `CODEX_AEGIS: GAP`: Codex no ofrece un mapping seguro demostrado para usuario explícitamente `/maintain` → Aegis inaccesible a Kael. El plane Aegis/OpenCode permanece intacto y no se instala role Aegis en Codex.
- La guía oficial permite custom prompts/config y permission profiles, pero no entrega el ACL por-role OpenCode. Los defaults de un child pueden ser reemplazados por sandbox/permission overrides runtime heredados del parent.
- `ALLOW/ASK/DENY` no es equivalente: profiles/approval cubren paths o categorías distintas; `request_permissions` puede solicitar permisos de filesystem/network. No está demostrado que cada approval/override respete siempre un boundary Olympus DENY.
- Enforcement Windows del perfil `elevated`, protección de recursos Olympus y restricciones cross-repository necesitan un smoke interactivo aislado. `unelevated` no es fallback aceptable para desbloquearlo.
- No hay smoke real Kael→Veyra, Kovan→Nox, especialistas, max 4 children, recolección de results, pregunta de child, cancellation o recovery. `codex agents`/`/agent` permite inspeccionar sesiones, pero no se validó el ciclo.
- `thread/read`, eventos `turn/completed` y filtros de descendants son evidencia de API documentada, no prueba de recovery de un result perdido. No se observó `No tool output found` ni se puede concluir que Codex carezca de algo equivalente.
- El installer/VerifyOnly existing no gestiona Codex; no se añadió install/upgrade/rollback para Codex. Se conserva fuera de esta primera prueba.
- No se obtuvo costo monetario ni se compara quality/speed/cost con OpenCode.

## OPENCODE ADVANTAGES OBSERVED

- El código existente declara per-role model, effort, herramientas y permisos OpenCode; Kael está configurado como default y Aegis usa el user-explicit `/maintain`.
- El Activity plugin y contratos OpenCode no se portaron mediante equivalencias no demostradas.
- `.opencode/**` y `opencode.jsonc` no cambiaron. La qualification nueva verifica roster/modelos y que esos archivos coincidan con el baseline.
- No se observó ventaja medida de calidad/costo/velocidad: el benchmark OpenCode por tareas no se ejecutó.

## CODEX ADVANTAGES OBSERVED

- El runtime ofrece custom-agent TOML con model/effort por role, config local trusted, multi-agent y límite de threads, además de App Server thread/turn/item APIs y continuation/resume documentados.
- Permission profiles y preguntas de permisos filesystem/network son primitives nativas útiles para probar, aunque beta/partial y no equivalentes por sí solas a Olympus authority grants.
- Los dos smokes Codex root-only previos demostraron edición/lectura en fixtures. La invocation adicional normal `codex exec` mostró que el modo no interactivo es read-only y puede terminar exit 0 con la aceptación incumplida; no prueba routing ni da superioridad comparativa.
- No se observó ventaja comparativa de calidad/costo/velocidad.

## RISKS

- **Permissions/authority:** sandbox de Windows no calificado; root/child policy y runtime overrides pueden divergir. `codex exec` no interactivo sin `--sandbox` fue read-only; `--sandbox` toma el camino legacy y no califica `default_permissions`. Un `tool success` no prueba que no apareció UI de approval; un denial read-only tampoco equivale a Olympus DENY.
- **Lifecycle/results:** la guía asegura espera/colección de resultados solicitados, pero el propio experimento no vio child/result. `idle`, ausencia de texto o un exit aislado no son prueba de DONE.
- **Question barrier:** Codex puede surfacear approval desde child thread directamente al usuario.
- **Session isolation:** thread independiente no implica workspace/worktree independiente; no permitir writers paralelos solapados.
- **Maintenance:** Aegis y su entrada explícita se quedan en OpenCode.
- **Duplicación:** root `CODEX.md` y prompts TOML preservan límites Olympus de forma específica a Codex; modificar principios requiere mantener ambos perfiles alineados.
- **Installer/global setup:** usuarios deben confiar proyecto; no hay sincronización ni installer Codex. No cambiar `.opencode/**` ni `opencode.jsonc` para reducir ese costo.
- **Benchmark bias:** la única evidencia runtime sigue root-only con sandbox override de fixture; no autoriza decisión de migración.

## NEXT EXPERIMENTS

1. En un Git fixture descartable y sesión Codex interactiva, confirmar trust/project config y sandbox Windows `elevated`; observar ALLOW, un ASK real y DENY sintético de path Olympus decoy, incluyendo exactamente qué reporta agent vs UI.
2. En fixture read-only, pedir Kael→Veyra para una pregunta de evidencia; guardar IDs, timestamps, terminalidad, result original y consumo por root. No repetir si el resultado queda ambiguo.
3. En fixture separado, implementación pequeña Kael→Kovan y validación→Nox; medir si el runner/test funciona bajo los permission profiles normales. No sumar Vera automáticamente.
4. En un repo fixture, investigar 2–4 items independientes y medir concurrencia efectiva, max-thread count, serialización, entrega y costo/tokens; recopilar toda la familia antes de cerrar.
5. Solo después de los gates anteriores, ejecutar el mismo conjunto de tareas en OpenCode y Codex para comparar resultados y tiempos; incluir caso largo/reanudación sin inducir corrupción o duplicación.
