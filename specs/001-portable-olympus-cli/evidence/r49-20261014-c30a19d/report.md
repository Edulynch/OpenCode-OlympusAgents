# R49 — instalación remota y VerifyOnly de v0.4.9

**Resultado**: PASS. **Slice A**: READY_FOR_IMPLEMENTATION respecto de sus gates técnicos.  
**Alcance**: Windows, `Scope=project`, `Harness=codex`, un repositorio Git temporal aislado. No valida OpenCode, scope global, Linux, agentes, prompts, disponibilidad de modelos ni autenticación. T002–T009 no se ejecutaron.

## Identidad y adquisición

- Release pública, no draft: [v0.4.9](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.4.9), publicada `2026-10-14T05:29:18Z`.
- Tag anotado: `a9c76fb47ae7826df57f2319a29be1397e8ff97f`; commit exacto `c30a19dd410b1815f4591b204615cae0dd9e9a5f`. Consultado mediante API pública HTTPS sin credenciales; tag revalidado después de las operaciones.
- Instalador ejecutado sin cambios: `https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install.ps1`. SHA-256: `ff72b31ea312e1ad9b0fbdd7f37a5c936e8ec062a7cbc17abaeea772b6fe7de9`.
- Adquisición normal en **ambas** operaciones: `https://github.com/Edulynch/OpenCode-OlympusAgents/archive/refs/tags/v0.4.9.zip`; sin `SourceRoot`, `SourceArchive`, master ni latest. Ambos logs registran `requested=v0.4.9 resolved=v0.4.9 origin=REMOTE_ARCHIVE`.
- Una descarga de referencia independiente de ese mismo archivo se comprobó contra los 274 blobs del árbol remoto del commit exacto, usando SHA-1 de objeto Git y SHA-256 de contenido. También se comprobó el instalador raw contra su blob. SHA-256 del **archivo de referencia**: `f3063ca37a8209720f2b780bebbff17356ddc644bd9a36325474ed240ab1326e`. No se presentó ese archivo local como input del instalador.
- Los archivos ZIP internos de install/verify fueron retirados por el `finally` normal del instalador. La evidencia de adquisición usada por cada operación es el comando sin overrides, el código del instalador verificado y su log REMOTE_ARCHIVE; los bytes entregados se contrastaron además con la referencia remota exacta.

## Aislamiento comprobado antes de instalar

Proceso hijo `pwsh -NoProfile -NonInteractive` con `ProcessStartInfo.Environment.Clear()` y whitelist explícita. HOME/USERPROFILE, APPDATA/LOCALAPPDATA, TEMP/TMP, XDG config/cache/data/state, CODEX_HOME, OPENCODE_CONFIG_DIR, Git global/template y caché de módulos PowerShell apuntaron al árbol temporal propio. PATH sólo incluyó Git, PowerShell y System32; preflight confirmó ausencia de `codex`/`opencode`, de variables de credenciales y de perfiles cargados.

Se verificaron paths absolutos/contención, ausencia de reparse points en sus ancestros, target inicialmente vacío y raíz Git exacta. Git usó configuración global vacía y sin configuración system ni plantillas personales. No se ejecutaron runtimes ni stubs; el camino Codex del bootstrap sólo escribe/valida archivos. Ninguna llamada a modelos o credencial de proveedor/GitHub se utilizó.

El target fue `C:/Users/BLAUTECH/AppData/Local/Temp/olympus-r49-945379521ce94b33870c71481bd622fa/target`, fuera del repositorio de desarrollo, sin scope global. Evidencia preservada. **Limpieza pendiente**: la revisión automática rechazó la eliminación recursiva del árbol propio con el motivo literal «blocked by policy», antes de iniciar el comando. El directorio temporal permanece; no se eludió el bloqueo ni se borraron recursos mediante otro mecanismo. Ver [cleanup.json](cleanup.json). Esta limitación operacional no invalida las operaciones de verificación ya ejecutadas ni permite afirmar cleanup completado.

## Operaciones ejecutadas una vez

