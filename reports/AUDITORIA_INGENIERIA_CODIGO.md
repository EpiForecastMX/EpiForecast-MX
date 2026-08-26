# Auditoria de Ingenieria — EpiForecast-MX

## 1. Veredicto y tablero de grados

| Dimension | Grado | Madurez / nota |
|---|---|---|
| Estructura Cookiecutter Data Science | A- | Muy fiel a CCDS; desviaciones cosmeticas (2 submodulos vacios, casing mixto en `reports/`, figuras en `notebooks/`). |
| Clean Code / SOLID | A- | Factory/Strategy/DIP real, manejo de errores ejemplar, type hints completos, ruff/mypy strict en verde. Baja por God-functions de visualizacion y una duplicacion de `smape()`. |
| Packaging y reproducibilidad | B | Wheel limpio (flit), deps con rangos disciplinados, semillas centralizadas. Sin lock file con cierre transitivo; entry point `epi` falla en instalacion no-editable. |
| Documentacion y DX | B | README y README_BUNDLE de nivel produccion. Faltan 2 de 5 model cards, doc de arquitectura stale, una referencia cruzada rota. |
| Madurez MLOps | B | Config-as-code, reproducibilidad disciplinada, seleccion productiva por serie, validacion prospectiva consciente del leakage. El bundle ampputa CI/DVC/MLflow/SageMaker. |
| Testing y gates de calidad | B | 908 tests, buena ergonomia (factory, fixtures, markers). Gate de cobertura NO enforced; motores nucleares poco cubiertos; 3 tests rojos por red. |

**Grado global ponderado: B+ (cercano a A-).** El nucleo de dominio (arquitectura de modelado, configuracion, manejo de errores, estructura del repo) es de calidad profesional y consistente con el 92% Grade A que arroja el `compliance_check.py` automatico. Lo que impide la A son tres debilidades concretas y acotables: (1) el gate de cobertura es aspiracional, no ejecutable, con la cobertura real ya en 69% por debajo del 70% declarado; (2) los dos motores mas avanzados (DeepAR, NBGLM) estan sub-documentados y sub-testeados justo en su ruta `fit`/`predict`; y (3) el bundle de patente excluye la automatizacion (CI/DVC/MLflow) y arrastra 3 tests que fallan offline por una descarga oculta de NOAA. Ninguna toca la correccion del metodo; son deudas de gobernanza y verificabilidad del entregable.

## 2. Fortalezas (lo que ya esta excelente)

