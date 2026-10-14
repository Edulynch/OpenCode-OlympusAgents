# Feature Specification: Aprovisionamiento de worktrees

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: SHIPPED en la implementación v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar el helper OpenCode existente; no crear worktrees ni correr smoke tests.  
**Evidence Reviewed**: E008-1–E008-5 en el [ledger](../EVIDENCE.md); fuente y guías al commit indicado.

**Input**: Inventario retrospectivo del setup de recursos Olympus en worktrees de Git.

## Purpose and Actors

El helper instala recursos Olympus administrados en worktrees Git relacionados. Los actores son quien administra el checkout OpenCode y quien trabaja en el worktree. La capacidad prepara archivos/configuración; el resultado de una sesión de agente es otro límite.

**Problem addressed (as built)**: Un worktree relacionado puede carecer de recursos Olympus del checkout base, y el helper prepara sólo los administrados que faltan.

## Scope and Interpretation

La capacidad es específica al comando de startup de proyecto OpenCode y su helper opt-in. El operador activa el comando de startup expresamente; copiar el helper distribuido no modifica automáticamente comandos de startup existentes ni preferencias globales. El helper comprueba que origen y destino pertenezcan al mismo Git common directory, copia sólo recursos administrados faltantes y valida hash/ownership/conflictos. Un reporte histórico del issue #27 observó Kael activation y los primeros prompts de sólo lectura en B/C de worktrees vinculados sobre la implementación candidata original; esa observación no se repitió después de cada cambio protector y no prueba el replay del código v0.4.9. No se declara una implementación equivalente de setup nativo Codex.

Los escenarios son ejemplos de comprobación del código existente, no criterios históricos reconstruidos. El test determinista crea worktrees Git reales con CLI stub; el smoke nativo está disponible como script, pero no se ejecutó en esta auditoría.

## User Scenarios & Testing

### User Story 1 - Preparar recursos administrados en un worktree (Priority: P1)

Una persona desarrolla en un worktree creado después de habilitar el setup y necesita que los recursos Olympus gestionados estén disponibles sin sobrescribir contenido de usuario.

**Why this priority**: El hook de setup es la integración del producto para que un worktree nuevo encuentre los recursos administrados del checkout base.

**Independent Test**: El contrato `tests/worktree-activation/qualify.ps1` crea worktrees con Git real y comprueba manifest/harness usando un CLI stub; el smoke nativo verifica API/hook aparte. El informe de issue #27 es evidencia H de una candidata anterior, no resultado del código actual re-ejecutado.

**Acceptance Scenarios**:

1. **Given** un source checkout y un worktree destino del mismo Git common directory, **When** se ejecuta el helper, **Then** escribe sólo los recursos administrados que faltan y conserva los mismos hashes.
2. **Given** un destino con recurso de usuario, drift, o sin pertenencia al mismo checkout, **When** se valida el worktree, **Then** el contenido ajeno no se sobrescribe y la condición queda visible como conflicto o error.
3. **Given** un worktree provisionado, **When** se inspecciona su manifest/default agent, **Then** existe la metadata de instalación; los prompts/delegación históricos se atribuyen sólo al candidato reportado, no a una verificación del baseline actual.

### Edge Cases

- Worktree de otro common directory, path traversal, link/reparse point, recurso administrado modificado o recurso del usuario con el mismo nombre.
- El hook es opt-in; un worktree creado antes de habilitarlo requiere el comando de setup documentado.
- La instalación del helper no activa por sí sola un comando startup existente ni toca preferencias globales.

## Requirements

### Functional Requirements

- **FR-001**: El helper compara Git root y common directory para validar la relación entre source checkout y target worktree.
- **FR-002**: El helper normaliza paths administrados y valida contención, contenido/hash y ownership en source y destino.
- **FR-003**: El helper escribe sólo archivos administrados faltantes; no reemplaza los existentes ni altera worktrees arbitrarios.
- **FR-004**: El operador activa el comando de startup OpenCode de forma opt-in; copiar/distribuir el helper no edita automáticamente startup commands existentes ni preferencias globales. La guía describe activación nativa y setup manual.
- **FR-005**: La evidencia de setup no se considera prueba de roster efectivo, prompt, delegación, resultado o cancelación.

### Key Entities

- **Source checkout**: checkout base desde donde se instala y habilita el helper.
- **Target worktree**: checkout relacionado donde se verifican/escriben únicamente paths administrados.
- **Managed resource**: archivo Olympus con ownership/hash comparables.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Un worktree del mismo common directory recibe sólo los paths administrados que faltan y conserva los hashes de origen.
- **SC-002**: Worktrees ajenos o contenido conflictivo quedan bloqueados sin sobrescritura de archivos de usuario.
- **SC-003**: Con el comando de startup activado por el operador o setup manual invocado, el helper prepara archivos de configuración/manifest para el harness instalado.
- **SC-004**: La ficha separa de forma explícita provisioning y comportamiento de agente/runtime.

## Dependencies and Risks

- **Dependencies**: Git worktrees; recursos instalados por bootstrap; [guía WORKTREES](../../../../docs/WORKTREES.md); helper `worktree-setup.ps1`; proyecto OpenCode y su startup hook.
- **Risks**: Un setup exitoso no implica que la versión v0.4.9 actual haya cargado roster, completado delegación o manejado cancelación. La evidencia #27 es de un candidato original; el script de smoke nativo omite prompts/modelo/delegación/cancelación, tal como limita [DEVELOPMENT](../../../../docs/DEVELOPMENT.md). El evento/cause original de cancellation no se capturó; no se concluye que cada cancelación haya quedado corregida.
- **Adapter boundary**: El helper pertenece al adapter OpenCode. Codex no se usa para afirmar o negar soporte de worktree fuera de ese mecanismo.

## Verification Scope

E008 lista la fuente y contratos. No se ejecutó helper, creación de Git worktree, OpenCode API ni smoke nativo en esta actualización.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Paths, hashes, manifests en worktrees | `tests/worktree-activation/qualify.ps1` con Git real y CLI stub | Simulated | NOT RUN |
| Startup hook y `worktree.create` | `tests/worktree-activation/native-smoke.ps1` | Real runtime | NOT RUN; no se afirma UI/agente |
| Kael activation y primeros prompts read-only en B/C linked worktrees | Issue #27 reporta OpenCode 2.0.26 sobre candidate implementation original | Real runtime | H histórico; no replay v0.4.9 verificado |
| Manual setup y limitaciones | `docs/WORKTREES.md`, `docs/DEVELOPMENT.md` | Deterministic | NOT RUN |

## Assumptions

- El resultado reportado se limita a crear/activar recursos administrados en worktrees OpenCode dentro de un mismo repositorio Git.
