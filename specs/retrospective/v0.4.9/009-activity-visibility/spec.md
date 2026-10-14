# Feature Specification: Visibilidad de actividad

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: PARTIAL en capacidades declaradas v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar visibilidad existente; no abrir UI ni ejecutar plugin.  
**Evidence Reviewed**: E009-1–E009-2 y notas de adapter en el [ledger](../EVIDENCE.md).

**Input**: Inventario retrospectivo de la visibilidad pasiva de children/actividad en los harnesses.

## Purpose and Actors

El HUD ayuda a la persona usuaria a observar actividad delegada sin intervenir en el control de sesiones. Los actores son la persona usuaria/root que observa y el plugin pasivo que lee estado nativo disponible.

**Problem addressed (as built)**: La persona usuaria puede observar pasivamente la actividad disponible de children directos sin controlar ni iniciar sesiones desde el HUD.

## Scope and Interpretation

OpenCode entrega un plugin HUD pasivo de actividad. La fuente toma lista/status de sesiones de children directos, presenta labels resumidos, muestra hasta cuatro y un indicador del resto; se coloca sobre el composer. No crea sesiones, consulta en polling ni ofrece acciones de orquestación. Los tests comprueban estructura, estado, labels y truncación; el cualificador de plugin discovery no prueba el renderizado de la UI activa.

Codex usa su visibilidad nativa y la capacidad está clasificada PARTIAL; no se genera un HUD equivalente. Estado PARTIAL refleja evidencia UI/cross-runtime incompleta, no que OpenCode carezca de plugin.

## User Scenarios & Testing

### User Story 1 - Ver actividad de children directos en OpenCode (Priority: P1)

Una persona usuaria observa la conversación del root durante el trabajo delegado y necesita un resumen pasivo de children que siguen ejecutándose.

**Why this priority**: Visibilidad de actividad ayuda a entender tareas en curso, sin cambiar quién asigna o completa trabajo.

**Independent Test**: Los tests de activity HUD validan estados/datos presentados y truncación; inspección de fuente confirma integración pasiva, no visualización interactiva en runtime.

**Acceptance Scenarios**:

1. **Given** children directos con estado running, **When** el plugin obtiene la lista de sesiones/estado, **Then** sus labels aparecen en el resumen HUD.
2. **Given** una entrada de formatter con más de cuatro children, **When** la lista se presenta, **Then** muestra los primeros cuatro según la regla implementada y el indicador de restantes; este límite de presentación no autoriza exceder el máximo de orquestación Core.
3. **Given** que cambia el estado de hijos o no hay hijos activos, **When** el HUD lee el estado pasivo, **Then** refleja el estado disponible sin crear sesiones ni alterar el flujo de trabajo.

### Edge Cases

- Actividad indirecta o nietos no se asume incluida: el filtro de fuente cubre children directos.
- La entrada de formatter con más de cuatro elementos es sólo una prueba de límite de presentación, no una expectativa de fan-out superior al máximo Core.
- Tests del payload/componente no demuestran que el usuario realmente vio un render en TUI.
- Visibilidad nativa de Codex no equivale a la presentación OpenCode.

## Requirements

### Functional Requirements

- **FR-001**: El plugin OpenCode considera sesiones de children directos y su estado de ejecución para construir el resumen.
- **FR-002**: El resumen etiqueta la actividad, trunca la lista visible a cuatro y comunica que existen elementos restantes.
- **FR-003**: El HUD es pasivo: no inicia children, hace polling ni altera los resultados o decisiones de Kael.
- **FR-004**: Discovery del plugin y representación visual interactiva se verifican por separado.
- **FR-005**: Codex mantiene su visibilidad nativa parcial sin atribuirle el plugin generado OpenCode.

### Key Entities

- **Direct child session**: sesión hijo visible directamente desde la conversación raíz.
- **Activity item**: label y estado corto de una sesión en ejecución.
- **Overflow indicator**: señal para children adicionales no listados individualmente.

## Success Criteria

### Measurable Outcomes

- **SC-001**: La lista de OpenCode deriva de session list/status y filtra direct children running.
- **SC-002**: Presentación de activity conserva límite de cuatro y resto contabilizado.
- **SC-003**: El plugin no contiene acción de spawn, polling ni control de orchestration.
- **SC-004**: El estado de Codex/interactive TUI queda separado del contrato de fuente/test.

## Dependencies and Risks

- **Dependencies**: `olympus/harnesses/opencode/activity.ts`, `tui.tsx`, plugin generado, OpenCode session list/status y `tests/activity-hud/`.
- **Risks**: Confundir presencia/discovery del plugin con render TUI; contar grandchildren como direct children; usar el HUD como mecanismo de scheduling.
- **Runtime difference**: OpenCode dispone de plugin de presentación; Codex mantiene UI nativa con `ACTIVITY_VISIBILITY = PARTIAL` y sin plugin HUD equivalente generado.

## Verification Scope

E009 enumera los test source y su alcance. No se ejecutó discovery, plugin o TUI en esta auditoría documental.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Formato offline y presentación estructural | `tests/activity-hud/activity.test.mjs`, slice offline de `qualify.ps1` | Deterministic / simulated | NOT RUN |
| Discovery del plugin por CLI OpenCode | Slice runtime de `tests/activity-hud/qualify.ps1` | Real runtime (evidencia R si se ejecuta) | NOT RUN; discovery no es render |
| Render OpenCode visible al usuario | Sesión interactiva | Real runtime | NOT RUN / sin evidencia observada |
| Visibilidad nativa Codex | Capabilities/docs del adapter | Real runtime | PARTIAL reportado; no ejecutado aquí |

## Assumptions

- La actividad descrita se limita a children directos y estados que el API/session list ofrece; no se infiere progreso interno del modelo.
