# Reporte de hallazgos — Dengue, Fase 1 (extracción y validación)

**Fecha:** 2026-06-03
**Alcance:** PoC de extracción + modelado. Esta Fase 1 cubre **solo extracción y validación** de la serie histórica de Dengue desde los boletines del SINAVE. El modelado (Fase 2+) queda pendiente.
**Estado:** completada y auditada (incluye un súper audit "a ciegas" contra los píxeles del PDF).

---

## 1. Decisión de modelado (con base científica)

**Se modela el Dengue TOTAL agregado, NO por severidad** (A97.0 no grave + A97.1 con signos de alarma + A97.2 grave, sumados en un único padecimiento `"Dengue"`).

Sustento (investigación de literatura, 21 fuentes primarias con verificación adversarial):
1. El dengue grave (A97.2) es ~0.1–0.2 % de los casos en las Américas → series estatales semanales casi en cero, ruidosas e intrínsecamente no pronosticables.
2. La capacidad predictiva proviene de la **autocorrelación y estacionalidad de la serie agregada** (quitar términos autorregresivos duplica el error; quitar clima apenas lo mueve, +1.8 %).
3. La vigilancia oficial (PAHO/WHO/SINAVE) tiende el **total** de casos como métrica primaria; severidad y muertes son subcategorías.
4. Ningún estudio publicado de forecasting de dengue modela las severidades como series separadas. Pronosticar severidad es un problema de **clasificación clínica**, distinto del pronóstico de incidencia.

Si en el futuro se requiere carga grave (planeación de camas): pronosticar el total y aplicar una **razón de severidad histórica**, nunca una serie de severidad independiente.

**Caveat:** A97.1 (signos de alarma) NO es tan raro como A97.2; su proporción exacta en SINAVE quedó sin verificar. Si fuera sustancial, podría justificarse modelarlo aparte a nivel nacional/regional (no estatal).

---

## 2. Estructura de los datos en el boletín (hallazgos)

- El **Dengue vive en una tabla aparte** del boletín (Cuadro 7.2 "Enfermedades Transmitidas por Vector"), **separado** del cuadro de padecimientos neurológicos. NO comparten página.
  - Ejemplo (2026_sem20.pdf): pág. 13 = resumen nacional; **pág. ~40 = tabla Dengue por entidad**; pág. 79 = tabla neuro por entidad.
  - La página del Dengue varía entre boletines (p. ej. pág. 30–40 según la semana/año).
- **Estructura por entidad: idéntica a la tabla neuro** → 12 columnas de datos = **3 severidades × 4 columnas** `[Sem, Acumulado_hombres, Acumulado_mujeres, Acumulado_año_anterior]`.
  - Confirmado leyendo los píxeles del PDF (encabezado: `Sem | Acum. H | Acum. M` del año en curso + `Acum.` del año anterior, por cada severidad).
  - El layout es **idéntico en 2021 y 2025** (verificado visualmente).
- **Heterogeneidad histórica por época de clasificación:**
  - **2014–2017:** esquema OMS 1997 (`A90` Dengue / `A91` hemorrágico). 2 categorías. **NO soportado.**
  - **2018–2019:** era A97 pero con layout de **10 columnas** (sin "año anterior"; redacción "sin/con datos de alarma / severo"). **NO soportado.**
  - **2020–2026:** layout moderno de **12 columnas** (esquema OMS 2009, A97.0/A97.1/A97.2). **Soportado.**

---

## 3. Enfoque de extracción

- Nuevo módulo `src/epiforecast/data/extraction/dengue_extractor.py` (SRP) + script `scripts/extrae_dengue.py` (batch). Reutiliza `clean_df`/`normalize_number` del extractor neuro.
- **Localización de página anclada en los códigos CIE `A97.0/A97.1/A97.2`** + marcadores de entidad (Aguascalientes/Zacatecas). Más estable que la redacción, que cambia entre años. Encuentra exactamente 1 página por boletín en 2020–2026.
- Extracción con Camelot (stream) → 32 filas × 12 columnas → **agregación de las 3 severidades** columna por columna → esquema idéntico a `dataset_boletin_epidemiologico.csv`.
- **Año y semana se toman del NOMBRE DE ARCHIVO** (`YYYY_semNN.pdf`), fuente autoritativa.

---

## 4. Bugs encontrados y corregidos (auditoría)

Cada uno fue real, encontrado por verificación independiente, y corregido:

| # | Bug | Causa | Fix |
|---|-----|-------|-----|
| 1 | **Off-by-one en la semana** (2024 sem43–48 desfasadas → sem49 duplicada, sem43 borrada) | La página usa "semana epidemiológica N del YYYY"; la rama `SEMANA_REGEX_2` heredada sumaba +1 | Derivar año/semana del **nombre de archivo** (`_year_week_from_filename`) |
| 2 | **Separadores de miles mixtos** (TOTAL con coma "1,332" Y espacio "7 655" en el mismo renglón) → 2024 (año epidémico) se perdía entero | El parser del TOTAL solo colapsaba espacios | Quitar comas + colapsar espacios de miles |
| 3 | **Pie "§FUENTE" colado** como fila | `clean_df` no filtra el "§" inicial | Restringir a las 32 entidades canónicas (`STATES`, normalizado sin acentos/case + alias) |
| 4 | **Parses incompletos** (Camelot pierde filas superiores, ~9 sem de 2020) | Camelot stream | Gate `n_states == 32`; los incompletos se descartan |
| 5 | **Artefacto de columna duplicada** (`2024_sem29`: Camelot copió A97.1-prev en A97.2-Sem → `Casos_semana` corrupto: Yucatán 526 en vez de 0, Quintana Roo 669 en vez de 4) | Camelot duplica una celda en páginas con cierto render; **la compuerta TOTAL no lo atrapaba porque el TOTAL de texto comparte el artefacto** | Gate `_duplicated_adjacent_column()` rechaza el boletín |

