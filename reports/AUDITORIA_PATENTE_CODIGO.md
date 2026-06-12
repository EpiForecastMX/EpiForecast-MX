# Auditoría de Código para Entrega de Patente — EpiForecast-MX

## 1. Veredicto general

El repositorio **requiere trabajo antes de entregar**: el código nuclear (`src/epiforecast`) es de calidad de entrega (ruff/mypy strict/tests verdes), pero existen **3 blockers** y **5 high confirmados** que tocan directamente la viabilidad de la patente. Los dos blockers críticos son legales/de novedad: el repo está **público bajo licencia MIT** (`gh repo view` confirma `PUBLIC`; `LICENSE` confirma MIT canónica), lo que constituye divulgación habilitante previa y licencia irrevocable de uso/venta sobre la propia invención. El tercer blocker es de reproducibilidad: datos y modelos viven solo en S3 privado (AccessDenied verificado), así que un entregable code-only no es auto-contenido. Ningún blocker está en el código en sí; todos son de gobernanza del entregable y deben resolverse con asesoría legal de PI antes de cualquier trámite.

## 2. Tabla de hallazgos por severidad

| Severidad | Dimensión | Hallazgo | Ubicación | Acción |
|---|---|---|---|---|
| **blocker** | Licencias | Repo PÚBLICO bajo MIT: divulgación previa que mina novedad y licencia irrevocable de uso/venta. NBGLM público desde 2026-06-05 (commit `a9b12372`), repo desde 2025-12-21 | `LICENSE:1-22`; `gh repo view` = PUBLIC; `nbglm/model.py` | Hacer privado el repo de inmediato; auditar fechas vs gracia 12m (US/MX); presentar provisional antes de seguir divulgando; relicenciar futuro código |
| **blocker** | Higiene-entrega | LICENSE MIT licencia públicamente el software a patentar (gobierna `pyproject.toml:15` y README) | `LICENSE:1-22`, `pyproject.toml:15`, `README.md:614-616` | Reemplazar por aviso "All Rights Reserved / Confidencial — Propiedad de Tec de Monterrey / IMSS"; alinear pyproject y README; coordinar con legal |
| **blocker** | Reproducibilidad | Datos y modelos solo en S3 privado (AccessDenied confirmado con `--no-sign-request`); git solo trackea punteros `.dvc` | `data/raw.dvc`, `models.dvc`, `.dvc/config`, `README.md:234-235` | Empaquetar subconjunto fijo de `.pkl` + datos raw congelados (o tarball versionado) con md5; incluir PDFs SINAVE fuente + script de regeneración end-to-end |
| **high** | Reproducibilidad | Entry point `epiforecast` roto: apunta a `scripts.train:main` inexistente (real `entrena.py`); `scripts/` ni siquiera es paquete instalable | `pyproject.toml:98` | Corregir a `scripts.entrena:main` (verificar `main()` + `scripts/__init__.py`) o eliminar; validar con `pip install -e . && epiforecast --help` |
| **high** | Código-muerto | `checkpoints/` (446M de `.ckpt`) NO está gitignored; `git check-ignore` exit 1 | `/checkpoints/`, `.gitignore:198-199` | Añadir `checkpoints/` y `*.ckpt` a `.gitignore`; excluir del paquete (artefactos regenerables) |
| **high** | Docs | GEMINI.md omite por completo el motor NBGLM (5.º registrado, "el mejor del estudio") | `GEMINI.md:7,20-26` | Actualizar a "5 motores" e incluir `NBGLMForecaster` en Arquitectura Polimórfica |
| **high** | Docs | README se contradice: "Currently registered models" lista 4, omite `nbglm` (que describe en L572) | `README.md:509` vs `:572` | Cambiar L509 a `prophet, deepar, ensemble, stacking, nbglm` y agregar subsección canónica |
| **high** | Higiene-entrega | `notebooks/` tracked con outputs base64 incrustados (118M; 3.0-jar 37M/61 PNGs) | `notebooks/3.0,4.0,5.0-jar-*.ipynb` | Excluir del entregable; limpiar con `nbstripout`; borrar `notebooks/bad` y `.zip` |
| **high** | Higiene-entrega | `references/` (213M) y `reports/` (134M) tracked: PDFs académicos, fotos del equipo, PNGs de 3-5M | `references/Avance7/**`, `reports/Avance4.Equipo01.pdf` (23M), `reports/FigResumenEjecutivo/**` | Excluir `references/` completo y `reports/` casi completo (conservar solo `ProdDetails/` si se requiere demostrar métricas) |
| **high** | IP-patentable | Selección de motor por serie auditable YA divulgada (paper MICAI título literal + `dengue.html` en vivo) | `reselect_motor_2026.py:97-165`, `produccion_dengue.py:112-164`, `paper_submission.tex:61-100`, `dengue.html:503` | Reorientar reivindicación a reglas no divulgadas (banda empate 5%+MAE, umbrales, fallback regional); auditar fechas vs gracia |
| **high** | IP-patentable | Motor NBGLM (NegBin GLM + Fourier + ENSO lag-16) descrito con hiperparámetros en Medium y web | `nbglm/model.py:39-104`, `enso.py`, `Stories/...md:75-90`, `metodologia_dengue.html:350-352` | Asumir NBGLM base no defendible; centrar PI en `freeze_trend`/`as_of`/persistencia amortiguada no divulgados; verificar prior art NegBin+ENSO |
| medium | Calidad | Cobertura justo en el mínimo (70%); motores nucleares por debajo (`prophet/model.py` 55%) | `prophet/model.py`, `stacking/*` | Subir cobertura de `predict()`/`fit()` sin cubrir antes de congelar snapshot |
| medium | Código-muerto | `_ajusta_incrementos` es código muerto (llamada comentada), solo lo invocan 3 tests | `transformer.py:133-181`, `:287-288` | Borrar método + 3 tests, o reducir a comentario de 1 línea |
| medium | Código-muerto | Script huérfano `patch_deepar_completo_dengue.py` (one-off de recuperación, 0 referencias) | `scripts/patch_deepar_completo_dengue.py` | Excluir del paquete o mover a `scripts/oneoff/` |
| medium | Código-muerto | `Stories/` (3.9M) y `Congresos/` (631M) presentes y no ignorados (material doble-ciego en revisión) | `/Stories/`, `/Congresos/` | No incluir; añadir a `.gitignore`; cuidar anonimato de papers |
| medium | Código-muerto / Higiene | `.epi_history.json` trackeado: historial personal de comandos con typos y preguntas off-topic | `/.epi_history.json` | `git rm --cached` + `.gitignore` |
| medium | Docs | `models/__init__.py` docstring lista 3 de 5 algoritmos | `src/epiforecast/models/__init__.py:3` | Corregir a los 5 motores |
| medium | Docs | NBGLM y DeepAR: métodos públicos clave sin docstring | `nbglm/model.py:107,233,...`; `deepar/model.py:127` | Documentar `fit/predict/run/save/load` de NBGLM y `__init__` de DeepAR |
| medium | Docs (downgraded de high) | `EnsembleForecaster`: 6 métodos del contrato `ForecastModel` sin docstring (no así `ProphetForecaster`) | `ensemble/model.py:186,207,231,261,288,303` | Añadir docstrings de 1 línea (NOTA: `fit` SÍ documenta; `prediction.py` citado no existe) |
| medium | Docs | `entrena.py` y `predice.py` (entry points centrales) sin docstring de módulo (10/47 scripts) | `scripts/entrena.py`, `scripts/predice.py` | Añadir docstring de módulo de 1-2 líneas |
| medium | Secretos | Rutas absolutas `/Users/haowei/` en 4 notebooks tracked (outputs sin limpiar) | `notebooks/0.1,3.0,4.0,5.0-*.ipynb` | `nbstripout` antes de empaquetar o excluir |
| medium | Secretos | Ruta absoluta a repo externo hardcodeada en script de producción | `scripts/actualiza_semanal.sh:22` | Parametrizar `DASHBOARD_ROOT` via env var con default relativo |
| medium | Reproducibilidad | `requirements.txt` viola constraints de pyproject (xgboost 3.2.0 vs serie 2.x; pytest 9.0.2 vs 8.x) | `requirements.txt:24,40` | Regenerar con `pip freeze` o eliminar |
| medium | Reproducibilidad | Sin lock file (rangos abiertos en deps) | `pyproject.toml:24-52` | Congelar lock exacto del entorno validado |
| medium | IP-patentable (downgraded de high) | Clamp de envolvente estacional: concepto/nombre YA divulgados en web; solo el algoritmo (woy-max × 1.5) sigue no descrito | `forecast_guards.py:24-60`, `metodologia_dengue.html:319-321,356-358` | Reivindicar el mecanismo concreto (máx por semana-ISO, factor 1.5, fallback); dejar de divulgar el detalle |
| medium | IP-patentable | Pipeline extracción PDF SINAVE: novedoso en lo específico pero probablemente obvio | `dengue_extractor.py:1-295`, `dengue_historico_a9091.py` | Entregar como soporte/reproducibilidad, no como reivindicación independiente |
| medium | IP-patentable | Validación prospectiva OOS con pronóstico congelado: método potencialmente reivindicable, no divulgado en detalle | `pronostico_congelado.py`, `enso.py:90-108` (`as_of`) | Considerar reivindicar el ciclo selección-revisable + congelado; verificar qué dice MICAI para no auto-anticiparlo |
| medium | Higiene-entrega | `CLAUDE.md` y `GEMINI.md` (config interna de IA) no deben ir en el entregable | `CLAUDE.md`, `GEMINI.md` | Excluir del árbol curado (revelan flujo de trabajo, caveats de leakage, decisiones no finales) |

