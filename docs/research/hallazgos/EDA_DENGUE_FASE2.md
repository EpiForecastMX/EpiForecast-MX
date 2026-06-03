# EDA — Dengue (Fase 2, antes del entrenamiento)

**Fecha:** 2026-06-03 · **Serie:** `data/interim/dengue_boletin.csv` (10,240 filas, 32 entidades, 2020-2026, 320 semanas-país). Dengue confirmado agregado (A97.0+A97.1+A97.2).

## Visión general
- Total de casos: **235,596** · media semanal por entidad: 23.0 · máximo semanal estatal: **1,907** · **44.3 % de ceros**.

## Años epidémicos (variación inter-anual fuerte)
| Año | Casos |
|---|---|
| 2020 | 14,966 |
| 2021 | 6,752 |
| 2022 | 12,650 |
| 2023 | 54,422 |
| **2024** | **122,752** (pico epidémico) |
| 2025 | 21,910 |
| 2026 (parcial, W1-20) | 2,144 |

Ciclo epidémico marcado (2024 ≈ 18× el mínimo 2021). El modelo debe capturar magnitud variable año a año, no solo el ciclo anual.

## Estacionalidad (muy fuerte)
- **84 % de los casos en semanas 27-52** (segundo semestre, temporada de lluvias).
- Semana pico promedio **W43**; valle en W53/W1. Ratio pico/valle enorme.
- → Estacionalidad anual dominante; coherente con estacionalidad **multiplicativa** (la amplitud crece con el nivel).

## Autocorrelación (clave de predictibilidad)
- **ACF lag-1 = 0.964** (autocorrelación de corto plazo altísima), lag-4 = 0.840, lag-52 = 0.363.
- Confirma empíricamente la decisión de Fase 1: **la capacidad predictiva viene de la propia serie agregada** (no de covariables). Serie altamente pronosticable.

## Heterogeneidad geográfica
- **2 estados SIN dengue (100 % ceros, total 0): Ciudad de México y Tlaxcala** → NO deben tener modelo propio (serie nula); el fallback regional / nacional los cubre.
- Casi-cero (~90 % ceros): Chihuahua, Zacatecas, Baja California, Durango → candidatos a fallback regional.
- Señal fuerte (tropicales/costeros): Veracruz (media 80.5), Guerrero, Michoacán, Chiapas, Sinaloa, Oaxaca.
- **29/32 estados** superan el umbral de 0.5 casos/sem del pipeline; ~3 caerían a fallback regional (consistente con la lógica híbrida existente).

## Implicaciones directas para Feature Engineering / config (Fase 2)
1. **Outliers: DESACTIVAR para Dengue.** El tratamiento actual (zscore>3 → reemplazo por mediana, por Padecimiento+Entidad) **medianizaría 289 semanas-estado** que son **picos epidémicos reales** = la señal a pronosticar. Crítico.
2. **Régimen COVID: quitar** el holiday de 913 días y `cv_weights` desiguales para Dengue (2020-2022 no fue disrupción; 2020 incluso tuvo 14,966 casos).
3. **Estacionalidad multiplicativa** + changepoints más flexibles (arranques epidémicos abruptos). `log_transform` a evaluar (comprime picos).
4. **2 estados nulos** (CDMX, Tlaxcala): excluir de modelos propios o dejar que el fallback los maneje; verificar que no generen artefactos.
5. La serie es corta para el ciclo inter-anual (solo ~2 ciclos epidémicos en 2020-2026); gestionar expectativas de pronóstico de la *magnitud* del próximo brote (el ciclo anual sí es robusto).