**Validación por boletín:** suma de las 32 entidades vs renglón TOTAL impreso (tolerancia `absdiff ≤ 10` para erratas tipográficas).

---

## 5. Súper audit a ciegas (metodología y resultado)

Se validó el CSV producido (ruta Camelot) **sin confiar en nada**, contra 4 fuentes independientes:
1. **Parser pypdf-texto** (camelot-free) — falló en celdas densas (pypdf parte dígitos: "21" → "2 1").
2. **pdfplumber por coordenadas** — falló en otras celdas densas.
3. **Lectura visual de los píxeles del PDF renderizado** (oráculo definitivo).
4. **Validador independiente del orden de columnas:** `cumsum(Casos_semana)` vs `Acum(H+M)` final.

Resultados:
- Las 9+ "discrepancias" entre parsers eran **artefactos de los parsers ingenuos**, no del CSV (Camelot, estructural, ganó cada caso adjudicado por lectura de píxeles).
- Verificación independiente del orden: **97.9 % exacto, 98.9 % dentro de ±2**; **0 outliers en años completos 2021–2025**.
- Estructura de columnas confirmada visualmente; total nacional CSV 2025-W47 = TOTAL impreso exacto (845 / 8284 / 10609).
- **Anomalías de FUENTE (no bugs):** Zacatecas 2024-W41 trae A97.1 acumulado = 14 522 / 17 657 **impreso así en el boletín** (error de SINAVE, capturado fielmente). Chihuahua 2024-W41: 14 casos sin desglose H/M (inconsistencia de fuente; `Casos_semana` correcto).

---

## 6. Estado final del dataset

- **`data/interim/dengue_boletin.csv`** (gitignored, regenerable; NO versionado en git ni DVC todavía):
  - **10,240 filas · 320 boletines OK · 2020–2026 · 32 entidades.**
  - 0 duplicados, 32 entidades por semana, consistencia cumsum mediana 1.000.
  - 2024 completo **salvo sem29** (cuarentena justificada).
- **Cobertura:** 2021–2025 ~100 % (52/52 por año), 2024 52/52, 2026 20/20, 2020 41/53.
- **No soportado** (reportado, no mezclado): 2018–2019 (layout 10 col) y 2014–2017 (esquema OMS 1997 A90/A91).
- Auditoría automática en cada corrida del script (`_audit_series`: duplicados, completitud, cumsum).

---

## 7. Limitaciones latentes (aceptables para PoC, documentadas)

- Regex de miles frágil ante el espaciado de pypdf (funcionó para todo lo incluido; validado contra TOTAL).
- `"n.d."` → 0 (conflación "sin dato" vs "cero"; irrelevante en 2020–2026, latente para datos antiguos).
- Tolerancia `absdiff ≤ 10` no atrapa desajustes de pocas decenas en categorías casi-cero.
- El localizador toma la **primera** página candidata; abre el PDF 3×.

---

## 8. Artefactos web (Fase 1 pública)

- **Página:** `dengue_fase1.html` (repo Dashboard) → https://epiforecast.mx/dengue_fase1.html — decisión de modelado, screenshot del cuadro PDF + pipeline de 6 pasos, 3 gráficos preliminares, **gráfico nacional interactivo (Chart.js, en vivo)** y **cuadro de cifras EN VIVO**. Enlazada desde el nav y desde Novedades.
- **Generador reproducible:** `scripts/build_dengue_web.py` (repo principal) → 3 charts PNG + `dengue_serie.json`. La tabla/gráfico web hacen fetch del JSON: al regenerar la serie y redeployar, **se actualizan solos**.

---

## 9. Archivos creados

**Repo principal (`EpiForecast-MX`):**
- `src/epiforecast/data/extraction/dengue_extractor.py`
- `scripts/extrae_dengue.py`
- `scripts/build_dengue_web.py`
- Sección "Dengue Expansion (In Progress)" en `README.md`
- Este documento.

**Repo Dashboard (`EpiForecast-IMSS-Dashboard`):**
- `dengue_fase1.html`
- `Reports/dengue/` (3 charts PNG + screenshot del cuadro + `dengue_serie.json`)
- Tarjeta de Novedades + enlace en nav en `index.html`

---

## 10. Pipeline para un boletín nuevo (canónico)

```
python scripts/extrae_dengue.py                # regenera data/interim/dengue_boletin.csv + manifest
python scripts/build_dengue_web.py --out ../EpiForecast-IMSS-Dashboard/Reports/dengue --generado <fecha>
# commit + push del Dashboard → Netlify despliega → tabla/gráfico web se actualizan
```

---

## 11. Pendiente (Fase 2+)

- Merge al dataset productivo (decidir DVC add+push para la serie de Dengue).
- Añadir `Dengue` a `constants.CONDITIONS` y propagación a reportes/Excel/EpiBot.
- Config de estacionalidad específica (ciclo anual fuerte; sin régimen COVID análogo).
- Entrenar y validar los 4 motores (Prophet, DeepAR, Ensemble, Stacking).
- Regiones: nacional + estatal, **sin** el fallback regional híbrido de salud mental (no aplica a una arbovirosis climática).
- Revisar los umbrales de `reselect_motor_2026.py` (calibrados para neuro de baja incidencia) ante el volumen/estacionalidad del Dengue.