## 3. Recomendación de entrega (qué código incluir)

Esta es la decisión central. El repo pesa ~5.5 GB en disco; la **invención real son ~2.4-2.6 MB**. La propuesta es entregar un **árbol curado** y dejar fuera todo el bloat documental tracked (~465 MB).

**INCLUIR (núcleo reivindicable + evidencia):**
- `src/epiforecast/` — el invento (94 `.py`, ~14.9k LOC): `models/` (factory + base + los 5 motores Prophet/DeepAR/Ensemble/Stacking/NBGLM), `evaluation/` (métricas), `features/`, `visualization/`, `pipelines/`, `data/` (extracción), `utils/`.
- `scripts/` — entry points CLI de orquestación (limpiando el script huérfano `patch_deepar_completo_dengue.py`).
- `config/` — los YAML que parametrizan el método.
- `epi_modules/` — consola interactiva (si se reivindica; periférica).
- `tests/` — evidencia de funcionamiento (56 archivos).
- `docs/model_cards/` + `docs/research/INFORME_ARQUITECTURA_MULTIMODELO.md`.
- Build: `pyproject.toml` (con entry point corregido), `requirements.txt` (regenerado), `Makefile`, `README.md`, `.pre-commit-config.yaml`, `.python-version`.
- **`LICENSE` corregida** (NO MIT).

