# Auditoría y uso de Spec Kit

Esta guía registra la auditoría documental de Spec Kit realizada contra OlympusAgents **v0.4.9**, la línea base funcional local indicada para esta actualización. La constitución aplicable está en [memory/constitution.md](memory/constitution.md). Los overrides de plantillas están en [templates/overrides/](templates/overrides/); las cinco plantillas originales se conservan en `templates/`.

## Inventario inicial

Al inicio de la auditoría se encontraron estos 21 archivos bajo `.specify`:

```text
.gitignore
init-options.json
integration.json
integrations/codex.manifest.json
integrations/opencode.manifest.json
integrations/speckit.manifest.json
memory/.constitution-template.json
memory/constitution.md
scripts/powershell/check-prerequisites.ps1
scripts/powershell/common.ps1
scripts/powershell/create-new-feature.ps1
scripts/powershell/resolve-template.ps1
scripts/powershell/setup-plan.ps1
scripts/powershell/setup-tasks.ps1
templates/checklist-template.md
templates/constitution-template.md
templates/plan-template.md
templates/spec-template.md
templates/tasks-template.md
workflows/speckit/workflow.yml
workflows/workflow-registry.json
```

La actualización modifica un archivo y crea cuatro. El propósito de cada cambio es:

| Archivo | Cambio y motivo |
|---|---|
| [`memory/constitution.md`](memory/constitution.md) | Actualizado desde el scaffold sin ratificar a la constitución v1.0.0, con principios verificables y referencias canónicas. |
| [`templates/overrides/spec-template.md`](templates/overrides/spec-template.md) | Nuevo; distingue comportamiento existente documentado con evidencia de alcance nuevo o modificado. |
| [`templates/overrides/plan-template.md`](templates/overrides/plan-template.md) | Nuevo; guía un diseño basado en rutas reales, riesgos y verificación proporcional. |
| [`templates/overrides/tasks-template.md`](templates/overrides/tasks-template.md) | Nuevo; limita tareas a documentación retrospectiva o trabajo restante autorizado. |
| [`README.md`](README.md) | Nuevo; conserva el inventario, hallazgos, referencias, límites y modo de uso auditados. |

No sustituye las plantillas genéricas compartidas ni modifica scripts, manifests, integraciones, workflows o configuraciones de agentes. Se preservó `memory/.constitution-template.json`: su SHA-256 (`ce7549540fa45543cca797a150201d868e64495fdff39dc38246fb17bd4024b3`) identifica la semilla de plantilla del Core, no es un hash de integridad de la constitución ya editada.

## Estado inicial y diferencias con `master`

Al comenzar, el `HEAD` local, `master` y el commit al que apunta la etiqueta `v0.4.9` coincidían en `c30a19dd410b1815f4591b204615cae0dd9e9a5f`. Los 21 archivos de `.specify` ya existían en el espacio de trabajo, pero no estaban en el árbol versionado de ese baseline. También estaban sin seguimiento `.agents/` y diez comandos `.opencode/commands/speckit.*`; permanecen intactos y fuera de este alcance. La rama de trabajo no cambió `master`, la etiqueta ni releases.

La constitución local era el scaffold genérico sin ratificar: conservaba placeholders de nombre, principios, gobernanza, versión y fechas. Las plantillas originales asumían una feature nueva de aplicación genérica: sugerían tres historias independientes y desplegables, estructuras `src/` y `tests/`, fases fijas de setup/fundación/pulido, y validaciones y métricas de ejemplo. No distinguían una descripción retrospectiva del comportamiento existente de requisitos nuevos. No se encontró una especificación de feature bajo `.specify` ni en el árbol `specs/`. Se preservan los documentos históricos de decisiones y releases existentes en `docs/`; no se inició el inventario de features ni el trabajo del issue #64.

El resolver existente permite plantillas de proyecto en `templates/overrides/` antes de recurrir a presets, extensiones o plantillas incorporadas. Se ejecutó `scripts/powershell/resolve-template.ps1 constitution-template -Json` en modo de resolución de sólo lectura para identificar el scaffold; no se encontró `extensions.yml`. La integración local declara OpenCode en `integration.json`; la existencia de un `codex.manifest.json` por sí sola no prueba que Codex esté registrado o tenga paridad funcional. Se conservó esa configuración sin inferir soporte no documentado.

## Principios y referencias canónicas

La constitución adopta Olympus Core como fuente canónica y define límites de adaptadores, autoridad de Kael y Aegis, controles reales del runtime, simplicidad, TFR, compatibilidad, integridad de instalaciones, evidencia y alcance autorizado. Su versión inicial ratificada es **1.0.0**, con fecha 2026-10-14; el historial indica expresamente que no había una versión constitucional ratificada previa.

