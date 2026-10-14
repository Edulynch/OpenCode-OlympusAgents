# Spec Kit: índice de documentación retrospectiva

## Alcance y línea base

Este árbol documenta retrospectivamente el producto que existe en el commit `c30a19dd410b1815f4591b204615cae0dd9e9a5f`, publicado como v0.4.9. La identidad de release y sus límites de evidencia están en [EVIDENCE.md](retrospective/v0.4.9/EVIDENCE.md). Estas especificaciones describen capacidades observadas en el código y fuentes históricas citadas; sus escenarios sirven como ejemplos de verificación del código actual, no como criterios de aceptación históricos reconstruidos.

La constitución vigente está en [.specify/memory/constitution.md](../.specify/memory/constitution.md). Las especificaciones anidadas son documentación retrospectiva; no se creó `feature.json`, rama ni ciclo de plan/tareas/implementación.

## Catálogo de capacidades

| ID | Capacidad | Área funcional | Estado de implementación v0.4.9 | Runtime aplicable | Especificación | Evidencia principal | Limitaciones |
|---|---|---|---|---|---|---|---|
| 001 | Core canónico y adaptadores | Core/modelos/identidades/generación | SHIPPED | OpenCode, Codex | [spec](retrospective/v0.4.9/001-core-and-adapters/spec.md) | [E001-1–3](retrospective/v0.4.9/EVIDENCE.md) | Roster/modelos compartidos; contenido de roles y sincronía semántica no verificados por renderer. |
| 002 | Orquestación con alcance y límites | Kael/routing/fan-out/fan-in | SHIPPED | OpenCode, Codex | [spec](retrospective/v0.4.9/002-scoped-orchestration/spec.md) | [E002-1–3](retrospective/v0.4.9/EVIDENCE.md) | Trazas parciales; sin garantía de scheduler equivalente ni ruta anidada directa. |
| 003 | Autoridad y confianza | ALLOW/ASK/DENY/permisos | PARTIAL | OpenCode, Codex | [spec](retrospective/v0.4.9/003-authority-and-trust/spec.md) | [E003-1–3](retrospective/v0.4.9/EVIDENCE.md) | DENY de Codex es GAP; fixtures/configuración no acreditan cada interacción nativa. |
| 004 | Ciclo de vida de resultados | Preguntas/resultado/reconciliación | PARTIAL | OpenCode, Codex | [spec](retrospective/v0.4.9/004-result-lifecycle/spec.md) | [E004-1–5](retrospective/v0.4.9/EVIDENCE.md) | Capturas terminales limitadas; recuperación desconocida. El resume ordinario no demuestra continuidad tras compaction. |
| 005 | Mantenimiento explícito con Aegis | Mantenimiento/autoridad privilegiada | PARTIAL | OpenCode; Codex GAP | [spec](retrospective/v0.4.9/005-explicit-maintenance/spec.md) | [E005-1–2](retrospective/v0.4.9/EVIDENCE.md) | Policy y fixtures cubren límites; sin captura nativa `/maintain`+resultado ni reanudación de autorización Aegis después de compaction. |
| 006 | UX de instalación pública | Entry points/prompts/versiones | SHIPPED | Instaladores OpenCode/Codex | [spec](retrospective/v0.4.9/006-public-installation-ux/spec.md) | [E006-1–4](retrospective/v0.4.9/EVIDENCE.md) | Prompts sólo con cero argumentos; modo directo inválido falla sin prompts parciales. Cualificación local stub; sin instalación nativa ni validación remota observada. |
| 007 | Instalación administrada | Bootstrap/manifests/ownership/uninstall | SHIPPED | Proyecto/global; OpenCode/Codex | [spec](retrospective/v0.4.9/007-managed-installation/spec.md) | [E007-1–4](retrospective/v0.4.9/EVIDENCE.md) | Código/contratos disponibles; reportes H son v0.4.6; riesgo #51 inferido, no incidente. |
| 008 | Aprovisionamiento de worktrees | Git/worktree/helper OpenCode | SHIPPED | OpenCode | [spec](retrospective/v0.4.9/008-worktree-provisioning/spec.md) | [E008-1–5](retrospective/v0.4.9/EVIDENCE.md) | Smoke nativo no ejecutado; prompts H #27 son de candidata original, no replay baseline. |
| 009 | Visibilidad de actividad | HUD/estado de sesiones | PARTIAL | HUD OpenCode; visibilidad Codex parcial | [spec](retrospective/v0.4.9/009-activity-visibility/spec.md) | [E009-1–2](retrospective/v0.4.9/EVIDENCE.md) | Fuente/fixtures cubren presentación pasiva; renderizado interactivo no comprobado. |
| 010 | Calificación y release | CI/qualification/publicación | SHIPPED | CI Windows; adapters donde aplica | [spec](retrospective/v0.4.9/010-qualification-and-release/spec.md) | [E010-1–3, E000-2](retrospective/v0.4.9/EVIDENCE.md) | FAST histórico pasó en SHA exacto; no prueba instalación remota ni runtime de agentes. |

