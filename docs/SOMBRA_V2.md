# Política v2 en sombra (22-nov-2026)

Corre en paralelo a lo publicado y **no publica, no reentrena ni toca releases sellados**. Mide si
dos cambios mejoran los 148 padecimientos del runner usando sólo semanas de 2026 que no existían al
emitir. La prueba única de 2025 sigue consumida: la sombra nunca la lee.

## Por qué

La auditoría del 21-nov-2026 encontró que la selección serie por serie con sMAPE premia pronosticar
cero en series escasas: la suma de las bases deja el nacional sesgado a la baja (−31 % en los
rechazos, en desarrollo). De los 87 rechazos, 67 fallaron sólo en el nacional. Ningún release trae
intervalos de incertidumbre.

## Reglas (`config/sombra/sombra_v2.yaml`)

1. **Selección consciente del nacional.** Un motor estacional por padecimiento (los candidatos que su
   benchmark de desarrollo evaluó), elegido por la media del sMAPE del nacional General en los
   pliegues de desarrollo. Un motor distinto del control sólo gana si mejora ese sMAPE al menos un
   5 % y le gana al control en la mayoría estricta de los pliegues.
2. **Intervalos empíricos 80 y 95 %.** Cuantiles del residuo `log1p(y) − log1p(ŷ)` del motor elegido
   en desarrollo, por producto (bases, estatales, regionales y nacionales), aplicados al pronóstico.

Datos: sólo filas `split == development` del benchmark sellado de cada release y la observación
vigente. El cargador falla cerrado si ve un año de prueba de la política del padecimiento.

## Retroprueba en desarrollo (ventana creciente)

Elige con los pliegues previos y mide en el siguiente; 114 padecimientos con al menos dos pliegues
(los de historia corta tienen uno solo).

| Estrategia | Mediana sMAPE nacional | Dentro del 10 % del control |
|---|---|---|
| Control (`seasonal_naive_lag52`) | 28.30 | 114 |
| Selección vigente serie por serie (retroprueba del 21-nov, mismo esquema) | 32.93 | 48 |
| v2 sin margen ni mayoría | 31.53 | 77 |
| **v2 (reglas declaradas)** | **28.77** | **89** |

La v2 mejora al control más de un 5 % en 33 padecimientos y empeora más de un 10 % en 25. La
cobertura mediana de los intervalos fue 82.1 % (nominal 80) y 93.9 % (nominal 95). Es evidencia de
desarrollo, no aceptación: sólo la validación prospectiva cuenta.

## Uso

```bash
make sombra-retro
make sombra-emite
make sombra-valida EMISION=sombra_v2_20261122_4ba61a03dc
```

La emisión vive en `runs/sombra_v2/<emisión>/` (sin versionar). Su índice con el SHA-256 de cada
pronóstico, la observación usada, el commit y el hash de la configuración se versiona en
`docs/sombra_v2/emisiones/`: el commit fecha la emisión antes de que exista la verdad. Una emisión
nunca se sobrescribe. **No re-emitir cada semana**: reiniciaría la comparación.

La validación cuenta, por padecimiento, sólo semanas posteriores a su origen con verdad completa en
todas las bases, y compara en esas mismas semanas la sombra, el pronóstico publicado y el control.

## Primera emisión: `sombra_v2_20261122_4ba61a03dc`

- Emitida el 22-nov-2026 a las 05:10 UTC (00:10 en hora del este), commit `98ec027c`, configuración
  `080e0743…`, índice `712c65fc…`. Última semana fuente ingerida: 44.
- Origen 2026-W43 en 125 padecimientos (rezago 1) y 2026-W44 en 23 (rezago 0); horizonte 52.
- Motores: control en 91; `seasonal_mean_5y` 28, `seasonal_median_5y` 11, `seasonal_mean_2y` 8,
  `seasonal_mean_3y` 7 y `seasonal_median_3y` 3.
- Frente a lo publicado: de los 87 controles publicados tras rechazo, la sombra usa otro motor en 48;
  de los portafolios aceptados, la sombra usa el control en 52.

## Criterio para proponer la v2

Ninguno se decide aquí: proponer el cambio requiere autorización del autor. Como guía, tras al menos
8 semanas observadas: la sombra debería no empeorar el sMAPE nacional mediano frente a lo publicado y
la cobertura empírica debería quedar cerca de la nominal (80 y 95 %).

## Sombra v3 (22-nov-2026): más candidatos desde el banco ampliado

Misma regla que la v2 (un motor por padecimiento, el control sólo cede con mejora de 5 % y
mayoritaria), con predicciones de desarrollo del banco (`config/sombra/sombra_v3.yaml`). Candidatos:
los de la v2 más la media de 52 semanas, ETS y TSB (orden del autor) y los mejores del banco:
top-down ETS nacional, nivel × perfil estacional, las dos combinaciones de los tres mejores y las
medias de 26 y 13 semanas. Ese criterio (mediana frente al naive ≤ −10 % y ganarle en al menos 2/3)
se aplicó después de ver los resultados de desarrollo del banco; por eso sólo cuenta la validación
prospectiva.

Retroprueba en desarrollo (ventana creciente, 114 padecimientos): mediana 25.92 frente a 28.30 del
control; le gana al control en 75 y queda dentro del 10 % en 98 (v2: 40 y 89). Con los cuantiles
nominales los intervalos cubrían 71 % y 87 %: los motores suavizados no copian los cambios de nivel
entre años. Se recalibró en desarrollo (banda 80 con el cuantil 90 y banda 95 con el 99): cobertura
81.3 % y 93.0 %, y 83.7 % y 95.2 % en el pliegue más reciente. La v2 reprodujo su emisión byte a byte
con el código nuevo.

Emisión congelada `sombra_v3_20261122_c0f26063ce`: 22-nov-2026 a las 07:46 UTC (02:46 en hora del
este), commit `2e5ddf92`, configuración `c5f35a01…`, índice `21081465…`. Origen W43 en 125 y W44 en
23. Motores: top-down ETS 26, nivel × perfil 26, media 26 sem 17, control 16, media 13 sem 14,
combinación media 10, media 52 sem 10, ETS 9, mediana 5 años 6, TSB 5, combinación mediana 5,
mediana 3 años 3, media 5 años 1.

```bash
make sombra-valida EMISION=sombra_v2_20261122_4ba61a03dc
python -m scripts.sombra_v2 --politica sombra_v3 valida sombra_v3_20261122_c0f26063ce
```
