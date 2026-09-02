# Deudas vigentes — índice canónico

> Actualizado el 1-sep-2026 para el trabajo P0 sobre backend
> `p0/namespace-e-inmutabilidad-del-sello@a9a694c8` y frontend `main@0e777995`.
> Este archivo separa
> trabajo vigente de bitácoras históricas. Una deuda que aparezca sólo en un documento
> antiguo no se ejecuta hasta contrastarla aquí y en el código.

## Activa — P0 del flujo de actualización semanal

El plan vigente es `../../planes/PLAN_ACTUALIZACION_SEMANAL_UNIFICADA_2026-09-01_v4.md`
(SHA256 `5cfdf5a4a2d8e5ed1acf004e8c90a00e929dfd217ba051fff925e742fe9e233d`). La rama
`p0/namespace-e-inmutabilidad-del-sello` lleva seis commits locales sobre `a9a694c8`
(checkpoint P0.9, runner de gates, P0.6, composición 41/41 + opción C, política ligada al
HEAD canónico, documentación), sin push.

Cerrado (1-sep, con controles negativos y mutaciones del código vistos caer):

- P0.9 runner real de gates: `censo/2`, `run-gates` sin shell sobre el árbol completo,
  evidencia con digests, `seal` sin flag de resultados;
- P0.6 apply confinado: par de worktrees desechables registrado, verificado con git y bajo
  lock; cualquier fallo invalida el par; `CONFINAMIENTO_LISTO = True`; la política del sello
  debe ser la del HEAD del repositorio canónico;
- composición 41/41 por `git archive`; `check-completeness` con seis conjuntos y composición
  aplicada == sellada; `actualiza_semanal.sh` y `make update-week-apply` recableados detrás
  del bloqueo;
- P0.11 decidido: opción C, superficies públicas al día y dataset DVC pendiente; ninguna
  operación DVC se declara;
- P0.12 ensayado en sintético y con la composición real (gates Node reales PASS); evidencia
  en `../../planes/ensayo_P012_2026-09-01/`.

Gate: 223 dirigidas; `make test-fast` = 2,645 passed, 1 skipped, 66 deselected; Ruff, mypy,
`bash -n`, `git diff --check` verdes.

Abierto, en orden: (1) P0.1 hidratación por allowlist con control positivo 333/99/432 y
conjuntos exactos; (2) P0.2 inputs bajo el staging con `digest_consolidado` antes/candidato;
(3) P0.8 Dengue fail-closed; (4) P0.10 cadena de caché; (5) `--out` de
`build_web_knowledge.py`, `build_tableau.py` y `genera_validacion_semanal.py` (P2); (6)
auditoría ciega externa de los commits; (7) P1 sólo con autorización. Límites declarados:
ni runner ni sello son sandbox; los digests no son firma; sin atomicidad entre repositorios.

## Cerradas o retiradas en esta auditoría

- **Gate de cifras públicas:** cerrado antes de esta ronda. `cifras:verify` ya recorre la
  superficie publicada completa, no sólo `knowledge.json`; su prueba negativa cubre HTML,
  JSON, subdirectorios y exenciones. Verificación actual: 41 archivos y 453 chunks, PASS.
- **Comparador «Depresión · ?»:** corregido en el frontend. El payload conserva ahora el
  motor de cada padecimiento; hay una prueba Node dedicada y se incrementó el cache-bust de
  `app.js` a v138.
- **Diagnóstico Netlify cortocircuitado:** corregido en el frontend. `deploy:verify`
  ejecuta `cifras:verify` y `rag:ci` aunque el primero falle, muestra ambos códigos y
  conserva un veredicto rojo si falla cualquiera. Tres controles unitarios cubren primer
  fallo, segundo fallo y doble PASS.
- **`bento.json` presentado como vivo:** retirado. La portada ya no contenía el mosaico;
  sólo quedaba un script muerto que descargaba el snapshot de junio sin tener nodos donde
  pintarlo. Se eliminó la petición y una prueba impide reintroducirla. El JSON se conserva
  como snapshot histórico.
- **`_fixCohortStats` supuestamente redundante:** deuda retirada por evidencia contraria.
  Al comparar `knowledge.json` crudo con `loadKnowledge()`, la función todavía corrige
  `por_motor`, el orden de `bottom5_smape` y la construcción de `dist_motor`. Quitarla hoy
  cambiaría cifras públicas. La deuda real es corregir el generador y demostrar igualdad
  antes de retirar la compatibilidad.
- **C7 prospectivo 1/4:** estado histórico superado. El estado efectivo es PASS 4/4 para
  `2026-W27..W30`; Obesidad continúa `trained` y NO-GO.
