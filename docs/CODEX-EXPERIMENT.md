# Olympus Codex experiment — comparison matrix

Esta matriz conserva el trabajo parcial y no convierte evidencia ausente en
PASS. Las cifras Codex son las que ya constaban en el experimento auditado; no
se repitieron esos smokes. Esta continuación añadió qualification estática y
research oficial, no nuevas tareas de calidad/modelo. Las filas OpenCode no son
una comparación de rendimiento: sus smokes equivalentes siguen pendientes.

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
| Repository exploration | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Delegación no comparada. |
| Repository exploration | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | Kael→Veyra no ejecutado; ningún resultado de child observado. |
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
| Parallel research (2–4 independent items) | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | No se inició child; cap efectivo, serial/paralelo, duplicación y entrega no medidos. |
| Authority / permission | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | Fixture de approvals no ejecutado. |
| Authority / permission | Codex | NOT_RUN | — | — | — | — | — | — | — | — | — | No se observó perfil Windows interactivo, ASK real ni DENY sintético. `--sandbox workspace-write` omite los `default_permissions`; no se usó sobre Olympus ni se atribuyó ausencia de UI a cero prompts. |
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
  y se consultaron docs oficiales actuales. No se iniciaron nuevos smokes con
  children. Por eso routing real, question/result barriers y lifecycle siguen
  pendientes, no PASS.
