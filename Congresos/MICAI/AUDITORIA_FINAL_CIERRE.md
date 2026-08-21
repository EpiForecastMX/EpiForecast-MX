# Auditoría final de cierre — MICAI 2026, ponencia 12

Fecha de corte: 2026-08-21. Rama del paper:
`paper/micai-2026-camera-ready`.

## Veredicto

El **artefacto del paper está técnicamente listo**: compila desde su propio ZIP,
respeta el techo de 20 páginas y pasa los controles científicos, tipográficos,
bibliográficos y de custodia. El envío completo sigue en **NO-GO operativo**
hasta cerrar cuatro acciones externas:

1. publicar el commit correctivo del repositorio reproducible;
2. hacer coincidir CMT con la portada;
3. obtener la conformidad de Ruth sobre la forma abreviada de su afiliación y
   firmar a mano la licencia;
4. subir el paquete y conservar el acuse.

## Candidato sellado

- Archivo: `Congresos/MICAI/Envio/012.zip`.
- SHA-256: `688315d48fd43bd6ecabbc47e363c5c8d6abd059d1c81a5af8c033fd8dec22bb`.
- Tamaño: 701,752 bytes.
- Contenido: un solo `012.tex`, `012.pdf`, `llncs.cls`, `splncs04.bst` y las
  tres figuras externas realmente referenciadas.
- Reconstrucción desde el ZIP: 20 páginas A4, `pdflatex rc=0`, cero errores,
  cero referencias sin resolver y cero desbordes mayores de 6 pt.

## Hallazgos bloqueantes encontrados y cerrados

1. **Ablación pública distinta del paper.** `analysis/ablation.py` elegía el
   menor sMAPE en la fase dinámica en vez de ejecutar la regla completa
   sMAPE → MASE → RMSE. La corrección está en el commit local `9282e37` del
   repositorio `per-series-model-selection2026`, junto con pruebas negativas y
   `data/ablation_results.csv` regenerado.
2. **Sobreafirmación de reproducibilidad.** El apéndice decía que la tabla por
   estado y la asignación congelada eran reproducibles. En realidad se liberan
   como entradas; lo reproducible desde ellas es la ablación. El texto ya hace
   esa distinción.
3. **Afirmaciones causales sin evidencia directa.** Se retiró que los picos
   “producen saturación” y se debilitó la atribución del déficit masculino a
   subregistro: ahora se presenta como posible contribución de búsqueda de
   atención o reporte, no como causa demostrada.
4. **Alcance y licencia del repositorio público.** El README ya no promete los
   wrappers productivos que no distribuye. Se separó MIT para código y
   documentación de los términos DGE para los datos, con procedencia y enlace
   oficial en `DATA_LICENSE.md`.
5. **Instrucciones operativas caducas.** El checklist ya apunta a la licencia
   local descargada, exige firma manuscrita, prohíbe los paquetes históricos y
   usa las fechas oficiales vigentes.

## Auditoría científica y numérica

- Tabla 1: estructura, denominadores y nota de cobertura coherentes.
- Tabla 2: 17 semanas W02–W18; observado 48,300; pronosticado 49,482;
  desviación +2.45%; sMAPE 7.40%; MAE 205.
- Figura 3 y Tabla 2 usan la misma numeración de boletín.
- Figura 4 y análisis por serie usan W03–W18, la intersección común de 16
  semanas; `n=99` principal y `n=111` sólo como sensibilidad regional.
- Tabla 3 pública reproducida desde clon limpio: 13 filas contrastadas antes
  del redondeo; hash determinista de `data/ablation_results.csv`
  `217192fa570e3f2e52e12c10d5ae239ff7385e80da3b3576bf454e894f9d88f4`.
- Regla dinámica: ventana W03–W11; puntuación W12–W18; ningún dato puntuado
  participa en la reselección.
- Los p de Diebold–Mariano se declaran exploratorios; con Holm los dos mínimos
  son 0.0502 y no cruzan 5%.
- La cobertura empírica se reporta como subcobertura, 10/17 = 58.8%, no como
  intervalo prospectivo calibrado.