- **44 pruebas innecesariamente condicionadas:** cerrada por D2.3-A: 15 unit + 29 contract
  corren en clon limpio.
- **Cuatro agregados legacy con doble guarda:** cerrada. Los checks se movieron a
  `tests/integration/`, conservan los cuatro casos, llevan marker `integration` y no
  contienen ningún `skip`. El job normal los deselecciona; el carril manual los ejecuta y
  la ausencia de un CSV es FAIL explícito.
- **Presupuesto de skips del job Tests:** cerrado en alcance inicial. El workflow pasa
  `--max-skips=497` mediante un plugin propio; un control subprocess demuestra que 1 skip
  con presupuesto 0 termina en rc=1. El límite parte del último Ubuntu (501) menos los
  cuatro agregados ahora deseleccionados. Sus controles, junto con los dos de compatibilidad
  ETS, elevan la colección de 2,505 a 2,509. El run de `main` `33467472543` confirmó
  exactamente 497 skips: el presupuesto está calibrado sin holgura.
- **Pickle ETS incompatible con SciPy 1.18:** cerrado en local y Ubuntu.
  El loader normal sigue siendo la primera ruta; sólo ante `KeyError('_xp')` un unpickler
  local completa el namespace NumPy de `LbfgsInvHessProduct`. No hay parche global y otro
  `KeyError` sigue fallando. Los 16 modelos del release reprodujeron 832 valores canónicos
  con error máximo `2.27e-13`; 54 pruebas focales, el carril completo y el run de `main`
  `33467472543` pasan.

## Prioridad 0 — siguiente trabajo local seguro

1. **Política de skips del carril manual.** El job Tests ya tiene presupuesto; falta decidir
   qué debe poder omitir Integration cuando se lanza expresamente por `workflow_dispatch`.
2. **Readiness de Obesidad rancio.** El manifiesto local conserva 1/4 aunque el status
   canónico da 4/4. El loader ETS ya pasó CI: regenerarlo localmente es el siguiente paso
   seguro, pero no autoriza preflight, apply, lifecycle, puntero, publicación ni DVC.

## Prioridad 1 — requiere un microplan propio

- **Cadena sellada sintética:** prototipo acotado antes de clasificar D1. Quedan 460
  nodeids en 156 grupos que consumen cadena; no llamarlos «460 grupos».
- **Retiro del shim ETS:** depende de `LbfgsInvHessProduct` y `_xp`, privados de SciPy.
  Mantenerlo mientras el release vigente use `statsmodels_pickle`; retirarlo sólo después
  de migrar a un estado ETS portable con schema versionado y equivalencia demostrada.
- **Generador de `knowledge.json`:** debe emitir las mismas estadísticas neuro que hoy
  recompone `_fixCohortStats` en runtime. Criterio: igualdad profunda de todos los campos
  afectados antes de borrar la compatibilidad.
- **Publicador legacy de Sheets:** `scripts/publish_gsheets.py` aún carece de retry/backoff y
  resume. No confundirlo con `GoogleSheetsTableSink`, que administra sólo `runner_*`, protege
  las cinco tabs legacy y tiene promoción/rollback compensado. El script legacy toca la hoja
  productiva y requiere diseño y pruebas antes de cambiarlo.

## Externas o manuales — no resolver desde código

- **Tableau Public W31:** sigue NO-GO hasta repuntar las 20 worksheets a
  `fecha_boletin`, publicar con la cuenta propietaria y hacer smoke test. Ver
  `ESTADO_TABLEAU_W31_2026-08-20.md`.
- **MICAI 2026:** falta resolver el registro de un autor; requiere coordinación humana.
- **CALASS:** el congreso terminó. Los pendientes de viaje expiraron; las observaciones de
  láminas son deuda de diseño histórica, no trabajo operativo urgente.

## Documentos históricos

- `OBESIDAD_PENDIENTES.md`: intento preliminar anterior a C1-C7; no es plan vigente.
- `PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`: conserva la cadena de auditoría; usar el plan C7 y
  el estado efectivo para operar.
- `PLAN_CONVERGENCIA_RAMAS_Y_DATOS.md`: bitácora de la convergencia del 18-ago; sus ramas,
  estado 1/4 y siguientes acciones quedaron superados.
- `PENDIENTES_2026-08-25.md`: bitácora CALASS/cifras; sus ítems vigentes se reflejan aquí.
- `RONDA_128_AUDITORIA_PENDIENTE_DE_PEGAR.md`: evidencia de una ronda, no cola de trabajo.

## Regla de cierre

Una deuda se cierra sólo con: cambio identificable, control positivo, control negativo cuando
aplique y actualización de este índice. Un documento antiguo no se borra para ocultar el
historial; se marca como supersedido y se enlaza a este índice.
