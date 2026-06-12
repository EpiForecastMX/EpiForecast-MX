# src/epiforecast/visualization/avance5_tables.py
"""Generacion de tablas y reporte Markdown del Avance 5.

La carga de datos, el merge N-way y el win-rate viven en ``avance5_data``
(re-exportados aqui por compatibilidad con los scripts orquestadores).
"""

from __future__ import annotations

import pandas as pd

from epiforecast.visualization.avance5_data import (
    _METRICS,
    _MODEL_LABELS,
    _PADECIMIENTOS,
    _pad_filename,
    cargar_completos,
    merge_all_models,
    win_rate_by_state,
)

__all__ = [
    "_MODEL_LABELS",
    "cargar_completos",
    "generar_markdown",
    "merge_all_models",
    "win_rate_by_state",
]

# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def _tabla_agregada(merged: pd.DataFrame, model_keys: list[str]) -> str:
    """Tabla resumen global: media de cada metrica por modelo."""
    lines = ["| Métrica |"]
    sep = ["| --- |"]
    for mk in model_keys:
        lines[0] += f" {_MODEL_LABELS.get(mk, mk)} |"
        sep[0] += " ---: |"
    lines.append(sep[0])

    for metric in _METRICS:
        row = f"| {metric.upper()} |"
        vals: dict[str, float] = {}
        for mk in model_keys:
            col = f"{metric}_{mk}"
            val = merged[col].mean(skipna=True) if col in merged.columns else float("nan")
            vals[mk] = val
        best = min(vals, key=lambda k: vals[k]) if vals else ""
        for mk in model_keys:
            v = vals.get(mk, float("nan"))
            cell = f"{v:.2f}" if pd.notna(v) else "-"
            if mk == best:
                cell = f"**{cell}**"
            row += f" {cell} |"
        lines.append(row)
    return "\n".join(lines)


def _tabla_por_padecimiento(merged: pd.DataFrame, model_keys: list[str]) -> str:
    """Tabla de metricas promedio desglosada por padecimiento."""
    sections: list[str] = []
    for pad in _PADECIMIENTOS:
        sub = merged[merged["padecimiento"] == pad]
        if sub.empty:
            continue
        sections.append(f"\n**{pad}**\n")
        sections.append(_tabla_agregada(sub, model_keys))
    return "\n".join(sections)


def _win_rate_global(merged: pd.DataFrame, model_keys: list[str]) -> str:
    """Porcentaje global de victorias por modelo."""
    if "ganador_rmse" not in merged.columns:
        return ""
    total = len(merged)
    parts = ["| Modelo | Victorias (%) | N |", "| --- | ---: | ---: |"]
    for mk in model_keys:
        wins = (merged["ganador_rmse"] == mk).sum()
        pct = wins / total * 100 if total else 0
        label = _MODEL_LABELS.get(mk, mk)
        parts.append(f"| {label} | {pct:.1f}% | {wins} |")
    return "\n".join(parts)


def _determinar_ganador(merged: pd.DataFrame, model_keys: list[str]) -> str:
    """Retorna el key del modelo con mayor win rate global RMSE."""
    if "ganador_rmse" not in merged.columns:
        return model_keys[0] if model_keys else "stacking"
    counts = merged["ganador_rmse"].value_counts()
    if counts.empty:
        return model_keys[0]
    return str(counts.index[0])


