# Feature Specification: Mantenimiento explícito con Aegis

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: PARTIAL en capacidades declaradas v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar la superficie autorizada sin cambios de producto ni cualificación de runtime.  
**Evidence Reviewed**: E005-1–E005-2 y reportes atribuidos en el [ledger](../EVIDENCE.md).

**Input**: Inventario retrospectivo del plano de mantenimiento privilegiado.

## Purpose and Actors

El plano separa una operación de mantenimiento privilegiada del routing regular. Actor habilitador: usuario que invoca `/maintain`; Aegis realiza esa tarea, mientras Kael y children permanecen fuera de la entrada.

**Problem addressed (as built)**: La tarea privilegiada requiere una entrada explícita de usuario separada del routing normal de Kael.

## Scope and Interpretation

El Core reserva Aegis como executor oculto y privilegiado fuera del routing normal. La única entrada soportada es user → comando OpenCode `/maintain` → Aegis. Kael y sus children no pueden invocarlo ni escalar automáticamente; Aegis no puede autoactivarse, delegar, ampliar scope o retry a ciegas. El usuario puede invocarlo explícitamente en cualquier repositorio; ser un repositorio Olympus no es un requisito de aceptación.

OpenCode no aporta un campo nativo de origen de comando/autoridad. Una entrada nueva válida emite `MAINTENANCE_AUTH: VALID` y `AEGIS_SCOPE: ACCEPTED` inmediatamente antes de usar herramientas; no hay admission gate por repositorio, ownership del repo ni provenance. En una continuación de la misma sesión, la policy acepta sólo el mensaje assistant previo atribuido a Aegis junto con la tarea original aún retenida. Un estado nuevo/desconocido que carece de esa atribución falla cerrado inmediatamente y requiere una nueva invocación explícita `/maintain`. El reporte histórico atribuido de OpenCode 2.0.21 registra aceptación y conservación de la autorización de Aegis en ese caso ordinario de la misma sesión. No acredita continuidad de autorización tras compaction, una captura completa de entrada nueva con resultado ni aceptación de v0.4.9; la continuidad tras compaction permanece no demostrada. Tampoco se reejecuta una mutación aplicada a ciegas tras restaurar contexto. Codex no genera Aegis y mantiene `AEGIS = GAP`; no se inventa equivalencia. Los cualificadores revisados son estáticos/sintéticos; no se encontró captura nativa verificada del comando con resultado.

El handoff de Aegis conserva, donde la tarea solicita estructura, los nombres de campos `EXPECTED_OUTPUT` y los valores producidos; el contrato está en la policy/prompts y la fidelidad del checker no equivale a una captura nativa posterior.

## User Scenarios & Testing

### User Story 1 - Iniciar una tarea privilegiada de forma explícita (Priority: P1)

Una persona que explícitamente solicita mantenimiento usa el entry point mantenido de OpenCode, y Aegis recibe sólo esa tarea dentro del límite aceptado.

**Why this priority**: La separación entre plano normal y mantenimiento privilegiado es una frontera de autoridad.

**Independent Test**: Inspeccionar policy, comando y configuración Aegis; los cualificadores estáticos/sintéticos verifican contrato, pero no reemplazan un smoke interactivo.

**Acceptance Scenarios**:

1. **Given** el usuario inicia explícitamente `/maintain`, **When** OpenCode despacha el comando, **Then** la declaración de entrada del comando establece el scope de ejecución para Aegis.
2. **Given** una continuación de la misma sesión Aegis con aceptación original atribuida y visible, **When** la nueva instrucción continúa la tarea original, **Then** el scope aceptado se conserva sin ampliarse.
3. **Given** una sesión nueva/desconocida o un intento de Kael/child de iniciar Aegis, **When** se requiere la entrada privilegiada, **Then** no hay auto-activación/escalation y se requiere una nueva invocación explícita autorizada.

### Edge Cases

- Un texto de usuario que cita o copia un acceptance previo no prueba que OpenCode adjuntó la sesión original.
- Checkpoint/transcript, título, `parentID` o coincidencia de texto no crean nueva autorización.
- Una invitación desde el flujo normal de Kael no es atajo para cambiar Olympus-owned files.

