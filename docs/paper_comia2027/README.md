# Expediente científico: artículo para COMIA 2027 (Guadalajara)

Borrador de trabajo (22-nov-2026). Reúne la evidencia, las pruebas y los dictámenes de la mesa de
expertos para escribir el artículo «De 4 a 152 padecimientos con pronóstico semanal: MLOps para la
vigilancia epidemiológica de México». No es el artículo ni una publicación: nada de esto cambió un
pronóstico publicado, reentrenó un release ni leyó un año de prueba.

La convocatoria de COMIA 2027 en Guadalajara no se localizó al 22-nov-2026 (búsqueda web sin
resultados; la SMIA sí convocó sedes para MICAI 2027). Formato, extensión, idioma y fechas quedan por
confirmar en el sitio de la SMIA antes de redactar.

## 1. Preguntas de investigación

- **P1 (MLOps).** ¿Qué mecanismos permitieron pasar de 4 padecimientos a 152 con pronóstico semanal
  sin publicar nada peor que el control, y cuánto de eso es código verificable frente a procedimiento?
- **P2 (motores).** En los años de desarrollo, ¿algún motor más elaborado le gana al naive estacional
  y a los métodos simples, en el total nacional y en las series estatales por sexo?
- **P3 (ajuste).** ¿Mejora una búsqueda de hiperparámetros con Optuna, anidada y honesta, a las
  configuraciones por defecto? ¿Conviene una configuración global o una por padecimiento?

## 2. Reglas de los datos

- Fuente: boletín epidemiológico semanal del SINAVE (casos nuevos por entidad y sexo). Se pronostica
  la cifra notificada en la primera publicación, no la incidencia real.
- Sólo años de **desarrollo** de la política de cada release (`folds.development`): 2021–2024 para
  109 padecimientos, 2023–2024 para 5 y 2025 para 34 de historia corta (cuya prueba es 2026).
- Los años de prueba nunca se pronostican ni se leen: el banco falla cerrado si desarrollo y prueba
  se traslapan (`src/epiforecast/banco/flujo.py`) y la búsqueda trunca la historia en el último año de
  desarrollo antes de cargarla (`src/epiforecast/banco/ajuste_flujo.py`, `cargar`).
- La prueba única de 2025 ya se consumió en cada padecimiento publicado; aquí no se reabre.

## 3. Cómo regenerar

```bash
make banco-corre
```
```bash
make banco-reporte
```
```bash
make banco-estadistica
```
```bash
pip install -e ".[tuning]"
```
```bash
make banco-optuna
```
```bash
make paper-comia
```

`make paper-comia` falla si el código del banco tiene cambios sin commit, para que `MANIFEST.json`
(SHA-256 de cada archivo, del código y de cada insumo de `runs/`, más el commit) sea verificable.
`runs/` no está en git: lo que el artículo cite se copia aquí, en `resultados/`. Los datos de entrada
son agregados públicos del boletín, pero viven en DVC sobre un S3 privado; un depósito público
(Zenodo) de los CSV agregados queda pendiente (sección 8).

## 4. Resultados que se pueden citar

Todas las cifras son de desarrollo y vienen de los archivos indicados (copias en `resultados/`).

### P1. Escalamiento y gobierno (`evidencia/`)

| Hecho | Cifra | Archivo |
|---|---|---|
| Publicados en el sitio | 152 = 4 legacy + 148 del runner | `evidencia/resumen.json` |
| Desenlace de los 148 | 51 portafolios aceptados en su prueba única; 87 controles tras rechazo; 10 controles por construcción | idem |
| Cronología | 4 (línea base, 22-jul-2026) → 35 (10-nov) → 65 (12-nov) → 85 (15-nov) → 152 (19-nov) | `evidencia/cronologia.csv`, `figuras/cronologia.png` |
| Productos pronosticados (runner) | 15,614 (111 por padecimiento con sexo, 37 sin sexo) | `evidencia/resumen.json` |
| Releases sellados en disco | 158 (incluye 10 reemplazados) | idem |
| CI del backend | 555 corridas: 413 éxito, 81 fallo, 61 canceladas | idem |
| PR fusionadas | 98 backend, 103 frontend | idem |

### P2. Banco de 30 motores (`resultados/banco/`)

- **Intersección común** (138 padecimientos y los mismos pliegues; `titular_interseccion.csv`):
  - nivel × perfil estacional: mediana del sMAPE nacional de 27.11.
  - Top-down ETS: 27.55.
  - Media de 26 semanas: 28.77.
  - Naive: 34.49.
  - En la media casi no hay diferencia (44.8 frente a 45.2 del naive): las colas pesadas dominan
    la media. La mejora está en el padecimiento típico, así que hay que reportar mediana,
    cuantiles y casos que empeoran.
