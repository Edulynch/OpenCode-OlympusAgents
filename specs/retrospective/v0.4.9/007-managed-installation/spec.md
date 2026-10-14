# Feature Specification: Instalación administrada

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: SHIPPED en la implementación v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Documentar instaladores, ownership, manifests y límites; no ejecutar ni modificar un instalador.  
**Evidence Reviewed**: E007-1–E007-3 en el [ledger](../EVIDENCE.md); fuentes y contratos al commit indicado.

**Input**: Inventario retrospectivo del bootstrap por proyecto, instalación global y desinstalación administrada.

## Purpose and Actors

La capacidad administra recursos Olympus en un proyecto o destino global y permite verificar/desinstalar el harness seleccionado. Actores: operador del instalador, mantenedor de la distribución y usuario propietario de archivos ajenos que el proceso debe preservar.

**Problem addressed (as built)**: Manifests, ownership y hashes distinguen recursos administrados de archivos que pertenecen al usuario durante install, verify y uninstall.

## Scope and Interpretation

Esta ficha describe cómo el bootstrap exige como destino de proyecto la raíz absoluta exacta de un Git worktree, detecta estado administrado/drift/conflictos, registra ownership y verifica el harness seleccionado. La instalación/upgrade es aditiva: conserva el harness no seleccionado y la configuración base/global o de usuario. El manifiesto `installed_harnesses` identifica harnesses instalados. La ruta de migración project-local es un override explícito, no un escaneo/borrado automático de preferencias. Incluye instalación global y retiro de archivos administrados. No declara que una serie de escrituras sea transaccional ni atribuye la falta de rollback exterior a un incidente observado. El issue #51 sustenta un riesgo inferido de estado parcial, no pérdida de datos reproducida.

## User Scenarios & Testing

### User Story 1 - Instalar y verificar sólo recursos administrados (Priority: P1)

Una persona operadora instala Olympus en un checkout o destino global y quiere que los recursos escritos, manifiesto y verificaciones correspondan al scope/harness elegido, preservando archivos ajenos.

**Why this priority**: La propiedad explícita permite distinguir recursos gestionados de archivos del usuario y detectar drift antes de sobrescribir o retirar contenido.

**Independent Test**: Revisar el plan/manifiesto y las condiciones de `Assert-Target`, `Assert-Managed`, `Assert-No-Conflicts` y `Assert-InstalledHarness`; los fixtures existentes ejercitan estos contratos sin requerir agente interactivo.

**Acceptance Scenarios**:

1. **Given** la ruta absoluta exacta de la raíz de un Git worktree y un harness seleccionado, **When** bootstrap planifica/instala, **Then** registra los recursos gestionados y valida el estado instalado para ese harness.
2. **Given** contenido administrado con drift, conflicto o ruta fuera del límite permitido, **When** se valida el destino, **Then** la condición se trata como blocker y no como autorización para sobrescribir contenido ajeno.
3. **Given** un manifiesto de proyecto con un harness seleccionado, **When** se desinstala ese harness, **Then** se validan las entradas administradas antes de retirar esos paths y se preservan recursos no seleccionados.

### Edge Cases

- Un path absoluto, traversal o reparse/symlink fuera del destino no debe tratarse como path administrado válido.
- El estado de un manifiesto ausente, alterado o incompatible es distinto a éxito de verificación.
- Falta de manifest de ownership requerido falla cerrada ([issue #46](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/46)); verify-only no modifica el destino ni inicia discovery del runtime externo.
- Una interrupción entre escrituras y validación puede dejar estado parcial; no se documenta rollback total.

## Requirements

### Functional Requirements

- **FR-001**: El bootstrap exige la ruta absoluta exacta de la raíz del Git worktree destino y valida entradas managed por manifiesto/ownership/hash.
- **FR-002**: El bootstrap detecta conflictos y drift en paths administrados y produce un plan/manifest para los recursos y harness seleccionados.
- **FR-003**: La verificación de harness en modo verify-only es de sólo lectura: no modifica el destino ni inicia discovery/reparación del runtime externo.
- **FR-004**: La instalación global resuelve un destino seguro, manifiesto y outputs por harness; instalación/upgrade agrega el harness elegido preservando baseconfig global/usuario y el harness no seleccionado.
- **FR-005**: El manifest de instalación identifica los harnesses instalados; la desinstalación global/proyecto valida hash/ownership de las entradas seleccionadas y conserva el otro harness y archivos fuera del manifiesto objetivo.
- **FR-006**: Instalación, manifest y desinstalación no convierten una escritura parcial observada en una afirmación de atomicidad.

### Key Entities

- **Managed manifest**: inventario de los recursos propios, harnesses y hashes esperados.
- **Selected harness**: superficie de OpenCode o Codex que el operador solicita verificar, instalar o retirar.
- **Managed path**: ruta bajo el destino permitido que el manifiesto atribuye a Olympus.

## Success Criteria

### Measurable Outcomes

- **SC-001**: El destino del proyecto coincide con la raíz absoluta exacta del Git worktree; los paths a modificar se validan por contención y ownership.
- **SC-002**: El manifiesto permite detectar ausencia, drift, conflicto y selección de harness durante verificación.
- **SC-003**: La desinstalación elimina solamente entradas administradas validadas del harness objetivo.
- **SC-004**: Verify-only no escribe en el destino ni inicia discovery externo del runtime.

## Dependencies and Risks

- **Dependencies**: `scripts/bootstrap.ps1`, `scripts/global-install.ps1`, `scripts/project-uninstall.ps1`, manifests generados, harness outputs y entry points descritos en [006](../006-public-installation-ux/spec.md).
- **Risks**: El issue #51 describe la secuencia write→manifest→validation sin rollback exterior. Se califica como riesgo de estado parcial; no se observó ni reprodujo pérdida de datos o recuperación bloqueada.
- **Runtime/platform**: La cualificación de instaladores está acotada a Windows para ambos harnesses; no implica paridad de comportamiento de runtime. La capacidad global OpenCode tiene un reporte externo de v0.4.6; los reportes Codex son atribuidos. Ninguno se vuelve a probar aquí ni se presenta como nueva aceptación v0.4.9.

## Verification Scope

E007 enumera los contratos. Los scripts y fixtures fueron leídos; no se ejecutaron instalación, reparación, verify ni uninstall en esta actualización documental.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Destino seguro, manifest, ownership, drift/conflict | `tests/global-installer/qualify.ps1`, tests release de installer/dirty worktree | Simulated | NOT RUN |
| Contención y outputs/hash de bootstrap | Fuente `scripts/bootstrap.ps1` y contrato existente | Deterministic | NOT RUN |
| Instalación global OpenCode/Codex | Reporte externo OpenCode v0.4.6/2.0.26; Codex reportado por separado, sin raw output re-ejecutado aquí | Real runtime | H histórico; no es aceptación runtime v0.4.9 |
| Revisión de issue #51 | Inspección de fuente/secuencia documentada | Deterministic | Riesgo inferido; no incidente reproducido |

## Assumptions

- El estado SHIPPED se refiere a implementación en fuentes del baseline, no a una comprobación nueva de todas las rutas de instalación.
