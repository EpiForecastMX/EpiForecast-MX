# Fixture del chrome común (frontend EpiForecast-IMSS-Dashboard)

Copia literal, sin editar, de archivos del frontend tras el hito 3 del rediseño, con la misma
disposición que un dashboard (`cargar_fragmentos(fixture)` funciona igual). Las pruebas del
backend (`tests/unit/publication/test_site_shell.py`, `test_editorial_chrome.py`) corren siempre con
ella, sin depender de que el repositorio hermano esté presente.

| Archivo | Origen en el frontend |
|---|---|
| `assets/site/shell.config.json` | `assets/site/shell.config.json` (fuente única de cabecera/pie) |
| `assets/site/shell.fragments.json` | `assets/site/shell.fragments.json` (lo genera `node scripts/site_shell.mjs`) |
| `asma_j45.html` | ficha de release estampada (familia `ficha-release`) |
| `reporte_resultados.html` | página editorial con productor en el backend (`scripts/genera_reporte.py`) |
| `epibot_index.html` | `epibot/index.html`: sólo `<head>` y cierre (recursos y su versión) |

Para actualizarla, después de cambiar el shell en el frontend:

```sh
D=../EpiForecast-IMSS-Dashboard
node $D/scripts/site_shell.mjs            # regenera fragmentos y estampa
cp $D/assets/site/shell.{config,fragments}.json tests/fixtures/site_shell/assets/site/
cp $D/asma_j45.html $D/reporte_resultados.html tests/fixtures/site_shell/
{ sed -n 1,20p $D/epibot/index.html; echo '<!-- … cuerpo omitido en el fixture … -->'; sed -n '/<!-- Panel lateral/,$p' $D/epibot/index.html; } > tests/fixtures/site_shell/epibot_index.html
```

Las pruebas comprueban la coherencia interna (página real = estampado de la página vaciada con estos
fragmentos; `aria-current` de cada familia = lo que declara `shell.config.json`) y no requieren Node.
