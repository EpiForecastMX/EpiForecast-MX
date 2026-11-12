**Dictamen: APTO_PARA_FALLBACK_Y_ACEPTADO_CON_CONTRASTE.** Las tres condiciones de `FABLE_CODE_RECHECK.md` quedan cerradas en el código congelado (v3) para los dos casos soportados. Es lectura estática: no ejecuté nada, no corrí las 84 pruebas y no comprobé que los guiones vivos en `scripts/` tengan los hashes de `SHA256.json`.

## A1: resuelto (`gen_fichas.py:262-311`)

- **Vínculo completo.** El tipo sale de `release_manifest.v2` (`chain.acceptance_outcome`, `calendar.origin`), ligado a:
  - el `acceptance.json` sellado, por su sha256 contra `chain.acceptance_digest`, con `accepted` coherente con el resultado;
  - el shard FE, por schema, `disease_id`, `release_id`, `lifecycle`, `origin` y veredicto igual al de la vista;
  - el puntero público y el gate, por `release_id` y `disease_id`.
- **Sin falso «aceptado».** Un control real sin marcas en vista o registry aborta (`:304`). Si el manifest perdiera `acceptance_outcome`, el `accepted: false` del acceptance sellado aborta (`:297`).
- **Run del control.** `acceptance_fallback_run` se compara con `chain.acceptance_run_id` (`:306`), como `registry_doctor.py:196-197`.
- **Tercer estado.** Un aceptado con candidato igual al control aborta con mensaje propio (`:309-310`) y no recibe ninguna plantilla. El criterio es el de `status.py:477-478`.
- **Control legítimo.** Exige candidato igual al control (`:307`). Quemaduras lo cumple en su gate real.

## A2: resuelto (`gen_fichas.py:141-176`)

- **Procedencia por id.** Ya no hay `--procedencia` global. Se carga sólo de `config/publication/<id>/` y debe coincidir con la vista en `disease_id`, `release_id` y `forecast_emitted_at`, o aborta.
- **Contradicción propia.** `first_available: false` en un boletín objetivo aborta, haya o no `--indice`. El archivo real de Asma tiene esa marca en `2026_sem43.pdf`, coherente con el aborto declarado.
- **Afirmación.** Sólo se escribe con una línea del índice con `http=200`, posterior a la emisión, del mismo año y con último boletín anterior al primero objetivo. El cruce de año nunca afirma.

## Revalidación v2: resuelta (`revalida_run.py`)

- **Evidencia original.** El `RUN.json` se conserva y su sha256 queda en `RUN_v2`. En `hepatitis_a_b15` de snapA el original no trae `pdf_previstos` (validador viejo) y el v2 registra inventario de 670 y excluidos iguales a declarados.
- **Qué valida.** Los sha256 de CSV y manifiesto (copia e interim) contra el RUN original, mtime del interim, snapshot en su commit y limpio, config de inicio y fin, e inventario y exclusiones con el validador fijado. El sha del validador en los `RUN_v2` leídos coincide con `SHA256.json` (`e1ed53a6…`).
- **Consumidores.** `post_snap.sh:16-23` y `model_test.sh:45-49` exigen `RUN_v2` válido, validador igual al fijado y snapshot de 40 caracteres. `model_dev.sh:19` sólo acepta `canon`.
- **Grupos con fuente cambiada.** Los `RUN_v2` de snapA/snapB de los seis ids son válidos como extracción, pero sólo excluyen `2014_sem01`. No pueden congelarse: los frena `config_efectiva.py` en fase fuente (`post_snap.sh:33`, `model_test.sh:52`). En `extract/canon/` no hay ninguno de los seis; sólo las dos desnutriciones, bocio y absceso hepático.

## Condiciones operativas

1. **Commit de las exclusiones.** `config_efectiva.py` lee `HEAD` con `git show`. Vi las seis exclusiones de `2016_sem20` en el árbol de `wt-be`, no en el commit. Confirma que están en `HEAD` antes de correr `post_snap.sh` sobre esos ids; si no, snapA/snapB pasarían el cotejo.
2. **Ruta de `--be`.** `wt-be` no tiene `artifacts/releases/`; el checkout principal sí. Con `--be` apuntando a `wt-be` todo aborta (cierra en seguro).
3. **Aceptado con candidato igual al control.** Sin plantilla: se detiene. Sólo es condición si aparece; los seis A6 no lo son.
4. **Emisión con boletín objetivo ya público.** Aborta la ficha entera, también la de control, que no afirmaría nada. Si alguno de los seis A6 se emite con el boletín 44 ya registrado como disponible, hará falta texto manual.

## Defectos menores, no bloqueantes hoy

- **`lista_publicables.py:74-75`:** si `refit_summary` no trae `engines`, cae en «aceptado» sin marca. El contrato lo exige (`artifact_refit.py:54`) y `gen_fichas` lo detendría después por el gate. Además lista el tercer estado bajo `publicables`.
- **`gen_fichas.py:285-286`:** no mira `active` ni el schema del puntero, ni el `disease_id` de la vista.
- **`gen_fichas.py:164`:** sólo veta `first_available`; un `captured` o `created` anterior a la emisión no veta.
- **`revalida_run.py:52`:** el inventario es el `pdfs/` de hoy y por nombre, sin hash de los PDF.
- **Consumidores de `RUN_v2`:** no cotejan `schema`, `id`, `pasada` ni el sha de inventario entre pasadas. El pin vive junto al validador; el ancla externa es `SHA256.json`.
- **`valida_extraccion.py:75-78`:** el `RUN.json` nativo sigue sin sellar la versión, así que toda pasada futura debe pasar por `revalida_run.py`.
- **Límite inherente:** la revalidación no prueba que el snapshot estuviera limpio durante la corrida original. Lo mitigan el CSV idéntico en dos worktrees y el hash y mtime del interim.

Este dictamen es técnico: no concede autorización humana, pretest, política, control, altas ni publicación, y no valida nada científicamente.