La constitución enlaza los documentos técnicos canónicos en lugar de duplicarlos: [Olympus Core](../olympus/README.md), [roles](../olympus/roles/), [identidades](../olympus/core/identities.toml), [modelos](../olympus/core/models.toml), [políticas](../olympus/policies/), [capacidades](../olympus/harnesses/capabilities.toml), [harnesses](../docs/HARNESSES.md), [compatibilidad de Codex](../docs/CODEX-COMPATIBILITY.md), [desarrollo](../docs/DEVELOPMENT.md), [release v0.4.9](../docs/RELEASE-v0.4.9.md) y [contribución](../CONTRIBUTING.md).

## Uso de las plantillas

- **Existing (retrospective)**: documenta el comportamiento observado con rutas, revisiones o evidencias citadas. Mantén desconocidos y límites como tales. No conviertas huecos en requisitos o trabajo de implementación.
- **New** y **Change**: limita el contenido a la solicitud autorizada. Separa estado actual y cambio; registra alcance, criterios observables, dependencias, riesgos y verificaciones enfocadas.
- En la especificación, define sólo historias, requisitos y resultados que correspondan. No inventes métricas ni completes secciones con supuestos genéricos.
- En el plan, usa rutas reales del repositorio y registra el diseño tal como existe o como se propone. Incluye artefactos adicionales sólo si responden una pregunta concreta. Distingue comprobaciones previstas de resultados ejecutados.
- En tareas, lista sólo trabajo restante autorizado. La documentación retrospectiva no genera tareas de implementación; un gap observado queda pendiente de autorización separada.
- Clasifica evidencia como determinista, simulada o de runtime real. Reporta PASS, FAIL, NOT RUN, BLOCKED o desconocido sin presentar fixtures como ejecución real.

### Límite de los workflows actuales

Los overrides adaptan el contenido de los artefactos, pero no reescriben los wrappers o el workflow bundled existentes. El ciclo completo conserva la secuencia `specify → plan → tasks → implement`, con las compuertas `review-spec` y `review-plan`; no se ejecutó en esta auditoría. El wrapper de plan solicita artefactos de investigación y diseño, y el de tareas conserva fases convencionales e instrucciones sobre tareas de pruebas. Por eso, el ciclo no ofrece documentación retrospectiva automática: para describir una feature existente, usa la plantilla activa en una edición acotada y no ejecutes automáticamente plan/tareas/implement. Añade artefactos auxiliares sólo cuando el caso lo justifique. No se añadieron hooks, automatizaciones ni aprobaciones.

## Verificaciones enfocadas y límites

Se observaron estas verificaciones estáticas de la configuración preexistente:

- **PASS**: parseo de los 7 archivos JSON de `.specify`.
- **PASS**: parseo AST de los 6 scripts PowerShell; esto no ejecuta los workflows. El único script ejecutado fue el resolver en modo de sólo lectura indicado arriba.
- **PASS**: hashes de 32 rutas referenciadas por los 3 manifests de integración coinciden con los recursos del baseline.
- **PASS**: no hay `extensions.yml`.

Estas comprobaciones no prueban comportamiento de OpenCode o Codex en runtime. La lectura de capacidades y manuales sirve como referencia documental; no equivale a una prueba nativa de ambos adaptadores.

La verificación enfocada de los documentos resultó así:

- **PASS**: el resolver en modo de sólo lectura resolvió las plantillas de specification, planning y tasks desde sus tres overrides de proyecto.
- **PASS**: 33 enlaces relativos comprobados.
- **PASS**: metadatos de constitución v1.0.0, fechas 2026-10-14 y ausencia de placeholders ALL_CAPS sin resolver.
- **PASS**: `git diff --check` y revisión explícita de whitespace en los cinco documentos authored no versionados; los hard breaks Markdown intencionales se conservaron.
- **PASS**: comparación del snapshot de 315 archivos existentes antes y 319 después: el único archivo previo modificado es `memory/constitution.md`; cuatro archivos se añadieron (este README y los tres overrides). Los otros 314 permanecen byte-identical, incluidos plantillas originales, scripts, manifests, `.agents/`, `.opencode/` y `.codex/`.
- **PASS**: referencias Git y el índice sin cambios.

El inventario de `.specify` pasó de 21 a 25 archivos. Estas comprobaciones son estáticas y documentales; no ejecutan runtimes ni instaladores. FAST, FULL y RUNTIME no se ejecutaron. El gate CI FAST existente se conserva como gate futuro de integración y no se declara aprobado aquí.

## Preparación retrospectiva

**El repositorio queda preparado para documentar retrospectivamente features existentes** mediante la plantilla de especificación en modo Existing, la plantilla de plan como registro opcional de diseño observado y la plantilla de tareas limitada a trabajo documental autorizado. La evidencia disponible y sus límites deben quedar explícitos. Esta preparación no afirma que existan specs históricas ya migradas ni que los wrappers soporten automáticamente una ejecución retrospectiva completa.