**EXCLUIR (no aporta a la patente y/o legalmente problemático):**
- `references/` (213 MB) y `reports/` (134 MB, salvo `ProdDetails/` si se requiere demostrar métricas) — material académico y de terceros, varios son divulgaciones públicas previas.
- `notebooks/` (118 MB con outputs base64) — exploratorios; la lógica reivindicable ya está en `src/`.
- `CLAUDE.md`, `GEMINI.md`, `.epi_history.json` — config interna de IA + historial personal.
- `Congresos/`, `Stories/`, `checkpoints/`, `mlruns/`, `lightning_logs/` — ya untracked; dejar fuera.
- Screenshots `x/xx/xxx`-prefijados, leftovers LaTeX (`.aux/.toc/.out`), `logs/*.log.zip`.
- `web_dashboard/` (deploy separado), `reports/dashboards/viz_epiforecastmx.twb`.

**DEPENDE (decisión explícita con legal):**
- **Datos del IMSS + modelos `.pkl` (DVC/S3, ~579 MB):** recomendable entregar SOLO código + config (el método reivindicable) y NO los datos clínicos (confidenciales) ni los binarios (no reivindicables). PERO ver §1: para reproducibilidad de la solicitud puede necesitarse un subconjunto congelado.
- `aws/` (SageMaker): incluir solo si el backend AWS forma parte de la reivindicación; parametrizar antes el AWS account ID `564141855321`.

## 4. Riesgo legal/patente

