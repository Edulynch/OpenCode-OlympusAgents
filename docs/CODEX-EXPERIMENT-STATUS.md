# Estado del experimento Olympus → Codex

**OLYMPUS_CODEX_ADAPTER: SUPPORTED_WITH_DECLARED_GAPS**

Codex es el segundo adapter oficialmente soportado y queda modularizado desde
Olympus Core. La evidencia runtime adicional que ya existía y fue suministrada
para esta tarea confirma root Kael, Kael→Veyra, Kovan→Nox funcional,
fan-out/fan-in acotado de cuatro children, al menos dos concurrentes, entrega de
resultados, ALLOW directo y ASK nativo aprobado por usuario. No se repitieron
esos smokes durante la modularización. El smoke estricto Kovan→Nox falló
únicamente en el diagnóstico del retry; su caso funcional sigue PASS. La
evidencia pertenece al usuario y no fue reproducida en esta ejecución; no se
inventan IDs o logs ausentes. DENY duro, Aegis y la paridad del HUD siguen siendo
gaps/parcialidades explícitos, no motivos para debilitar Olympus Core.

## WHAT WORKS

- Branch `experiment/codex-compat` parte del baseline `c11d4f59370871a5c0978daab2512ea39c0928c0`; el perfil nuevo permanece fuera de master/beta.3.
- `.codex/config.toml`, `CODEX.md` y diez custom roles especialistas ahora son outputs generados por el adapter Codex. Kael se mantiene en el root; no hay `aegis.toml`.
- Codex CLI instalado: `0.159.1`; OpenCode CLI: `v2.0.20`.
- `python tests/codex/validate_profile.py`: PASS. Python/TOML validó config y los 10 outputs generados; el catálogo local `codex debug models --bundled` confirmó modelos/esfuerzos; referencias de roles, ausencia de Aegis, cap 4, roster/modelos/efforts OpenCode y renderer pasaron.
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
- Mapeo estático de OpenCode actual: 12 outputs generados desde `olympus/core/models.toml`; la qualification compara los modelos/efforts con la fuente canónica y verifica drift con el renderer.
- Research oficial actual de OpenAI/Codex recuperado el 2026-09-29 para instrucciones, custom agents, config, permissions, approvals, modelos, App Server, CLI, MCP, skills y hooks. Context7 no estuvo disponible; se consultaron directamente endpoints Markdown oficiales.
- Evidencia runtime previa suministrada por el usuario, no rerun: Kael root PASS; Kael→Veyra PASS; Kovan→Nox functional PASS; bounded fan-out/fan-in de 4 children PASS; concurrencia real observada de al menos 2 PASS; child-result delivery PASS; ALLOW `DIRECT_MAPPING`; ASK `ADAPTABLE` con aprobación nativa confirmada por el usuario.
- Codex permanece `DENY: GAP`, `AEGIS: GAP` y activity visibility `BASIC/PARTIAL`. Question centralization es `PARTIAL`; la reconciliación de un result perdido no se promueve a runtime PASS.

## STATIC ONLY

- TOML/config syntax, custom role roster y nombres se parsean estáticamente. La evidencia runtime cubre Kael, Veyra, Kovan, Nox y el fan-out/result delivery indicados arriba; no se calificó individualmente cada uno de los diez roles.
- El modelo/effort aparece en el catálogo bundled; no se inspeccionó en runtime el modelo seleccionado para un child.
- Codex documenta `CODEX.md` mediante `project_doc_fallback_filenames`, instrucciones jerárquicas y project config en proyectos trusted. Un registro previo informó que Codex cargó `CODEX.md`; la inspección `debug prompt-input` de esta continuación no expuso el texto/path del root, así que ese load no se vuelve a declarar como gate runtime reproducido. `codex exec --strict-config` terminó sin error de configuración, pero usó sandbox read-only y no demuestra por sí solo qué permission profile fue efectivo. `--strict-config` no es aceptado por `codex debug`; el CLI no tiene `codex debug agents`. `codex agents` es un browser de sesiones de agente del App Server, no una prueba de descubrimiento del catálogo de roles.
- La evidencia de cuatro children, fan-in, al menos dos simultáneos, entrega de resultados y ASK aprobada cubre los smokes ya ejecutados; no se repitieron. No implica que se haya medido cada opción del scheduler o enforcement de permisos.
- El enforcement de `olympus-project`/`olympus-readonly`, `windows.sandbox = "elevated"`, `request_permissions` y paths protegidos no se promueve a PASS. El rechazo read-only del CLI no-interactivo no cuenta como Olympus DENY.
- OpenCode: este host reporta `v2.0.20`; `opencode debug config` y `opencode debug agents` terminaron con exit 0. Un registro previo de `debug agents` fue `[]`, por lo que el discovery dinámico no se toma como gate resuelto. La qualification actual verifica 12 outputs contra Core/renderer; no hubo TUI/prompt conversacional.
- No se ejecutaron smokes OpenCode ni Codex durante esta modularización; el benchmark comparable continúa incompleto.

## GAPS