- **Factory/Strategy/DIP real, no decorativo.** `factory.py:9` usa registry global + decorador `@register_model` + `create_model(name)` que levanta `ValueError` con motores disponibles (OCP cumplido). `base.py:10` define `ForecastModel(ABC)` con interfaz uniforme (`fit/predict/cross_validate/save/load/get_params/run`) implementada por los 5 motores (LSP). CLAUDE.md exige "no importar clases de modelos directamente; usar `create_model`" y el codigo lo respeta.
- **Manejo de errores ejemplar.** Los 5 `except` amplios del paquete llevan `noqa: BLE001` con comentario del porque, loguean y tienen fallback determinista (`deepar/model.py:948`, `stacking/meta_learner.py:87`, `base.py:108`). Cero `except: pass` a ciegas; `merger.py` re-lanza con `typer.Exit(1)`.
- **Cohort helpers centralizan literales.** `utils/cohorts.py` expone `is_neuro()`, `is_count_log_cohort()` y `filter_neuro()`, eliminando el `df.isin(NEURO_CONDITIONS)` repetido y divergente en bordes (None, columna ausente, df vacio).
- **Reproducibilidad disciplinada.** `RANDOM_SEED=42` en `constants.py:6` propagado a numpy/torch/sklearn en los 5 motores (`ensemble/model.py:127`, `deepar/model.py:487-488`, `prophet/cross_validator.py:161`, `stacking/experts.py:29`); `scripts/entrena.py:31` fija `PYTHONHASHSEED` antes de importar; `requirements.txt` con versiones exactas.
- **Configuracion como codigo madura.** OmegaConf con interpolacion de rutas (`config/base.yaml:31` `./models/${modelo_activo}`); 6 directorios de config parametrizan el metodo sin tocar codigo.
- **Type hints completos y verificados.** 0 defs de una linea sin retorno tipado; `mypy strict=true`; `ruff check` en verde (0 hallazgos); overrides de mypy acotados y comentados (stubs matplotlib/pandas), no globales.
- **Suite de tests amplia y bien organizada.** 908 tests en estructura `unit/` (sub-paquetes models/data/evaluation/visualization/utils/features) + `integration/`; `conftest.py` raiz resuelve elegantemente el `sys.exit(1)` de `config.py` con modulo mock + `setdefault`; markers con `--strict-markers` correctamente aplicados a los e2e.
- **Validacion prospectiva OOS consciente del leakage.** `pronostico_congelado.py` congela la cola futura (`ds > corte` = no vista) y la confronta contra boletines posteriores; su docstring reconoce abiertamente que `smape_real_2026` es in-sample y referencia `DENGUE_AUDITORIA_LEAKAGE.md`. Honestidad MLOps poco comun.
- **Seleccion de modelo productivo por serie como codigo versionado y auditable.** `reselect_motor_2026.py` (SMAPE 2026 real + MASE desempate), `produccion_dengue.py` (banda de empate 5% -> MAE), `genera_tabla_produccion.py` (base CV de los 333).
- **Estructura CCDS fiel y limpia.** `data/` con `raw -> interim -> processed + external/`; 6 notebooks en convencion `#.#-jar-desc`; submodulos `src/` cohesivos; `config/` jerarquizado; Makefile como interfaz unica (~72 targets); README con arbol ASCII anotado. Artefactos de entrenamiento (`checkpoints/`, `lightning_logs/`, `mlruns/`) todos gitignored.
- **SRP por extraccion aplicado correctamente.** `ensemble/helpers.py`, `stacking/experts.py` + `meta_learner.py`, `prophet/data_prep.py`, `visualization/comparison_html.py` + `comparison_css.py` + `chart_renderer.py` separan responsabilidades.

## 3. Hallazgos por severidad