- **MIT + repo público = doble problema (BLOCKER, confirmado dos veces).** MIT concede a cualquiera derecho irrevocable a "use, copy, modify, publish, distribute, sublicense, and/or sell". Es irrevocable sobre copias ya distribuidas y contradice la exclusividad de patente. Además, publicar el código bajo MIT en repo público constituye **divulgación habilitante previa** que destruye la novedad en jurisdicciones de novedad absoluta (EPO/Europa, MX). **Verificar con legal:** hacer privado el repo de inmediato (`gh repo edit --visibility private`), documentar fechas exactas de divulgación, y evaluar gracia de 12 meses (US 35 USC 102(b)(1); MX) para presentar provisional a tiempo.
- **Fechas de divulgación a documentar con precisión:** primer commit del repo 2025-12-21 (`83afdd09`); NBGLM introducido 2026-06-05 (`a9b12372`); puesta en vivo de `epiforecast.mx/dengue` (ya EN VIVO); paper MICAI 2026 (marcado NO ENVIADO, deadline 14-jun-2026); post de Medium ("listo para publicar"). El reloj de novedad del método y del NBGLM ya empezó vía la web.
- **Novedad ya comprometida por publicaciones propias** (ver §5): el paper MICAI titula literalmente la contribución central, y la web/Medium describen NBGLM con hiperparámetros. En jurisdicción sin gracia, enfocar la solicitud en sub-invenciones no divulgadas.
- **Terceros:** núcleo original sobre librerías permisivas (statsmodels BSD, etc.); **0 imports directos de GPL en `src`** (ghostscript/grandalf/text-unidecode son transitivos, usados como binarios). Punto fuerte. **Verificar con legal:** reemplazar el logo IMSS hot-linked desde seeklogo.com (`README.md:2`) por un asset autorizado; confirmar consentimiento de los correos personales en `.tex`/`.twb`.

## 5. IP patentable identificada

Mapeo a `archivo:función` para alimentar reivindicaciones, ordenado por defensibilidad **dado que la novedad de las candidatas fuertes ya está parcialmente comprometida**:

1. **Clamp de envolvente estacional por semana epidemiológica** (mejor margen restante) — `models/forecast_guards.py:24-60`. Cota cada semana de pronóstico al **máximo histórico de esa misma semana-ISO × 1.5**, con fallback al máximo global. El *concepto* ya está nombrado en `metodologia_dengue.html`, pero el **algoritmo concreto** (máx por woy, factor 1.5, fallback) NO está divulgado. Reivindicar el mecanismo específico como guard de plausibilidad agnóstico al motor.
2. **Regresor ENSO/ONI desplegable** — `data/enso.py:77-108`. ONI futuro = observado + persistencia amortiguada hacia neutral; parámetro **`as_of`** que trunca el ONI conocido para backtest sin leakage climático. Elementos no divulgados en detalle.
3. **Proyección multi-anual NBGLM** — `models/nbglm/model.py:140-205`. `freeze_trend`, `trend_anchor_weeks`, `future_oni`, fallback constante para series degeneradas. No divulgados en Medium/web → reivindicaciones dependientes aun si el NBGLM base pierde novedad.
4. **Reglas de selección/desempate por serie** — `scripts/produccion_dengue.py:112-164` (banda de empate 5% desempatada por MAE, "si es 0 es 0" por menor MAE) y `scripts/reselect_motor_2026.py:97-165` (fallback ruidosa→Ensemble, fallback CV). El método general ("auditable per-series model selection") **ya está divulgado** en MICAI y web; reivindicar las reglas y umbrales concretos (no la idea).
5. **Protocolo de validación prospectiva con pronóstico congelado** — `scripts/pronostico_congelado.py`. Selección provisional + congelado de la cola futura no vista + reselección al llegar boletines (migración a CV si OOS>2x). Método de operación no descrito algorítmicamente.

**NO patentable (entregar solo como contexto del sistema):** patrón Factory/registry (`factory.py:12-36`) e interfaz `ForecastModel` (`base.py:10-48`) son prior-art GoF masivo. Pipeline de extracción PDF (`dengue_extractor.py`) es novedoso en lo específico pero probablemente obvio.

## 6. Checklist de remediación antes de entregar

Por prioridad:

