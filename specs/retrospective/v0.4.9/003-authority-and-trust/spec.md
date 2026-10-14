# Feature Specification: Autoridad y confianza por operación

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: PARTIAL en capacidades declaradas v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar semántica y controles existentes; no alterar permisos ni ejecutar operaciones nativas.  
**Evidence Reviewed**: E003-1–E003-3 en el [ledger](../EVIDENCE.md).

**Input**: Inventario retrospectivo de ALLOW/ASK/DENY, perfiles de harness y límites de confianza.

## Purpose and Actors

La capacidad expresa qué operación puede realizarse, requerir autorización nativa o permanece prohibida. Actores: usuario que autoriza y runtime/harness que configura o presenta los controles disponibles.

**Problem addressed (as built)**: Las semánticas de autorización y los controles del harness deben distinguirse de la guía textual de un prompt.

## Scope and Interpretation

La política de Olympus define ALLOW como autorización de la operación exacta dentro de scope; ASK puede requerir una pregunta/aprobación nativa cuando el harness ofrece ese mecanismo; DENY identifica una frontera que una aprobación común no eleva. OpenCode declara permisos en config y metadata de agentes, mientras los prompts describen además conducta y scope; son capas distintas. La implementación representa esos límites mediante controles y políticas propios de cada harness. Que una regla aparezca en prompt no demuestra enforcement del filesystem, proceso o UI. El contrato Core exige que un rechazo o cancelación detenga la operación; no habilita un bypass.

OpenCode incluye reglas de permission/agent y Codex tiene perfiles filesystem/approval, pero Codex declara `DENY = GAP`. Los cualificadores deterministas/sintéticos y probes de configuración no acreditan todas las decisiones nativas de aprobación, overrides de sesión o fronteras OS/ACL.

## User Scenarios & Testing

### User Story 1 - Respetar el límite exacto de una operación (Priority: P1)

Una persona solicita una acción en un proyecto con restricciones conocidas; Kael interpreta la política y el adapter aplica los controles disponibles sin ampliar scope por una frase de prompt.

**Why this priority**: Scope del usuario y límites protegidos gobiernan qué operación se puede autorizar y con qué mecanismo.

**Independent Test**: Consultar authority policy, perfiles/config efectivos y fixtures aislados/sintéticos; una prueba de texto no se interpreta como evento nativo de aprobación.

**Acceptance Scenarios**:

1. **Given** una operación dentro del scope explícito y permitida por el perfil, **When** el adapter la representa como ALLOW, **Then** sólo se autoriza esa operación y scope.
2. **Given** una operación que puede requerir aprobación y un ASK nativo disponible, **When** se intenta esa operación, **Then** el usuario decide mediante la superficie nativa; configuración estática sola no prueba que la UI apareciera.
3. **Given** una operación que cruza DENY o una protección del usuario, **When** se solicita una concesión ordinaria, **Then** la política no eleva la frontera; los límites Codex DENY permanecen clasificados GAP.

### Edge Cases

- Un role prompt puede describir la política sin que el runtime o ACL la aplique como control técnico.
- Un allowlist de ruta/config no prueba que una sesión no tenga un override no inspeccionado.
- ASK configurado, ASK presentado, decisión humana y operación completada son eventos distintos.

## Requirements

### Functional Requirements

- **FR-001**: La semántica Core distingue autorización exacta ALLOW, solicitud de aprobación ASK y frontera no elevable DENY.
- **FR-002**: El adapter OpenCode representa asks/denies de shell, subagent, external/edit y límites específicos en config/prompts.
- **FR-003**: Codex expresa filesystem profiles y approval nativo; su garantía DENY sigue GAP y no se reemplaza con instrucciones.
- **FR-004**: Evidencia de política, configuración estática, casos sintéticos, UI ASK y enforcement runtime se clasifican por separado.
- **FR-005**: Una autorización no expande la petición del usuario ni convierte un control ausente en un control existente.
- **FR-006**: Rechazo/cancelación de un control detiene esa operación; no se evade con una nueva ruta o concesión ordinaria.

### Key Entities

- **Operation**: acción exacta, paths y efectos dentro de un scope solicitado.
- **Authority label**: semántica Core ALLOW, ASK o DENY.
- **Runtime control**: mecanismo nativo/configurable que puede presentar o hacer cumplir una decisión, separado de la instrucción textual.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Cada clasificación mantiene por separado política, configuración declarada y evidencia de enforcement runtime.
- **SC-002**: Las fronteras DENY no se modelan como elevables mediante aprobación normal.
- **SC-003**: ASK sólo se reporta como observado si hay evidencia de UI/decisión; tests estáticos conservan `NOT ASSESSED`. La regla de rechazo/cancelación se documenta como contrato, no como observación de cada ruta de UI.
- **SC-004**: Codex `DENY = GAP` se mantiene visible en la matriz de compatibilidad.

## Dependencies and Risks

- **Dependencies**: `olympus/policies/authority.md`, configs/prompts OpenCode y Codex, test authority y [matriz de harness](../../../../docs/HARNESSES.md).
- **Risks**: Configs de roles no equivalen a ACL inmutable; overrides de sesión y paths externos pueden requerir evidencia separada. Issue #41 no establece por sí mismo un defecto de autorización.
- **Limitación**: Probes de runtime/config están descritos en el código, pero no se encontró un artefacto de salida actual de ese runtime en el material revisado.

## Verification Scope

E003 contiene fuentes y el scope del cualificador. No se ejecutó el cualificador ni ASK en OpenCode/Codex durante esta tarea.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Semántica de autoridad y config declarada | `authority.md`, `config.jsonc`, `config.toml`, `root.md` | Deterministic | NOT RUN |
| Casos de permisos aislados/sintéticos | `tests/authority/qualify.ps1` | Simulated | NOT RUN |
| ASK UI/decisión y comportamiento de proceso nativo | Procedimiento runtime del cualificador; sin artefacto verificado en este ledger | Real runtime | NOT RUN / no observado |

## Assumptions

- Las capacidades del adapter se describen usando la matriz del baseline; no se presume que un control de un harness exista en el otro.