- No sobreviven cifras retiradas de la alineación antigua.

## Auditoría de referencias, una por una

Se comprobaron título, autores, año, sede y destino. Los DOI se resolvieron y
se contrastaron con Crossref o la página editorial; un HTTP 403 del editor se
trató como protección automatizada sólo cuando el DOI y sus metadatos seguían
siendo válidos. Las referencias de arXiv se contrastaron además con su registro
final en OpenReview.

| # | Referencia abreviada | Resultado |
|---:|---|---|
| 1 | Albert 2015, depresión y sexo | DOI y metadatos correctos |
| 2 | Alexandrov et al. 2020, GluonTS | JMLR canónico y HTTPS directo |
| 3 | Ansari et al. 2024, Chronos | arXiv válido; publicación TMLR verificada |
| 4 | Benidis et al. 2022, survey | DOI ACM y metadatos correctos |
| 5 | Box et al. 2015, 5.ª edición | autores, edición, editorial y año verificados en Wiley |
| 6 | Challu et al. 2023, N-HiTS | DOI AAAI y páginas correctos |
| 7 | Chen y Guestrin 2016, XGBoost | DOI ACM, sede y páginas correctos |
| 8 | Chimmula y Zhang 2020 | DOI Elsevier y metadatos correctos |
| 9 | Cramer et al. 2022 | DOI PNAS y metadatos correctos |
| 10 | Dash et al. 2024 | DOI Scientific Reports correcto |
| 11 | DGE/SINAVE | página oficial viva; fecha de consulta coherente |
| 12 | García-Pacheco et al. 2024 | DOI y volumen impreso correctos |
| 13 | Godahewa et al. 2023 | DOI IJF y páginas correctos |
| 14 | Hewamalage et al. 2021 | DOI IJF y páginas correctos |
| 15 | Hyndman y Athanasopoulos 2018 | segunda edición oficial FPP2 viva |
| 16 | Hyndman y Koehler 2006 | DOI IJF y páginas correctos |
| 17 | Hyndman et al. 2008 | DOI Springer del libro correcto |
| 18 | Ke et al. 2017, LightGBM | actas NeurIPS oficiales vivas |
| 19 | Lim y Zohren 2021 | DOI Royal Society y metadatos correctos |
| 20 | Makridakis et al. 2020, M4 | DOI IJF y páginas correctos |
| 21 | Makridakis et al. 2022, M5 | DOI IJF y páginas correctos |
| 22 | Nie et al. 2023, PatchTST | arXiv válido; ICLR 2023 verificado |
| 23 | Reich et al. 2019 | DOI PNAS y metadatos correctos |
| 24 | Salinas et al. 2020, DeepAR | DOI IJF y páginas correctos |
| 25 | Santomauro et al. 2021 | DOI Lancet y páginas correctos |
| 26 | Taylor y Letham 2018 | DOI American Statistician correcto |
| 27 | Wickramasuriya et al. 2019 | DOI JASA correcto; 2018 es publicación online |
| 28 | Wolpert 1992 | DOI Neural Networks y páginas correctos |

Resultado bibliográfico: 28 referencias, 28 citadas, ninguna cita sin entrada,
ninguna entrada huérfana, orden alfabético íntegro y cinco grupos multicita en
orden numérico.

## Auditoría visual y tipográfica

- Se revisaron las 20 páginas renderizadas, no sólo el texto extraído.
- Portada legible; cinco ORCID; una sola nota de correspondencia; afiliaciones
  y correos sin colisiones.
- Cuatro figuras mencionadas y numeradas consecutivamente; ninguna leyenda se
  cruza con datos o bigotes.
- Tamaño efectivo mínimo de figura entre 6.48 y 6.97 pt, por encima del mínimo
  de Springer; cero fuentes Type 3 y todas las fuentes incrustadas.
- Tablas 1–3 completas, captions arriba y sin superposición.
- Bibliografía continua en páginas 19–20, sin flotantes intercalados.
- Los ORCID verdes y el trim de libro observados en MICAI 2025 son parte de la
  composición editorial final de Springer. La clase oficial de autores muestra
  los identificadores numéricos en el manuscrito fuente; no debe falsificarse el
  acabado del volumen publicado.