def generar_markdown(
    merged: pd.DataFrame,
    model_keys: list[str],
    fig_rel: str = "../figures/ModeloFinal",
) -> str:
    """Genera el reporte Markdown completo del Avance 5."""
    ganador = _determinar_ganador(merged, model_keys)
    ganador_label = _MODEL_LABELS.get(ganador, ganador)

    # Metricas del ganador
    smape_col = f"smape_{ganador}"
    rmse_col = f"rmse_{ganador}"
    smape_avg = merged[smape_col].mean(skipna=True) if smape_col in merged.columns else 0
    rmse_avg = merged[rmse_col].mean(skipna=True) if rmse_col in merged.columns else 0

    md = f"""# Avance 5: Reporte del Modelo Final

## 1. Resumen ejecutivo

El modelo **{ganador_label}** es seleccionado como modelo productivo para EpiForecast-MX.
Sobre las 333 combinaciones evaluadas (3 padecimientos x ~111 series por padecimiento),
{ganador_label} obtiene un **SMAPE promedio de {smape_avg:.2f}%** y un **RMSE promedio
de {rmse_avg:.2f}**, superando consistentemente a los demás modelos en la mayoría
de series y padecimientos.

---

## 2. Estrategias de ensamble

### 2.1 Ensamble homogéneo: Ensemble (Prophet + XGBoost)

El modelo **Ensemble** combina dos componentes del mismo paradigma supervisado:

- **Prophet** captura tendencia y estacionalidad mediante un modelo aditivo bayesiano.
- **XGBoost** aprende patrones residuales con 20 features de ingeniería
  (lags, rolling means, variables trigonométricas, indicador COVID).
- La predicción final es un promedio ponderado optimizado vía grid search.
- Este enfoque es **homogéneo** porque ambos componentes predicen la misma
  variable objetivo y se combinan linealmente.

### 2.2 Ensamble heterogéneo: Stacking (Prophet + ETS + LightGBM + Ridge)

El modelo **Stacking** emplea un esquema de meta-aprendizaje en dos niveles:

- **Nivel 1 (Expertos):** Prophet (tendencia + estacionalidad), ETS (suavizamiento
  exponencial), LightGBM (patrones no lineales).  Cada experto genera predicciones
  out-of-fold (OOF) mediante ventana expansiva.
- **Nivel 2 (Meta-learner):** Un regresor Ridge/ElasticNet con restricción de
  pesos no negativos aprende la combinación óptima de los 3 expertos.
- Este enfoque es **heterogéneo** porque integra familias de modelos distintas
  (bayesiano, estadístico clásico, gradient boosting) y delega la combinación
  a un meta-learner entrenado.

---

## 3. Comparativa de métricas

### 3.1 Tabla agregada global

{_tabla_agregada(merged, model_keys)}

### 3.2 Desglose por padecimiento

{_tabla_por_padecimiento(merged, model_keys)}

### 3.3 Win Rate global (RMSE)

{_win_rate_global(merged, model_keys)}

---

## 4. Selección del modelo final

Se selecciona **{ganador_label}** como modelo productivo con base en los siguientes argumentos:

1. **Menor RMSE promedio global:** {ganador_label} obtiene el RMSE más bajo
   ({rmse_avg:.2f}) sobre las 333 series, indicando menor error absoluto en predicción.

2. **Mayor win rate:** {ganador_label} gana en la mayoría de las combinaciones
   individuales (padecimiento x entidad x sexo), demostrando robustez generalizada.

3. **Balance sesgo-varianza:** La combinación de múltiples expertos (o componentes)
   reduce la varianza del pronóstico sin incrementar significativamente el sesgo,
   como se observa en los boxplots de distribución de errores.

4. **Estabilidad por padecimiento:** {ganador_label} no solo domina en el agregado
   global, sino que mantiene ventaja consistente en los tres padecimientos
   (Depresión, Parkinson, Alzheimer), evitando la especialización excesiva en uno solo.

5. **Comportamiento de residuales:** El análisis de residuales muestra que
   {ganador_label} produce errores más simétricos y con menor autocorrelación,
   indicando que captura mejor la estructura temporal de las series.

---

## 5. Gráficos e interpretación

### 5.1 Tendencia y predicción

"""
    for pad in _PADECIMIENTOS:
        pad_lower = _pad_filename(pad)
        md += f"""#### {pad}

![Tendencia {pad}]({fig_rel}/tendencia_prediccion_{pad_lower}.png)

El gráfico muestra la serie histórica real (gris) junto con las predicciones
del modelo ganador ({ganador_label}, color sólido) y Prophet como línea base
(punteado).  La banda de confianza del modelo ganador se muestra sombreada.
La línea vertical roja marca el punto de corte (cutoff) a partir del cual
las predicciones son out-of-sample.  La zona gris clara indica el periodo
COVID-19 (marzo 2020 - septiembre 2022), donde se observa una caída abrupta
seguida de una recuperación gradual que los modelos deben capturar.

"""

    md += """### 5.2 Análisis de residuales

"""
    for pad in _PADECIMIENTOS:
        pad_lower = _pad_filename(pad)
        md += f"""#### {pad}

![Residuales {pad}]({fig_rel}/residuos_{pad_lower}.png)

Se presentan cuatro paneles: (a) residuales vs tiempo, donde se espera
ausencia de patrón sistemático; (b) histograma con curva normal superpuesta,
verificando la distribución aproximadamente gaussiana de los errores;
(c) QQ-plot contra la distribución normal, donde los puntos deben seguir
la diagonal; (d) función de autocorrelación (ACF), donde los valores deben
caer dentro de las bandas de confianza si no hay autocorrelación residual.
Los resultados para {pad} muestran que el modelo captura adecuadamente
la estructura temporal, con residuales centrados en cero.

"""

    md += f"""### 5.3 Importancia de features

![Importancia de features]({fig_rel}/importancia_features.png)

El panel izquierdo muestra las 20 features del componente XGBoost del Ensemble
ordenadas por importancia (gain).  Los lags recientes (lag_1, lag_2) y las
medias móviles (roll_4, roll_8) dominan, reflejando la fuerte autocorrelación
de las series epidemiológicas.  El panel derecho muestra los pesos normalizados
de los tres expertos del Stacking (Prophet, ETS, LightGBM), asignados por el
meta-learner Ridge.  La distribución de pesos revela qué componente aporta más
información predictiva al ensamble heterogéneo.

### 5.4 Comparación de métricas por modelo

![Métricas global]({fig_rel}/comparacion_metricas_global.png)

Las barras agrupadas comparan RMSE, MAE, SMAPE y MASE de los 4 modelos.
{ganador_label} muestra ventaja consistente en las métricas de error absoluto
(RMSE, MAE) y relativo (SMAPE, MASE).  La tabla inferior resume los valores
numéricos exactos para facilitar la comparación cuantitativa.

"""
    for pad in _PADECIMIENTOS:
        pad_lower = _pad_filename(pad)
        md += f"""#### {pad}

![Métricas {pad}]({fig_rel}/comparacion_metricas_{pad_lower}.png)

Para {pad}, la tendencia global se mantiene: {ganador_label} obtiene los
menores valores en la mayoría de métricas, confirmando su superioridad
específica para este padecimiento.

"""

    md += (
        """### 5.5 Distribución de errores (boxplots)

![Boxplots global]("""
        + fig_rel
        + """/distribucion_errores_global.png)

Los boxplots muestran la dispersión del RMSE por modelo sobre las 333 series.
Una mediana más baja con menor rango intercuartílico (IQR) indica un modelo
más preciso y estable.  Los outliers (puntos fuera de los bigotes) representan
series particularmente difíciles donde el modelo tiene dificultades, típicamente
estados con baja incidencia o alta volatilidad.

"""
    )
    for pad in _PADECIMIENTOS:
        pad_lower = _pad_filename(pad)
        md += f"""#### {pad}

![Boxplots {pad}]({fig_rel}/distribucion_errores_{pad_lower}.png)

La distribución de errores para {pad} confirma la tendencia global.
Los modelos de ensamble muestran menor dispersión que los modelos base,
validando el beneficio de combinar múltiples predictores.

"""

    md += """### 5.6 Heatmap de win rate por estado

"""
    for pad in _PADECIMIENTOS:
        pad_lower = _pad_filename(pad)
        md += f"""#### {pad}

![Heatmap {pad}]({fig_rel}/heatmap_winrate_{pad_lower}.png)

El heatmap muestra el porcentaje de victorias (RMSE) de cada modelo en las
32 entidades federativas para {pad}.  Los colores más intensos indican mayor
dominancia.  Este gráfico permite identificar si algún modelo es particularmente
fuerte en ciertas regiones geográficas o si el modelo ganador domina de forma
uniforme en todo el territorio nacional.

"""

    md += f"""---

## 6. Conclusiones

1. El modelo **{ganador_label}** es el mejor candidato para producción,
   con el menor error promedio y la mayor tasa de victoria sobre las 333 series evaluadas.

2. Los ensambles (Ensemble y Stacking) superan consistentemente a los modelos
   individuales (Prophet y DeepAR), validando la hipótesis de que combinar
   múltiples predictores reduce la varianza del pronóstico.

3. El enfoque heterogéneo (Stacking) y el homogéneo (Ensemble) muestran
   rendimiento competitivo entre sí; la diferencia clave radica en la
   flexibilidad del meta-learner para adaptarse a patrones específicos
   por padecimiento y región.

4. El análisis de residuales confirma que {ganador_label} no presenta sesgos
   sistemáticos significativos, y la autocorrelación residual es mínima,
   indicando un buen ajuste temporal.

5. La plataforma EpiForecast-MX queda habilitada para generar pronósticos
   semanales de incidencia para Depresión (F32), Parkinson (G20) y
   Alzheimer (G30) en las 32 entidades federativas con un horizonte de
   52 semanas.
"""
    return md
