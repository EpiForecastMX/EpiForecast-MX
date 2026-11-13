**Dictamen: APTO_CON_CONDICIONES.** A3 y M1 quedan resueltos; A1 sigue abierto en dos puntos, A2 en uno, y los `RUN.json` de snapA/snapB salieron del validador anterior a la corrección. No ejecuté nada; las 59 pruebas no las corrí.

## Bloqueantes

**A1: parcial.** El tipo y el sexo ya se derivan y la discordancia aborta. Sigue:
- **Identidad y estado del release** (`gen_fichas.py:251-256`):
  - Sólo se lee el manifiesto FE (`publication_shard.v1`) y de él sólo se compara `disease_id`.
  - No se cotejan con la vista su `release_id`, `origin`, `lifecycle` ni `publication_status`.
  - El manifiesto científico (`release_manifest.v2`, con `chain`) no se lee.
  - `acceptance_fallback_run` se usa como booleano, sin compararlo con `chain.acceptance_run_id` como hace `registry_doctor.py:196-200`.
  - La prueba lo consagra con un manifiesto `{'disease_id': d}` (`test_operativos.py:330-332`).
- **CONTROL_ONLY**: la clasificación es binaria.
  - Un aceptado cuya selección es entera el motor de control (`status.py:477-478`) recibe la plantilla de aceptado: «Superó la prueba de 2025» y validación en curso, aunque el contraste es contra sí mismo.
  - No se mira `engines`. `lista_publicables.py:73` lo lista como `aceptado` sin marca.

**A2: resuelto en lo esencial.** La frase exige una consulta del índice posterior a la emisión. Sigue (`gen_fichas.py:145-150`):
- `--procedencia` es opcional y único para todos los ids.
- No se coteja su `disease_id`, `release_id` ni `forecast_emitted_at` con la vista (`bulletin_provenance.py:147-152`).
- No se carga solo desde `config/publication/<id>/`. Con dos ids, el veto se evalúa contra la emisión de otro.

**A3: resuelto** (`model_test.sh:52-53`, `post_snap.sh:30-33`). Latente: `extract_snap.sh:39` registra `$SHA` literal, no su `rev-parse`; hoy todos son SHA de 40.

**M1: resuelto**; el linaje coincide con el contrato (`orchestrator.py:604`, `forecasting.py:211`). Menor: la rama de control no coteja `acceptance.json` con el digest del manifest ni registra su sha256; lo reverifica el runner.

## M2 a M9

- M2, M3, M6, M7 y M8: resueltos. `autorizaciones/` está vacía.
- M4: corregido en código, pero no aplicado a las pasadas existentes (ver abajo).
- M5: `model_dev.sh:19` sólo exige `RAW.json` con `canon`; otra pasada entra sin verificar hasta `model_test.sh:40-46`.

## ¿Corrieron mientras cambiaban archivos?

Sí. snapA y snapB corrían desde las 16:51 (hora del este) y a las 17:32 seguían sin `DONE`, mientras se reescribían los guiones (`READY_FABLE_CODE_FIXED`, 17:23).
- Sus `RUN.json` hasta las 17:32 no traen `pdf_previstos` y sus líneas de estado llevan `estados=`: los validó la versión por conteo.
- `RUN.json` no sella la versión del validador; `model_test.sh:45` y `post_snap.sh:21` aceptan ese `valida: true`.
- Si `extract_snap.sh` se editó en sitio, los ids restantes pudieron ejecutar código mezclado.
- No detecté cambios en los guiones durante mi lectura.

## Condiciones

1. A1 (identidad y estado del release, y CONTROL_ONLY) antes de generar fichas.
2. A2: ligar la procedencia al release antes de afirmar prospectividad con `--indice`.
3. Repetir o revalidar snapA/snapB con el validador corregido y los guiones quietos antes de congelar un raw o abrir 2025.

Este dictamen no concede pretest, política, control, altas ni publicación.