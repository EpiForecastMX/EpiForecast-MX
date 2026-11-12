# Esquema de autorizaciones nominales del autor (alta10b)

Única fuente de autoridad para políticas y controles: archivos JSON en
`/tmp/epiforecast-alta10b-20261112/autorizaciones/<nombre>.json`, validados por `scripts/autoridad.py`.
Ningún `.md` (propuestas, resúmenes, ejemplos en bloques de código) ni archivo vacío (`.ok`) autoriza nada.

Root escribe un archivo por respuesta del usuario, con la pregunta y la respuesta **literales**. El
validador no autentica a una persona (root no inventa respuestas ni firmas): sólo impide que un texto
accidental cuente como decisión y registra el sha256 del archivo leído.

Campos (exactamente estos; `evidencia` es opcional):

- `schema`: `"autorizacion_autor.v1"`
- `registrado_por`: `"root"`
- `recibida_utc`: ISO 8601 con zona (momento en que el usuario respondió)
- `canal`: dónde respondió (p. ej. el chat del supervisor)
- `pregunta_literal`: la pregunta tal como se le presentó, con ids, runs y cifras
- `respuesta_literal`: la respuesta del usuario, sin editar
- `alcance`: lista no vacía; cada elemento es uno de
  - `{"tipo": "control", "id": <id>, "test_run": <id>_benchmark_test_...}`: publicar el control de ese run
  - `{"tipo": "politica", "id": <id>, "politica": <política conocida>}`: correr desarrollo y prueba con esa política
- `evidencia`: ruta o referencia opcional (p. ej. la propuesta mostrada)

Reglas del validador: claves desconocidas, campos vacíos, fechas sin zona, ids o runs mal formados,
políticas desconocidas o textos con marcas de plantilla (`<`, `>`, «EJEMPLO», «TODO», «xxx», «...»)
invalidan el archivo completo. Una autorización parcial se expresa listando sólo los ids autorizados.

Consumidores: `model_dev.sh` y `model_test.sh` (política distinta de `rolling_cv_v1`),
`lista_publicables.py` (control). Comprobar a mano: `python3 scripts/autoridad.py lista`.

Estado actual: no hay ninguna autorización de política ni de control para este lote.
