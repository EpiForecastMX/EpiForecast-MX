# Banco ampliado de motores (23-nov-2026)

Pregunta del autor: ¿le ganamos al naive estacional y a los métodos simples? Se corrieron **19
motores en los 148 padecimientos del runner**, sólo en los pliegues de desarrollo de la política de
cada uno (2021–2024; 2025 en historia corta). Ningún año de prueba se pronostica ni se mide. No
selecciona ni publica: es comparación.

Configuración: `config/banco/banco_ampliado_v1.yaml`. Código: `src/epiforecast/banco/`. Resultados
locales en `runs/banco_ampliado/v1/` (`motor_fijo.csv`, `metricas.csv`, `resumen.json`).

```bash
make banco-corre      # 2812 tareas, unos 15 min con 11 procesos
make banco-reporte
```

## Motores

| Clase | Motores |
|---|---|
| Simple | naive lag 52 (control), media y mediana de la misma semana en 2, 3 y 5 años, media de las últimas 52 semanas, último valor |
| Combinación simple | promedio de los cinco estacionales |
| Ajuste de nivel | naive y media 3 años × razón de las últimas 13 semanas (acotada a 0.5–2) |
| Estadístico | ETS amortiguado (log1p), Theta (log1p), Ridge con Fourier (log1p), GLM Poisson con Fourier, Croston SBA, TSB, Prophet (config. congelada del runner) |
| ML | LightGBM global y directo por padecimiento (sin recursión; rasgos sólo hasta el origen) |

Diferencias declaradas con el runner: un negativo se recorta a cero y se cuenta; una serie no finita
se registra como fallo y ese pliegue sale del nacional del motor.

## Resultados (métrica principal: sMAPE del nacional General, media de los pliegues)

| Motor | Clase | Mediana | vs naive (mediana) | Le gana al naive | Pierde > 10 % |
|---|---|---|---|---|---|
| media de 52 semanas | simple | 30.75 | −14.9 % | 120 / 148 | 18 |
| ETS amortiguado | estadístico | 31.93 | −10.7 % | 99 / 138 | 22 |
| TSB | estadístico | 32.54 | −12.9 % | 103 / 148 | 33 |
| Croston SBA | estadístico | 33.38 | −6.3 % | 89 / 148 | 50 |
| media 3 años con nivel | ajuste de nivel | 33.67 | −6.1 % | 89 / 148 | 31 |
| **naive lag 52 (control)** | simple | **36.98** | — | — | — |
| GLM Poisson | estadístico | 39.37 | −1.4 % | 75 / 148 | 61 |
| Ridge Fourier | estadístico | 41.22 | +7.9 % | 64 / 148 | 70 |
| Prophet | estadístico | 41.32 | +7.4 % | 63 / 148 | 71 |
| Theta | estadístico | 43.20 | +10.5 % | 53 / 138 | 70 |
| LightGBM global | ML | 53.33 | +43.9 % | 15 / 114 | 93 |

ETS y Theta no corren en los 10 padecimientos con un solo año previo; LightGBM tampoco en los de
historia corta. Por MAE nacional el orden se sostiene (ETS −14.6 %, TSB −12.5 %, media de 52 semanas
−12.0 % frente al naive).

**Selección honesta por ventana creciente** (elige con los pliegues previos, mide en el siguiente;
114 padecimientos): entre todos los motores, mediana 27.50 frente a 28.30 del naive, gana en 61 y
pierde más de 10 % en 33. Sólo entre simples: 29.40; sólo entre complejos: 29.83. Los complejos le
ganan a los simples en 58 de 114: una moneda al aire.

**Techo a posteriori** (optimista): el mejor complejo de cada padecimiento supera al mejor simple en
108 de 148, con mejora mediana de 10.4 %; pero elegirlo de antemano no reproduce esa ventaja.

## Lectura

1. **Sí le ganamos al naive, pero con un método simple.** El naive lag 52 copia el ruido del año
   anterior; promediar las últimas 52 semanas le gana en 120 de 148 padecimientos.
2. **Los modelos elaborados no le ganan de forma fiable a los simples.** Sólo ETS y TSB quedan a la
   par de la media de 52 semanas; Prophet, Ridge, Theta y LightGBM son peores que el naive en la
   mediana.
3. **La métrica por base sigue premiando pronosticar cero**: por sMAPE de bases ganan las medianas y
   el último valor, el mismo sesgo que hunde el nacional.
4. Siguiente paso sugerido (requiere autorización): probar en la sombra v2 la media de 52 semanas,
   ETS y TSB como candidatos, medidos sólo en semanas de 2026 no vistas.
