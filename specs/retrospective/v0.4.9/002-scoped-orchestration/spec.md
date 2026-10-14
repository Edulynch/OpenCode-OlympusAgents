# Feature Specification: Orquestación acotada por Kael

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: SHIPPED en la implementación v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar el routing existente, sin cambios de producto ni cualificación de runtimes.  
**Evidence Reviewed**: E002-1–E002-3 en el [ledger](../EVIDENCE.md).

**Input**: Inventario retrospectivo de cómo Kael selecciona, limita y coordina trabajo delegado.

## Purpose and Actors

La orquestación permite que Kael distribuya trabajo acotado y reconcilie resultados. Actores: usuario que define objetivo/scope, Kael como root y especialistas cuando su contribución es necesaria.

**Problem addressed (as built)**: El trabajo delegado necesita selección de roles por necesidad, ownership acotado y reconciliación por Kael antes del cierre.

## Scope and Interpretation

Kael es el único orquestador conceptual. El Core exige el menor conjunto suficiente de roles, conserva dependencias, propiedad de tareas, barreras y cierre; el máximo es cuatro children abiertos, incluidos los que siguen pendientes de reconciliación, límite y no meta. Una respuesta directa usa cero children; un cambio trivial y determinista puede usar un writer y luego un check directo de Kael. OpenCode representa Kael como agente primario y Codex como hilo raíz. Cada adapter tiene controles/superficies propias; prompts describen política, pero no son scheduler técnico ni garantía de paridad.

OpenCode nativo no soporta la ruta anidada directa que requiere que un hijo origine otro hijo; se clasifica incompatible, sin bypass. Las trazas disponibles cubren caminos seleccionados y contienen casos sintéticos distintos de las proyecciones archivadas. Issue #41 conserva un síntoma de fidelidad de prompt con causa desconocida. Los modos de orquestación NORMAL/FAST son distintos de los perfiles de cualificación FAST/FULL/RUNTIME del mantenedor.

## User Scenarios & Testing

### User Story 1 - Asignar el trabajo suficiente y cerrar el fan-out (Priority: P1)

Una persona usuaria pide trabajo que puede requerir especialistas; Kael decide qué evidencia/raciocinio hace falta, asigna tareas acotadas y reconcilia los resultados originales antes de cerrar.

**Why this priority**: La selección de roles y el cierre pertenecen a Kael en ambos adapters aunque sus superficies nativas difieran.

**Independent Test**: Revisar routing policy/configuración y traces seleccionadas; clasificar por separado checks sintéticos, proyecciones nativas y propiedades no capturadas.

**Acceptance Scenarios**:

1. **Given** una solicitud simple con resultado observable, **When** el routing aplica el fast path documentado, **Then** no fan-out innecesario y se conserva validación proporcional.
2. **Given** tareas independientes que justifican especialistas, **When** Kael hace fan-out bajo el límite del Core, **Then** cada child recibe propiedad/scope y dependencias definidos; el número cuatro se interpreta como techo, no como promesa de cuatro tareas paralelas.
3. **Given** un child termina o su resultado parece faltar, **When** Kael evalúa completion, **Then** reconcilia la identidad y resultado original antes de declarar cierre o retry.

### Edge Cases

- Solicitudes que requieren ejecución child→grandchild chocan con profundidad nativa OpenCode; no se evade el límite.
- La evidencia de mensaje simultáneo no prueba paralelismo de scheduler, speedup ni duración de procesos.
- Una traza de cualificación puede tener children adicionales a la feature bajo observación; no mezclarlos en el conteo de producto.

## Requirements

### Functional Requirements

- **FR-001**: Kael sigue siendo el único root conceptual responsable de routing, scope, assignments, dependencias, preguntas y completion.
- **FR-002**: El conjunto de roles y fan-out se limita a la necesidad observable y al máximo Core de cuatro children abiertos, incluidos los resultados aún pendientes de reconciliar.
- **FR-003**: Cada trabajo delegado conserva ownership y no permite a child agents generar hijos.
- **FR-004**: Normal/FAST permite trabajo independiente sólo bajo límites y gates de validación/completion del Core.
- **FR-005**: Las capacidades se describen por adapter; la configuración de Codex o prompt de OpenCode no prueba scheduler equivalente.
- **FR-006**: Incompatibilidad de profundidad directa y síntomas sin causa demostrada quedan documentados como límites, no como bypasses ni requisitos aprobados.

