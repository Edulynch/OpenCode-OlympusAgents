# Ledger de evidencia — línea base v0.4.9

**Commit**: `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**Release publicada**: [v0.4.9](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.4.9), 2026-10-14 05:29:18 UTC.  
**Fecha de auditoría**: 2026-10-14.

Este ledger respalda las diez fichas en [specs/README.md](../../README.md) y [COVERAGE.md](COVERAGE.md). Las rutas relativas apuntan a la línea base local. Un source/test file acredita código o contrato existente; no afirma que se ejecutó ahora.

## Clases y precedencia

Se prefiere el código, configuración efectiva versionada y contratos deterministas fijados al commit. Informes de issues, experimentos y notas de fases son contexto atribuido y no sustituyen un artefacto nativo. Un test presente no significa PASS.

| Clase | Significado |
|---|---|
| **D** | Contrato determinista comprobable en fuente o fixture versionado. Esta auditoría no implica ejecución del checker. |
| **S** | Simulación, stub, synthetic trace o prueba con runtime simulado; no es sesión de agente ni UI nativa. |
| **R** | Proyección/captura archivada de una observación nativa en el repositorio. Puede estar redactada o incompleta; no es raw export, ejecución actual ni prueba de lo que la captura no contiene. |
| **H** | Informe histórico o externo atribuido. No se releen raw logs salvo donde se indica expresamente; no repetir runtime. |
| **U** | Desconocido, GAP o evidencia insuficiente. |

## Identidad del baseline

| ID | Clase | Observación | Referencia / límite |
|---|---|---|---|
| E000-1 | D | La observación local `git rev-parse HEAD master 'v0.4.9^{}'` devuelve para las tres refs `c30a19dd410b1815f4591b204615cae0dd9e9a5f`. | Identidad del baseline de esta auditoría; el comando sólo observa refs. |
| E000-2 | H | GitHub FAST CI reportó éxito para el SHA `c30a19d…`; CodeQL reportó éxito en la corrida correspondiente. | [FAST run 38516290563](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38516290563), completada 05:23:10 UTC; [CodeQL run 38516290529](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38516290529). No equivalen a ejecución remota del instalador ni a runtime de agentes. |
| E000-3 | H | PR #65 fusionado 2026-10-14 05:22:30 UTC: UX de instalador y cualificación local pasaron con OpenCode stubbed; validación del tag remoto inmutable aún era gate de publicación. | [PR #65](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/65). No se encontró aquí un registro observado de instalación desde ese tag remoto. |
| E000-4 | H | La página de release registra publicación de v0.4.9 el 2026-10-14 05:29:18 UTC. | [Release v0.4.9](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.4.9). La metadata de publicación no prueba aceptación de instalación remota. |

## 001 — Core canónico y adaptadores

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E001-1 | D | [`models.toml`](../../../olympus/core/models.toml#L1) (familias, IDs por runtime y esfuerzo para 12 roles); [`identities.toml`](../../../olympus/core/identities.toml#L1); `role_ids` y `checked_sources` (`scripts/render_harnesses.py`, líneas 55–105); `role_model` (108–116); `opencode_outputs` (188–269) y `codex_outputs` (272–319). | El renderer usa stems de `roles/*.md` para el roster, no consume el contenido de esos archivos. Consume modelos, identidades, orquestación, capacidades, sección TFR de routing y policy OpenCode de mantenimiento; no inyecta los cuerpos de `authority.md` ni `result-lifecycle.md`. Los adapters sí mantienen texto de política correspondiente por separado. Byte check no prueba sync semántica. |
| E001-2 | D | [`tests/harness-core/qualify.py`](../../../tests/harness-core/qualify.py#L132) revisa identidades/modelos, render y capacidades, líneas 132–174, 227–263 y 296–352. | Fuente de cualificador determinista; no ejecutado durante esta auditoría. No acredita prompts ni runtime. |
| E001-3 | D | `render_harnesses.py`, `outputs_for` línea 346 y `check` líneas 358–376; [docs/HARNESSES.md](../../../docs/HARNESSES.md); Codex [`root.md`](../../../olympus/harnesses/codex/root.md#L1). | 12 agentes OpenCode y 10 especialistas Codex; Kael como root thread representado por `root.md`; Codex no tiene Aegis. Comparar bytes no prueba equivalencia de contenido. |

## 002 — Orquestación acotada

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E002-1 | D | [routing policy](../../../olympus/policies/routing.md#L3), límite Core en [`orchestration.toml`](../../../olympus/policies/orchestration.toml); OpenCode [config](../../../olympus/harnesses/opencode/config.jsonc#L3) y [Kael prompt](../../../olympus/harnesses/opencode/agent-prompts/kael.md#L3); Codex [`config.toml`](../../../olympus/harnesses/codex/config.toml#L3) y [`root.md`](../../../olympus/harnesses/codex/root.md#L90). | Core limita children abiertos a cuatro; configuración/prompt expresan reglas, no un scheduler de Olympus. Codex configura límite nativo 4 y permite multi-agent en el root; ciertos perfiles child establecen `[agents] enabled=false`. |
| E002-2 | S/R | [Phase 11 RUNME](../../../tests/phase11-integrated-routing/RUNME.md#L3), casos sintéticos A–L separados de proyecciones nativas archivadas B3, C, E2, H, K en `tests/phase11-integrated-routing/`. | No todos los caminos se ejercitaron. Caso C incluye Nox de cualificación además de Kael→Kovan. E2 registra ruta Talos corregida tras fallo E1; su metadata marca proyección/redacción y `RAW_EXPORT_PERSISTED:false`, y el starting head es `3e5b2af…`, distinto al baseline de esta ficha. K tiene campos de ruta/concurrencia null. No implica raw export, runtime actual, scheduler ni speedup. Phase 11 no incluye traza Codex nativa; consultar Phase 12 como registro separado. |
| E002-3 | H/U | [Issue #41](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/41); registros Phase 12 atribuidos durante la auditoría. | Síntoma de fidelidad de prompt reportado, sin causa demostrada. Los registros Phase 12 tienen versiones/config efectivos incompletos; no se releen aquí logs nativos originales. |

## 003 — Autoridad y confianza

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E003-1 | D | [authority semantics](../../../olympus/policies/authority.md#L1); [OpenCode config](../../../olympus/harnesses/opencode/config.jsonc#L5); [Kael permissions](../../../olympus/harnesses/opencode/agent-metadata/kael.md#L18) y [Kovan permissions](../../../olympus/harnesses/opencode/agent-metadata/kovan.md#L5); sus prompts contienen además política textual; [Codex config](../../../olympus/harnesses/codex/config.toml#L19); [Codex root permissions](../../../olympus/harnesses/codex/root.md#L90). | OpenCode expresa external/edit asks, shell/subagent denies, paths y allowlists. Rechazo/cancelación detiene la operación; no habilita bypass. Codex expresa filesystem profiles y approval. Configuración efectiva declarada no es ACL inmutable. Codex `DENY = GAP`. |
| E003-2 | D/S | [`tests/authority/qualify.ps1`](../../../tests/authority/qualify.ps1#L580), aislamiento/probes líneas 580–674 y 723–903; native ASK UI not assessed lines 1245–1251. | Contratos estáticos, casos sintéticos y probes de config/API; salida de runtime no presente en la evidencia revisada. No cubre cada decisión/ventana de aprobación. |
| E003-3 | H/U | Reportes de ASK nativo suministrados por usuario y [Codex compatibility](../../../docs/CODEX-COMPATIBILITY.md). | Atribuidos; no constituyen ejecución repetida en esta auditoría. DENY Codex permanece GAP; profiles no se tratan como ACL inmutable y overrides de sesión son desconocidos. |

## 004 — Lifecycle de resultados

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E004-1 | D | [result lifecycle policy](../../../olympus/policies/result-lifecycle.md#L3); Kael prompt OpenCode líneas 601–608 y 847–888; [Codex root](../../../olympus/harnesses/codex/root.md#L72). | Ledger Kael es instrucción en prompt, no scheduler propio. Codex documenta lifecycle, preguntas/completion parcialmente. La policy permite continuar la operación original tras evidencia reconciliada de no ejecución, o un retry correctivo acotado tras consumir el resultado terminal y detectar falla material de aceptación con evidencia/estrategia nueva; nunca replay ciego de efectos completos, resultados vivos o desconocidos. |
| E004-2 | D/S | [`tests/result-reconciliation/qualify.ps1`](../../../tests/result-reconciliation/qualify.ps1#L12), líneas 165/201; [`tests/question-barrier/qualify.ps1`](../../../tests/question-barrier/qualify.ps1#L97). | Fixtures deterministas/sintéticas; la carrera live figura como NOT AUTOMATED. No ejecutados ahora. |
| E004-3 | R/U | Proyecciones nativas archivadas B3, E2 y H en `tests/phase11-integrated-routing/`; metadata de E2 registra `projection_and_redaction`, disponibilidad de contenido y `RAW_EXPORT_PERSISTED:false`; [issue #8: resume ordinario](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-5934781194), [reporte posterior de compaction](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6093432997) y [auditoría final](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6121112547). | Las proyecciones específicas señalan hijos terminales/cero pendientes, pero los raw sessions originales no se inspeccionaron. E2 parte de `3e5b2af…`, no del baseline v0.4.9. Resume ordinario OpenCode 2.0.21 es reporte H y no prueba continuidad de autoridad tras compaction. Timing exacto y concurrencia permanecen desconocidos donde no se muestran. |
| E004-4 | D/U | Prompts de proceso Aegis: [`aegis.md`](../../../olympus/harnesses/opencode/agent-prompts/aegis.md#L61); [`external-work-ownership/qualify.ps1`](../../../tests/external-work-ownership/qualify.ps1#L1); contrato de proceso ausente de forma equivalente en Codex. | Contrato de recepción/identidad y progreso acotado distingue ACTIVE, STALLED, ORPHANED y UNKNOWN; no permite kill por nombre global ni retry ciego. Es instrucción/contrato existente, no daemon ni servicio automático; Codex no tiene detalle equivalente. |
| E004-5 | D/S/H | [`maintenance-plane.md`](../../../olympus/policies/maintenance-plane.md) (sección de salida estructurada); prompts Kael/Aegis; [`qualify-fidelity.ps1`](../../../tests/maintenance-handoff/qualify-fidelity.ps1); [issue #10](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/10); [DEVELOPMENT runtime limits](../../../docs/DEVELOPMENT.md#L394). | Contrato conserva nombres `EXPECTED_OUTPUT` y valores producidos, sin resumen renombrado/lossy. Test source es determinista/sintético y no se ejecutó aquí. El reporte runtime de fidelidad antecede la integración; no se infiere smoke posterior. |

## 005 — Mantenimiento explícito con Aegis

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E005-1 | D | [maintenance-plane policy](../../../olympus/policies/maintenance-plane.md#L3), entry rules líneas 17–27; [OpenCode `/maintain`](../../../olympus/harnesses/opencode/maintain.md#L1); [Aegis prompt](../../../olympus/harnesses/opencode/agent-prompts/aegis.md#L1). | Aegis es hidden, entrada user→`/maintain`; una entrada nueva emite `MAINTENANCE_AUTH: VALID` y `AEGIS_SCOPE: ACCEPTED` antes de tools; no hay admission gate por repositorio/provenance. Kael/child no invocan, Aegis no delega ni auto-activa. OpenCode no aporta campo nativo de origen de comando/autoridad. Codex Aegis = GAP. |
| E005-2 | D/S/H/U | [`maintenance-scope` qualifier](../../../tests/maintenance-scope/qualify.py#L1), [handoff qualifier](../../../tests/maintenance-handoff/qualify.ps1#L13), [output fidelity qualifier](../../../tests/maintenance-handoff/qualify-fidelity.ps1#L1), [live-control instructions](../../../tests/maintenance-handoff/live-control.md#L1); [issue #8 ordinary resume report](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-5934781194), [compaction report](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6093432997), [final audit](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6121112547). | Tests static/synthetic; live-control preparado, no ejecución actual. Los reportes H de issue #8 son distintos: resume ordinario OpenCode 2.0.21 no prueba compaction ni invocación `/maintain`. No hay captura nativa verificada de comando `/maintain` más resultado. La fidelidad estructurada está en E004-5; el reporte runtime de issue #10 antecede la integración. |

## 006 — UX de instalación pública

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E006-1 | D | [`install-olympus.ps1`](../../../install-olympus.ps1#L21), `Read-InstallScope`/`Read-InstallHarness`, gate de argumentos en línea 58; [`uninstall-olympus.ps1`](../../../uninstall-olympus.ps1#L21) y gate equivalente. | Sólo cero argumentos entra al modo de prompts. Con cualquier argumento se usa modo directo y la firma incompleta/incorrecta falla sin prompt parcial. Entrada vacía redirigida exige argumentos. Requiere PowerShell 7; ejemplo de firmas válidas en la spec 006. |
| E006-2 | D | [`scripts/launch-latest.ps1`](../../../scripts/launch-latest.ps1#L24) (latest tag y fetch exact tag); instalador directo por defecto v0.4.9 y verifica versión de archive (líneas 137, 178; fuente del entrypoint). | Latest wrapper y pinned default son superficies distintas; no convertir latest en la línea base de feature. |
| E006-3 | D/S | [`tests/installer-ux/qualify.ps1`](../../../tests/installer-ux/qualify.ps1#L17), mocks de prompts/uninstall lines 22–70, dispatch native PowerShell lines 164–171. | Fixtures verifican parámetros y rutas de UX; no ejecutar instalaciones reales de usuario ahora. |
| E006-4 | H | PR #65 informó que la cualificación local de UX de instalación pasó con OpenCode stubbed. | [PR #65](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/65). La validación del tag remoto seguía siendo gate de publicación; no demuestra aceptación de instalación remota. |

## 007 — Instalación administrada

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E007-1 | D | [`scripts/bootstrap.ps1`](../../../scripts/bootstrap.ps1#L182) `Assert-Target`; `Read-Manifest` 222; `Assert-Managed` 297; `Assert-No-Conflicts` 346; `Manifest-Text` 519; `Plan` 536; `Assert-InstalledHarness` 651; verify-only checks 700/754. | Proyecto exige la raíz absoluta exacta del Git worktree; ownership/hash, set administrado, conflicto/drift, manifest y selección/verificación harness. `installed_harnesses` registra selección; verify-only no modifica destino ni hace runtime discovery/reparación. Missing ownership manifest falla cerrado (#46); migration override project-local no escanea/borrar preferencias automáticamente. |
| E007-2 | D | [`scripts/global-install.ps1`](../../../scripts/global-install.ps1#L29) `Assert-SafeDestination`, `Read-GlobalManifest` 132, `Invoke-OneHarness` 206; [`scripts/project-uninstall.ps1`](../../../scripts/project-uninstall.ps1#L30) `Resolve-ManagedPath` y `Read-ProjectManifest` 87, flujo principal 118–230. | Instalación global por destino seguro/manifest/harness; instalación/upgrade es aditiva y conserva config base/global/usuario y harness no seleccionado. Uninstall verifica hash/ownership de las entradas objetivo; no se afirma que prevalide todas las entradas globales antes de cualquier borrado ni rollback exterior. |
| E007-3 | D/S/U | [`tests/global-installer/qualify.ps1`](../../../tests/global-installer/qualify.ps1#L19); release `dual-harness-installer.ps1`, `installer-compatibility.ps1`, `dirty-worktree.ps1`. [Issue #51](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/51). | Tests de fuente, stubs/OpenCode mock y fixtures Git desechables; no equivalen a runtime nativo. #51: escrituras secuenciales hasta manifest y validación sin rollback externo, riesgo inferido; sin incidente reproducido de pérdida de datos/recovery stuck. |
| E007-4 | H | Issue #7 reporta instalación global v0.4.6 en Windows/OpenCode 2.0.26 con 15 recursos, 12 roles, dos controles, loader y selección de Kael; H Codex global fue provista por separado. | [Issue #7 comment](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7#issuecomment-6106396436), tomado como reporte del operador sin raw directory adjunto. Es evidencia de v0.4.6, no una repetición en v0.4.9; sin LLM/prompt/delegación ni otros OS/versiones. Codex no se rerunó aquí. |

## 008 — Worktree provisioning

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E008-1 | D | [`worktree-setup.ps1`](../../../olympus/harnesses/opencode/worktree-setup.ps1#L31), `Get-Git-Root`/`Get-Git-Common-Directory`; `Normalize-Managed-Path` 48; `Write-New-File` 96; main flow 112–283. | Acepta worktrees del mismo Git common dir, copia sólo resources gestionados, comprueba hashes/ownership/conflictos y sólo escribe faltantes. El operador activa el comando de startup opt-in; la copia del helper no edita automáticamente un startup command ni preferencias globales. |
| E008-2 | D | [WORKTREES guide](../../../docs/WORKTREES.md#L1); [`tests/worktree-activation/qualify.ps1`](../../../tests/worktree-activation/qualify.ps1#L26). | Contrato usa Git real y CLI stub; no equivale a hook runtime. |
| E008-3 | D/U | [`native-smoke.ps1`](../../../tests/worktree-activation/native-smoke.ps1#L12); [DEVELOPMENT limitations](../../../docs/DEVELOPMENT.md#L394). | Script existente usa API OpenCode en worktrees desechables y comprueba manifests/default agent, sin modelo; NOT RUN en este trabajo y sin output raw nativo guardado. No prueba prompt, roster, delegación ni cancelación. |
| E008-4 | H/U | Issue #8 reporta un smoke no-model con manifests y Kael efectivo. | [Issue #8 reopening comment](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6093432997), snippet provisto, no raw runtime completo. Acredita sólo provisioning/configuración reportada; no prompt, delegación, cancelación ni autoridad. |
| E008-5 | H/U | Issue #27 quedó CLOSED con resolución acotada de provisioning. Un operador reportó en Windows/OpenCode 2.0.26 activación Kael en worktrees B/C vinculados y primeros prompts read-only exitosos sobre la implementación candidata original. | [Issue #27 final disposition](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/27#issuecomment-6106712288). Reporte histórico candidato; no repetido tras cada cambio protector ni prueba de replay v0.4.9. Tests 23 PASS fueron reportados en `39eae45`, mientras la comprobación renderer Python figuraba bloqueada; no se atribuye ese PASS al baseline ni se leen raw native outputs. El evento/causa exactos de cancelación no se capturaron; no todos los casos de cancelación quedan acreditados como corregidos. |

## 009 — Visibilidad de actividad

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E009-1 | D | [`activity.ts`](../../../olympus/harnesses/opencode/activity.ts#L22), [`tui.tsx`](../../../olympus/harnesses/opencode/tui.tsx#L5). | Filtra hijos directos en ejecución, etiqueta/trunca hasta cuatro más remainder; muestra pasivamente arriba del composer desde session list/status; no polling ni acciones. |
| E009-2 | D/S/U | [`activity.test.mjs`](../../../tests/activity-hud/activity.test.mjs#L11); [qualifier](../../../tests/activity-hud/qualify.ps1#L35); [Codex capability notes](../../../docs/HARNESSES.md#L220). | Slice offline cubre instalación/estructura; slice runtime intenta discovery del plugin mediante CLI OpenCode. Ambos no prueban render interactivo en TUI. Ningún slice se ejecutó en esta auditoría. Codex native visibility PARTIAL sin HUD generado equivalente. |

## 010 — Qualification y release

| ID | Clase | Evidencia | Alcance / límite |
|---|---|---|---|
| E010-1 | D | [`scripts/qualify.ps1`](../../../scripts/qualify.ps1#L81) FAST; #105 FULL; #151 RUNTIME; [FAST workflow](../../../.github/workflows/fast.yml#L41); [development/qualification contract](../../../docs/DEVELOPMENT.md#L186); [TFR routing](../../../olympus/policies/routing.md#L3). | FAST offline; FULL ejecuta FAST exactamente una vez y luego sus adiciones Windows; RUNTIME es slice no interactivo de catálogo/config/API/proceso, no smoke general de agentes/modelos. TFR selecciona checks existentes proporcionales al riesgo y conserva gates obligatorios; no impone FAST a todo cambio. Perfiles no ejecutados aquí. |
| E010-2 | D/H | [`tests/release/qualify.ps1`](../../../tests/release/qualify.ps1); `installer-compatibility.ps1`, `github-release-notes.ps1`, `tag-transition-stability.ps1`; [release process](../../../docs/DEVELOPMENT.md#L495); E000-2. | Fixtures usan source local y/o mocks; no prueban tag remoto. CI FAST histórica exact SHA pasó; no prueba instalación del release ni comportamiento de agente. |
| E010-3 | D | TFR y elección proporcional de checks en [`olympus/policies/routing.md`](../../../olympus/policies/routing.md#L3) y [`docs/DEVELOPMENT.md`](../../../docs/DEVELOPMENT.md#L190). | La implementación distingue verificación enfocada determinista/simulada/native, mantiene ownership de Kael y usa Nox/Vera sólo cuando contrato/riesgo los justifican. CI Windows no vuelve Windows intrínseco a Olympus Core. Los perfiles de mantenedor no se imponen a proyectos de usuario. |

## Límites comunes de esta auditoría

Se leyeron fuentes, contratos, capturas y reportes referenciados; no se ejecutaron suites, perfiles FAST/FULL/RUNTIME, instaladores, worktree helpers ni runtimes interactivos durante esta tarea. No se releyeron raw logs de los reportes históricos. Las afirmaciones R se limitan a los artefactos capturados citados; H sigue atribuido. Las incertidumbres se mantienen como U en vez de completarlas con suposiciones.

## Inconsistencias y diferencias de evidencia

Son diferencias entre snapshots, reportes y estado actual; no se clasifican automáticamente como defectos del baseline. Se conserva la fuente histórica sin elevarla a comportamiento actual.

| Diferencia | Evidencia / estado de interpretación |
|---|---|
| IDs de roles/modelos en reportes antiguos frente al Core actual | Reportes experimentales congelan el mapping de su fecha. La fuente canónica del baseline es [`models.toml`](../../../olympus/core/models.toml) y [`identities.toml`](../../../olympus/core/identities.toml); no se altera retrospectivamente el texto de aquellos reportes. |
| GAP global en snapshot Phase 12 frente a soporte acotado documentado ahora | Phase 12 es snapshot de configuración/versión con campos efectivos incompletos; la [matriz actual de harnesses](../../../docs/HARNESSES.md) distingue soporte de brechas por superficie. No se convierte el snapshot viejo en una ejecución v0.4.9. |
| PASS de resume ordinario issue #8 frente a compaction | El [reporte de resume](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-5934781194) y los reportes de [compaction](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6093432997) / [auditoría](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6121112547) tienen alcance distinto; el primero no demuestra continuidad tras compaction. |
| Discusión histórica de admission por repo/ownership en issues #3/#4 frente al plano actual | [Issue #3](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/3) y [issue #4](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/4) conservan contexto anterior; la policy actual requiere invocación explícita `/maintain` y no filtra por repo Olympus/ownership. No se recrea un gate antiguo. |
| Propuesta de sintaxis GNU en #61 frente a entrypoints actuales | [Issue #61](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/61) conserva una propuesta; el código actual usa parámetros nativos PowerShell y modo interactivo sólo sin argumentos, no una interfaz GNU. |
| Check de bytes del renderer frente a traducción semántica | [`render_harnesses.py`](../../../scripts/render_harnesses.py) verifica outputs seleccionados; no consume cuerpos de roles ni todos los cuerpos de policy. Los adapters mantienen texto por separado; igualdad de bytes no demuestra sincronía semántica. |
| Wrapper latest frente al pin de instalación directa | [`launch-latest.ps1`](../../../scripts/launch-latest.ps1#L24) selecciona el tag reciente; entrypoint directo tiene default v0.4.9. Son rutas/versiones de fuente distintas. |
| Issue #51 frente a un incidente de datos | Fuente muestra escrituras/manifest/validación secuenciales sin rollback exterior; esto sustenta riesgo inferido de estado parcial, no pérdida de datos ni recuperación bloqueada reproducida. |

## Contexto de Spec Kit fuera del baseline de producto

La constitución/overrides y fichas de Spec Kit se escribieron como infraestructura documental después del baseline; no son features v0.4.9 ni evidencia de comportamiento de runtime. Para políticas TFR de producto se usan Olympus Core y DEVELOPMENT, no instrucciones genéricas de plantillas. Los wrappers y gates existentes de Spec Kit no se modificaron por este inventario.

## Registro de revisión y verificaciones de documentación

El 2026-10-14, Kael y Vera revisaron los 14 documentos y las diez fichas retrospectivas. Se corrigieron las observaciones independientes de Vera y ella aprobó la revisión final; Kael aceptó el inventario documental. La revisión confirma suficiencia documental, no cambia SHIPPED/PARTIAL ni eleva evidencia de runtime.

Pasaron verificaciones locales, de sólo lectura y enfocadas a documentación: headings y modo Existing conforme a la plantilla activa; SHA completo del baseline; IDs FR y campo de problema abordado; enlaces locales, existencia de rutas fuente y límites de línea; whitespace y `git diff --check`. En el snapshot de auditoría, los 319 archivos preexistentes rastreados/descubribles permanecieron byte-identical, se añadieron exactamente 14 Markdown bajo `specs/`, y refs Git, índice y `master` permanecieron sin cambios.

Los 14 documentos añadidos son:

- Índice/registro: `specs/README.md`, `specs/future/README.md`, `specs/retrospective/v0.4.9/COVERAGE.md`, `specs/retrospective/v0.4.9/EVIDENCE.md`.
- Fichas: `specs/retrospective/v0.4.9/001-core-and-adapters/spec.md`, `specs/retrospective/v0.4.9/002-scoped-orchestration/spec.md`, `specs/retrospective/v0.4.9/003-authority-and-trust/spec.md`, `specs/retrospective/v0.4.9/004-result-lifecycle/spec.md`, `specs/retrospective/v0.4.9/005-explicit-maintenance/spec.md`, `specs/retrospective/v0.4.9/006-public-installation-ux/spec.md`, `specs/retrospective/v0.4.9/007-managed-installation/spec.md`, `specs/retrospective/v0.4.9/008-worktree-provisioning/spec.md`, `specs/retrospective/v0.4.9/009-activity-visibility/spec.md`, `specs/retrospective/v0.4.9/010-qualification-and-release/spec.md`.

FAST, FULL, RUNTIME, instaladores y runtimes de producto no se ejecutaron en esta auditoría. No se añadieron automatizaciones, hooks, gates ni procesos de aprobación.