El detalle de cobertura de roles, módulos y verificaciones está en [COVERAGE.md](retrospective/v0.4.9/COVERAGE.md). Las futuras propuestas y limitaciones abiertas se mantienen fuera del catálogo implementado en [future/README.md](future/README.md); no cuentan en el denominador de diez capacidades.

## Métricas y estado documental

- **Denominador**: las diez capacidades 001–010. Subgaps de runtime, issues abiertos y propuestas futuras se mapean a estas filas o al registro futuro; no agregan funciones ni inflan el denominador.
- **Estado de implementación**: SHIPPED/PARTIAL describe el baseline de producto. No significa que se hayan vuelto a ejecutar pruebas.
- **Suficiencia documental**: una ficha cuenta cuando existe, incluye el problema abordado y los campos requeridos, describe la implementación existente con evidencia trazable y límites, y ha recibido revisión. Kael y Vera fueron las revisiones elegidas para este inventario retrospectivo amplio; esto no establece un gate permanente para otras tareas. El porcentaje es `fichas revisadas y suficientes / 10`.
- **Revisión**: las diez fichas fueron revisadas y aceptadas; suficiencia documental **10/10 (100%)**. El estado de implementación y la evidencia de runtime se registran por separado.
- **Completitud de evidencia y runtime**: se clasifica por capacidad en [COVERAGE.md](retrospective/v0.4.9/COVERAGE.md); las categorías D, S, R, H y U se definen en [EVIDENCE.md](retrospective/v0.4.9/EVIDENCE.md). Un test existente no equivale a ejecución PASS, y no se afirma runtime que no tenga evidencia.

La suficiencia documental **10/10** no equivale a runtime verificado ni a un 10/10 de aceptación nativa. La partición de evidencia y los límites no verificados permanecen en [COVERAGE.md](retrospective/v0.4.9/COVERAGE.md).

El inventario registra el estado de v0.4.9. No implementa features futuras, no interpreta issues abiertos como requisitos aprobados y no declara gates de release satisfechos por esta actualización documental.

## Gaps mapeados fuera del denominador

Estos límites están vinculados a capacidades existentes; no son funciones adicionales ni filas del denominador de diez.

| ID GAP | Límite observado | Capacidad / evidencia | Estado |
|---|---|---|---|
| GAP-01 | Garantía Codex DENY | 003 / E003-1–3 | GAP; los perfiles no se presentan como ACL inmutable. |
| GAP-02 | Adaptador Aegis Codex | 005 / E005-1–2 | GAP; no se genera Aegis para Codex. |
| GAP-03 | Enrutamiento anidado directo OpenCode | 002 / E002-1–2 | No soportado por la profundidad observada; no se propone bypass. |
| GAP-04 | Reanudación de la autorización de mantenimiento de Aegis tras compaction | 005 (principal), 004 / E005-2, E004-3 | El PASS histórico atribuido cubre ese caso ordinario de la misma sesión; no demuestra continuidad de autorización tras compaction ni aceptación de v0.4.9. |