## Afiliación de Ruth

La portada usa la forma aprobada para este candidato:

`Instituto Mexicano del Seguro Social, OOAD Guerrero, Mexico`.

El IMSS usa también la forma larga con “Estatal Guerrero”. La abreviación
actual conserva IMSS, OOAD y Guerrero, pero antes de firmar debe quedar una
confirmación escrita de Ruth de que acepta omitir “Estatal” y la expansión de
OOAD, y usar “Mexico” en inglés. Si pide la forma larga, hay que cambiar paper,
CMT y licencia en una sola ronda y volver a sellar el ZIP.

## Plan brutal de ejecución

### A. Publicar la reproducción corregida

1. En `perseriesmodel2026`, revisar el commit `9282e37`.
2. Ejecutar:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 analysis/ablation.py
   git diff --exit-code
   ```

3. Empujar la rama y abrir/mezclar el cambio a `main` sólo si las tres órdenes
   quedan verdes. No publicar el paper ni documentos de auditoría en ese repo.
4. Desde un clon nuevo de `main`, repetir las tres órdenes y comprobar que
   `data/ablation_results.csv` conserva el hash registrado arriba.

### B. Congelar identidad antes del envío

1. Obtener de Ruth un “sí” escrito a la afiliación exacta.
2. En CMT, hacer coincidir nombres, orden, correos y organizaciones carácter por
   carácter con la portada.
3. Descargar/capturar la pantalla final de autores de CMT y compararla con la
   primera página del PDF.
4. No tocar autores después de firmar la licencia.

### C. Firmar la licencia

1. Abrir la copia local indicada en `LICENCIA_LNAI.md`.
2. Copiar el título y los cinco nombres completos de la portada.
3. Dejar `Edition ID / IPS` en blanco.
4. Confirmar que Javier firma en nombre de los cinco y preguntar a Ruth si IMSS
   exige un trámite adicional.
5. Imprimir, firmar con tinta y escanear; no insertar una firma digital.
6. Revisar visualmente el escaneo completo antes de cargarlo.

### D. Preflight irreversible de subida

1. No recompilar ni editar nada después de iniciar este bloque.
2. Ejecutar:

   ```bash
   ./Congresos/MICAI/compila.sh
   .venv/bin/python -m pytest tests/paper_micai_2026 -q --no-cov
   .venv/bin/python scripts/paper_micai_2026/auditoria_paquete.py --verifica
   .venv/bin/python scripts/paper_micai_2026/url_repo_viva.py
   .venv/bin/python scripts/paper_micai_2026/sello_sincronizado.py
   shasum -a 256 Congresos/MICAI/Envio/012.zip
   ```

3. El último valor debe ser exactamente el SHA-256 del candidato sellado.
4. Abrir el ZIP y confirmar visualmente que contiene `012.tex` y no contiene
   versiones ciegas, paquetes viejos, datos, checkpoints ni auditorías.

### E. CMT y acuse

1. Subir únicamente `012.zip` en Camera Ready Submission.
2. Subir la licencia manuscrita en el campo que corresponda.
3. Guardar antes de cerrar la página.
4. Volver a entrar a CMT y comprobar nombre/tamaño del archivo cargado.
5. Descargar o capturar el acuse, la ficha final de autores y la marca temporal.
6. Guardarlos fuera del ZIP junto con `HASH_ENVIO.txt`; no reconstruir el ZIP
   después del acuse.

### F. Después del envío

1. Completar registro y pago dentro de las fechas oficiales.
2. Conservar la rama del paper y el bundle/backup privado; no empujar las
   auditorías internas a `origin`.
3. Cuando llegue la prueba editorial de Springer, revisar en prioridad nombres,
   ORCID, afiliaciones, ecuaciones, Tabla 3, URLs y saltos de referencias.
4. Responder dentro de la ventana de prueba editorial; no asumir que Springer
   corregirá una discrepancia de CMT por cuenta propia.