### Key Entities

- **Kael**: raíz conceptual de coordinación y cierre.
- **Child assignment**: scope, ownership, dependencia y resultado requerido de un especialista.
- **Open child**: ejecución que permanece dentro del límite; el límite no prescribe utilización.

## Success Criteria

### Measurable Outcomes

- **SC-001**: La política conserva un solo orquestador y un máximo configurable actual de cuatro children.
- **SC-002**: Casos triviales pueden suprimir fan-out mientras conservan check y completion apropiados.
- **SC-003**: Rutas/dependencias se atribuyen sólo cuando la traza contiene esos campos; `null` permanece desconocido.
- **SC-004**: La documentación diferencia casos synthetic, captures, limitaciones nativas y reportes de issues.

## Dependencies and Risks

- **Dependencies**: Olympus `routing.md`, `orchestration.toml`, prompts/configs de ambos adapters, completion gates y policies en [EVIDENCE](../EVIDENCE.md).
- **Risks**: Un prompt de child cap no sustituye scheduler enforcement; algunas trazas tienen contexto de cualificación; Phase 12 registra versiones/config efectivas incompletas y no se verificaron logs nativos originales durante esta tarea.
- **Responsabilidades y selección de roles**: Se enruta por necesidad concreta; las responsabilidades canónicas completas están en [Olympus Core](../../../../olympus/roles/) y no se duplican aquí.

| Rol | Responsabilidad en esta coordinación |
|---|---|
| Veyra | Reúne evidencia de repositorio o documentación cuando hace falta. |
| Orin | Resuelve una decisión material de arquitectura/interfaz. |
| Atlas | Ordena un plan de ejecución cuando el trabajo acotado requiere secuencia significativa. |
| Kovan | Escribe el cambio dentro de su scope asignado. |
| Nox | Valida evidencia de test/runtime cuando hace falta. |
| Vera | Revisa independientemente cuando el riesgo o la solicitud lo justifica. |
| Argus | Diagnostica un defecto funcional establecido con causa o dirección de arreglo incierta. |
| Talos | Es obligatorio al diagnosticar un defecto material de seguridad/confianza/autorización establecido o fuertemente evidenciado. |
| Thales | Escala incertidumbre técnica material después de que evidencia ordinaria no baste. |
| Helios | Sólo ante solicitud explícita de optimización; entrega propuesta, no implementación. |
| Aegis | Fuera del routing ordinario; se documenta en [005](../005-explicit-maintenance/spec.md). |

**Futuro/exploración**: Issue #26 jerarquía, #28 Kael→Aegis y #37 supervisión adaptativa siguen no comprometidos. #28 contradice la regla vigente y no se convierte en autoridad. Ver [future registry](../../../future/README.md).

## Verification Scope

Las fuentes y traces referenciadas están en E002. No se ejecutó routing interactivo, check de scheduler ni qualifier de Phase 11/12 en esta tarea.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Scope, límites y gates de routing | Core policy, adapter config/prompt | Deterministic | NOT RUN |
| Escenarios A–L y casos sintéticos | `tests/phase11-integrated-routing/qualify.py`, RUNME | Simulated | NOT RUN |
| Casos archivados OpenCode | Proyecciones B3/C/E2/H/K; ver metadata en EVIDENCE | Real runtime | Observación archivada; no re-ejecutada; no raw export afirmado |
| Resultado Codex/interactividad/scheduler | Sin traza nativa comparable en Phase 11; otras notas atribuidas | Real runtime | NOT RUN / desconocido |

## Assumptions

- La capacidad SHIPPED describe ownership/reglas e interfaces presentes, no garantiza que un runtime dado aplique cada instrucción como enforcement técnico.