Parámetros efectivos, intérprete, timestamps y exit codes completos: [operations.json](operations.json). Cambiar `<installer>` por el archivo raw validado y `<target>` por la raíz Git temporal al reproducir, manteniendo la whitelist de [environment.json](environment.json).

```text
pwsh -NoProfile -NonInteractive -File <installer> -Version v0.4.9 -Target <target> -Scope project -Harness codex
pwsh -NoProfile -NonInteractive -File <installer> -Version v0.4.9 -Target <target> -Scope project -Harness codex -VerifyOnly
```

| Operación | Resultado | Evidencia |
|---|---|---|
| Preflight aislado | PASS, exit 0 | [isolation-preflight.stdout.log](isolation-preflight.stdout.log) |
| Inicializar Git / resolver raíz | PASS, exit 0 cada uno | operations.json; sin commit ni remote Git |
| Instalación normal remota | PASS, exit 0 | [install.stdout.log](install.stdout.log), [install.stderr.log](install.stderr.log) |
| VerifyOnly con readquisición remota | PASS, exit 0 | [verify-only.stdout.log](verify-only.stdout.log), [verify-only.stderr.log](verify-only.stderr.log) |
| Inventario y hashes instalados | PASS, 12/12 | [managed-files.json](managed-files.json) |
| Contenido/inventario target antes/después VerifyOnly | PASS, 25 registros iguales | [result.json](result.json) |

Se preservó `.codex/orchestrator-install.json` en [installed-manifest.json](installed-manifest.json): schema 1, scope project, versión v0.4.9, único harness codex y 12 entradas propias. Los recursos son `.codex/config.toml`, diez `.codex/agents/*.toml` y `CODEX.md`. Cada hash de contenido coincide con manifest y blob correspondiente de la release; sin Aegis Codex ni salida de agentes ejecutada.

`installed_from_commit` es **unknown**, pues el archive GitHub no contiene `.git`. No se alteró el manifest para corregirlo ni se usó ese campo como prueba: la identidad exacta quedó acreditada externamente por tag/commit y comparación de los 274 blobs remotos, además de los 12 recursos instalados.

## Efectos y límites de evidencia

Las huellas antes/después son idénticas para:

- Repositorio de desarrollo, incluyendo metadata Git: 13.874 registros.
- Configuraciones/recursos personales de Codex/OpenCode y cachés seleccionadas: 95 registros; rutas exactas en [snapshots-before.json](snapshots-before.json).
- Control ajeno al target: 2 registros.
- Target instalado durante VerifyOnly: 25 registros; cero escrituras observadas por inventario y contenido.

No se modificó una instalación personal ni otro repositorio observado. La garantía está acotada al flujo inspeccionado de archivos, entorno/path aislado y snapshots registrados. Los logs/databases de sesiones personales activas quedaron fuera de las huellas; no se afirma ausencia de actividad ajena del propio runtime. No se invocó ninguno de esos runtimes por esta prueba.

Dos ajustes de preflight se registran sin ocultarlos: un log personal activo no pudo hashearse y se acotó el snapshot a configuración/cachés; después, la resolución de PowerShell devolvió dos ejecutables y se seleccionó un único binario antes de iniciar el hijo. Ninguno de esos intentos inició install/VerifyOnly. Evidencia: [preflight-adjustment.json](preflight-adjustment.json), [preflight-start-failure.json](preflight-start-failure.json). **No se repitió instalación ni verificación.**

## Reproducción mínima y aceptación

Consultar endpoints públicos del tag/release exactos, crear otro árbol temporal sin enlaces, preparar la whitelist con nuevos paths, comprobar HOME/temp y ausencia de runtimes/credenciales, inicializar el Git aislado y ejecutar las dos órdenes anteriores sin overrides. Comparar manifest/12 archivos con el archive del tag y árbol del commit; comparar huellas antes/después y preservar logs antes de limpiar sólo el árbol propio. No usar configuraciones personales, prompts o APIs de modelos.

Todos los criterios pedidos de R49 se cumplen para esta validación de distribución/instalación de archivos de proyecto Codex. Esto resuelve T001 y habilita los gates técnicos de A; no acredita la funcionalidad nueva, la experiencia completa A+B+C ni soporte nativo de otros entornos.
