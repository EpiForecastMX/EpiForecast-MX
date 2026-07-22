# Ejecución nocturna — Registry de Padecimientos + Obesidad (E66)

> Bitácora viva de la ejecución autónoma. Rama: `feat/registry-padecimientos-obesidad`.
> Regla de integridad: neuro+Dengue byte-idénticos (golden verde en cada frontera);
> commits locales por épica; **sin** push/deploy/dvc-push/flip-published (gates que requieren OK del usuario).

## Estado por épica

| Épica | Estado | Notas |
|---|---|---|
| E0 — baseline+golden | ✅ DONE | catálogo canónico 432, golden per-motor (17 gates × 5 pad), 15 tests. Commit c3784ddf. |
| E1 — registry+migración | ✅ DONE | registry+loader+doctor (config-only verde todos); cohorts.py + 3 gates divergentes migrados a trait_or; **suite 970 verde = byte-idéntico**. Commits 960379db, 6eac84ae. |
| E2 — extracción E66 | ⏳ backfill corriendo | extractor genérico validado en 6 muestras; backfill 654 PDFs (~99% ok); merge/validate pendiente. Commit ccbfb557. |
| E3 — selector unificado | ⬜ bloqueado parcial | legacy_neuro/dengue reproducibles; rolling_cv_v1 de Obesidad necesita forecasts (training). |
| E4 — web data-driven | ⬜ | manifiesto `padecimientos` (Python) testeable sin deploy; JS refactor + 11 tests = gate de deploy. |
| E5 — Obesidad train/publish | ⬜ gate compute | registrado (configured, invisible); training DeepAR (horas) + publish = gates. |

**Commits en la rama** (revisar por diff): E0 → E1 registry → E1 gates → E2 extracción.

## Gates que NO cruzo autónomamente (requieren tu OK en la mañana)
- `git push` a remoto · deploy web (Netlify) · `dvc push` a S3 · flip de Obesidad a `lifecycle=published`.
- Entrenamiento DeepAR concurrente / MPS (riesgo de deadlock; CLAUDE.md).

## RESUMEN EJECUTIVO (leer esto primero)

Se completó el **núcleo del refactor "sin hard-codes"** (EPIC 0-1-2) y se **probó end-to-end** que
un padecimiento nuevo (Obesidad E66) fluye por todo el pipeline con solo 1 entrada de registry +
1 grupo de cuadro. **Neuro + Dengue quedan byte-idénticos** (suite 970 verde en cada frontera).

### Qué está HECHO y commiteado (5 commits, hooks verdes)
- **EPIC 0** (c3784ddf): catálogo canónico 432 (corrige el 435/102 inflado) + golden freeze per-motor.
- **EPIC 1** (960379db, 6eac84ae, 38ddfc57): registry central + `cohorts.py` + 3 gates divergentes +
  `_GRID_KEY_MAP` migrados. Doctor + completeness. Obesidad registrada (lifecycle=configured, invisible).
- **EPIC 2** (ccbfb557): extractor genérico por grupo de cuadro. **Backfill E66: 653/654 PDFs, 20,896
  filas, layouts 53/600, 1 NA Casos_semana (Querétaro 2016_sem50), 1696 NA año-anterior, 0 dups,
  32 estados/boletín** — coincide EXACTO con el contrato. Merge idempotente (neuro+Dengue byte-idéntico
  por hash).
- **EPIC 5 (prueba de abstracción)**: Obesidad extraída→merge→prep→**Prophet 15 modelos**→predict
  (10,545 filas de forecast, gráficos). El pipeline completo funciona para un padecimiento nuevo.

### Estado del working tree (NO commiteado — artefactos DVC/locales)
- `data/processed/dataset_boletin_epidemiologico.csv`: **Obesidad mergeada** (75456→96352 filas).
  Diverge del puntero DVC. Para persistir: `dvc add ...` + `dvc push` (GATE). Para revertir: `dvc checkout`.
- `models/prophet/Obesidad/`: **15 pkl** entrenados (DVC-tracked dir).
- `data/interim/obesidad_*.csv`, `data/processed/data_{raw,prepare,inegi}_Obesidad.csv`,
  `reports/forecasts/prophet/Obesidad/`, `reports/ProdDetails/catalogo_canonico.*`: locales/gitignored.

### Qué FALTA y por qué (gates que requieren tu OK / compute)
- **EPIC 5 full**: entrenar DeepAR + Ensemble + Stacking de Obesidad (DeepAR = horas, MPS deshabilitado,
  sin concurrencia). Comando: `make train ARGS="padecimiento.tipo='Obesidad' modelo_activo=<motor>"` por motor.
- **EPIC 3 selector**: `produccion_padecimiento.py` con 3 políticas (legacy_neuro/legacy_dengue/rolling_cv_v1).
  El rolling_cv_v1 de Obesidad necesita los forecasts de los 4 motores (bloqueado por lo anterior).
- **EPIC 4 web**: manifiesto `padecimientos` en `knowledge.json` + refactor JS (kb/app/entities) +
  green de 11 tests del dashboard + cache-bust por hash. NO se tocó (es gate de deploy; findings de los
  11 tests en `scratchpad/dashboard_11_fallos_findings.md`).
- **Publicación**: flip de Obesidad a `lifecycle=published` = gate (solo tras 4 motores + selección +
  revisión visual, dentro del commit de deploy). `git push` / deploy web / `dvc push` = gates.

### Cómo continuar (orden sugerido cuando des el OK)
1. `make train ARGS="padecimiento.tipo='Obesidad' modelo_activo=deepar"` (y ensemble, stacking).
2. `predice` para los 4 motores → construir selector `rolling_cv_v1` (EPIC 3).
3. EPIC 4 web (manifiesto + JS) — ver diseño en el plan.
4. `dvc add/push` de consolidado + modelos; flip a published dentro del commit de deploy.

### Verificación reproducible (cualquiera de estos):
- `make test-fast` → 970 passed (byte-idéntico neuro+Dengue).
- `.venv/bin/python -m scripts.doctor_padecimiento --config-only` → todos completos.
- `.venv/bin/python -m scripts.build_catalogo_canonico` → 432 (neuro 333 + Dengue 99).

---

## Bitácora cronológica
- E0: catálogo canónico (432 = 333 neuro + 99 Dengue), golden freeze per-motor, 15 tests verdes.
- E1: registry + cohorts.py + gates (log/short_series/fallback) + tuner migrados a registry; suite 970 verde.
- E2: extractor genérico + backfill E66 (653/20896, contrato exacto) + merge idempotente (no-Obesidad intacto).
- E5 (prueba): Obesidad prep + Prophet train (15 modelos) + predict (10,545 forecasts). Abstracción demostrada.
