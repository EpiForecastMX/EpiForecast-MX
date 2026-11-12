**Dictamen: APTO_CON_CORRECCIONES.** Es la revisión de un plan vivo, no de una ejecución terminada. No se abre ningún `benchmark_test` hasta resolver las condiciones 1 a 9. Este dictamen no otorga permisos del autor.

## ¿Alcanza la cartera para 10?

No, tal como está. Hay 10 candidatos nominales para una meta de 10, es decir, cero reserva.

- **Camino normal (siete motores):** sólo 2. Desnutrición leve tiene el smoke `succeeded`; helmintiasis sigue en extracción (`logs/extract_pass2_helmintiasis_b65.log:5`, 400/670).
- **Nivel B (8):** todos dependen de una orden nominal de política por candidato. Moderada y severa ya fallaron ETS y Ridge (`PLAN_ALTA10.md:55-56`); los otros seis no tienen smoke.
- **Referencia de alta20:** aceptaron 5 de 8 con siete motores y 5 de 17 con cinco (`PLAN_ALTA10.md:29`).

El plan debe decir expresamente que con esta cartera el techo realista está por debajo de 10. Los controles tras rechazo no cuentan a priori: cada uno exige orden nominal posterior a sus cifras.

## Defectos ya observados (corregir)

1. **Brucelosis: configuración rota.** 403 boletines `invalid` por «columnas inesperadas: 11 (esperaba [8, 12])» de 2014 a 2022, más `2023_sem28` con 31 estados (`extract/pass1b/brucelosis_a23_extraccion_manifest.csv:3-471,499`). Sólo 265 salieron ok (`logs/extract_pass1b_brucelosis_a23.log:8,10`), aunque el status marca `rc=0` (`logs/extract_pass1b.status:3`). Falta el ancho 11 en `cuadros.yaml:1448`. Hay que abrir `2023_sem28` antes de declarar exclusión. Ese raw no puede entrar a `validate-data`.

2. **Leptospirosis: misma causa.** 0 ok en los primeros 300 PDFs y 25 en 400 (`logs/extract_pass1b_leptospirosis_a27.log:2-5`). `cuadros.yaml:1473` sólo declara el ancho 12.

3. **Hepatitis A, `2024_sem09`: exclusión por fallo del extractor con PDF válido.** El PDF trae las 32 entidades y el TOTAL 133/467/335/657 (`txt/2024_sem09.txt:692-732`). La configuración lo excluye e imputa (`cuadros.yaml:1118-1123`) bajo un bloque comentado como «erratas de FUENTE» (`cuadros.yaml:94`). Es el patrón que el skill marca como error (`SKILL.md:170-172`). Hay que reparar la lectura y cotejar con el TOTAL. Si no se logra, se declara como dato real descartado en un pliegue de desarrollo, y el patrón nunca se usa en 2025. El plan lo llama «668/668» (`PLAN_ALTA10.md:57`) sin decir que se descarta un dato real.

4. **Helmintiasis: CIE y alias inexactos.** El rótulo se confirmó en fuente (`txt/2016_sem10.txt:1104-1106`, `txt/2017_sem10.txt:902-904`, `txt/2026_sem43.txt:1605-1607`). Pero `cie_codes` incluye `B70-B76`, que abarca B73 y B75, excluidos por el rótulo (`padecimientos.yaml:2391` frente a `2409`). El precedente de neumonías enumera sin los excluidos (`padecimientos.yaml:1255`). Además:
   - el alias `b65-b83` abarca B68, B69, B77 y B80, que son otros bloques;
   - `helmintiasis` y `parasitosis por helmintos` a secas exceden el bloque (`padecimientos.yaml:2392`); deben pedir precisión, como «otitis» y «amebiasis»;
   - las cifras de B73/B75 del plan (`PLAN_ALTA10.md:46-47`) no tienen artefacto citado; falta medir la continuidad 2016→2017 con el «año anterior» impreso.

5. **Otras hepatitis: cambio de rótulo no declarado.** En 2014 el bloque dice sólo «B17-B19» (`txt/2014_sem10.txt:1810-1814`); desde 2015 dice «Excepto B17.1 y B18.2» (`txt/2015_sem10.txt:1972-1974`). Coincide con el paso de 11 a 12 columnas (`cuadros.yaml:1417-1418`). Falta medir la comparabilidad 2014→2015. Los `cie_codes` `["B17","B18","B19"]` y el alias `b17-b19` (`padecimientos.yaml:2316-2317`) absorben B17.1 y B18.2, que son de hepatitis C (`padecimientos.yaml:1925`). El registry sólo detecta duplicados exactos (`registry.py:437-442`), así que no falla solo.

