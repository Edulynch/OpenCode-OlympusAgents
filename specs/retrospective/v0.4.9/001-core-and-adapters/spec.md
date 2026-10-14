# Feature Specification: Olympus Core y adaptadores

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: SHIPPED en la implementación v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Describir arquitectura fuente y salidas actuales; no regenerar ni modificar archivos del producto.  
**Evidence Reviewed**: E001-1–E001-3 en el [ledger](../EVIDENCE.md).

**Input**: Inventario retrospectivo de Olympus Core y sus adaptadores OpenCode/Codex.

## Purpose and Actors

El Core centraliza contratos compartidos y genera representaciones específicas por harness. Actores: personas que mantienen Core/adapters y quienes operan Olympus a través de OpenCode o Codex.

**Problem addressed (as built)**: Las fuentes centrales de identidad y modelo alimentan salidas distintas para OpenCode y Codex, con límites propios por runtime.

## Scope and Interpretation

Olympus Core mantiene los doce roles, identidades, modelos por runtime, responsabilidades de orquestación, capacidades y políticas canónicas. `scripts/render_harnesses.py` produce archivos para OpenCode y Codex desde el Core y sus fuentes de adapter. OpenCode tiene 12 agentes generados; Codex tiene 10 especialistas y representa a Kael mediante el root thread y `root.md`; no se genera Aegis para Codex.

Compartir Core no implica paridad de runtime. El renderer usa stems de los archivos de rol para el roster, pero no consume el contenido de `olympus/roles/*.md`. También deja fuera del contenido generado los cuerpos de las políticas canónicas de autoridad y ciclo de resultados; los adapters mantienen texto de política correspondiente por separado. Esta frontera no significa que todo control esté ausente, y una comparación de bytes aprobada no prueba sincronía semántica completa entre instrucciones o capacidades.

## User Scenarios & Testing

### User Story 1 - Mantener un núcleo canónico con salidas específicas (Priority: P1)

Una persona que mantiene Olympus modifica una fuente Core y necesita que las superficies declaradas de cada runtime se deriven de esa fuente según el renderer existente.

**Why this priority**: El Core representa definiciones compartidas; las salidas adaptan su expresión al runtime.

**Independent Test**: Comparar fuentes de identidad/modelo, outputs del renderer y los checks de Harness Core; esto verifica estructura de generación, no semántica total de cada prompt.

**Acceptance Scenarios**:

1. **Given** el conjunto de fuentes Core del baseline, **When** se resuelve el roster para ambos adaptadores, **Then** se identifican 12 agentes OpenCode y 10 especialistas Codex, con Kael en el root de Codex y sin agente Aegis.
2. **Given** una identidad o mapping de modelo por runtime, **When** el renderer la procesa, **Then** genera sus representaciones para los adapters según las tablas de Core.
3. **Given** una verificación de outputs generados, **When** se compara el contenido, **Then** el resultado sólo prueba igualdad de outputs cubiertos, no que toda política o cuerpo de `roles/*.md` fue consumido.

### Edge Cases

- Un role stem puede estar en el roster aunque el contenido del archivo de rol no sea una entrada del renderer.
- Identidad/modelo compartido no garantiza autorización, herramienta, lifecycle, comando o capacidad runtime equivalente.
- Codex no tiene Aegis y no debe generarse un sustituto por similitud nominal.

## Requirements

### Functional Requirements

- **FR-001**: El Core mantiene el roster canónico de 12 roles con identidades y asignaciones de modelo/familia/esfuerzo por runtime.
- **FR-002**: El renderer transforma las fuentes Core y adapter en 12 agentes OpenCode y 10 especialistas Codex, con Kael como root de Codex.
- **FR-003**: Los archivos de rol describen responsabilidad, pero su contenido no se considera consumido por el renderer actual.
- **FR-004**: Las capacidades y límites de cada adapter se evalúan por evidencia propia; un nombre o modelo compartido no constituye paridad.
- **FR-005**: La verificación de outputs compara los artefactos seleccionados y no se presenta como garantía de sincronización semántica total.

### Key Entities

- **Olympus Core**: fuentes canónicas de roles, identidades, modelos, políticas y capacidades.
- **Harness adapter**: fuente que expresa Core en las superficies nativas OpenCode o Codex.
- **Generated output**: archivo de runtime generado; su autoridad de edición permanece en la fuente Core/adapter.

## Success Criteria

### Measurable Outcomes

- **SC-001**: El roster generado contiene los 12 roles OpenCode y los 10 especialistas Codex del baseline.
- **SC-002**: Kael se representa como root thread de Codex; no existe salida Codex para Aegis.
- **SC-003**: El mapping de modelos e identidades es derivado de las tablas Core soportadas por el renderer.
- **SC-004**: Se registran explícitamente los contenidos y políticas que el renderer no incorpora.

## Dependencies and Risks

- **Dependencies**: `olympus/core/`, `olympus/roles/`, `olympus/policies/`, `olympus/harnesses/` y `scripts/render_harnesses.py`; detalle de fuentes en [docs/HARNESSES.md](../../../../docs/HARNESSES.md).
- **Risks**: Como el renderer no lee los cuerpos de los roles ni inyecta toda policy, instrucciones adaptadas pueden divergir semánticamente. El inventario registra esta frontera sin prescribir una reparación no autorizada.
- **Runtime difference**: OpenCode expresa Kael como agente primario; Codex como thread raíz. Capacidades como Aegis y DENY difieren o son GAP, documentadas en [compatibilidad Codex](../../../../docs/CODEX-COMPATIBILITY.md).

## Verification Scope

E001 lista fuentes y cualificadores deterministas. La auditoría leyó los archivos; no regeneró outputs ni ejecutó cualificadores.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Tablas de modelo/identidad y outputs | `scripts/render_harnesses.py` y outputs generados | Deterministic | NOT RUN en esta auditoría |
| Invariantes de roster, familia/esfuerzo y capacidades | `tests/harness-core/qualify.py`; `tests/codex/validate_profile.py` | Deterministic | NOT RUN en esta auditoría |
| Carga y semántica de instrucciones en runtime | Capacidad depende del adapter; el check de bytes no la acredita | Real runtime | NOT RUN / desconocido según capacidad |

## Assumptions

- Se usan las asignaciones definidas en `olympus/core/models.toml`; un modelo/ID histórico en un reporte no cambia el mapping del baseline.