- **Frente al naive** (Wilcoxon emparejado por pliegue, Holm por familia; `contra_naive_lag52.csv`):
  - Familia confirmatoria (ronda 1, diseñada antes de ver resultados):
    - Media de 52 semanas: −14.9 % (IC 95 % de −17.2 a −11.0).
    - TSB: −12.9 %.
    - ETS amortiguado: −10.7 %.
    - Prophet y Ridge armónico: sin diferencia.
    - LightGBM global (+42.9 %), Theta y las medianas estacionales: peores.
  - Familia exploratoria (ronda 2, construida tras ver la ronda 1):
    - nivel × perfil: −20.4 % (IC de −22.3 a −17.9; 14 de 148 empeoran más de 10 %).
    - Top-down ETS: −16.3 %.
- **Consistencia por año** (`por_pliegue.csv`):
  - 2021 infla todas las mejoras, porque el naive copia 2020.
  - Sin 2021, nivel × perfil sigue siendo significativo cada año (−5.8 %, −7.9 % y −6.4 % en
    2022, 2023 y 2024).
  - La media de 52 semanas deja de serlo.
- **Estratos** (`por_estrato.csv`):
  - La mejora de nivel × perfil se sostiene en los perfiles agudo, crónico y de baja incidencia.
  - En el tercil de menor incidencia no es significativa (p = 0.19).
- **Series estatales por sexo:** el resultado depende de la métrica.
  - En **WAPE** (`contra_naive_lag52_wape_bases.csv`), todos los motores suavizados le ganan al
    naive entre 12 y 18 %. nivel × perfil gana en 141 de 148 padecimientos.
  - En **sMAPE de bases**, todos salen peores (`contra_naive_lag52_bases.csv`). Es un artefacto
    del sMAPE con muchos ceros: vale 200 en cada semana con cero observado y pronóstico positivo.
  - Prophet, Ridge y LightGBM también ganan en WAPE de bases: su problema es el agregado
    nacional, no la serie individual.
- **Friedman** con corrección por empates, sin clones (`friedman.json`): χ² = 914.4,
  p = 4.9e-176, 138 padecimientos × 27 motores.
  - Los primeros puestos caen dentro de la diferencia crítica de Nemenyi (3.53), que se usa sólo
    como descripción.
  - No hay evidencia de que un motor complejo supere a los simples de nivel.

### P3. Búsqueda anidada con Optuna (`resultados/optuna/`)

- **Diseño:** CV anidada con dos años externos (2023 y 2024), cada uno ajustado sólo con los años
  anteriores, más un estudio de transferencia a los 34 padecimientos de historia corta.
  - El objetivo es una media recortada del log de la razón contra el naive, la misma escala del
    reporte.
  - Se usa TPE multivariado con 300 intentos, y una rejilla completa para la media móvil.
  - El ajuste por padecimiento usa 100 intentos y sólo entra donde hay al menos dos años internos.
- **Mejor configuración:** nivel × perfil global, con −13.6 % frente al naive en los años externos
  (IC 95 % de −16.0 a −11.0).
  - Supera a su propio valor por defecto (Holm p = 0.017).
  - Sus hiperparámetros son estables entre años: ventana de nivel de 46–47 semanas, perfil de 5
    años y encogimiento de 0.68–0.73.
- **Ajuste por padecimiento:** no supera al global (Holm p ≥ 0.08). El optimismo es grande: prometía
  −35 % en los años internos y dio −11 % en los externos (`resumen_configuraciones.csv`).
- **Selección del sistema:** elegir motor y alcance por padecimiento con los puntajes internos
  (−9.6 %) sale peor que usar nivel × perfil global para todos. Casi siempre escoge configuraciones
  por padecimiento, cuyo puntaje interno es el más optimista.
- **Transferencia:** top-down con nivel × perfil nacional, ajustado con los padecimientos de
  historia larga, da −25.0 % en los 34 de historia corta, que la búsqueda nunca vio.

## 5. Lo que no se puede afirmar

- Que 152 padecimientos tengan pronóstico **validado**: 97 de 148 son el naive estacional
  publicado como control (65.5 %). La cifra correcta es cobertura con gobierno, no validación.
- Que los motores de la ronda 2 o los «top3» sean superiores fuera de muestra: se construyeron
  después de ver la ronda 1 en los mismos pliegues (familia exploratoria).
- Que haya evidencia prospectiva: la validación semanal está en 0 a 2 de 4 semanas y las sombras v2 y
  v3 se miden a partir del boletín 45. Es un protocolo prerregistrado, no un resultado.
- Que la prueba única de 2025 esté impuesta por código: hoy es un procedimiento con registro
  auditado (la selección congelada sí la exige el código).
- Diebold-Mariano: se retiró, porque con un solo origen la serie de pérdidas mezcla horizontes.
- Que el sistema sirva como alerta temprana o detección de brotes: los motores no anticipan brotes y
  ningún release publicado trae intervalos.

## 6. Amenazas a la validez

- Choque común de años (rebote pos-COVID de 2021): los padecimientos no son independientes.
  Mitigación: resultados por año y conclusión sólo cuando se sostienen sin 2021.