| Severidad | Dimension | Hallazgo | Ubicacion | Accion |
|---|---|---|---|---|
| high | MLOps | CI/CD ausente del bundle: el quality gate descrito en README no viaja ni esta declarado como exclusion en README_BUNDLE §2 (omision no documentada). | `.github/workflows/` (ausente); `README.md:194-195,595-597` | Incluir `ci.yml` o listar `.github/` en exclusiones de README_BUNDLE y notar que el gate es reproducible via `make quality`. Reconciliar conteo "907 vs 915 tests / 55 vs 56 archivos". |
| high | Testing | Gate de cobertura NO enforced: no existe `--cov-fail-under` en ninguna parte; cobertura real medida 69%, ya bajo el 70% declarado. | `pyproject.toml:187-188,216-218`; `Makefile:408-420`; `.pre-commit-config.yaml` | Anadir `fail_under = 70` en `[tool.coverage.report]` (o `--cov-fail-under=70` en addopts). Luego subir cobertura o ajustar el claim a 69%. |
| high | Testing | DeepAR (motor productivo) con ruta `fit`/`predict` casi sin cubrir (21%); ningun test, ni slow/integration, la ejercita. | `deepar/model.py` (395/500 stmts sin cubrir); `cross_validator.py` 26% | Anadir un smoke test slow/integration: entrenar serie sintetica corta (epochs=1), validar forma, no-negatividad, horizonte y roundtrip save/load. |
| high | Testing | Logica de seleccion de motor neuro (`reselect_motor_2026`, Reglas 1/2/3 sobre 333 series) sin test propio; contraste con Dengue que si tiene 7 tests. | `scripts/reselect_motor_2026.py:96 reselect`, `:114 _pick_row`, `:67 smape_per_motor` | Espejar `test_produccion_dengue.py`: un test por rama (real-fuerte -> SMAPE; ruidosa -> Ensemble; pocas-sem -> respeta CV; empate -> MASE). |
| high | Testing | 3 tests NBGLM fallan offline por dependencia de red oculta (descarga ONI de NOAA); colapsan a fallback constante. | `tests/unit/test_nbglm.py:103,121,136`; raiz `data/enso.py:48 _ensure_oni` | Mockear `load_oni_weekly`/`_ensure_oni` en conftest o enviar fixture `oni.ascii.txt`; opcional `pytest-socket` para fallar ante red inesperada. |
| high | Docs | Faltan model cards de DeepAR y NBGLM (solo 3 de 5 motores documentados); justo los dos mas avanzados. | `docs/model_cards/` (sin `deepar.md`, `nbglm.md`) | Crear ambas con el esquema existente; NBGLM con regresor ONI/ENSO + backtest leave-one-epidemic-out; DeepAR con `short_series`, CUDA/MPS y StudentT. |
| high | Docs | `INFORME_ARQUITECTURA_MULTIMODELO.md` severamente stale: titulo "Prophet + DeepAR", fecha 2026-02-27, DeepAR descrito como "simulacion", Ensemble como trabajo futuro; unico doc de arquitectura del bundle. | `docs/research/INFORME_ARQUITECTURA_MULTIMODELO.md` | Reescribir a 5 motores reales y eliminar mock/Fase 3, o marcar como "documento historico — ver README §Architecture". |
| medium | MLOps | Targets de Makefile cuelgan sobre archivos ausentes (`aws/`, dvc): rotos desde un clon limpio del bundle. | `Makefile:258-285` (train-sagemaker*), `:441-449` (data-pull/push) | Comentar/eliminar targets que dependen de `aws/`+dvc, o documentar cuales son no-operativos por exclusion. |
| medium | MLOps | Sin model registry formal ni store de experimentos persistido: el tracking no deja rastro en el bundle (`_MODEL_REGISTRY` es dict en memoria; `mlruns/` ausente). | `factory.py:9`; `utils/mlflow_logger.py`; `mlruns/` (ausente) | Adoptar MLflow Model Registry (stages) o versionar `tabla_333`/`auditoria` como artefacto de registro; documentar que `mlruns/` es regenerable. |
| medium | Cleancode | God-function de visualizacion `build_small_multiples` (214 lineas, 18 ramas); complejidad ciclomatica real. | `visualization/comparison_builders.py` (modulo 728 lineas) | Extraer `_render_panel(ax, serie, motor)` y separar layout de grilla; partir el modulo en builders overlay/small-multiples/metrics-bars. |
| medium | Cleancode | 4 modulos de visualizacion siguen >300 lineas pese a estar "extraidos" y NO estan en la lista de excepciones. | `comparison_builders.py:728`, `avance5_tables.py:603`, `avance5_charts.py:537`, `comparison_bars.py:532` | Partir por responsabilidad o documentar la excepcion en `pyproject.toml`/CLAUDE.md como se hizo con `deepar/model.py`. |
| medium | Cleancode | DRY: dos `smape()` que difieren solo en el caso borde (0.0 vs NaN en todo-cero), misma matematica en el mismo subpaquete. | `evaluation/metrics.py:39` vs `evaluation/real_eval.py:31` | Unificar: `real_eval` importa `metrics.smape`; parametrizar `empty_value=float('nan')` si se necesita esa semantica. |
| medium | Packaging | `requirements.txt` diverge/omite deps de pyproject (no incluye joblib, tqdm, geopandas, pdfplumber; criticos para paralelismo Prophet y extraccion). | `requirements.txt` vs `pyproject.toml:24-52` | `requirements.txt` debe ser superconjunto pinado de las deps directas, o renombrar a `requirements-core.txt` y documentar que la instalacion canonica es `pip install -e ".[dev]"`. |
| medium | Packaging | Entry point `epi` falla en instalacion no-editable: `cli.main()` busca `repo/epi.py` por filesystem, que flit no empaqueta. | `src/epiforecast/cli.py:18-23` | Mover `epi.py` a `epiforecast/console/__main__.py` e invocar via import; minimo, documentar que `epi` requiere instalacion editable. |
| medium | Testing | Prophet `model.py` (motor_ganador global neuro, 126 series) al 55%; la ruta `run()`/`predict` solo la toca el e2e deseleccionado. | `prophet/model.py` (259-327, 138-166); `data_prep.py` 72% | Test unit de `run()`/`predict` sobre serie sintetica: caso suficiente, insuficiente (`umbral_minimo_semanal`), e integridad del forecast. |
| medium | Docs | Referencia cruzada rota: README_BUNDLE apunta a `reports/AUDITORIA_PATENTE_CODIGO.md`, ausente en el bundle. | `README_BUNDLE.md:147` (y §2 lo lista como excepcion que entra) | Incluir el archivo (es liviano y es la evidencia que el README invoca) o corregir la referencia y la §2. |
| medium | Docs | Cobertura de docstrings debil en scripts entry-point (56%): 10 scripts core sin docstring de modulo + metodos override de ensemble/nbglm sin documentar. | `scripts/*.py`; `models/{ensemble,nbglm}/model.py` | Docstring de modulo a los 10 scripts core + docstrings a los overrides de `ForecastModel`; sube el API publico a >85%. |
| low | Cookiecutter | Dos submodulos del paquete vacios (placeholder muerto) anunciados en el README. | `data/loaders/__init__.py` (0 bytes); `pipelines/__init__.py` | Eliminar o poblar; sincronizar el arbol del README. |
| low | Cookiecutter | Casing inconsistente / Spanish CamelCase en subdirectorios de `reports/`. | `reports/{FigCanva,HTMLsCanva,ConclusionesClave,RuthPoster,ProdDetails,Latex}` | Normalizar a snake_case lowercase para consistencia CCDS. |
| low | Cookiecutter | Figuras/binarios dentro de `notebooks/` en vez de `reports/figures/`. | `notebooks/figuras_avance5/`, `*.zip` (tracked) | Mover PNGs a `reports/figures/ModeloFinal/` y no versionar `.zip`. |
| low | MLOps / Docs | Model cards de gobernanza al 60%; deteccion de drift manual (depende de operador). | `docs/model_cards/`; `pronostico_congelado.py` | Codificar criterio de drift (OOS/in-sample > 2x -> alerta) como check automatizado disparable desde el workflow de boletines. |
| low | Cleancode | `generar_markdown`: 240 lineas en una funcion (legibilidad/SRP, complejidad baja, mayormente plantilla f-string). | `avance5_tables.py:364` | Mover prosa a plantilla externa (`scripts/templates/`) como ya hace `reporte_resultados.tmpl.html`. |
| low | Testing | Modulos a 0% que aun cuentan: `xgb_tuner.py` (111 stmts, busqueda HP del Ensemble productivo) y `prophet_compat.py`. | `ensemble/xgb_tuner.py`, `prophet/prophet_compat.py` | Test minimo (1-2 trials) que valide params validos + smoke de la capa de compatibilidad. |
| low | Packaging | Sin `.gitignore` propio en el bundle (hereda el del repo raiz). | `dist/patent_bundle/` | Copiar subconjunto relevante (`.env`, `.venv`, `*.pkl`, `data/`) para que el bundle sea autocontenido. |

