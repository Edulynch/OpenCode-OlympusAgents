# Registro futuro y limitaciones conocidas

Este registro separa propuestas, evaluación y bugs abiertos de las diez capacidades ya presentes en v0.4.9. Estar aquí no autoriza implementación ni crea tareas, plan o criterios de aceptación. Estado de issues consultado el 2026-10-14; verificarlo antes de cualquier trabajo posterior.

## Propuestas abiertas

| Issue | Estado / intención registrada | Estado actual relacionado | Tratamiento retrospectivo |
|---|---|---|---|
| [#64](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/64) | OPEN; CLI portable para operadores | La configuración centralizada de modelos ya existe. La brecha propuesta es editar/aplicar de forma segura y portable mediante CLI, no centralizar modelos desde cero; cualificación hosted cross-platform también queda como futuro. El renderer Python usa la biblioteca estándar y no hace Core Windows-only. | **PLANNED como propuesta**, no compromiso de implementación; sin spec de feature, plan ni tareas aquí. |
| [#66](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/66) | OPEN; UX unificada `fast` sin checkout | Ya existen wrappers remotos heredados; el issue trata una experiencia sin checkout unificada, no un fallo del motor de instalación. | **PLANNED como propuesta**, no compromiso; separada de 006/007. |
| [#67](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/67) | OPEN; evaluación de Wiki | Sólo evaluación, sin decisión de adoptar ni publicar una Wiki. | **PLANNED sólo para evaluación**; no decisión, publicación ni producto aprobado. |

## Exploración sin decisión de implementación

| Issue | Estado / tema | Límite de interpretación |
|---|---|---|
| [#13](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/13) | OPEN; auto-review opcional | Exploración no comprometida. No crea un gate de aprobación. |
| [#26](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/26) | OPEN; jerarquía | Exploración no comprometida; no cambia la propiedad actual de Kael ni la política de profundidad. |
| [#28](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/28) | OPEN; variación Kael→Aegis | Exploración no comprometida, en tensión con la regla actual que prohíbe a Kael y a sus hijos invocar Aegis. No es una excepción aprobada ni un cambio de autoridad. |
| [#37](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/37) | OPEN; supervisión adaptativa y fidelidad de skills | Exploración futura no comprometida. |

## Limitaciones y bugs abiertos ya representados

Los issues [#1](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/1), [#8](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8), [#41](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/41) y [#51](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/51) permanecen abiertos y se tratan como limitaciones o incertidumbres de las capacidades 004, 004/005, 002 y 007, respectivamente. No generan features futuras automáticamente:

- **#1**: errores intermitentes de correlación de resultados; las observaciones históricas no demuestran el disparador del runtime.
- **#8**: el resume ordinario tuvo reporte histórico PASS ([comment](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-5934781194)); el reporte posterior sobre compaction ([comment](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6093432997)) y la auditoría final ([comment](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/8#issuecomment-6121112547)) tienen otro alcance. El resultado ordinario no prueba continuidad de autoridad tras compaction ni acredita una entrada `/maintain`.
- **#41**: se reportó una diferencia de fidelidad/presentación de prompt relacionada con el routing de 002; la causa entre generación, transporte y visualización no está establecida. No se clasifica como un defecto específico del HUD 009.
- **#51**: se inspeccionó secuencia de escrituras/manifest/validación sin rollback exterior. Es riesgo inferido de estado parcial; no se reprodujo pérdida de datos ni recuperación atascada.

Los informes de fase conservan diferencias de UX entre versiones: la evidencia histórica de flags de startup no se convierte en una expectativa uniforme de la v0.4.9. Una sintaxis de estilo GNU sugerida en #61 fue una propuesta; la interfaz actual usa parámetros nativos de PowerShell. El README #66 es válido para instalar desde checkout, pero no acredita una UX primaria sin checkout. Consultar los documentos fuente de cada feature y [EVIDENCE.md](../retrospective/v0.4.9/EVIDENCE.md) antes de interpretar esos hallazgos.