- `CODEX_AEGIS: GAP`: Codex no ofrece un mapping seguro demostrado para usuario explícitamente `/maintain` → Aegis inaccesible a Kael. El plane Aegis/OpenCode permanece intacto y no se instala role Aegis en Codex.
- La guía oficial permite custom prompts/config y permission profiles, pero no entrega el ACL por-role OpenCode. Los defaults de un child pueden ser reemplazados por sandbox/permission overrides runtime heredados del parent.
- `DENY` sigue siendo GAP: profiles read-only y policy no son una garantía hard equivalente a OpenCode. No está demostrado que cada approval/override respete siempre un boundary Olympus DENY.
- Enforcement Windows del perfil `elevated`, protección de recursos Olympus y restricciones cross-repository necesitan un smoke interactivo aislado. `unelevated` no es fallback aceptable para desbloquearlo.
- `thread/read`, eventos `turn/completed` y filtros de descendants son evidencia de API documentada, no prueba de recovery de un result perdido. La reconciliación de missing result permanece PARTIAL.
- El installer/VerifyOnly existente sigue gestionando OpenCode; no se añadió install/upgrade/rollback para Codex. Installer Codex es el siguiente trabajo, no un requisito de esta modularización.
- No se obtuvo costo monetario ni se compara quality/speed/cost con OpenCode.

## OPENCODE ADVANTAGES OBSERVED

- El código existente declara per-role model, effort, herramientas y permisos OpenCode; Kael está configurado como default y Aegis usa el user-explicit `/maintain`.
- El Activity plugin y contratos OpenCode se mantienen como adaptación específica; Codex usa su visibilidad nativa y no recrea el HUD.
- `.opencode/**` y `opencode.jsonc` conservan el contenido funcional beta.3, con marcadores generados y DENY de edición añadidos para Core/adapter sources. La qualification verifica roster, modelos y renderer, no identidad byte-a-byte con el baseline.
- No se observó ventaja medida de calidad/costo/velocidad: el benchmark OpenCode por tareas no se ejecutó.

## CODEX ADVANTAGES OBSERVED

- El runtime ofrece custom-agent TOML con model/effort por role, config local trusted, multi-agent y límite de threads, además de App Server thread/turn/item APIs y continuation/resume documentados.
- Permission profiles y preguntas de permisos filesystem/network son primitives nativas útiles, pero no sustituyen hard DENY por-role.
- Los dos smokes Codex root-only previos demostraron edición/lectura en fixtures. La invocation adicional normal `codex exec` mostró que el modo no interactivo es read-only y puede terminar exit 0 con la aceptación incumplida; no prueba routing ni da superioridad comparativa.
- No se observó ventaja comparativa de calidad/costo/velocidad.

## RISKS

- **Permissions/authority:** sandbox de Windows no calificado; root/child policy y runtime overrides pueden divergir. `codex exec` no interactivo sin `--sandbox` fue read-only; `--sandbox` toma el camino legacy y no califica `default_permissions`. Un `tool success` no prueba que no apareció UI de approval; un denial read-only tampoco equivale a Olympus DENY.
- **Lifecycle/results:** el fan-out/fan-in y entrega de resultados tienen evidencia runtime suministrada; recovery de un resultado faltante no está calificado. `idle`, ausencia de texto o un exit aislado no son prueba de DONE.
- **Question barrier:** Codex puede surfacear approval desde child thread directamente al usuario.
- **Session isolation:** thread independiente no implica workspace/worktree independiente; no permitir writers paralelos solapados.
- **Maintenance:** Aegis y su entrada explícita se quedan en OpenCode.
- **Drift:** `CODEX.md` y prompts TOML son outputs generados del adapter Codex. `render_harnesses.py check` detecta drift; cambiar semántica requiere modificar Core y calificar la representación.
- **Installer/global setup:** usuarios deben confiar proyecto; no hay sincronización ni installer Codex. No cambiar `.opencode/**` ni `opencode.jsonc` para reducir ese costo.
- **Benchmark bias:** la evidencia runtime disponible no establece calidad/costo/velocidad comparativos ni justifica una migración entre harnesses.

## NEXT EXPERIMENTS

1. En un Git fixture descartable y sesión Codex interactiva, confirmar trust/project config y sandbox Windows `elevated`; observar ALLOW, un ASK real y DENY sintético de path Olympus decoy, incluyendo exactamente qué reporta agent vs UI.
2. En fixture read-only, pedir Kael→Veyra para una pregunta de evidencia; guardar IDs, timestamps, terminalidad, result original y consumo por root. No repetir si el resultado queda ambiguo.
3. En fixture separado, implementación pequeña Kael→Kovan y validación→Nox; medir si el runner/test funciona bajo los permission profiles normales. No sumar Vera automáticamente.
4. En un repo fixture, investigar 2–4 items independientes y medir concurrencia efectiva, max-thread count, serialización, entrega y costo/tokens; recopilar toda la familia antes de cerrar.
5. Solo después de los gates anteriores, ejecutar el mismo conjunto de tareas en OpenCode y Codex para comparar resultados y tiempos; incluir caso largo/reanudación sin inducir corrupción o duplicación.
