**Dictamen: APTO_CON_CONDICIONES.** Las guardas de extracción y de apertura fallan cerradas en lo esencial, pero hay tres defectos altos que corregir antes de generar fichas o abrir otra prueba de 2025.

Leí los guiones tal como estaban en disco durante esta sesión (`READY_CODE_REVIEW` fechado 2026-11-12T22:04:51Z). No ejecuté pruebas ni calculé hashes, y no leí CSV reales. No vi cambios durante la lectura.

## Altos

**A1. La ficha no deriva su tipo del release** (`gen_fichas.py:194-198`, `45-87`)
- El tipo `aceptado|control` sale sólo del argumento de la CLI; el `:<release_id>` se descarta y nunca se lee ningún manifiesto de release, contra lo que dice el docstring.
- `control()` falla cerrado porque exige `v['caida_al_control']` (línea 139). `aceptado()` no comprueba lo contrario.
- Un padecimiento publicado con el control y pasado como `=aceptado` sale con la plantilla que dice «Superó la prueba de 2025».
- `aceptado()` tampoco coteja el sexo contra las series de la vista, como sí hace `control()` en la línea 137.

**A2. La ficha afirma prospectividad sin comprobarla** (`gen_fichas.py:107-114`)
- `prospectiva()` y `semanas_objetivo()` escriben siempre que los boletines «aún no existían al emitir». Lo deducen sólo del calendario.
- No leen la disponibilidad real, que el backend ya registra (`after_emission.first_available`, `bulletin_provenance.py:130-132`).
- La consulta del índice (P5) ocurre al abrir la prueba, no al emitir. Si el boletín 44 aparece entre ambos momentos, la ficha afirma algo falso (precedente: Asma).

**A3. P3 no compara la configuración del snapshot de extracción** (`model_test.sh:61-75`, `47-48`)
- P3 compara la entrada del registry y el grupo de cuadro entre el commit de la selección y HEAD. El `snapshot_sha` de las pasadas sólo se compara entre sí.
- El propio skill (línea 178) declara que `source_exclusions` no entra en el digest del dataset.
- Un raw extraído antes de un cambio de exclusiones, con selección posterior al cambio, pasa P3 y P4 y abre 2025.
- Arreglo: añadir el snapshot a la comparación de entrada y grupo.

## Medios

**M1. La lista de publicables confía en una línea de texto** (`lista_publicables.py:34-41`)
- «Aceptado» se decide por la línea `OK aceptado` de `registro.txt`. No se comprueba en disco que refit y forecast existan con manifest `succeeded`, ni que `test=` sea el `test_run` leído.
- La rama de control no exige que el manifest del test sea `succeeded`. `model_test.sh:103` puede haberse detenido con `acceptance.json` ya escrito.
- La prueba `test_operativos.py:140-154` consagra el defecto: `sint_ok` es publicable sin ningún run de refit o forecast en el fixture.

**M2. La autorización de control es auténtica sólo por nombre de archivo** (`lista_publicables.py:17-21`)
- Cualquier `AUTORIZACION_AUTOR*.md` cuenta, incluida una línea de ejemplo dentro de él.
- La salida no registra el sha256 del archivo leído.

**M3. La autorización de política es un archivo vacío** (`model_test.sh:29`, `model_dev.sh:14`)
- `AUTORIZACION_POLITICA_<id>.ok` habilita cualquier política distinta de `rolling_cv_v1`, sin nombrar cuál. Es más débil que P1.

**M4. El manifiesto se valida por conteo de filas** (`valida_extraccion.py:47`)
- No se comprueba unicidad ni se coteja contra el listado de `pdfs/`. Un duplicado más una omisión pasa.
- El skill (líneas 175-176) exige «sin duplicados ni omisiones».
- `N_PDF = 670` vale para este corte; parametrizarlo al llegar el boletín 44 es un pendiente, no un defecto.

**M5. El raw canónico no se verifica contra lo validado** (`extract_snap.sh:34-35`, `post_snap.sh:29-30`, `model_dev.sh:18`)
- No se borra el `RUN.json` previo antes de cada id, se ignora el código de salida del validador y el `cp` va silenciado.
- `post_snap.sh` calcula `raw` del canónico y nunca lo compara con `csv_sha256` de `RAW.json`.
- `model_test.sh:40-45` lo detecta antes de abrir 2025, pero smoke, full y select ya habrían corrido sobre un raw sin verificar.

**M6. La selección no se liga al dataset en desarrollo** (`model_dev.sh:31`, `post_snap.sh:43-44`)
- El código de salida de `select` no detiene nada y el guion devuelve 0.
- `post_snap.sh` da por buena cualquier `<id>_select_*`, sin cotejar su dataset. Lo frena después `model_test.sh:53`.

**M7. El texto de política es fijo** (`gen_fichas.py:68-74`, `163-168`)
- Toda política distinta de `rolling_cv_v1` recibe «cinco motores estacionales», «pliegues de 2021 a 2024» y umbrales de 5 % y 10 % escritos a mano.
- Una política de historia corta quedaría mal descrita. Falta un `assert` de política conocida.

**M8. Calendario frágil, latente en este corte** (`gen_fichas.py:104`, `65-67`, `41-42`)
- El número de boletín se calcula como semana + 1, que se rompe en el cambio de año (W52 daría «53»).
- Sin `target_weeks` en la vista, las semanas de la plantilla de otitis quedan intactas sin aviso.
- Los `re.sub` de fechas y semanas no comprueban que hubo reemplazo.

**M9. Pruebas que no prueban**
- `test_calendario_semanas_objetivo` (`test_operativos.py:166-175`) sólo comprueba que `cola` termina en punto. Su comentario dice W13 en curso; por mi cálculo MMWR, el 1-abr-2030 W11 a W13 ya concluyeron y W14 está en curso.
- `importorskip` salta esa prueba en silencio si falta el `PYTHONPATH`.
- No hay pruebas de: tipo contra vista, sin sexo, texto «no validado», cambio de año, duplicados en el manifiesto, `RUN.json` rancio, ni de ninguna guarda de shell (P3 a P7, candado, apartado).
- En `guarda_aprobacion` sólo se muta `raw_sha256`.

## Skill

Sin objeciones. Las dos copias coinciden en F1 (líneas 173-179). No fijan 670: piden «el inventario de PDF previsto para ese corte». Los worktrees detached van como «por ejemplo», y no añaden autorizaciones por configuración.

## Comprobado sin hallazgo

- `guarda_aprobacion.py` exige línea exacta y cinco campos, y falla cerrado ante archivos ausentes o malformados.
- P6 y P7 no reintentan.
- El runner valida el linaje del refit contra el test (`orchestrator.py:556-600`).
- El extractor no escribe CSV sin boletines válidos, y la validación lo marca como no fresco.

## Condiciones

1. A1 y A2 antes de generar cualquier ficha.
2. A3 antes de la siguiente apertura de 2025.
3. M1 antes de usar la lista para crear releases.

El resto puede ir como pendiente. Este dictamen no acepta padecimientos ni concede autorizaciones de pretest, política, control o publicación.