## Requirements

### Functional Requirements

- **FR-001**: La única entrada de Aegis en OpenCode es la invocación explícita del comando Olympus `/maintain` por el usuario; la entrada nueva válida emite `MAINTENANCE_AUTH: VALID` y `AEGIS_SCOPE: ACCEPTED` antes de tools.
- **FR-002**: El alcance de ejecución es la tarea autorizada por el comando; una continuación no la amplía.
- **FR-003**: Kael no puede invocar Aegis y ningún child puede escalar o crear una cadena hacia Aegis.
- **FR-004**: Aegis no se autoactiva, no delega, no amplía scope y no repite ciegamente una mutación.
- **FR-005**: Continuación de sesión conserva autorización sólo con identidad de sesión/atribución Aegis y tarea original visibles conforme a policy; estado nuevo/desconocido sin esa evidencia falla cerrado.
- **FR-006**: No se genera Aegis para Codex; `AEGIS = GAP` permanece declarado.
- **FR-007**: Reportes de runtime o handoff se atribuyen a su procedencia; pruebas sintéticas no se describen como interacción real.
- **FR-008**: La admisión no se condiciona a que el repositorio pertenezca a Olympus ni a una comprobación de propiedad/provenance del repo; una recuperación de contexto no autoriza repetir ciegamente efectos ya aplicados.
- **FR-009**: Handoff estructurado mantiene nombres de campo esperados y valores producidos sin sustituirlos por una síntesis incompleta; la evidencia del contrato se atribuye separada del runtime observado.

### Key Entities

- **`/maintain` task**: solicitud explícita del usuario que define el scope aceptado.
- **Aegis session**: sesión OpenCode donde el entry point atribuye aceptación a Aegis.
- **Same-session continuation**: continuación que preserva la sesión/tarea original; no es permiso para iniciar una sesión nueva.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Una sesión nueva de Aegis requiere entrada explícita del usuario a través de `/maintain`.
- **SC-002**: La entrada válida declara las señales de autorización/scope antes del primer uso de herramientas; Kael, children y el propio Aegis no pueden autoescalar ni delegar a Aegis.
- **SC-003**: Continuación misma sesión no amplía la tarea que recibió la autorización original.
- **SC-004**: Matriz de compatibilidad registra Codex Aegis como GAP y no inventa un agente.
- **SC-005**: El documento distingue source/static/synthetic de runtime interactivo observado.

## Dependencies and Risks

- **Dependencies**: `maintenance-plane.md`, `olympus/harnesses/opencode/maintain.md`, metadata/prompt Aegis, lifecycle policy y tests de maintenance scope/handoff.
- **Risks**: No existe campo nativo de command-origin/maintenance-auth en OpenCode; la policy depende de sesión y mensaje atribuido para continuación. La UI/handoff real no está comprobada por las fixtures revisadas.
- **Exploración no aprobada**: Issue #28 propone variar Kael→Aegis y contradice la prohibición vigente. No es excepción implementada ni requisito aceptado; figura en el [registro futuro](../../../future/README.md).

## Verification Scope

E005 presenta pruebas de policy y contrato, y marca smoke interactivo como ausente. No se invocó `/maintain` ni se ejecutó prueba durante esta documentación.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Entry point y scope declarado | Core policy, `maintain.md`, metadata/prompts Aegis | Deterministic | NOT RUN |
| Reglas de scope y handoff simulado | `tests/maintenance-scope/qualify.py`, `tests/maintenance-handoff/qualify.ps1` | Simulated | NOT RUN |
| Entrada y resultado visibles en runtime | `live-control.md` da instrucciones, sin capture native verified | Real runtime | NOT RUN / no evidence in repo |
| Resume ordinario y compaction | Issue #8: [resume ordinario](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-5934781194), [reapertura compaction](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6093432997), [auditoría final](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6121112547) | Real runtime | H atribuido; reportes no son evidencia de invocación `/maintain` |
| Aegis Codex | Matriz de capabilities | Real runtime | GAP; no Codex Aegis disponible |

## Assumptions

- La clasificación PARTIAL refleja la diferencia entre política/configuración y evidencia nativa, no prueba una violación ocurrida en cada uso.
