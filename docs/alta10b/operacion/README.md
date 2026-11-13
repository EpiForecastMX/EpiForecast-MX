# Cápsula operativa del lote alta10b (no es código de producción)

Guiones con los que se preparó alta10b. Están fuera de `tests/` y de `src/`: el CI no los ejecuta ni los
analiza (el ruff del CI sólo revisa `src/`, `tests/` y scripts nombrados; el hook de pre-commit excluye `docs/`). Sirven para reanudar la tanda y como referencia para el skill.

## Limitaciones

- Rutas por omisión de esta tanda: base `/tmp/epiforecast-alta10b-20261112` (env `ALTA10B_BASE` en
  `autoridad.py`, `lista_publicables.py`; `ALTA10B_RUNS` para los runs), worktree `wt-be`, venv del checkout
  principal. Los `.sh` llevan esas rutas escritas: para reusarlos hay que ajustarlas.
- `VALIDADOR.sha256` fija `valida_extraccion.py` (versión `valida_extraccion.v2`) con ruta relativa a la base
  (`scripts/valida_extraccion.py`); la copia de esta carpeta tiene el mismo sha256.
- `check_index.sh` reconoce el índice de boletines de 2026 (`semNN.pdf` y `Boletin-NN26.pdf`).
- El inventario de PDF se deriva del directorio del corte; no hay número fijo.

## Piezas

- Extracción aislada: `extract_snap.sh` (worktree detached por pasada, candado, salida previa apartada),
  `valida_extraccion.py`, `revalida_run.py` (revalida sin reextraer), `config_efectiva.py` (fases fuente y
  selección), `post_snap.sh` (raw canónico, cotejo, desarrollo).
- Desarrollo y prueba: `model_dev.sh` (sólo raw canónico; smoke 7 -> full -> select con linaje),
  `model_test.sh` (apertura única de 2025 con aprobación nominal P1-P7 y A3), `guarda_aprobacion.py`.
- Autoridad y publicación (usadas el 12-nov-2026 para publicar los diez): `autoridad.py` (esquema en
  `../ESQUEMA_AUTORIZACION.md`), `lista_publicables.py`, `gen_fichas.py` (tres estados: aceptado, aceptado
  CONTROL_ONLY que aborta, control), `model_control.sh` (refit y forecast de un control autorizado),
  `guarda_orden.py` (orden fijo y tope), `registry_fase.py` y `construye_release.py`.
- Fase de publicación: `cola_tests.sh` (recorre el orden fijo; espera la aprobación nominal de cada id, no la
  crea; se detiene con cuatro aceptados o ante un rc distinto de cero), `resultado_test.py` (resultado desde
  manifiestos), `consolida_controles6.py` y `consolida_alta10b.py` (consolidado de paridad sólo añadiendo
  filas), `postedita_controles6.py` (dos frases editoriales medidas sobre las fichas v3 de los controles) y
  `radar_update.py` (marca los publicados en el radar vigente del frontend).
- QA: `qa_total_terna.py`, `qa_acumulado.py`, `qa_identidad.py`, `encabezados.py`, `estadisticas_canon.py`,
  `diag_motores.py`, `propuesta.py`.

## Pruebas (sintéticas, sin cifras reales)

    PYTHONPATH=<repo>/src:<repo> <venv>/bin/python -m pytest docs/alta10b/operacion/tests -q

84 pruebas; incluyen mutantes de las guardas revisadas por Fable (dictámenes en `../revisiones/`).
`SHA256SUMS` registra los archivos de esta carpeta.

## Recuperación

Si `/tmp` se pierde: los raws canónicos, los registros de cada pasada (`*_RUN.json`, `*_RUN_v2.json`) y el QA
están en `planes/alta10b_2026-11-12/`; los runs y datasets, en `runs/` del checkout principal. Los PDF del
corte son los de `raw_PDFs.dvc`. Para recrear los snapshots: `git worktree add --detach` en `a894a1c3`
(diez ids) o `fe593a44` (seis ids con la exclusión de 2016_sem20).
