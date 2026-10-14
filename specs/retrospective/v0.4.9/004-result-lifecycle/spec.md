# Feature Specification: Lifecycle y reconciliación de resultados

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: PARTIAL en capacidades declaradas v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar lifecycle existente; sin cambios de producto ni cualificación/experimentos de runtime.  
**Evidence Reviewed**: E004-1–E004-4 e historial atribuido en el [ledger](../EVIDENCE.md).

**Input**: Inventario retrospectivo de barreras de pregunta/completion, resultados faltantes y mutaciones interrumpidas.

## Purpose and Actors

El lifecycle evita declarar completion a partir de una respuesta prematura o perder la relación con trabajo original. Actores: usuario, Kael/root, child asignado y harness que entrega estados/resultados.

**Problem addressed (as built)**: Errores tempranos del parent, resultados ausentes y procesos externos pueden dejar incierto el estado terminal del trabajo original.

## Scope and Interpretation

El Core asigna a Kael la espera de trabajo requerido, reconciliación de cada identidad original, obtención/validación y consumo de resultados antes de declarar completion. Un error temprano de parent no prueba que el child haya fallado; no se reintenta a ciegas cuando el estado es indeterminado. La política permite seguir con la operación original cuando se reconcilia evidencia positiva de que no se ejecutó; también permite una corrección acotada después de consumir un resultado terminal y conciliar sus efectos, si falla materialmente la aceptación y nueva evidencia/estrategia justifica corregir. No permite replay de efectos ya completados ni retry mientras haya ejecución o resultado desconocido. El prompt OpenCode describe un ledger efímero; no es scheduler o estado persistente adicional. Codex expresa reglas en instrucciones raíz y tiene capacidades documentadas de delivery/completion, con reconciliación y barrera de preguntas parciales.

El contrato de ownership para trabajo en procesos externos recibe identidad/receipt y progreso acotado, y distingue ACTIVE, STALLED, ORPHANED y UNKNOWN. No autoriza terminar procesos por nombre global ni retry ciego; es un contrato de instrucciones y verificación, no un daemon o servicio automático. Codex no presenta el mismo detalle de lifecycle de proceso.

Para tareas con salida estructurada, la policy conserva nombres de campo `EXPECTED_OUTPUT` y los valores producidos; no sustituye la respuesta con un resumen renombrado o con pérdida de campos. El contrato está presente en policy/prompts y tiene un cualificador de fidelidad determinista/sintético; no se infiere un smoke runtime posterior a esa integración.

Las capturas seleccionadas acreditan solamente los eventos que conservan. Raw sessions no se inspeccionaron; algunas son proyecciones redactadas y no incluyen timing exacto de consumo. La continuidad de autorización tras compaction no está demostrada: un PASS histórico de resume ordinario no cubre ese caso.

## User Scenarios & Testing

### User Story 1 - No declarar cierre antes de consumir resultados originales (Priority: P1)

Una persona pide trabajo delegado; Kael espera por las tareas necesarias y reporta sólo un resultado terminal que pudo reconciliar y revisar.

**Why this priority**: El resultado final depende de la ejecución original; una señal temprana, ausencia de salida o estado idle no establece el resultado.

**Independent Test**: Los checks deterministas/sintéticos comprueban clasificación de identidades/estados; las proyecciones archivadas se revisan como observaciones acotadas, sin inferir cada ejecución.

**Acceptance Scenarios**:

1. **Given** que un child original está activo o su output está pendiente, **When** el parent reporta error de correlación, **Then** el trabajo permanece pendiente y no se asigna un resultado de fallo por inferencia.
2. **Given** que la ejecución original alcanza terminal y el resultado está disponible, **When** Kael lo reconcilia, **Then** valida/consume el resultado requerido antes de completion.
3. **Given** que se desconoce identidad o estado de ejecución, **When** el resultado original no está reconciliado, **Then** Kael conserva `COMPLETION_UNCONFIRMED` y no reintenta ni repite efectos a ciegas.
4. **Given** un resultado terminal ya consumido y efectos reconciliados con falla material de aceptación, **When** nueva evidencia/estrategia justifica una corrección, **Then** se limita a la corrección necesaria y no reproduce efectos ya completados.

### Edge Cases

- Si una pregunta ordinaria necesaria se conoce antes de lanzar trabajo dependiente, se pregunta antes de esa rama. Después del fan-out, preguntas ordinarias esperan la reconciliación del trabajo/resultados requeridos; el trabajo independiente útil puede continuar. Una solicitud de ASK nativa puede aparecer por separado.
- Una primera respuesta, launch acknowledgement, sesión idle o ausencia en lista no prueba completion.
- Checkpoint/compaction no equivale a un resume ordinario probado ni crea autorización Aegis nueva.

