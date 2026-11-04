# C7.7 — Publicación de Obesidad (E66)

**Estado al 4-nov-2026:** Obesidad está `published` con el OK formal del autor. Se publica desde el
release sellado `obesidad_release_2517e7858901` en los canales `web`, `epibot` y `reports`.
Tableau quedó fuera por decisión del autor, porque requiere pasos manuales en Sheets y Tableau
Desktop. `gallery_enabled` sigue en `false`. F50 y Diabetes siguen ocultas.

| hecho | valor |
| --- | --- |
| Release | `obesidad_release_2517e7858901` (64 modelos, 111 productos, origen 2026-W26, 52 semanas, sin intervalos) |
| Validación prospectiva | PASS 4/4 (W27–W30) con gate congelado `5bc39aa5…` (ver «Cronología») |
| Verdad observada | `obesidad_b5e1209fe31b` (boletín W42, semana epidemiológica W41) |
| Desempeño fuera de muestra W27–W41 | nacional sMAPE 13.8 %, sesgo −11.4 %; mediana estatal 17.9 % (32 estados, ambos sexos) y 21.3 % en las 64 series base |
| Puntero activo | `config/publication/obesidad/public_release_pointer.json` |

## Cronología del pronóstico (qué sostiene «prospectivo»)

Auditoría del 4-nov-2026. Las fechas salen de artefactos sellados y de la historia de Git, no de
la memoria:

| hecho | fecha | fuente |
| --- | --- | --- |
| Último dato de entrenamiento | semana 26 de 2026 (653 semanas) | `release_manifest.json` · `calendar`; `train_end` de cada modelo |
| Emisión del pronóstico | 25-jul-2026 04:55 UTC (24-jul, 22:55 en CDMX) | `forecast/run_manifest.json` · `created_at` |
| Gate de la validación fijado | 26-jul-2026 | commits `f41c2e3d`, `83f04ce6` |
| Boletín 28 (semana 27) capturado | 28-jul-2026; la corrida del 23-jul no lo encontró | `ci: actualiza dataset.dvc` `a2bbb103` |
| Primera semana registrada | 29-jul-2026 | `f025045a` |
| Semanas 28 a 30 registradas | 19-ago-2026 (boletines 29 a 31, publicados en agosto) | `7385fdf9`, `d9fd64b6`, `a8f62672` |

Lectura correcta:

- **Prospectivo respecto de la información:** los datos de las semanas 28 a 30 se publicaron después
  de emitir el pronóstico. La semana 27 se capturó cuatro días después de la emisión, y no podemos
  fechar su publicación con más precisión que «entre el 23 y el 28 de julio».
- **No es prospectivo en el calendario:** al emitirse, las semanas 27 y 28 ya habían terminado y la
  29 estaba en curso. No se afirma que fueran semanas futuras ni que el pronóstico se emitiera
  «en la semana de origen».
- La selección de motores usó validación cruzada temporal en pliegues de 2021 a 2024
  (`rolling_cv_v1`). No se describe como hecha «antes del origen».
- La vista pública lleva `forecast_emitted_at` (leído del bundle verificado). Las superficies
  muestran la fecha de emisión junto al origen.

## Qué cambió en el contrato semanal

- **Paridad de corte:** cubre a **todos** los publicados, incluida Obesidad. El consolidado debe
  traer Obesidad en la misma `(año, semana)` que los otros cuatro (`revisa_consolidado`).
- **Revisiones de archivos:** las revisiones de `all_forecast_*`, `tabla_333`,
  `produccion_dengue` y zoom aplican solo al carril legacy (`ContratoCobertura.legado`).
- **Publicados del runner:** en lugar de esas revisiones, cada uno exige su bundle íntegro
  (inventario y checksums) y una validación prospectiva publicable del **mismo** release
  (`revisa_releases`).
- **Generadores legacy:** los rosters de `knowledge.json` y la demografía iteran
  `registry.legacy_published()`. Las cifras 333/99/432 de los cuatro padecimientos no cambian.

## Cadena de publicación

