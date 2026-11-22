# #180: matriz de evidencia de primera tarea — 2026-11-21

## Alcance y procedencia

Evidencia local de la candidata de trabajo asociada a #175 frente a la versión publicada v0.12.3; no cierra #180 ni acredita adopción por terceros. El baseline publicado es el commit inmutable `92eed5458b302b64d268b8ef7725cbc191810c8a` (v0.12.3, con assets `install.ps1` y `install.sh`); el baseline previo es `c0c955401e56b5ed41c66d789a9cf58943670dd4` (v0.12.2). La candidata parte de v0.12.3 y contiene cambios locales en prompts de Kael/Thales y documentación del instalador/flujo; no es una nueva versión publicada.

Enlaces: [issue #180](https://github.com/multica-ai/OpenCode-OlympusAgents/issues/180), [release v0.12.3](https://github.com/multica-ai/OpenCode-OlympusAgents/releases/tag/v0.12.3), [release v0.12.2](https://github.com/multica-ai/OpenCode-OlympusAgents/releases/tag/v0.12.2), [flujo actual de primera tarea](../../../docs/WORKFLOWS.md#first-task-in-a-plain-git-project). La referencia histórica #143 y el CI `44855193097` corresponden sólo a descubrimiento de v2.3.0 y fixtures, respectivamente; no son evidencia de una primera tarea en vivo.

## Matriz

| Plataforma / paso | Candidata frente a release | Estado y evidencia |
|---|---|---|
| Windows: instalación publicada | v0.12.3, `install.ps1` etiquetado, con rutas aisladas explícitas | **PASS observado.** PowerShell 7.6.10, Python 3.13.0 (`py -3`) y OpenCode 2.3.2. Origen `REMOTE_ARCHIVE`; `olympus version` → `olympus v0.12.3`; `doctor: ok`; `VerifyOnly` → `OLYMPUS_GLOBAL_VERIFY: opencode v0.12.3 PASS (read-only; 16 managed resources)`, salida 0. |
| Windows: desinstalación publicada | v0.12.3, `install.ps1 -Uninstall` con las mismas rutas aisladas | **PASS observado.** Salida 0; `OLYMPUS_GLOBAL_UNINSTALL: opencode REMOVED_MANAGED_RESOURCES_ONLY`; launcher, config, manifest y muestra administrada ausentes; almacén PATH aislado vacío y marcador ajeno intacto. El wrapper genérico de desinstalación no se ejecutó. |
| Windows: instalador genérico completo y actualización | Release v0.12.3 | **NOT_RUN.** El wrapper público no reenvía los argumentos de prueba basados en archivos PATH. Hace falta una cuenta Windows desechable/VM o una vía segura justificada. |
| Windows: descubrimiento nativo de la candidata | Árbol local #175 sobre v0.12.3; OpenCode real v2.3.2 | **PASS, sólo presencia y selección.** Con rutas aisladas explícitas: `debug config --standalone` seleccionó `default_agent=kael`; `debug agents --standalone` mostró los 11 IDs esperados; ambas llamadas terminaron con salida 0. El verificador de unicidad falló en su expresión: **unicidad no verificada**, no es evidencia de duplicados ni de fallo del CLI. |
| Candidata: render y límites | Árbol local #175 | **PASS determinista.** Render y `check` fuera del árbol de trabajo: 18 salidas coincidieron; no aparecieron nombres de prompts generados y se conservaron los límites. No prueba ejecución en vivo. |
| Candidata: fixture Python de documentación | Árbol local #175 | **Resultado de fixture, no tarea de agente.** La comprobación determinista/manual inicial falló como se esperaba (`2 items \| READY` en vez de `READY \| 2 items`, salida 1); tras aplicar el arreglo equivalente, una prueba falló como se esperaba y una pasó. No representa uso autónomo ni por terceros. |
| Windows: intento no interactivo de primera tarea de la candidata, fixture aislado nuevo | Árbol local #175; OpenCode v2.3.2; `--agent kael`; modelo solicitado `openai/gpt-6.2-sol` | **EJECUCIÓN FALLIDA; evaluación de Kael NO CONFIRMADA.** El 2026-11-21 `opencode run --standalone --model openai/gpt-6.2-sol --agent kael --format json ...` terminó con salida 1. La prueba inicial y la repetición independiente posterior `python -B -m unittest -v test_status.StatusTest.test_status_precedes_detail` terminaron ambas con 1 por el mismo desacuerdo: `2 items \| READY` frente a `READY \| 2 items`; el diff del worktree contra el baseline del fixture staged fue vacío, sin edición. Renderer y descubrimiento de la candidata pasaron en este fixture (10 observaciones de PATH aislado, 11 IDs). En esta ejecución no había `default_agent` global explícito: Kael se seleccionó con el argumento CLI; esto no sustituye ni altera la observación nativa separada de la fila anterior. Sólo se observó un evento JSON sin tipo recuperable ni diagnóstico; no hubo ID de modelo reportado en runtime, respuesta normal ni metadata de parada terminal/hijos. El proceso externo terminó, pero no se confirmó el estado terminal de la familia/Kael. **Causa desconocida**: no inferir autenticación, llamada exitosa al modelo, fallo de lanzamiento, modelo ausente ni defecto del producto. |
| Windows: primera tarea interactiva posterior, en la misma fixture aislada | Candidata #175; OpenCode v2.3.2; resultado y comandos aportados por la persona usuaria | **PASS reportado manualmente.** La persona usuaria informó que inició sesión en OpenAI en esa sesión, envió el prompt y recibió `OK`, atribuido a `Kael · GPT-6.2 Sol`. Es un resultado interactivo distinto del intento no interactivo anterior; la secuencia posterior no establece la causa de su salida 1. Detalle del test y diff en la adenda bajo la matriz. |
| WSL2 Ubuntu 24.04.2: instalación publicada | Release v0.12.3, `install.sh` público; Python 3.12.3, curl 8.5.0, Git 2.43.0, POSIX `sh` | **PASS observado.** Usuario regular UID 1000; `/` pertenece a 0:0. Instalación aislada → `Olympus install: ok`, `olympus v0.12.3`, `doctor: ok`. `doctor` no demuestra disponibilidad de binario/modelo. |
| WSL2: actualización y desinstalación | v0.12.2 → v0.12.3 | **PASS observado.** `Selected release: v0.12.3`, `olympus update: ok`, versión v0.12.3. Seguimiento verificó las 16 eliminaciones de archivos, marcador actual, paquete activo y ausencia de launcher/journal; el marcador sobrevivió, los locks estables permanecieron según contrato; `uninstall: ok`, `Installation: removed`, salida 0. La aserción previa de ausencia del directorio padre era inválida, no un fallo del producto. |
| WSL2: descubrimiento de candidata / primera tarea en vivo | Candidata #175; OpenCode portable v2.3.2 | **NOT_RUN.** `opencode --version` en PATH Linux limpio terminó con 127. Luego se identificó el asset portable oficial [v2.3.2](https://github.com/anomalyco/opencode/releases/tag/v2.3.2), pero no se intentó adquirirlo/probarlo: esa operación requería aprobación explícita. El antecedente documentado de WSL con v2.3.2 no queda refutado por no tener binario local. |
| Linux nativo / macOS | Release y candidata | **NOT_RUN.** Sin verificación en esas plataformas. |

### Adenda: evidencia interactiva manual reportada

La matriz conserva la fecha del registro original, 2026-11-21; la fecha/hora exactas de esta interacción manual no se verificaron. La persona usuaria aportó el resultado de la sesión interactiva en la misma fixture Windows `first-live-sol`:

- `py -3 -B -m unittest -v test_status.StatusTest.test_status_precedes_detail` → `Ran 1 test` / `OK`.
- `git status --short` → `AM status.py` y `A  test_status.py`. Los archivos de fixture estaban staged como baseline; sólo `status.py` tenía un cambio en el worktree.
- `git diff -- status.py` mostró sólo este cambio:

  ```diff
  -    return f"{detail} | {status}"
  +    return f"{status} | {detail}"
  ```

- `git diff --check` mostró sólo un aviso LF/CRLF; no se mostró error de whitespace. El código de salida no fue aportado.

La salida `OK`, el test y el diff son evidencia manual reportada por la persona usuaria, no una captura independiente. No se aportó transcript completo ni evidencia nativa de delegación, agente hijo, solicitud/decisión de permisos o ejecución terminal; no se afirma ninguno de esos hechos. El inicio de sesión informado ocurrió antes de la interacción manual y no demuestra que la autenticación causara el resultado del intento no interactivo previo.

## Límites y seguimiento

- La instalación, el descubrimiento, los fixtures, el intento no interactivo fallido y el PASS interactivo reportado son evidencias distintas. La causa del exit 1 anterior continúa desconocida; el PASS posterior no la explica. La persona usuaria informó iniciar sesión para la interacción manual; no se infiere estado de autenticación previo ni se afirma que el agente modificara credenciales o perfiles.
- El PASS manual confirma el resultado del fixture según la evidencia aportada, pero no prueba delegación de Kael, ejecución de agente hijo ni observabilidad de ASK/aprobación nativa. No hace falta repetir la tarea para registrar esta evidencia; esos detalles permanecen sin verificar.
- Para WSL, pedir aprobación antes de adquirir/probar el asset portable. Para endpoints genéricos de Windows, usar una cuenta/VM desechable o justificar por separado una ruta segura. No ampliar afirmaciones de plataforma mientras falte esa evidencia.
- No se publicó, confirmó ni cerró este informe mediante commit, push o comentario remoto. #178 aporta distinciones de evidencia aplicadas aquí; resolver ese issue no es requisito de este informe.
