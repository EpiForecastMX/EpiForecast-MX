# Decisiones pendientes del autor (lote alta20, 12-nov-2026)

Ninguna se ha tomado. Lo que sigue son cifras para decidir, no recomendaciones de política.

## 1. Política para los detenidos por ETS o Ridge

`rolling_cv_v1` exige ETS y Ridge como incumbentes; en series estado×sexo con semanas en cero o casi en cero
ambos producen pronósticos negativos y fallan cerrado (trampa 16). Ningún candidato detenido abrió 2025, así
que la prueba sigue disponible. La alternativa vigente es `rolling_cv_baja_incidencia_v1` (los cinco motores
estacionales, mismos pliegues y la misma aceptación), que no tiene criterio escrito: hace falta una orden
nominal por padecimiento o un criterio medible.

Detenidos (diecisiete): faringitis_j02, protozoarios_a07, salmonelosis_a02, alimentaria_a05, tifoidea_a01, shigelosis_a03,
escabiosis_b86, erisipela_a46, escarlatina_a38, parotiditis_b26, peaton_v01, varicela_b01 (smoke OK, full
falla), candidiasis_b37 (Ridge OK, ETS falla en series de hombres), displasia_leve_n87, displasia_severa_n87,
embarazo_diabetes_o24, hepatitis_c_b17.

Incidencia 2021-2024 por serie base (mediana de las medianas semanales, % de semanas en cero), con referencias
publicadas (F50 y Diabetes I con la política de baja incidencia; Asma con ella por orden del autor):

```
          disease                        dataset  mediana_de_medianas  p10_mediana  min_mediana  pct_ceros_mediana  series_con_ceros_gt50  nacional_semanal
     anorexia_f50      anorexia_f50_f6b8e86568b8                 0.00         0.00          0.0              53.12                     34            105.25
      diabetes_t1       diabetes_t1_0a2919cafe60                 0.00         0.00          0.0              54.33                     33             78.38
         asma_j45          asma_j45_31a60e299dc4                25.50         9.15          2.5               0.00                      0           2504.33
    isquemica_i20     isquemica_i20_f93d2b76ab37                 8.00         3.00          1.5               0.48                      0           1104.11
 intestinales_a04  intestinales_a04_d1e86bdf9c6b               798.75       321.15        181.0               0.00                      0          65530.89
          ivu_n39           ivu_n39_0f79dbff9c04               656.00       223.95         95.0               0.00                      0          61728.86
  alimentaria_a05   alimentaria_a05_da7ae33f4055                 3.00         0.00          0.0              12.50                     16            459.29
    amebiasis_a06     amebiasis_a06_8d41b62066a7                17.00         6.00          3.0               0.00                      0           2037.90
conjuntivitis_h10 conjuntivitis_h10_631e8317331c               148.50        75.50         37.0               0.00                      0          12741.15
    erisipela_a46     erisipela_a46_d789f911b786                 1.00         0.00          0.0              45.43                     29            147.92
   escabiosis_b86    escabiosis_b86_733412793349                 6.50         1.00          0.0               1.20                      2            696.42
   faringitis_j02    faringitis_j02_75e7d9f4be07                21.25         0.00          0.0               0.24                      8           4123.76
       otitis_h65        otitis_h65_d7c983f8aca3               122.00        51.90         24.0               0.00                      0           9552.93
 protozoarios_a07  protozoarios_a07_5f63a43d12f8                 6.25         2.00          0.0               1.92                      2            915.75
 salmonelosis_a02  salmonelosis_a02_77c3a9dc8643                 3.00         0.00          0.0               5.77                     10            775.61
   shigelosis_a03    shigelosis_a03_895f89001458                 0.00         0.00          0.0              85.10                     54             38.62
     tifoidea_a01      tifoidea_a01_6e5065cef2f2                 0.50         0.00          0.0              50.00                     32            257.43
     peaton_v01      peaton_v01_2a1b23ab1034                 3.00          0.0          0.0              11.54                      8            404.58
   varicela_b01    varicela_b01_9409edf02bac                 7.00          3.3          2.0               1.92                      0            698.71
escarlatina_a38 escarlatina_a38_536f06aba41f                 0.00          0.0          0.0              82.21                     58             21.38
parotiditis_b26 parotiditis_b26_e0e6fceef8f7                 0.00          0.0          0.0              57.93                     42             57.50
  vehiculos_v20   vehiculos_v20_d62f799adf95                40.25          9.6          2.0               0.00                      0           3441.03
      candidiasis_b37       candidiasis_b37_6e4dfd284f90                 11.0          1.0          0.0               0.00                      1           2238.09
   displasia_leve_n87    displasia_leve_n87_9598d047995c                 10.0          2.0          1.0               2.16                      0            588.60
 displasia_severa_n87  displasia_severa_n87_538858b62aa5                  1.5          0.0          0.0              24.04                      9             85.33
embarazo_diabetes_o24 embarazo_diabetes_o24_da850db74ab8                  6.5          2.1          1.0               1.20                      0            413.98
      hepatitis_c_b17       hepatitis_c_b17_0a974ec6fc81                  0.0          0.0          0.0              66.35                     43             79.06
```

