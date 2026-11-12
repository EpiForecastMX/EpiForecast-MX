**Dictamen: AUTORIZABLE_PRETEST, sólo `desnutricion_leve_e441`, sólo con `rolling_cv_v1`, una única apertura de 2025.** Nada científico lo impide y no depende de las reservas, de helmintiasis ni de las políticas de moderada y severa. La apertura queda sujeta a las condiciones P1 a P7, que sólo el orquestador puede ejecutar. Sólo leí: no calculé sha256, no hice diffs de git ni consulté la red.

## Lo que comprobé

- **Fuente y CIE.** Es el tercer bloque del Cuadro 14, rotulado «Desnutrición leve, E44.1» en `2014_sem10`, `2017_sem30`, `2018_sem30` y `2026_sem43`. El boletín 43 dice «hasta la semana 42», así que el rezago es 1. En ese boletín, el renglón nacional «Desnutrición E40-E43, E44.0, E44.1» da 1 134 = 87 + 188 + 859, la suma de los tres grados.
- **Sin confusión de grados ni de población.** El registry declara `cie_codes: ["E44.1"]` y sólo los alias «desnutricion leve», «desnutricion grado leve» y «e44.1»; «desnutrición» a secas no es alias. Frente a moderada coinciden 93 de 21 384 celdas y frente a severa 56 de 21 374. El cuadro no define edad, así que no debe presentarse como pediátrica.
- **Extracción.** Las dos pasadas dieron 669 boletines ok y 21 408 filas. El único excluido es `2014_sem01`, que no tiene columna semanal y cuyo objetivo cae fuera de la serie. Ningún boletín tiene menos de 32 entidades ni está todo en cero. La pasada 1 corrió antes del commit de configuración `e4d15b34`; la pasada 2, ya sobre él.
- **TOTAL impreso.** El denominador honesto es 501 de 669: 501 iguales, 0 distintos y 168 sin cotejo por tokenización del renglón TOTAL.

  | Periodo | Boletines cotejados |
  | --- | --- |
  | 2025 (año de prueba) | 53 de 53 |
  | 2026 | 43 de 43 |
  | 2021-2024 (desarrollo) | 192 de 208 |
  | 2017-2018 | 4 de 104 |

- **Por qué los 168 no bloquean.** La verdad de 2025 está cotejada completa y el control `lag52` se alimenta de 2024, cotejado en 51 de 52. Un error en 2016-2019 sólo degradaría el ajuste del portafolio; no puede fabricar un PASS.
- **Dataset.** `desnutricion_leve_e441_e211223d9d39`, con raw `d88a5327…`, 64 bases y 111 productos. Su digest de configuración sólo depende de id, rezago, número de estados, exposición y catálogo geográfico (`epi_dataset.py:231-251`).
- **Historia real.** La serie va de 2014-W01 a 2026-W42 sin huecos, con 366 semanas de entrenamiento antes del pliegue 2021 (el mínimo es 260).
- **Smoke, full y select.** Smoke y full `…full_f114ac85adf5` terminaron `succeeded` con los siete motores en el commit `54e6ba24`. La selección `…select_f114ac85adf5_fe2324b2e0e7` reparte ETS 38, media 5 años 15, Ridge 6, media 3 años 3 y mediana 5 años 2. No es sólo control, así que la validación sería propia.

  | sMAPE en desarrollo | Portafolio | `seasonal_naive_lag52` |
  | --- | --- | --- |
  | 64 bases | 40.76 | 54.40 |
  | 111 productos | 33.47 | 48.58 |
  | Nacional general | 12.81 | 19.57 |

- **Commits posteriores.** Hay nueve después de `54e6ba24`, hasta `63fa732f`, y por sus mensajes sólo tocan otros grupos. En el código actual, `valor_en_columna_nombre` está activo en cuatro grupos y no en `alta10b_desnutricion`. El reintento por área de página sólo se dispara con menos de 32 estados, lo que no ocurre en ningún boletín de leve. El stage `test` exige igual política y `dataset_id`, no igual commit (`orchestrator.py:486-494`), así que la selección sirve en HEAD.
- **Test previo.** No existe `desnutricion_leve_e441_benchmark_test_*` en el lote ni en `runs/` del checkout principal, y el id no aparece en la configuración de `main`. No busqué en `planes/` ni en el resto de `/tmp`.
- **Nivel 2024 → 2025.** Pasa de 50 316 a 53 164 casos por año fuente, de 968 a 1 003 por semana (+3.7 %). No hay riesgo de nivel que avisar.

