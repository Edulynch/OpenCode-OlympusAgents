# Feature Specification: UX de instalación pública

**Feature Branch**: N/A (documentación retrospectiva)  
**Created**: 2026-10-14  
**Status**: SHIPPED en la implementación v0.4.9  
**Documentation Review**: Revisado y aceptado por Kael y Vera el 2026-10-14.  
**Documentation Mode**: Existing (retrospective)  
**Baseline**: v0.4.9, `c30a19dd410b1815f4591b204615cae0dd9e9a5f`  
**User Constraints**: Inventariar comportamiento existente; no cambiar instaladores ni ejecutar una instalación.  
**Evidence Reviewed**: E006-1–E006-4 en el [ledger](../EVIDENCE.md); fuentes al commit indicado.

**Input**: Inventario retrospectivo de las entradas públicas de instalación y desinstalación.

## Purpose and Actors

La capacidad ayuda a operadores a elegir destino y harness durante instalación/desinstalación y ofrece rutas latest o pinneadas para obtener el instalador. El actor es quien ejecuta PowerShell, no un usuario interactivo del agente Olympus.

**Problem addressed (as built)**: Los entrypoints ofrecen selección interactiva de scope/harness sin argumentos y despacho directo por parámetros, mientras wrappers legacy conservan variantes fijas; esto no añade una UX sin checkout.

## Scope and Interpretation

Los entry points preguntan scope y harness sólo cuando no se proporciona ningún argumento (`$PSBoundParameters.Count -eq 0`). Si la invocación contiene argumentos, entra al modo directo: una combinación incompleta o inválida falla con `ARGUMENTS_INVALID` en vez de preguntar lo que falta; la llamada sin argumentos en una entrada redirigida/no interactiva falla con `ARGUMENTS_REQUIRED`. El wrapper `launch-latest` busca el tag reciente, mientras la entrada directa fija v0.4.9 por defecto; no son la misma versión de instalador. Los wrappers legacy adicionales mantienen su scope y harness fijos. Los escenarios son ejemplos para verificar el código actual, no aceptación histórica inventada.

## User Scenarios & Testing

### User Story 1 - Seleccionar alcance y harness (Priority: P1)

Una persona operadora invoca instalación o desinstalación y usa el modo sin argumentos para elegir scope/harness, o pasa una combinación válida completa en modo directo.

**Why this priority**: El scope y harness seleccionados determinan qué instalación administrada se crea o retira.

**Independent Test**: Revisar el gate de entrada sin argumentos y las funciones `Read-InstallScope`, `Read-InstallHarness`, `Read-UninstallScope` y `Read-UninstallHarness`; el cualificador UX simulado comprueba los parámetros de proceso, no la instalación.

**Acceptance Scenarios**:

1. **Given** una invocación sin argumentos, **When** el entry point se ejecuta con entrada interactiva, **Then** solicita scope y harness; una invocación sin argumentos redirigida exige argumentos en vez de leer un prompt.
2. **Given** una invocación directa válida como `-Project -Here -Harness all`, `-ProjectPath '<path>' -Harness codex` o `-Global -Harness opencode`, **When** el entry point la despacha, **Then** conserva la combinación especificada sin prompts.
3. **Given** una invocación con argumentos incompletos o inválidos, **When** entra en modo directo, **Then** devuelve error de argumentos y no rellena campos con prompts interactivos.

### Edge Cases

- La entrada redirigida sin argumentos exige parámetros; cualquier argumento selecciona modo directo, aunque falten parámetros requeridos.
- El wrapper `launch-latest` y la instalación directa tienen distintas políticas de versión; no deben describirse como la misma fuente de binarios.

## Requirements

### Functional Requirements

- **FR-001**: Las entradas `install-olympus.ps1` y `uninstall-olympus.ps1` preguntan scope/harness sólo si no reciben ningún argumento; con argumentos, requieren una firma directa completa y válida y no hacen fallback a prompts.
- **FR-002**: `scripts/launch-latest.ps1` consulta el tag más reciente y solicita el script fijado a ese tag.
- **FR-003**: La entrada directa conserva el default v0.4.9 y valida la versión del archive descargado antes de instalar.
- **FR-004**: El despacho usa la sintaxis de parámetros nativa de PowerShell; no define una interfaz de parámetros estilo GNU.

### Key Entities

- **Scope**: destino de proyecto o global que selecciona la entrada.
- **Harness**: adaptador OpenCode, Codex o selección admitida por el instalador.
- **Entry point**: script público que solicita opciones o reenvía una invocación a un script fijado.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Invocación sin argumentos interactiva obtiene scope/harness mediante prompts; invocación redirigida vacía y modo directo inválido producen sus errores declarados en lugar de prompts parciales.
- **SC-002**: Una instalación directa parte del default v0.4.9 y compara la versión esperada con la del archive.
- **SC-003**: El wrapper latest resuelve el tag actual y obtiene el instalador de ese tag, separado del default directo.

## Dependencies and Risks

- **Dependencies**: PowerShell 7; entry points públicos; scripts de bootstrap/instalación; release/tag consultado por el wrapper latest.
- **Risks**: Los wrappers legacy tienen combinaciones fijas de scope/harness. El issue #66 propone un flujo sin checkout distinto; no significa que el motor actual de instalación falle.

## Verification Scope

Los contratos/cualificadores disponibles se describen en E006. Ningún check se ejecutó de nuevo en esta auditoría.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| Prompts y despacho de parámetros | `tests/installer-ux/qualify.ps1` mockea prompts y comprueba parámetros del proceso | Simulated | NOT RUN |
| Firma y default de scripts | Fuentes `install-olympus.ps1`, `uninstall-olympus.ps1`, `scripts/launch-latest.ps1` | Deterministic | NOT RUN |
| Release-local UX qualification | PR #65 reporta éxito con OpenCode stubbed; validación de tag remoto seguía pendiente | Simulated | PASS histórico atribuido; no equivale a instalación remota |
| Instalación interactiva real | No se encontró evidencia nativa v0.4.9 en el ledger | Real runtime | NOT RUN; sin afirmación de éxito |

## Assumptions

- No se infiere desde los wrappers legacy un flujo portátil de CLI ni una experiencia sin checkout primaria.