Hallazgos rebajados/descartados en verificacion adversarial: la exclusion de DVC del bundle es una decision de alcance **documentada y justificada** (datos clinicos confidenciales; README_BUNDLE §2 y caveat en :137), no un defecto — rebajada a low/info. La ausencia de lock file se rebaja a medium: las deps directas si estan pinadas exactas y el build no se rompe; para una patente el sujeto protegido es el metodo, no la salida numerica byte-identica.

## 4. Madurez MLOps

**Nivel 2-3 en el repo vivo; Nivel 2 efectivo en el bundle entregado.**

Justificacion: el proyecto exhibe practicas de nivel 3 en su forma completa — configuracion como codigo con OmegaConf e interpolacion, reproducibilidad disciplinada (semilla central + `PYTHONHASHSEED` + pins exactos), MLflow logger tolerante a fallos (no-op si no esta instalado, traga excepciones para no tumbar el lote de 333 modelos en workers loky), orquestacion con ~72 targets de Makefile, seleccion automatica de motor productivo por serie y, notablemente, **validacion prospectiva OOS que reconoce explicitamente el leakage in-sample de su propia metrica de seleccion**. Esa autoconciencia del leakage es nivel 3+ y poco habitual.

Sin embargo, el bundle de patente ampputa CI/CD (`.github`), DVC (`.dvc`), `mlruns/` y `aws/`, degradando la madurez **efectiva del entregable** a ~nivel 2: sin esos artefactos no hay gate de calidad ejecutable, ni datos/modelos versionados recuperables, ni historial de experimentos, y ~6 targets del Makefile cuelgan sobre archivos ausentes. Para una patente la integridad conceptual del metodo se preserva; la afirmacion "buildable from clean clone" es parcial.