## Scripts

- **`model_dev.sh`:** ya no corre el full si el smoke no termina `succeeded`.
- **`check_index.sh`:** falla cerrado sin red, con página antibot o con un boletín 44. La última consulta registrada es de las 15:43:50 hora del este.
- **`model_test.sh`:** cubre determinismo de las dos pasadas contra el raw, dataset de la selección igual al actual, índice, búsqueda de test previo y registro de nivel. Tiene un defecto que corregir (P1) y un comportamiento que vigilar (P7).

## Condiciones previas a la apertura

- **P1. Aprobación nominal.** `model_test.sh:11` sólo comprueba que exista `FABLE_PLAN_APPROVED.md`. Un archivo genérico desbloquearía también helmintiasis, que usa `rolling_cv_v1` y no está aprobada. El archivo debe nombrar únicamente `desnutricion_leve_e441`, y la línea 11 debe exigirlo, por ejemplo con `grep -qx "AUTORIZABLE_PRETEST desnutricion_leve_e441"`.
- **P2. Denominador.** Cambiar «501/501» por «501 de 669, 0 distintos, 168 sin cotejo» y la cobertura por año en `PLAN_ALTA10.md` (tabla del nivel A) y en `PROGRESS.md`. No ampliar anchos para subir la cifra.
- **P3. Diff acotado, que debe salir vacío.** `git diff --stat 54e6ba24..HEAD -- config/evaluation config/engines src/epiforecast/runner src/epiforecast/data/epi_*.py config/exposicion.yaml config/geografia`. Además, el diff de `config/padecimientos.yaml` y `config/data/cuadros.yaml` no debe tocar la entrada `desnutricion_leve_e441` ni el grupo `alta10b_desnutricion`. Guardar la salida en `model/desnutricion_leve_e441/`.
- **P4. Identidad.** `model_test.sh desnutricion_leve_e441 pass1 pass2` debe pasar sus guardas con sha256 de pass1, pass2 y raw igual a `d88a5327…` y dataset `…e211223d9d39`. Tras el `validate-data`, el digest `config` debe seguir en `f4a1066d…`.
- **P5. Índice.** `check_index.sh` debe dar http 200, 43 adjuntos y último 43 en esa misma ejecución. Si aparece el 44, no se abre ni se rodea la guarda; primero se redefine el corte.
- **P6. Test previo.** La búsqueda de la línea 27 debe dar 0, con su salida guardada.
- **P7. Una sola apertura.** Si el test termina con rc distinto de 0 o sin `acceptance.json`, se detiene y se reporta, sin reintento silencioso. Si rechaza, el padecimiento queda `configured`, con el run conservado, sin refit y sin control salvo orden nominal del autor posterior a las cifras.

Recomendado, no bloqueante: cotejar a la vista el único boletín de 2024 sin TOTAL (ancho 10), porque alimenta una semana del control. La nota «información preliminar, incluye casos probables» debe ir en la ficha si se publica.

## Punto separado: fuente SUIVE de helmintiasis (no es aprobación de pretest)

Abrí los dos PDF de `fuentes_suive/` y coinciden con `qa/helmintiasis_fuente_suive.json`.

- **Formato SUIVE-1-2014:** el renglón 14 es «Otras helmintiasis B65-B67, B70-B76, B78, B79, B81-B83 excepto B73 y B75». Triquinosis (B75) tiene la clave 103 y oncocercosis (B73) la 69. También tienen clave propia teniasis, cisticercosis, ascariasis y enterobiasis.
- **Formato SUIVE-1-2019:** idéntico en esos renglones.

Esto es la fuente documental excluyente que pidió la revisión de continuidad: la captura ya excluía B73 y B75 desde 2014, y el cambio de rótulo de 2017 en el boletín es una aclaración. El punto de comparabilidad 2016 → 2017 queda cerrado sin decisión del autor.

Salvedades:
- No verifiqué los sha256 ni las URL de los PDF.
- No hay formato de 2015-2018 en la carpeta; la definición queda acotada por dos extremos idénticos.
- La conclusión del JSON debería decir «por diseño de captura» en lugar de «nunca estuvieron dentro».

Helmintiasis sigue necesitando su propio raw con dos pasadas idénticas, TOTAL por periodo, full, select y una revisión de pretest propia.