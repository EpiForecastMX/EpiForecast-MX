# Ejecución nocturna — Registry de Padecimientos + Obesidad (E66)

> Bitácora viva de la ejecución autónoma. Rama: `feat/registry-padecimientos-obesidad`.
> Regla de integridad: neuro+Dengue byte-idénticos (golden verde en cada frontera);
> commits locales por épica; **sin** push/deploy/dvc-push/flip-published (gates que requieren OK del usuario).

## Estado por épica

| Épica | Estado | Notas |
|---|---|---|
| E0 — baseline+golden | ✅ DONE | catálogo canónico 432, golden per-motor (17 gates × 5 pad), 15 tests. |
| E1 — registry+migración | ⏳ EN CURSO | registry+loader+doctor+paridad golden (verde); cohorts.py migrado; gate suite completa corriendo. |
| E2 — extracción E66 | ⬜ | backfill 653 PDFs (lento, background) |
| E3 — selector unificado | ⬜ | 3 políticas, catálogo 543 |
| E4 — web data-driven | ⬜ | + green 11 tests dashboard (sin deploy) |
| E5 — Obesidad train/publish | ⬜ | training gate (compute); publish gate (OK usuario) |

## Gates que NO cruzo autónomamente (requieren tu OK en la mañana)
- `git push` a remoto · deploy web (Netlify) · `dvc push` a S3 · flip de Obesidad a `lifecycle=published`.
- Entrenamiento DeepAR concurrente / MPS (riesgo de deadlock; CLAUDE.md).

## Bitácora cronológica
- E0: catálogo canónico (432 = 333 neuro + 99 Dengue), golden freeze per-motor, 15 tests verdes. Ruff+mypy limpios.
- E1: (arrancando) registry `config/padecimientos.yaml` + `src/epiforecast/registry.py`.