## Requirements

### Functional Requirements

- **FR-001**: Kael reconcilia miembros de la familia original y reúne el resultado terminal de cada tarea requerida antes de finalizar.
- **FR-002**: Errores tempranos de correlación no reemplazan la verdad terminal observable del child original.
- **FR-003**: Evidencia reconciliada de no ejecución permite continuar la operación original. Tras resultado terminal consumido, aceptación material fallida y efectos conciliados, nueva evidencia/estrategia puede justificar una corrección acotada. Ejecución viva o desconocida no permite retry; no se repiten efectos ya completados.
- **FR-004**: Preguntas, ejecución, visibilidad de resultado y outcome se mantienen como estados distintos; una pregunta conocida antes del trabajo dependiente precede su lanzamiento, y después de fan-out la barrera de pregunta ordinaria respeta reconciliación sin bloquear trabajo independiente útil.
- **FR-005**: Mutaciones compuestas interrumpidas se reconcilian por efectos ya aplicados y faltantes; no se repite el lote entero a ciegas.
- **FR-006**: Codex/openCode muestran diferente grado de soporte para delivery, reconciliación y barrera; no se afirma paridad.
- **FR-007**: La evidencia de resume ordinario no se extrapola a la continuidad de autoridad por compaction.
- **FR-008**: Ownership de proceso externo usa identidad/receipt y progreso acotado, conserva los estados ACTIVE/STALLED/ORPHANED/UNKNOWN y no habilita kill por nombre o retry ciego.
- **FR-009**: La entrega terminal estructurada preserva nombres de campo esperados y valores producidos; no sustituye salida estructurada por una paráfrasis incompleta.

### Key Entities

- **Original child**: ejecución identificada que conserva ownership hasta su terminal/reconciliación.
- **Result state**: pending, visible, unavailable o unknown según la evidencia disponible; ejecución/result desconocido mantiene completion sin confirmar.
- **Completion**: outcome permitido sólo después del trabajo y resultados requeridos.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Una señal de error parent previa al terminal child no se reporta como fallo de la ejecución original.
- **SC-002**: Una conclusión completion incluye la reconciliación del trabajo requerido y el consumo de sus resultados.
- **SC-003**: Si la ejecución o el resultado original es desconocido, el estado es `COMPLETION_UNCONFIRMED`; `NOT RUN` sólo indica que un check conocido no se ejecutó. Ninguno habilita retry automático.
- **SC-004**: Compaction y resume ordinario se registran como escenarios separados.

## Dependencies and Risks

- **Dependencies**: `result-lifecycle.md`, instrucciones Kael/Aegis de ambos harnesses, ownership externo, result reconciliation y question barrier tests.
- **Risks**: El ledger OpenCode es ephemeral/prompt-level y Codex tiene recovery parcial; no atribuir un poller/daemon/dedupe persistente. Issue #1 sigue abierto; issue #8 diferencia resume ordinario de continuidad tras compaction, que sigue desconocida.
- **Aegis boundary**: Aegis sigue un flujo explícito separado; su resultado requiere la misma reconciliación, pero lifecycle normal no le concede entrada de mantenimiento.

## Verification Scope

E004 distingue fixtures sintéticos de proyecciones nativas archivadas. No se reejecutaron checks, conversación, compaction ni runtime.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Políticas de pregunta/completion y no-retry | Fuente Core y test fixtures | Deterministic | NOT RUN |
| Missing result y question races | `tests/result-reconciliation/qualify.ps1`, `tests/question-barrier/qualify.ps1` | Simulated | NOT RUN; live race no automatizada |
| Ownership y estados de proceso externo | `tests/external-work-ownership/qualify.ps1`; instrucciones Aegis | Deterministic / simulated | NOT RUN; no servicio automático atribuido |
| Fidelidad de salida estructurada | `tests/maintenance-handoff/qualify-fidelity.ps1`; policy/prompts | Deterministic / simulated | NOT RUN; no se infiere smoke posterior a la integración |
| Capturas B3/E2/H seleccionadas | Proyecciones archivadas con metadata de redacción | Real runtime | Evidencia histórica acotada; no raw export ni reejecución |
| Resume tras compaction y reconciliación de autoridad | Issue #8 y límites descritos | Real runtime | UNKNOWN / NO DEMOSTRADO |

## Assumptions

- La clasificación PARTIAL refleja límites de capacidad y evidencia documentados; no afirma que cada ejecución de v0.4.9 falló.
