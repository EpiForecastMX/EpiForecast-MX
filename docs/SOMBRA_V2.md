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