- [ ] **(BLOCKER, legal)** Hacer privado el repo de inmediato (`gh repo edit --visibility private`) para detener nueva distribución.
- [ ] **(BLOCKER, legal)** Reemplazar `LICENSE` MIT por aviso propietario/confidencial; alinear `pyproject.toml:15` y `README.md:614-616`; coordinar texto con legal/INDAUTOR/IMSS.
- [ ] **(BLOCKER, legal)** Auditar con abogado de PI las fechas de divulgación (repo, NBGLM `a9b12372`, web en vivo, MICAI, Medium) vs gracia 12m; presentar provisional antes de seguir divulgando.
- [ ] **(BLOCKER, reproducibilidad)** Definir bundle auto-contenido: subconjunto fijo de `.pkl` + datos raw congelados (o PDFs SINAVE + script de regeneración verificado) con md5 documentados.
- [ ] **(high)** Corregir entry point `pyproject.toml:98` (`scripts.train:main` → real) y validar `pip install -e . && epiforecast --help`.
- [ ] **(high)** Añadir `checkpoints/` y `*.ckpt` a `.gitignore`; confirmar 0 `.ckpt` tracked.
- [ ] **(high)** Actualizar `GEMINI.md:7` y `README.md:509` para incluir NBGLM (5 motores).
- [ ] **(high)** Excluir `notebooks/`, `references/`, `reports/` (salvo `ProdDetails/`) del paquete; limpiar `notebooks/bad` y `.zip`.
- [ ] **(IP/legal)** Reorientar reivindicaciones a elementos no divulgados (§5 #1-3, #5); verificar exactamente qué publican MICAI/Medium/web para no auto-anticipar.
- [ ] **(medium)** Subir cobertura de motores nucleares antes de congelar snapshot (`prophet/model.py` 55%, `stacking/*`).
- [ ] **(medium)** Eliminar código muerto `_ajusta_incrementos` + 3 tests y bloques comentados (`transformer.py`); mover/excluir `patch_deepar_completo_dengue.py`.
- [ ] **(medium)** `git rm --cached .epi_history.json` + `.gitignore`; excluir `CLAUDE.md`/`GEMINI.md` del árbol curado.
- [ ] **(medium)** `nbstripout` a notebooks (rutas `/Users/haowei/`); parametrizar `DASHBOARD_ROOT` en `actualiza_semanal.sh:22`; mover AWS account ID a config/env.
- [ ] **(medium)** Documentar interfaz pública de `EnsembleForecaster` y métodos clave de NBGLM/DeepAR; corregir docstring de `models/__init__.py`; docstring de módulo en `entrena.py`/`predice.py`.
- [ ] **(medium)** Regenerar `requirements.txt` (resolver xgboost/pytest fuera de constraints) y congelar lock file.
- [ ] **(low)** Fijar `.python-version` a `3.12.3`; ampliar excepciones SRP en `CLAUDE.md` o relajar la regla; actualizar conteos (47 scripts, 56 archivos, 917 tests); borrar screenshots `x/xx/xxx` y leftovers LaTeX; reemplazar logo IMSS hot-linked.

## 7. Métricas de calidad

Resultados reales ejecutados durante la auditoría (núcleo `src/epiforecast`):

- **ruff** `check .`: **0 errores** ("All checks passed!"). Sin `print()` de debug en `src` (5 prints legítimos en CLI/Rich), sin `breakpoint()/pdb`, sin `TODO/FIXME/HACK/XXX` reales, sin `except: pass`, sin ramas `if False/if True`.
- **mypy** (strict=true): **0 errores** ("Success: no issues found in 94 source files") — tipado de retorno completo en todo `src`.
- **pytest**: **914-917 tests** pasan (la dimensión calidad reporta 914 rápidos; docs cuenta 917 collected en 56 archivos), **0 fallos**, 3 deselected. Única warning: `SettingWithCopyWarning` en `tests/unit/data/test_filter.py:132` (mutación deliberada del test, no defecto de producción).
- **Cobertura**: **70% exacto** (TOTAL 5306 stmts, 1566 miss) — **al filo del gate**. Módulos nucleares por debajo: `prophet/model.py` 55%, `stacking/experts.py` 70%, `prophet/data_prep.py` 72%; glue al 0% (`utils/config.py`, `prophet_compat.py`, `web_theme.py`) y reporte/figuras bajo (`comparison_bars.py` 27%, `mlflow_logger.py` 33%).
- **SRP (límite 300 líneas)**: **15 módulos en `src` exceden** el límite (solo `deepar/model.py` 1048 está documentado como excepción): `comparison_builders.py` 728, `avance5_tables.py` 603, `avance5_charts.py` 537, `comparison_bars.py` 532, `ensemble/model.py` 391, `prophet/model.py` 338, `transformer.py` 322, `stacking/model.py` 310, etc. La deuda se concentra en visualización/reporte (periférico), no en la lógica patentable. Funciones largas hasta 240 líneas (`avance5_tables.py:364 generar_markdown`).

**Conclusión de calidad:** desde herramientas estáticas el núcleo se puede entregar con confianza (ruff/mypy/tests verdes). El punto más débil defendible es la cobertura del motor central (`prophet/model.py` al 55%) y el gate al 70% exacto; conviene reforzarlos antes de congelar el snapshot de la patente.