Huecos para subir de nivel:
- **A nivel 3 pleno (entregable):** incluir `ci.yml` o declararlo como exclusion explicita; reconciliar Makefile con lo que viaja; gate de cobertura autonomo (`fail_under=70`).
- **A nivel 4:** lock file con cierre transitivo (`requirements.lock` / `uv.lock`, idealmente con hashes); MLflow Model Registry con stages Staging/Production o versionar `tabla_333`/`auditoria_motores_2026` como artefacto de registro reproducible; **deteccion de drift automatizada** (codificar OOS/in-sample > 2x -> alerta y disparar desde el workflow de boletines, en vez de prosa en CLAUDE.md + ejecucion manual).

## 5. Cumplimiento Cookiecutter Data Science

**Grado A-.** El repo es muy fiel al estandar CCDS.

Cumple:
- `data/` por etapas `raw -> interim -> processed` + `external/` (4 etapas; CCDS pide 3), cada una versionada con DVC.
- `src/epiforecast/` con submodulos cohesivos que mapean al estandar (`data`, `features`, `models`, `evaluation`, `visualization`, `utils`) mas extensiones razonables (`pipelines`, `infrastructure`); `models/` con subpaquetes limpios por algoritmo.
- 6 notebooks productivos en convencion exacta `#.#-iniciales-desc` (`0.1-jar-pdf-data-extraction.ipynb` ... `5.0-jar-ensemble-final-model.ipynb`); borradores no tracked.
- 0 archivos `.py` no-snake_case en `src/` ni `scripts/`.
- `config/` centralizado y jerarquizado; Makefile como interfaz unica; README con seccion "Project Structure" (arbol ASCII anotado).
- `reports/figures/` separa figuras de outputs tabulares; `references/` con bibliografia. El bundle de patente preserva el esqueleto canonico y omite a proposito `data/`/`notebooks/`/`models/`.

Se desvia (cosmetico):
- Dos submodulos vacios (`data/loaders/`, `pipelines/`) anunciados en el README pero sin codigo.
- Casing mixto / Spanish CamelCase en ~6 subdirectorios de `reports/` (CCDS prefiere minusculas).
- Figuras y `.zip` binarios dentro de `notebooks/` en vez de `reports/figures/`.
- `requirements.txt` + `pyproject.toml` coexisten (documentado como derivado, no bug).

## 6. Checklist de remediacion priorizado