```bash
# backend
.venv/bin/python -m scripts.publication_activate obesidad --out runs/publication --check
.venv/bin/python -m scripts.publication_view obesidad \
    --shard-root runs/publication/compile_a/obesidad/obesidad_release_2517e7858901 \
    --out runs/publication/vista_obesidad.json
# frontend (desde epibot/)
node scripts/install_publication.mjs \
    --shard  ../../EpiForecast-MX/runs/publication/compile_a/obesidad/obesidad_release_2517e7858901 \
    --pointer ../../EpiForecast-MX/config/publication/obesidad/public_release_pointer.json \
    --vista  ../../EpiForecast-MX/runs/publication/vista_obesidad.json
GEMINI_API_KEY=… npm run rag:build && npm run check && npm run deploy:verify
```

`publication_activate` compila dos veces y exige árboles idénticos. Con `--write-pointer`, en vez
de `--check`, escribe el puntero, y solo lo acepta si el registry ya está en `published`. El
instalador vuelve a verificar cada archivo del shard. El release instalado es inmutable y
`publication/catalog.json` es el único commit visible.

## Cada boletín nuevo (paso adicional al carril productor semanal)

Para el boletín N, sin reentrenar ni tocar el release:

1. `make prospective-week DISEASE=obesidad PDF=<2026_semN.pdf>`; si el dry-run sale verde,
   `make prospective-week-record …`.
2. `dvc add artifacts/observations/obesidad/<nuevo_id>` y `dvc push` del `.dvc`. Usar un entorno
   DVC sano: el `.venv` tiene aiobotocore incompatible con botocore.
3. Unir las filas nuevas de `inputs/data_raw_Obesidad.csv` de esa observación al consolidado de la
   semana N del carril productor. El cambio solo puede añadir filas y el prefijo debe quedar
   byte-idéntico. Comprobar `revisa_consolidado`: los cinco publicados deben estar en `(2026, N)`.
4. Regenerar la vista y reinstalar con el instalador (el release no cambia; `vista.json` sí).
   Después, `npm run rag:build`.

Si Obesidad no avanza con los demás, la paridad falla cerrada. No se publica parcialmente.

La nota semanal (`scripts/build_news_weekly.py`) describe los dos carriles. El corte de la ronda y
los 432 gráficos son del carril semanal. Cada release conserva su origen y suma sus series (111 en
Obesidad); la galería muestra en total 543 tarjetas.

## Rollback (objetivo: menos de 30 minutos, sin reentrenar; no ensayado)

Obesidad llega al sitio por varias superficies, añadidas en PRs sucesivos. Se retiran **en orden
inverso**, para que ninguna página quede apuntando a un recurso retirado. Se conserva toda la
evidencia (bundle, observaciones, PRs).

1. **Frontend, presentación** (un solo PR que revierte, en este orden, los merges de #44, #42 y #41):
   - Figura 1 de la portada (pastilla de Obesidad);
   - galería: tarjetas y `Reports/obesidad_galeria.js`;
   - noticia de `news.json` y banner estático, regenerado con `render_news_banner`;
   - textos y tarjeta de la portada;
   - gráficas y panel del EpiBot (`obesidad_charts.js`).

   Tras revertir, `npm run check` y `npm run deploy:verify` en verde.
2. **Frontend, instalación** (revertir el merge de #39):
   - salen `publication/` (catálogo, punteros, vista), `obesidad.html`, el handler y el sitemap;
   - `npm run rag:build` para retirar los chunks del release;
   - `npm run deploy:verify`.
3. **Backend** (revertir `C7.7 publish obesity release …`): lifecycle `trained`, canales y puntero.
   Revertir también #30, para que la nota semanal vuelva a exigir solo a los cuatro.
4. **Fusionar y desplegar** (frontend antes que backend). En vivo:
   - `/obesidad` responde 404;
   - la galería no muestra Obesidad y cuenta 432;
   - el EpiBot ya no responde sobre Obesidad.
5. No borrar nada: el bundle y las observaciones quedan en DVC.