- Un solo año de prueba consumido por padecimiento; sin baseline externo (canales endémicos, FluSight
  u otros sistemas) ni revisores independientes. Las autorizaciones son del mismo autor y algunas se
  tomaron por delegación en un agente: hay que declararlo.
- Ceros y sMAPE: el titular nacional y el de bases pueden contradecirse según la métrica; se reportan
  sMAPE, WAPE y MAE relativo geométrico.
- Años MMWR de 53 semanas: el naive y ETS (periodo 52) desfasan una semana tras 2020 y 2025.
- Rezago y revisiones del boletín: se pronostica la primera publicación; no se cuantificó la
  magnitud de las revisiones.
- Historia de git reescrita en junio de 2026 (filter-repo): conserva fechas de autor y cambia hashes
  anteriores.
- Lotes de 20 a 66 altas en un día: alta automatización, poca revisión por padecimiento.

## 7. Mesa de expertos (22-nov-2026)

Cuatro dictámenes independientes, en solo lectura: estadística de pronóstico, ajuste de
hiperparámetros, epidemiología y MLOps con revisión adversarial para COMIA.

| Hallazgo | Acción | Estado |
|---|---|---|
| Medianas sobre poblaciones distintas (138 frente a 148) | Titular sobre la intersección común | Atendido |
| Emparejamiento no garantizado por pliegue | `estadistica_banco.pares` empareja por pliegue | Atendido |
| Diebold-Mariano inválido con un origen | Retirado; victorias de MAE descriptivas | Atendido |
| Clones y empates en Friedman | Clones fuera, corrección de Conover, DC sólo descriptiva | Atendido |
| Empates mecánicos (historia corta) | Marcados «no aplica» | Atendido |
| Selección posterior a resultados | Familias de Holm confirmatoria y exploratoria | Atendido |
| sMAPE nacional insuficiente | MAE relativo geométrico, WAPE de bases, cuantiles 10/50/90 | Atendido |
| Independencia por choque común de años | Resultados por año | Atendido en parte |
| Años de prueba en memoria de la búsqueda | `cargar` trunca y una prueba lo exige | Atendido |
| Objetivo (media) distinto del reporte (mediana) | Objetivo relativo al naive, recortado | Atendido |
| Un solo año externo | CV anidada con 2023 y 2024 más transferencia | Atendido |
| Ajuste por padecimiento con un año interno | Exige dos años internos | Atendido |
| Tabla de optimismo interno y externo | `mejora_interna_pct` en el resumen | Atendido |
| Manifiesto con commit que no contiene el código | El paquete exige árbol limpio y guarda hashes del código | Atendido |
| Optuna fuera del lock | `requirements.lock` y extra `tuning` | Atendido |
| Fechas de alta legacy no comparables | Línea base común: creación del registry | Atendido |
| Fechas de rama y no de main | `--first-parent` sobre main | Atendido |
| Conteos de GitHub incompletos | Por conclusión, evento y frontend | Atendido |
| Estratos por perfil e incidencia | `por_estrato.csv` | Atendido |
| Sensibilidad sin 2020–2021 en la historia | Pendiente | Pendiente |
| Magnitud de las revisiones del boletín | Pendiente | Pendiente |
| Candado de la prueba única en código | Pendiente (decisión del autor) | Pendiente |

## 8. Pendientes antes de redactar

1. Confirmar la convocatoria de COMIA 2027 (formato, idioma, extensión, fechas).
2. Acumular de 4 a 8 boletines de las sombras v2 y v3 (desde el 45) para tener evidencia prospectiva.
3. Sensibilidad excluyendo 2020–2021 de la historia de entrenamiento.
4. Medir las revisiones del boletín para una misma semana en boletines sucesivos.
5. Depósito público (Zenodo) de los agregados y manifiestos, con DOI.
6. Medir el tiempo de alta a publicación y las intervenciones humanas por lote; hoy el registry y la
   publicación suelen entrar el mismo día (mediana 0 días), lo que mide el carril, no el esfuerzo.
7. Un baseline externo (por ejemplo, canal endémico clásico).
8. Decidir si la prueba única se impone por código (registro de pruebas consumidas por id).

## 9. Estructura propuesta

1. Introducción: escalar de 4 a 152 sin degradar la gobernanza.
2. Arquitectura MLOps: registry con lifecycle, runner genérico, contratos y harness sin fuga.
3. Identidad y linaje: dataset_id y run_id por contenido, cadena de digests del release, DVC.
4. Gobierno de la evaluación: política declarativa, prueba única, control, sombras, presupuesto de
   skips en CI.
5. Escalamiento: cronología y lotes.
6. Calidad: 51 aceptados frente a 97 controles; banco, ajuste anidado y pruebas.
7. Amenazas a la validez y limitaciones.

Figuras: diagrama de la cadena de artefactos (por hacer), `figuras/cronologia.png`,
`figuras/diferencia_critica.png`, `figuras/mejora_vs_naive.png`, `figuras/optuna_externo.png`.
