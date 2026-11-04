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

- **Prospectivo respecto de la información, con una reserva en W27:** los datos de las semanas 28
  a 30 se publicaron después de emitir el pronóstico. El boletín con la semana 27 se capturó el
  28 de julio, cuatro días después de la emisión. Capturarlo ese día **no demuestra** que se
  publicara después del 24: solo acota su publicación entre el 23 (última corrida que no lo
  encontró) y el 28. Esta reserva documental va aparte del `PASS 4/4` numérico. Por eso las
  superficies dicen que esas semanas se **registraron** después de la emisión, no que se
  publicaran.
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

## Rollback (objetivo: menos de 30 minutos, sin reentrenar; no ensayado, sin plazo demostrado)

Obesidad llega al sitio por varias superficies, añadidas en PRs sucesivos. Se retiran **en orden
inverso**, para que ninguna página quede apuntando a un recurso retirado. Se conserva toda la
evidencia (bundle, observaciones, PRs).

1. **Frontend** (un solo PR que revierte, en este orden, los merges de #45, #44, #42, #41 y #39):
   - #45: `epibot/js/obesidad_kb.js`, el marcador `<!--OBESIDAD:-->`, el alias de Obesidad en
     `entities.js` y la vista con `forecast_emitted_at`. Al revertirlo, `kb.js` recupera el
     handler en línea que trae #41;
   - #44 y #42: la Figura 1, la galería (`Reports/obesidad_galeria.js` y sus tarjetas), la noticia
     de `news.json` (con el banner estático regenerado con `render_news_banner`) y los textos y la
     tarjeta de la portada;
   - #41: `epibot/js/obesidad_charts.js` y el panel del EpiBot;
   - #39: `publication/` (catálogo, punteros, vista), `obesidad.html`, el handler y el sitemap.

   #40 (tilde de «publica») y #43 (caché de la galería) no dependen de Obesidad y se conservan.
   Después: `npm run rag:build`, `npm run check` y `npm run deploy:verify` en verde.
2. **Backend**: revertir **solo** el commit `C7.7 publish obesity release obesidad_release_2517e7858901`
   (lifecycle `trained`, canales y puntero).
   - **No** revertir #30, #31 ni el de hidratación de manifiestos. Todo se deriva del registry:
     - con Obesidad en `trained`, `published_members()` vuelve a cuatro y la nota dice «cuatro»;
     - `release_published()` queda vacío, la nota no describe releases y el sandbox no hidrata
       ningún manifiesto.
   - Revertir #30 sobre #31 chocaría, porque tocan las mismas líneas.
3. **Fusionar y desplegar** (frontend antes que backend). En vivo:
   - `/obesidad` responde 404;
   - la galería no muestra Obesidad y cuenta 432;
   - la Figura 1 tiene cuatro pastillas;
   - el EpiBot ya no responde sobre Obesidad.
4. No borrar nada: el bundle y las observaciones quedan en DVC.
