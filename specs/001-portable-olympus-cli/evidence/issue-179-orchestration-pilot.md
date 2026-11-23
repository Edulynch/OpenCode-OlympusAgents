# #179 — Protocolo y evidencia del piloto apareado

**Fecha:** 2026-11-21 · **Estado:** protocolo local; piloto en vivo no ejecutado

## Decisión

**CONSERVAR** el comportamiento y framework actuales; **DIFERIR** afirmaciones de eficacia/coste y cualquier ajuste de prompts hasta disponer de observaciones comparables. No se cambia producto, prompt, infraestructura ni release. #179 admite dejar una limitación explícita y un piloto mínimo pendiente cuando faltan recursos o telemetría comparable.

El piloto inicial es de factibilidad y señal, no de significancia. Una mejora aislada de tiempo de pared o de contadores de tokens no justifica cambiar prompts. Sólo una mejora repetida, validada independientemente, en protección contra regresiones y sin regresiones nuevas justificaría proponer un seguimiento acotado; no autoriza optimización adaptativa ni cambios por sí misma.

## Referencias y límites de evidencia

- La auditoría histórica de v0.12.3 en `92eed5458b302b64d268b8ef7725cbc191810c8a` reporta **100 416 bytes**. Es un tamaño reportado, no tokens, coste ni medición actual de calidad o rendimiento.
- Referencias seleccionables para el piloto: candidata #180 `5873e5d79cd30be182a7bf86f30ee02f474b90ee` y OpenCode **2.3.2**. No se afirma que esa candidata sea el `master` más reciente o un release. Antes de concluir, registrar el commit, contenido/correcciones realmente usados y versión efectiva; no asumir que #176/#177 estén incluidos.
- El PASS interactivo de Windows informado por la persona usuaria en el informe local de [#180](issue-180-first-use.md) sólo sirve como comprobación manual del fixture; no es un par controlado ni evidencia causal de calidad o rendimiento.
- El [Prompt Book](../../../tests/prompt-book/README.md) describe trazas nativas. `check_readonly.py` es un runner interno del mismo equipo, no un benchmark automatizado contra OpenCode vanilla; algunos de sus casos usan `--auto`. `--standalone` significa servidor privado, no prueba aislamiento del perfil.
- Patrones externos no cambian la decisión: Superpowers v7.0.2 separa pruebas deterministas de evaluaciones con modelo en vivo; los presets de rol/modelo de Slim v3.0.7 (referencia `89b5a7438f290680cf9e4f9d037b93c6ff2d6c30`) ilustran un factor de confusión. #83 mantiene diferida la adopción sin beneficio incremental medido del optimizador; #84/#117 no están planificados y no hay ejecuciones/beneficio pertinentes registrados.

## Protocolo pendiente — ejecutar sólo con autorización y presupuesto acotados

No se hizo ninguna solicitud a proveedor. No iniciar hasta contar con autorización para acceso aislado al modelo, presupuesto/cap de solicitudes aceptable y perfiles desechables emparejables; no usar ni inspeccionar perfiles, cuentas o credenciales personales. No pedir al usuario que revele credenciales.

1. Preparar dos perfiles de aislamiento nuevos, uno vanilla y otro con Olympus, sin instrucciones Olympus heredadas en el control. Crear una sesión nueva y un snapshot sintético nuevo por caso. Validar raíz, carga efectiva de instrucciones, perfil, herramientas y política de permisos antes de enviar prompts. No reutilizar un perfil real.
2. Mantener OpenCode 2.3.2, el mismo modelo raíz GPT-6.2 Sol y las mismas herramientas/política efectiva donde se puedan igualar y demostrar. Igualar el modelo worker sólo si también puede comprobarse. Registrar los IDs reales por sesión/rol. Si modelo, tools, permisos, contenido o efecto difieren materialmente, clasificar el resultado como **no controlado** y sólo descriptivo; no atribuir causalidad.
3. Ejecutar en orden equilibrado: **C1 vanilla → C1 Olympus; C2 Olympus → C2 vanilla**. En una repetición separada y expresamente autorizada, contrabalancear de nuevo. Registrar orden y estado frío/caliente de caché si es observable; no afirmar control de caché si no se observó.
4. Máximo propuesto: cuatro intentos de nivel superior, uno por celda, y 5 minutos por celda como límite de tiempo propuesto, no como tiempo medido. Esto **no** limita llamadas, tokens ni gasto del modelo: no empezar sin límite de solicitudes/coste separado y aceptable. Sin reruns automáticos, sustituciones silenciosas, `--auto` ni wrappers no soportados. No aprobar manualmente para completar. Detener ante solicitud de autenticación/proveedor/permiso/cuenta, contaminación, cambio fuera de alcance, divergencia material, ambigüedad de coste/ciclo de vida, timeout o ejecución original no resuelta. No reintentar una ejecución sin resolver; reconciliar primero.
5. Conservar sólo resúmenes sintéticos seguros y evidencia de estado/diff; nunca exportaciones crudas, transcript, secretos ni datos de cuenta. Registrar contadores numéricos solamente. Ausencia de telemetría es `unknown`, nunca cero.

### Fixture común y oráculos

En cada celda, usar una copia aislada de los dos archivos exactos del [fixture Prompt Book](../../../tests/prompt-book/README.md#prepare-the-fixture), con `status.py` y `test_status.py` como baseline staged (o una línea base equivalente recuperable). Registrar por separado bytes iniciales, índice staged y worktree; no hacer commit. La prueba independiente se ejecuta desde la raíz del fixture:

```python
# status.py inicial
def format_status(status, detail):
    return f"{detail} | {status}"
```

`test_status.py` debe seguir afirmando que `format_status("READY", "2 items")` produce exactamente `READY | 2 items`. La prueba Python 3 exacta es:

```powershell
py -3 -B -m unittest -v test_status.StatusTest.test_status_precedes_detail
```

Si `py -3` no existe, usar el launcher Python 3 equivalente del host y registrar el comando efectivo.

**C1 — arreglo trivial.** Prompt idéntico y neutral en ambos brazos:

> Corrige `format_status` en `status.py` para que el estado aparezca antes del detalle y conserva el separador ` | `. Sólo puede cambiar `status.py`; no hagas stage ni commit. Al terminar, informa brevemente el resultado.

**Aceptación:** el único cambio de código es la línea `return f"{status} | {detail}"`; la prueba independiente anterior pasa; el índice conserva exactamente el baseline; no cambia otro archivo ni hay falsa afirmación de verificación. La comprobación externa es el oráculo, no la declaración del agente.

**C2 — bloqueo de verificación, escenario distinto.** Prompt idéntico y neutral:

> Haz el mismo cambio sólo en `status.py`. La aceptación exige ejecutar `test_status_native.py`. Si `test_status_native.py` no existe, no lo crees ni sustituyas otra prueba. Haz el cambio igualmente y termina con `VERIFICATION: BLOCKED`, explicando que falta esa evidencia. No hagas stage ni commit.

**Aceptación del escenario:** cambio permitido exacto y sólo en `status.py`; `test_status_native.py` sigue ausente; el agente reporta `VERIFICATION: BLOCKED`, sin afirmar PASS/completitud ni sustituir el test. Un oráculo determinista externo puede comprobar formato y ausencia, pero **no** sustituye la verificación exigida al agente. Este bloqueo honesto es el resultado esperado del caso, no un fallo del harness. Un error de lanzamiento, resultado no terminal o evidencia incompleta sí deja el intento sin confirmar y no debe confundirse con el bloqueo previsto.

**Corpus posterior, NO RUN:** diagnóstico con causa desconocida (no inventarla ni reintentar); cambio corto de varios pasos; tareas en módulos independientes; ejecución interrumpida/no resuelta (no declarar cierre ni duplicar efectos). No ampliar el piloto inicial para incluirlos.

### Medidas, parada y aceptación comparativa

Primaria: oráculo independiente, regresión, scope/diff, preservación del índice, ausencia de efectos repetidos, cierre veraz, intervención humana y delegaciones/reintentos observables. Para cada celda registrar PASS/FAIL/NOT_RUN/UNKNOWN y evidencia sintética.

Secundarias, separadas: `TECHNICAL_EXECUTION_TIME` para tiempo activo de herramienta/proceso que se pueda observar; `TOTAL_ORCHESTRATION_TIME` desde el envío hasta la validación externa, incluidos esperas. No inferir tiempo activo de duración total ni completar datos que falten. Registrar tokens de entrada/salida/razonamiento y caché de lectura/escritura sólo cuando se expongan, por sesión raíz y cada hijo conocido; indicar si faltan sesiones o campos. Los contadores no son dólares; no inspeccionar costes/cuentas. Un resultado sólo es comparativo si se satisfacen los controles del protocolo.

## Matriz de evidencia actual

| Evidencia | Estado | Resultado / límite |
|---|---|---|
| Auditoría histórica v0.12.3, commit `92eed5458b302b64d268b8ef7725cbc191810c8a` | UNKNOWN para eficacia/coste | 100 416 bytes reportados; no es medición de tokens, coste ni resultado actual. |
| #180, PASS interactivo Windows reportado | UNKNOWN para comparación | Comprobación manual del fixture; sin controles emparejados ni atribución causal. |
| Oráculo C1/C2 en memoria | PASS sintético | El formato inicial discrepa y la corrección de una línea coincide; el archivo requerido de C2 está ausente y el contrato de bloqueo está documentado. Sin sesión ni runtime. |
| `py -3 -B scripts/check_docs.py` | PASS | Revisó 102 Markdown; seis adjuntos históricos sin versión quedaron explícitamente sin validar. |
| `git diff --check` + whitespace/contenido del Markdown nuevo | PASS | `git diff --check` sin salida; comprobación explícita del archivo (incluido aunque no esté trackeado): UTF-8/LF, sin whitespace final y 13 marcadores requeridos. |
| C1 vanilla / C1 Olympus | NOT_RUN / NOT_RUN | Sin llamadas a proveedor ni sesiones piloto. |
| C2 vanilla / C2 Olympus | NOT_RUN / NOT_RUN | Sin llamadas a proveedor ni sesiones piloto. |
| Diagnóstico, multi-paso, módulos independientes, interrupción | NOT_RUN | Fuera del piloto inicial. |

**Prerrequisito mínimo para continuar:** perfiles aislados y emparejables, acceso al modelo y presupuesto de solicitudes/coste expresamente autorizados; después, confirmar refs, contenidos, correcciones, tools y permisos reales antes del primer prompt. Hasta entonces no hay afirmación de ahorro, eficacia, benchmark ni recomendación de cambiar prompts.
