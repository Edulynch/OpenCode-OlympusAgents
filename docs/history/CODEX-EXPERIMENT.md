# Olympus Codex experiment — comparison matrix

Esta matriz conserva el trabajo parcial y no convierte evidencia ausente en
PASS. Las cifras históricas Codex se conservaron sin repetir sus smokes. Esta
continuación añadió qualification estática, research oficial y un diagnóstico
root-only de `codex exec`; este último no cumplió la edición y no califica la
calidad del modelo ni los permission profiles interactivos. Las filas OpenCode
no son una comparación de rendimiento: sus smokes equivalentes siguen
pendientes.

## Cómo iniciar cada runtime

En PowerShell, desde el worktree experimental actual:

**OpenCode** — usa `opencode.jsonc`, default agent `kael`, sin tocar beta.3:

```powershell
Set-Location -LiteralPath 'C:\Users\eduma\OneDrive\WORKSPACE\Personal\Tools\OpenCode-OlympusAgents-codex-exp'
opencode
```

**Codex** — usa `.codex/config.toml`, `.codex/agents/` y `CODEX.md`:

```powershell
Set-Location -LiteralPath 'C:\Users\eduma\OneDrive\WORKSPACE\Personal\Tools\OpenCode-OlympusAgents-codex-exp'
codex
```

Equivalente: `codex --cd "C:\Users\eduma\OneDrive\WORKSPACE\Personal\Tools\OpenCode-OlympusAgents-codex-exp"`.
Codex solo carga las capas `.codex/` del proyecto cuando éste está trusted; si
el CLI pregunta, inspeccionar y confiar este repositorio explícitamente antes de
calificarlo. No cambiar la configuración global para evitar ese control. El
perfil selecciona `windows.sandbox = "elevated"` localmente; no sustituirlo por
`unelevated` para forzar un smoke.

CLI observado en el host: Codex `0.159.1`, OpenCode `v2.0.20`. Los fixtures bajo
`tests/codex/fixtures/` son sintéticos. Los smokes con cambios deben copiar el
fixture a un Git root temporal desechable; no usarlos para escribir en este
worktree Olympus.

La CLI `codex exec` no interactiva sin selección explícita de sandbox usa
read-only; `--sandbox` usa la vía legacy y no califica los `default_permissions`
de este perfil. Los smokes anteriores que usaron `--sandbox workspace-write`
estaban restringidos a fixtures temporales y no prueban los perfiles normales.
No inferir que una tarea interactiva tuvo cero approvals a partir de una
ejecución no interactiva.

## Criterios

- PASS requiere aceptación funcional, scope intacto y validación terminada.
- Registrar aprobación solo si se observó la UI/runtime; `0 observado` no prueba
  que una UI interactiva no hubiera aparecido.
- Una delegación solo cuenta con identity, terminal result y consumo por Kael
  reconciliados. Sin child no se califica result lifecycle.
- `RETRIES` cuenta reejecuciones de tarea. Un comando de CLI rechazado antes de
  comenzar no es retry de tarea; mantenerlo en notas.
- Wall time mide inicio de invocation a resultado terminal; token usage solo si
  el runtime lo reportó. No estimar costos.

## Resultados registrados