Prioridad alta (cierra los hallazgos high; mayormente quick-wins):
- [ ] Anadir `fail_under = 70` en `[tool.coverage.report]` para que el gate de cobertura sea autonomo (quick-win). Luego elevar cobertura o ajustar el claim a 69%.
- [ ] Hacer herméticos los 3 tests NBGLM: mockear `enso/load_oni_weekly` en conftest o enviar fixture `oni.ascii.txt`; opcional `pytest-socket` (quick-win).
- [ ] Crear `test_reselect_motor_2026.py` espejando `test_produccion_dengue.py`, un test por Regla 1/2/3 + desempate MASE (quick-win; funciones puras sobre `pd.Series`).
- [ ] Anadir smoke test slow/integration de `DeepARForecaster.fit()/predict()` sobre serie sintetica corta + roundtrip save/load (mayor; requiere fixture y tiempo de entrenamiento).
- [ ] Crear `docs/model_cards/deepar.md` y `nbglm.md` con el esquema existente (quick-win, alto valor para la patente).
- [ ] Reescribir o marcar como historico `INFORME_ARQUITECTURA_MULTIMODELO.md` (5 motores reales, DeepAR no-mock) (quick-win).
- [ ] Resolver CI en el bundle: incluir `ci.yml` o listar `.github/` en exclusiones de README_BUNDLE §2 + nota de que el gate se reproduce con `make quality`. Reconciliar conteo 907/915 tests (quick-win).

Prioridad media:
- [ ] Test unit de `ProphetForecaster.run()/predict` (caso suficiente / insuficiente / integridad) (mayor).
- [ ] Comentar/eliminar o documentar como no-operativos los targets de Makefile sobre `aws/`+dvc (quick-win).
- [ ] Reconciliar `requirements.txt`: superconjunto pinado de deps directas (incluir joblib/tqdm/geopandas/pdfplumber) o renombrar a `requirements-core.txt` (quick-win).
- [ ] Arreglar entry point `epi` para instalacion no-editable (mover consola a `epiforecast/console/__main__.py`) o documentar que requiere `-e` (mayor / quick-win segun opcion).
- [ ] Unificar `smape()`: `real_eval` importa `metrics.smape` con `empty_value` parametrizable (quick-win).
- [ ] Refactor `build_small_multiples` (extraer `_render_panel`) y partir `comparison_builders.py` (mayor).
- [ ] Documentar la excepcion de los 4 modulos viz >300 lineas en `pyproject.toml`/CLAUDE.md, o partirlos (quick-win si se documenta).
- [ ] Incluir `reports/AUDITORIA_PATENTE_CODIGO.md` en el bundle o corregir la referencia en README_BUNDLE:147 (quick-win).
- [ ] Anadir docstring de modulo a los 10 scripts core + docstrings a overrides de ensemble/nbglm (quick-win).

Prioridad baja:
- [ ] Generar lock file (`pip freeze > requirements.lock` o `uv pip compile`, idealmente `--generate-hashes`) y documentar el camino de reproduccion exacta (quick-win).
- [ ] Eliminar o poblar los submodulos vacios `data/loaders/` y `pipelines/`; sincronizar el README (quick-win).
- [ ] Normalizar casing de subdirectorios de `reports/` a snake_case lowercase (quick-win; cuidado con paths referenciados en codigo).
- [ ] Mover figuras de `notebooks/` a `reports/figures/ModeloFinal/`; dejar de versionar `.zip` (quick-win).
- [ ] Codificar criterio de drift (OOS/in-sample > 2x -> alerta) como check automatizado (mayor).
- [ ] Test minimo de `xgb_tuner.py` (1-2 trials) y smoke de `prophet_compat.py` (quick-win).
- [ ] Copiar `.gitignore` relevante dentro del bundle; anadir `[project.urls]` a `pyproject.toml`; CONTRIBUTING.md minimo con "Adding a new engine" (quick-wins).

Nota de completitud: las 6 dimensiones se auditaron y verificaron de forma adversarial. Las verificaciones independientes confirmaron los hallazgos high de testing y docs, y rebajaron dos hallazgos de MLOps/packaging (exclusion DVC y ausencia de lock file) por ser decisiones de alcance documentadas y justificadas para un entregable de patente. Este reporte respeta esos veredictos.
