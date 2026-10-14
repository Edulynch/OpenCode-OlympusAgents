# Cobertura retrospectiva — OlympusAgents v0.4.9

**Baseline**: `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**Fecha de inventario**: 2026-10-14  
**Revisión documental**: las diez fichas fueron revisadas y aceptadas por Kael y Vera el 2026-10-14.

Esta matriz describe la cobertura del inventario, no aprueba runtime. SHIPPED/PARTIAL es estado de implementación; suficiencia documental y completitud de evidencia se evalúan por separado. Véase [índice](../../README.md) y [ledger de evidencia](EVIDENCE.md).

## Capacidades y evidencia

| ID | Área / componente | Implementación | Cobertura documental | Completitud de evidencia (independiente) | Evidencia disponible y límites actuales |
|---|---|---|---|---|---|
| 001 | Olympus Core; identidad, modelos, generación de adaptadores | SHIPPED | Spec revisada y aceptada (2026-10-14) | D suficiente para contrato estructural; no verifica semántica/paridad de runtime | Fuentes Core y checks deterministas disponibles. El renderer usa stems de roles para el roster, no los contenidos de `roles/*.md`; no inyecta los cuerpos de toda policy. Los adapters mantienen parte del texto correspondiente por separado; sincronía semántica completa no comprobada. |
| 002 | Kael; selección de roles, dependencias, fan-out/fan-in | SHIPPED | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta para comportamiento nativo completo | Fuentes D/S y proyecciones archivadas R seleccionadas. Phase 11 no es aceptación v0.4.9 uniforme; no promete scheduler equivalente, profundidad anidada ni speedup. Issue #41 sin causa establecida. |
| 003 | ALLOW/ASK/DENY; rutas y permisos del harness | PARTIAL | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta para comportamiento nativo completo | Configuración/fixtures D/S disponibles; ASK/UI y enforcement Codex DENY permanecen no verificados. DENY Codex = GAP. |
| 004 | Barreras de pregunta, resultado y recuperación | PARTIAL | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta para comportamiento nativo completo | Fuentes D/S y proyecciones R archivadas específicas. No acreditan timing exacto ni recuperación completa. Issue #1 abierto; carrera de pregunta no automatizada. Issue #8 no demuestra continuidad tras compaction. |
| 005 | Plano privilegiado de Aegis y `/maintain` | PARTIAL | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta para comportamiento nativo completo | Política/fixtures D/S; H de issue #8 trata resume, no invocación Aegis. No hay captura verificada de entrada `/maintain` con resultado ni reanudación de autorización Aegis tras compaction. Codex Aegis = GAP. |
| 006 | Entradas públicas de instalación y desinstalación | SHIPPED | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta para aceptación nativa completa | Contrato D/S y PR #65 H de cualificación local con OpenCode stubbed. No se ejecutó instalación nativa ni se observó validación remota del tag. |
| 007 | Bootstrap de proyecto; instalación global; manifests y uninstall | SHIPPED | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta para instalación de v0.4.9 | Fuentes/fixtures D/S; issue #7 H reporta v0.4.6, no ejecución v0.4.9. No se ejecutaron instaladores ni se verificó instalación remota publicada. Riesgo #51 inferido, no incidente reproducido. |
| 008 | Helper de creación y activación de worktree | SHIPPED | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta; H candidato, sin replay de baseline | Helper/contrato D/S; issue #27 H reporta prompts en candidata original, no replay v0.4.9 ni comprobación de cada cambio protector. El smoke actual no se ejecutó; evento/causa exactos de cancelación no capturados. |
| 009 | HUD de actividad OpenCode y visibilidad de Codex | PARTIAL | Spec revisada y aceptada (2026-10-14) | Parcial/incompleta para comportamiento nativo completo | Contratos/fixtures D/S; render interactivo TUI desconocido. Visibilidad nativa Codex es PARTIAL y no tiene HUD generado equivalente. |
| 010 | FAST/FULL/RUNTIME, CI y flujo de release | SHIPPED | Spec revisada y aceptada (2026-10-14) | D suficiente para estructura de perfiles; CI histórica exacta, no aceptación runtime universal | Scripts/workflows definen contratos; FAST CI histórico pasó en el commit baseline. Ningún perfil se volvió a ejecutar en esta auditoría; éxito CI no prueba instalación remota ni runtime interactivo. |

**Total del inventario: 10 capacidades**. Por implementación: 6 SHIPPED y 4 PARTIAL. Propuestas futuras y filas GAP subordinadas no se cuentan como capacidades ni alteran este denominador.

La completitud de evidencia es independiente de SHIPPED/PARTIAL: **2/10** (001 y 010) tienen evidencia de fuente/determinista suficiente para describir sus contratos estructurales; 010 también tiene CI histórica del SHA exacto. Esto no equivale a aceptación nativa universal. Para **8/10** (002–009), la evidencia es incompleta/parcial frente al comportamiento nativo observable completo: combina fuentes D/S con proyecciones R archivadas en 002/004, reportes H atribuidos en algunos casos y límites nativos aún desconocidos en otros; no se afirma que las ocho tengan observaciones nativas positivas. Todos los perfiles y runtimes están NOT RUN en esta auditoría. Los límites no demostrados incluyen ASK/UI y Codex DENY, recuperación de resultados, reanudación de autorización de mantenimiento Aegis tras compaction, captura nativa de entrada/resultado `/maintain`, instalación remota publicada v0.4.9, replay de worktree sobre baseline actual y render TUI del HUD OpenCode.

## Cobertura de los doce roles

El inventario conserva los doce roles del Core, agrupados por capacidad y responsabilidad para evitar una spec por agente:

| Roles | Cobertura principal |
|---|---|
| Kael | 001 identidad como raíz; 002 orquestación; 003 autoridad de alcance; 004 cierre de resultado; 005 límite de acceso a Aegis. |
| Aegis | 001 roster/identidad; 005 única vía de mantenimiento explícita y sus límites. |
| Atlas, Orin | 001 roster y perfiles; 002 separación de planificación y arquitectura de la ejecución. |
| Veyra, Thales, Argus, Talos | 001 perfiles; 002 selección por necesidad; 003 límites de evidencia, seguridad y clasificación. |
| Kovan, Nox, Vera | 001 perfiles; 002 propiedad de implementación, validación y revisión; 010 cualificación y gates donde aplica. |
| Helios | 001 perfil/modelo; 002 optimización sólo cuando se solicita explícitamente y dentro de su límite de propuesta. |

Las definiciones completas siguen en [Olympus Core](../../../olympus/README.md) y [`olympus/roles/`](../../../olympus/roles/); esta tabla es un mapa de cobertura, no reemplaza esas responsabilidades.

## Matriz de componentes y runtimes

| Componente / capacidad | OpenCode | Codex | Declaración que no se hace |
|---|---|---|---|
| Core, roster, modelos, identidades | Renderer genera 12 agentes a partir de fuentes Core. | Renderer genera 10 especialistas; Kael es root thread y Codex no genera Aegis. | Igualdad semántica completa o ejecución de todos los roles. |
| Orquestación | Kael agente primario; límites expresados por Core, configuración y prompts. | Kael es el root; cap nativo de cuatro y multi-agent habilitado en root config; algunos perfiles child optan por `[agents] enabled=false`. | Scheduler Olympus idéntico, capacidad de bypass o traza nativa equivalente. |
| Autoridad | Permisos y reglas por configuración; runtime ASK/UI requiere evidencia nativa aparte. | Profiles; DENY sigue GAP. | Que un prompt sustituya enforcement. |
| Lifecycle | Capturas específicas y prompts; carreras/fallas de correlación limitadas. | Entrega soportada por reporte; reconciliación/pregunta parcial. | Reconciliación exact-once no demostrada; resume ordinario no acredita reanudación de autorización Aegis tras compaction. |
| Aegis | `/maintain` explícito, hidden Aegis y límites Core. | GAP, sin Aegis generado. | Auto-escalación desde Kael o paridad Codex. |
| Instalación administrada | Fuentes y pruebas de aislamiento/instalación. | Misma herramienta soporta selección de harness y manifiestos; evidence de runtime externo es atribuida. | Verificación de instalación remota en este trabajo. |
| Worktrees | Hook OpenCode opt-in y helper. | No aplica al startup nativo OpenCode; no se declara helper Codex equivalente. | Delegación o prompts exitosos durante worktree activation. |
| Actividad | Plugin pasivo de OpenCode. | Visibilidad nativa parcial; no se genera el plugin HUD. | Renderizado interactivo comprobado. |
| Release | Windows CI y herramientas de instalador. | Compatibilidad y paths estáticos por harness. | Instalación remota exitosa derivada de CI offline/mock. |

Fuentes y límites por fila se registran con IDs en [EVIDENCE.md](EVIDENCE.md); allí también se separa evidencia externa/histórica de fuente actual.

## Gaps mapeados fuera del denominador

Son límites de compatibilidad o evidencia dentro de las diez capacidades anteriores; no se cuentan como filas del inventario.

| Gap | Capacidad relacionada | Estado de evidencia |
|---|---|---|
| Garantía Codex DENY | 003 | GAP declarado; configuración/perfiles no prueban enforcement inmutable. |
| Adaptador Aegis Codex | 005 | GAP; no se genera agente Aegis Codex. |
| Ruta anidada directa en OpenCode | 002 | No soportada por la profundidad observada; sin bypass. |
| Reanudación de autorización de mantenimiento de Aegis tras compaction | 005 (principal), 004 | El PASS histórico atribuido cubre ese caso ordinario de la misma sesión; no demuestra continuidad de autorización tras compaction ni aceptación de v0.4.9. |

## Estado de suficiencia documental

Una ficha suficiente cubre el problema abordado, actores/propósito, implementación observada, requisitos, dependencias/riesgos, runtimes, límites y referencias. En este inventario la revisión de Kael y Vera es la revisión escogida para esta auditoría amplia, no un gate futuro obligatorio. Las diez fichas fueron revisadas y aceptadas: suficiencia **10/10 (100%) documental**. Esto no mide aceptación nativa: la evidencia completa/parcial y los límites desconocidos se mantienen en la columna anterior y no se convierten en PASS por la revisión.

No se ejecutaron FAST, FULL, RUNTIME, instaladores ni runtimes nativos durante esta documentación. Los resultados históricos exactos se distinguen de estas verificaciones no ejecutadas.