6. **Exclusiones por «escasez extrema» sin criterio escrito.** El plan excluye hepatitis B (13 semanales), fiebre reumática (16), bocio (18) y otras de 13 o menos (`PLAN_ALTA10.md:94-98`), pero incluye brucelosis (24, `txt/2026_sem43.txt:415`) y otras hepatitis (21, `DECISIONES_PENDIENTES.md:97-98`). Shigelosis, con 38.6 semanales y 85 % de ceros, fue aceptada (`DECISIONES_PENDIENTES.md:44`). Es un umbral inventado. Deben pasar a reservas de nivel B, o excluirse sólo por un defecto de datos medido. El bocio de `2016_sem20` tiene precedente de errata de fuente (`cuadros.yaml:101-106`).

7. **Sensibilidad por población.** El plan excluye coqueluchoide, rotavirus y parálisis flácida como «vigilancia pediátrica» (`PLAN_ALTA10.md:86`). Coqueluchoide y parálisis flácida van «hasta la semana 43» (`txt/2026_sem43.txt:3961-3966`): el motivo medido es rezago 0. Rotavirus necesita su rezago medido o reclasificarse. Vulvovaginitis y la familia de transmisión sexual siguen fuera por orden expresa (`OPUS_TAREA.md:11`).

8. **`model_test.sh` no cumple el §4.5 del plan.**
   - Busca `benchmark_test_` sólo en el checkout principal y en el worktree (`scripts/model_test.sh:17`), no en los temporales de alta20. Importa para los ids heredados: hepatitis A, ascariasis y enterobiasis.
   - No exige `FABLE_PLAN_APPROVED.md`.
   - No registra la revisión de nivel 2024→2025.
   - `model_dev.sh:14-15` corre el full aunque el smoke falle, contra el §4.3.

9. **Orden de commits.** Las correcciones 1 a 5 cambian la configuración después de `e4d15b34`, y los datasets de desnutrición llevan ese `code_commit` (`runs/desnutricion_leve_e441_e211223d9d39/dataset_manifest.json:5`). Conviene congelar la configuración antes de cualquier full oficial. No verifiqué si `select` acepta un benchmark de otro commit.

## Reservas legítimas por aprovechar

10. **Giardiasis.** Está excluida por un fallo de camelot (`PLAN_ALTA10.md:94-95`), y esa misma página ya se resuelve por ancho para helmintiasis (`cuadros.yaml:1498-1505`). Es la reserva con más probabilidad de ir por siete motores. Requiere reparar el primer bloque y cotejar el TOTAL en los 92 boletines, sin imputar 2025.
11. **Ascariasis y enterobiasis.** Los anchos 11 ya están declarados (`cuadros.yaml:700,726`). Falta extracción, TOTAL y smoke.
12. **Alacrán y mordeduras.** Sólo con decisión del autor (`PLAN_ALTA10.md:69-76`). El plan las deja fuera correctamente.

## Políticas y autorizaciones

- **Historia:** `rolling_cv_v1` y la de baja incidencia piden 260 semanas con `series_start` 2014-W01 (`rolling_cv_v1.yaml:11,15`). Todos los bloques existen desde 2014_sem02, así que no hay exclusión por historia. `policy.py:145,192` compara contra el YAML, no contra los datos: brucelosis y leptospirosis deben demostrar cobertura real tras el arreglo.
- **Política de cinco motores:** una orden por candidato, con mediana estatal, porcentaje de ceros, nacional semanal y motor que falla. La de los 17 no se extiende (`DECISIONES_PENDIENTES.md:99-101`). La política también expulsa a Ridge (`SKILL.md:184-186`).
- **Si la selección resulta sólo control** (digests de candidato y control iguales): no se promete validación propia; el veredicto sería `CONTROL_ONLY`.
- **Controles:** ninguna orden genérica vale; sólo nominal, con el run y sus cifras.

## Pendientes expresos (no son defectos)

- Pass2 de moderada, severa, helmintiasis y todas las reservas; hoy sólo leve lo tiene (`logs/extract_pass2.status:1`).
- TOTAL y smoke de helmintiasis y de los seis de nivel B.
- Nueva consulta del índice antes de cada apertura; `check_index.sh:14` falla cerrado.
- Aviso de nivel de hepatitis A, 8 586 → 3 977 (`PLAN_ALTA10.md:64-65`), al autor antes de abrir.

## Antes del primer `benchmark_test`

- Resolver las condiciones 1 a 9 y actualizar el plan con cartera, techo y motivos de exclusión corregidos.
- Tener pass2 idéntico y TOTAL cotejado del candidato.
- Tener full y `select` con la configuración congelada.
- Buscar tests previos en principal, worktrees y temporales.
- Consultar el índice.
- Contar con `FABLE_PLAN_APPROVED.md` emitido sobre el plan corregido.

No verifiqué: las cifras de mediana estatal, los cotejos «501/501» y «668/668» (no hay directorio `qa/`), los md5 de los PDFs ni la ausencia de tests previos. Tampoco ejecuté nada.