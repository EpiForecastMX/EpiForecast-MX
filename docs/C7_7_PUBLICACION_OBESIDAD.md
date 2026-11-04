# C7.7 — Publicación de Obesidad (E66)

**Estado al 4-nov-2026:** Obesidad está `published` con el OK formal del autor. Se publica desde el
release sellado `obesidad_release_2517e7858901` en los canales `web`, `epibot` y `reports`.
Tableau quedó fuera por decisión del autor, porque requiere pasos manuales en Sheets y Tableau
Desktop. `gallery_enabled` sigue en `false`. F50 y Diabetes siguen ocultas.

| hecho | valor |
| --- | --- |
| Release | `obesidad_release_2517e7858901` (64 modelos, 111 productos, origen 2026-W26, 52 semanas, sin intervalos) |
| Validación prospectiva | PASS 4/4 (W27–W30) con gate congelado `5bc39aa5…` |
| Verdad observada | `obesidad_b5e1209fe31b` (boletín W42, semana epidemiológica W41) |
| Desempeño fuera de muestra W27–W41 | nacional sMAPE 13.8 %, sesgo −11.4 %; mediana estatal 20.2 |
| Puntero activo | `config/publication/obesidad/public_release_pointer.json` |

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

## Rollback (objetivo: menos de 30 minutos, sin reentrenar)

1. Revertir en el backend el commit `C7.7 publish obesity release …` (lifecycle `trained`,
   canales y puntero).
2. Revertir en el frontend el commit de instalación. Sale `publication/` con catálogo, punteros y
   vista, y salen `obesidad.html`, la tarjeta de la portada y el handler. Después,
   `npm run rag:build`.
3. Fusionar y desplegar. Comprobar en vivo que `/obesidad` responde 404 y que el EpiBot ya no
   responde sobre Obesidad.
4. Conservar el bundle, las observaciones y la evidencia. No borrar nada.
