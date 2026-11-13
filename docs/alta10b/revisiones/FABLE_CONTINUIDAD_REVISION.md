**Dictamen: Otras hepatitis 2014→2015 queda demostrada en la muestra (falta el artefacto de todo 2014); Otras helmintiasis 2016→2017 no está demostrada, porque la prueba de continuidad no tiene potencia para ese cambio.** Ambas son pendientes, no fallos. Los CIE actuales son correctos. Sólo leí; no ejecuté nada.

## Otras hepatitis víricas (rótulo 2014 «B17-B19» → 2015 «excepto B17.1 y B18.2»)

- **Dominancia estatal:** en `txt/2014_sem10.txt:1820-1858` el bloque vecino de Hepatitis C (B17.1, B18.2) supera a «Otras» en varias entidades. Baja California tiene 49 de C frente a 6 de Otras; Chihuahua 15 frente a 6; Sinaloa 21 frente a 13; Hidalgo 4 frente a 0. Un bloque que contuviera a C no podría ser menor que C, así que el de 2014 ya la excluía.
- **Lo mismo para 2013:** en la columna de 2013 de ese boletín, Baja California tiene 60 de C frente a 11 de Otras.
- **Aquí la razón nacional sí tiene potencia:** C sumaba 238 en la semana 9 de 2014 frente a 317 de Otras. Si el bloque la hubiera contenido, el reimpreso caería del orden de 75 %; fue 313 frente a 317 (`txt/2015_sem10.txt:2019`).
- **Cierre del año:** 2 085 → 2 027 (−2.8 %), dentro de los años vecinos (−0.6 %, +1.1 %, +4.8 %).
- **Extracción:** el CSV coincide con el PDF en las celdas que cotejé (2014/10 y 2015/10 de Aguascalientes, Baja California y Jalisco).

Condiciones para darla por cerrada:
1. Guardar en `qa/` la dominancia para todos los boletines de 2014: celdas estado-semana con acumulado de Otras menor que el de C, usando el raw de `hepatitis_c_b17`.
2. Guardar el artefacto del TOTAL «518/518» y confirmar que cubre 2014 y el paso de 11 a 12 columnas en 2015_sem02. En `qa/` sólo hay desnutrición y continuidad.
3. Explicar los extremos de los años de control (0.51 en 2015→2016 y 1.67 en 2016→2017) indicando la semana. Probablemente son denominadores pequeños de las primeras semanas, pero el JSON no lo dice.

## Otras helmintiasis (desde 2017 «excepto B73 y B75»)

- **Lo medido:** la razón 2016→2017 (mediana 1.0097, cierre +0.99 %) es indistinguible de los vecinos (+0.56 %, +0.77 %, +1.97 %, +0.42 %).
- **Por qué no prueba nada:** B73 y B75 pesan a lo sumo 0.14 % del bloque, por debajo del ruido de revisión (cerca de 1 %). La razón saldría igual con o sin la exclusión.
- **Dominancia:** tampoco sirve; el bloque siempre supera a B75.
- **Lo que sí consta:** triquinosis (B75) y oncocercosis (B73) ya tenían bloque propio en 2014, 2015 y 2016 (`txt/2014_sem10.txt:1650,2033` y equivalentes). El rótulo de 2014 a 2016 saltaba B68, B69, B77 y B80, pero no B73 ni B75. Es compatible tanto con una aclaración como con un doble conteo previo; el boletín no lo distingue.
- **Cifra sin respaldo:** el «6 a 223 casos al año» de `PLAN_ALTA10.md:57-59` sigue sin artefacto, es nacional y es un argumento de magnitud. La frase «no rompe la comparabilidad» debe retirarse o reformularse como cota.

Evidencia concreta que falta:
1. Acumulados de B73 y B75 por entidad y año, 2014 a 2016, extraídos de los propios PDFs. Si son cero en todas las celdas, la exclusión es vacía y la identidad queda demostrada sin umbral. Si no, queda la cota máxima por entidad (el riesgo está en entidades chicas como Durango o Zacatecas), no una demostración.
2. O bien la fuente documental: el catálogo SUIVE con las claves de 2014 a 2016, que mostraría si triquinosis y oncocercosis se capturaban con clave propia excluyente.

Opciones si no se demuestra (ninguna la concedo yo):
- **A. Serie completa desde 2014 con `rolling_cv_v1` intacta**, declarando la limitación y la cota medida. Es una decisión de comparabilidad del autor, como la de mordeduras (§2, nivel C).
- **B. Truncar a 2017:** no cabe en la política vigente. De 2017-W01 a 2020-W53 hay 209 semanas, menos de las 260 exigidas, y el pliegue 2021 falla en `policy.py:192`. Exigiría una política nueva, es decir, cambiar criterios, fuera de este lote sin orden del autor.
- **C. Dejarla `configured`**, sin full oficial ni apertura de 2025, hasta tener la evidencia 1 o 2.

Recomiendo C mientras se mide la evidencia 1, que es barata, y llevar A al autor sólo si sale distinta de cero.

## Controles de `scripts/continuidad.py`

- **Semana:** `Semana` es la semana fuente (el boletín 10 imprime «hasta la semana 9»). El cruce usa la misma semana fuente en ambos años y el rezago es 1 en los cuatro `sem10` leídos. El rezago sólo está muestreado en un boletín por año; el script no lo verifica.
- **Denominadores:** completos (1 664 = 52×32; 1 632 = 51×32). Las 32+32 filas sin par de 2014→2015 son la semana 01 excluida y la semana 53 de 2014; son coherentes.
- **Salida por entidad:** el docstring la promete, pero sólo se emite el conteo de celdas iguales, sin peor entidad ni razón estatal.
- **Trazabilidad:** falta el sha256 del CSV. El de helmintiasis es `pass1c`, no el raw fijado con dos pasadas idénticas; hay que repetir sobre el definitivo.

## CIE en `padecimientos.yaml` (wt-be)

- **`otras_hepatitis_b17` (línea 2317):** enumera B17.0, .2, .8, .9, B18.0, .1, .8, .9 y B19. No absorbe B17.1 ni B18.2 (hepatitis C, línea 1925) ni B15 o B16. El alias `b17-b19` ya no está.
- **`helmintiasis_b65` (línea 2394):** enumera sin B73, B75, B68, B69, B77 (ascariasis, línea 1461) ni B80. El único alias es «otras helmintiasis».
- **Salvedad:** los `cie_codes` de helmintiasis afirman la definición posterior a 2017 para toda la serie. Mientras no se demuestre, el periodo del rótulo sólo consta en un comentario (línea 2392) y no en la ficha.