| TASK | RUNTIME | SUCCESS | WALL_TIME | CHILDREN | RETRIES | USER_APPROVALS | RESULT_LIFECYCLE_ERRORS | UNNECESSARY_ORCHESTRATION | MODEL | EFFORT | TOKEN/COST DATA IF AVAILABLE | NOTES |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| Trivial one-file edit | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Smoke equivalente no ejecutado. |
| Trivial one-file edit | Codex | PASS, root-only | 109.9 s | 0 | 1 revalidación segura | 0 observado | 0 observado, sin children | 0 observado | `gpt-6.1-sol` | `high` configurado; no emitido por evento | 170,393 input (148,224 cached), 717 output, 73 reasoning; costo no disponible | Editó y verificó `target.md`. Primer intento terminó sin cumplir aceptación porque el sandbox read-only dejó `Status: pending`; se verificó que el fixture no había cambiado y se repitió la misma edición con workspace-write limitado al Git root temporal. No probó Kovan ni los permission profiles normales. |
| Trivial edit con config de proyecto, vía `codex exec` | Codex | BLOCKED: sandbox read-only | 16 s | 0 | 0 | 0 observado; sin TTY | 0: `turn.completed`, salida final consumida | 0 observado | `gpt-6.1-sol` | `high` configurado; no emitido por evento | 26,859 input (20,480 cached), 178 output; costo no disponible | `--strict-config`, sin `--sandbox`; `agents.enabled=false` por seguridad. El patch fue rechazado (`writing is blocked by read-only sandbox`), el fixture quedó `Status: pending`. Exit code 0 no significó aceptación. El `.codex/` copiado coincide con el perfil final; el `CODEX.md` fixture precede las últimas aclaraciones de authority/barrier. No prueba `default_permissions`. |
| Repository exploration | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Delegación no comparada. |
| Repository exploration / Kael → one specialist | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | Kael→Veyra no ejecutado; Aegis no puede lanzar/delegar un child. Discovery y routing permanecen estáticos. |
| Functional implementation | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Smoke separado no ejecutado. |
| Functional implementation | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | No existe resultado separado del caso implementation+tests. |
| Bug diagnosis | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Pendiente. |
| Bug diagnosis | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | Argus/Talos no invocados. |
| Implementation + tests | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Pendiente. |
| Implementation + tests | Codex | PARTIAL | 69.7 s | 0 | 0 | 0 observado | 0 observado, sin children | 0 observado | `gpt-6.1-sol` | `high` configurado; no emitido por evento | 84,593 input (77,824 cached), 501 output, 45 reasoning; costo no disponible | Codex editó solo `calculator.py`; su `python -m unittest -v` falló dentro del sandbox porque `python` no estaba en PATH. Aegis ejecutó el mismo comando en el fixture temporal: 2 tests PASS. No equivale a Kovan→Nox. |
| Architecture | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Pendiente. |
| Architecture | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | Orin no invocado. |
| Execution planning | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Pendiente. |
| Execution planning | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | Atlas no invocado. |
| Parallel research (2–4 independent items) | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Cap y entrega no comparados. |
| Parallel research (2–4 independent items) | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | Aegis no puede lanzar/delegar subagents; cap efectivo, serial/paralelo, duplicación y entrega no medidos. |
| Authority / permission | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Fixture de approvals no ejecutado. |
| Authority / permission | Codex | PARTIAL | 16 s | 0 | 0 | 0 observado; sin TTY | 0 lifecycle errors observados | 0 | `gpt-6.1-sol` | `high` configurado | 26,859 input (20,480 cached), 178 output; costo no disponible | El `exec` no interactivo denegó una escritura de workspace por su sandbox read-only; no validó ALLOW/DENY del permission profile, ASK real, UI ni enforcement Windows. Solo fixture sintético. |
| Long-running child / result handling | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | No se indujo el fallo upstream. |
| Long-running child / result handling | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | Sin child, no hay medida runtime de continuation, cancellation, missing result ni entrega. No se observó `No tool output found` ni se declara ausente un equivalente. |

## Interpretación y límites

- Los dos registros Codex son root-only y usaron una sandbox override de fixture;
  no demuestran invocación de custom agents ni enforcement del profile
  `olympus-project`/`olympus-readonly`.
- Dos invocaciones anteriores (`--no-daemon` y `--ask-for-approval` en posición
  no aceptada por el parser de `exec`) terminaron antes de iniciar tarea. No
  cuentan como retries de tarea ni como resultado funcional.
- La validación externa de 2 unit tests pasó desde el directorio correcto del
  fixture. Un primer harness host-side desde otro directorio dio `Ran 0 tests`,
  exit 5; se corrigió el working directory. No cambió ningún archivo Olympus.
- Los tokens provienen del evento `turn.completed`; no hubo costo monetario
  reportado. No inventar ni extrapolar cifras.
- En esta continuación se auditó el perfil, se amplió la qualification estática
  y se consultaron docs oficiales actuales. Una invocation adicional de
  `codex exec` llegó a `turn.completed`, pero su edición no cumplió aceptación y
  el fixture quedó intacto; no se iniciaron smokes con children. El límite
  read-only del CLI no interactivo impide usar esa invocation para demostrar
  ALLOW/DENY del perfil. Routing real, question/result barriers y lifecycle de
  children siguen pendientes, no PASS.
- El `codex exec` nuevo usó un Git root desechable bajo el área temporal
  `opencode`, copias de `.codex/` y `CODEX.md`, `--strict-config`, y overrides
  limitados a desactivar agents/MCP no usados. No pasó `--sandbox`. La CLI
  devolvió exit 0, cinco eventos JSONL incluido `turn.completed`, pero la
  respuesta terminal informó el rechazo de escritura y el host verificó que no
  cambió ningún archivo. Se recolectó el resultado original antes de limpiar.
- La salida de shell recolectada tras el restart reporta `opencode debug config`
  exit 0 y `opencode debug agents` exit 0 con Kael; el stdout crudo no se guardó
  como archivo de repo. Un resultado OpenCode anterior devolvió `[]` para
  `debug agents`. Se conservan ambas observaciones y discovery dinámico queda
  sin resolver. Qualification estática confirma 12 fuentes/roles y modelos sin
  cambios contra baseline; no hubo TUI ni prompt conversacional.