Los cinco últimos se midieron el 12-nov-2026 con el mismo cálculo (`epi_dataset_v2.csv` de cada dataset,
2021-2024). Displasias y diabetes del embarazo no tienen sexo: sus series base son 32.

Motor que falla cerrado por etapa de desarrollo (sólo se listan los que fallan; los demás motores terminaron):

| id | smoke | full |
| --- | --- | --- |
| faringitis_j02, protozoarios_a07, salmonelosis_a02, alimentaria_a05, tifoidea_a01, shigelosis_a03, erisipela_a46, escarlatina_a38, peaton_v01, displasia_severa_n87, hepatitis_c_b17 | ETS y Ridge | ETS y Ridge |
| parotiditis_b26 | ETS y Ridge | no se corrió |
| escabiosis_b86 | ETS | ETS |
| varicela_b01, displasia_leve_n87 | ninguno | ETS y Ridge |
| candidiasis_b37, embarazo_diabetes_o24 | ninguno | ETS |


## 2. Controles de los rechazos

quemaduras_t20, ivp_i87 e hiperplasia_prostata_n40 rechazaron en el total nacional (cifras en
`docs/C7_15_ALTA20.md`). Publicar su control exige orden nominal con esas cifras.

## 3. Comparabilidad

Mordeduras por perro y por otros mamíferos suben en 2024 junto con el cambio de formato del Cuadro 18.1. No
se modelaron.

## 4. Reservas que no se dieron de alta

- **Vulvovaginitis (N76)**: sin problema de datos que la bloquee. Desde 2017 el boletín la imprime como N76
  (hasta 2016 «Vulvovaginitis inespecífica A76.0») y reexpresa 2016 casi igual bajo el código nuevo
  (acumulado de 2016: 487,508 en `2016_sem52`; 484,590 como año anterior en `2017_sem52`); el salto de
  2016 a 2017 (+28 %) es del mismo tipo que el de otitis y conjuntivitis. Está en el Cuadro 6.2,
  Enfermedades de Transmisión Sexual, y el primer dictamen de Fable puso esa familia bajo decisión nominal
  del autor: no se dio de alta sin ella (12.4 mil casos por semana en la W42 de 2026).
- **Absceso hepático amebiano (A06.4), Tuberculosis otras formas, Otras hepatitis víricas e Intoxicación
  por monóxido de carbono**: 10, 16, 21 y 9 casos en la semana 42 de 2026 en todo el país (radar del boletín
  43), por debajo de shigelosis (58) y erisipela (166), que ya fallan ETS y Ridge en el smoke. Quedarían bajo
  la misma decisión de política del punto 1; no se dieron de alta.
