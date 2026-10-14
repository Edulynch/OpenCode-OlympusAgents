# Feature Specification: Calificación y release

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: SHIPPED en la implementación v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar perfiles y gates existentes; no ejecutar FAST/FULL/RUNTIME ni publicar release.  
**Evidence Reviewed**: E010-1–E010-2 y E000-2 en el [ledger](../EVIDENCE.md); fuentes, workflow y metadata histórica.

**Input**: Inventario retrospectivo de los perfiles de cualificación y del proceso de release.

## Purpose and Actors

La capacidad ayuda a contributors y release maintainers a seleccionar checks por contrato/riesgo, cumplir gates de integración y dejar evidencia ligada al commit/tag. FAST/FULL/RUNTIME son perfiles del cualificador, distintos al modo de orquestación NORMAL/FAST de Olympus.

**Problem addressed (as built)**: Los perfiles y gates separan tipos de verificación y vinculan evidencia de CI/release al commit o tag correspondiente.

## Scope and Interpretation

La cualificación distingue FAST offline, FULL (ejecuta FAST exactamente una vez y después las adiciones FULL de Windows) y RUNTIME, un slice separado de evidencia no interactiva de catálogo/config/API/proceso. RUNTIME no equivale a un smoke general de agentes/modelos interactivos. El flujo de release valida fuentes, compatibilidad/instalador, versión/tag inmutable y estabilidad de transición según sus checks existentes. Estas fichas y resultados describen contratos existentes; la CI histórica exitosa del SHA exacto no acredita instalación remota, runtime interactivo o éxito universal de release.

## User Scenarios & Testing

### User Story 1 - Elegir evidencia de calificación adecuada (Priority: P1)

Una persona contribuidora necesita ejecutar el perfil correspondiente al límite que cambió y conservar la diferencia entre pruebas offline/simuladas y comportamiento de un runtime real.

**Why this priority**: Los perfiles tienen alcances distintos y uno no sustituye automáticamente a los demás.

**Independent Test**: Inspeccionar `scripts/qualify.ps1`, el workflow FAST y el contrato de DEVELOPMENT; confirmar que la selección y delimitación de perfiles coincide con lo documentado.

**Acceptance Scenarios**:

1. **Given** un cambio sin dependencia de runtime, **When** corresponde la selección de perfil, **Then** FAST provee sólo evidencia offline definida en su selector.
2. **Given** una aceptación que depende de comportamiento real de harness, **When** la evidencia es requerida, **Then** se identifica un check RUNTIME/nativo enfocado; un resultado FAST o FULL con mocks no se reporta como esa prueba.
3. **Given** un release publicado, **When** se evalúan notas/tag y compatibilidad, **Then** se usan gates de release descritos; una fixture con fuente local no se presenta como prueba del instalador remoto publicado.

### Edge Cases

- FAST contextual como modo de orquestación es distinto a la calificación FAST; ninguno salta gates obligatorios.
- FULL y RUNTIME no son sustitutos: FULL no ejecuta agentes reales; RUNTIME no contiene el perfil FULL.
- CI PASS histórico está vinculado al SHA; no se extrapola a otra revisión.

## Requirements

### Functional Requirements

- **FR-001**: `scripts/qualify.ps1` ofrece selección explícita FAST, FULL y RUNTIME con slices documentados.
- **FR-002**: FAST es offline; FULL ejecuta FAST exactamente una vez y después sus fixtures/checks Windows adicionales; RUNTIME contiene un slice separado de evidencia no interactiva de catálogo/config/API/proceso.
- **FR-003**: La selección de checks preserva gates de CI/release y reporta checks no ejecutados como tales.
- **FR-004**: Los tests de release comprueban aspectos locales/publicados específicos y declaran sus límites; tests con fuente local o mock no se etiquetan como instalación del tag remoto.
- **FR-005**: Los registros de CI deben vincularse al commit correspondiente para sostener afirmaciones sobre el baseline.
- **FR-006**: TFR escoge la evidencia existente más pequeña que cubre el riesgo/interfaz afectada; se preservan gates obligatorios, sin imponer FAST a todo cambio ni duplicar harness/gates.
- **FR-007**: Checks de versión/tag inmutable y transición de release conservan su alcance; un cambio de tag o fuente local no se interpreta como aceptación de instalación remota.

### Key Entities

- **Qualification profile**: selección de checks con límites propios: FAST, FULL o RUNTIME.
- **Release gate**: check del flujo que valida compatibilidad, installer, estado del tag o cuerpo de release.
- **Execution result**: resultado PASS/FAIL/NOT RUN con SHA y artefacto asociados cuando existen.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Cada perfil se describe por los checks que incluye y excluye; FULL corre FAST exactamente una vez antes de sus adiciones, y RUNTIME es slice no interactivo separado.
- **SC-002**: El reporte distingue ejecución actual de fuente de test disponible, simulación y runtime histórico.
- **SC-003**: El registro FAST histórico exitoso enlaza al run cuyo HEAD corresponde al SHA del baseline.
- **SC-004**: Las pruebas de release locales no se presentan como verificación de una instalación remota publicada.

## Dependencies and Risks

- **Dependencies**: `scripts/qualify.ps1`, `.github/workflows/fast.yml`, tests de release, [TFR routing](../../../../olympus/policies/routing.md#L3) y el [procedimiento DEVELOPMENT](../../../../docs/DEVELOPMENT.md).
- **Risks**: Confundir FAST contextual con perfil FAST; convertir fixtures en garantía runtime; reutilizar un PASS histórico para cambios posteriores; omitir una gate de release obligatoria.
- **Platform boundary**: La calificación de instaladores/runtime está actualmente acotada por los procedimientos de Windows. Esto no hace que la arquitectura Core sea intrínsecamente Windows-only; el Python renderer usa standard library. CLI portátil y cualificación hosted cross-platform siguen como aspiraciones #64, no como requisito implementado.
- **Limitación actual de este inventario**: Ningún perfil fue ejecutado en la tarea retrospectiva. FAST/FULL/RUNTIME queda NOT RUN aquí.

## Verification Scope

E010 muestra los scripts y resultados históricos que respaldan esta ficha. La calificación y los tests de release no se ejecutaron durante la documentación.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Selector y contenidos de perfiles | Fuente `scripts/qualify.ps1`; workflow `.github/workflows/fast.yml` | Deterministic | NOT RUN en esta tarea |
| CI FAST del commit baseline | Run GitHub histórico vinculado a `c30a19d…` | Historical evidence | PASS histórico de los checks reportados; no re-ejecutado |
| Instalación / compatibilidad de release | Fixtures existentes usan checkout local, stubs o mocks | Simulated | NOT RUN en esta tarea |
| Runtime interactivo de OpenCode/Codex | Requiere smoke nativo aplicable y límites declarados | Real runtime | NOT RUN en esta tarea |

## Assumptions

- Los scripts y gates de release describen el flujo v0.4.9, mientras que el run histórico valida exclusivamente el commit y los checks reportados allí.
