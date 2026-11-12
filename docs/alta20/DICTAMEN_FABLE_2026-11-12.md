# Dictamen de validación del plan alta20 (Fable 5.2 medium)

- Modelo: `claude-fable-5-2`; resultado `success`, `is_error: False`, 61 turnos,
  sin denegaciones de herramientas (`permission_denials: []`).
- Fecha: 12-nov-2026. Archivo de origen (fuera del repo): `/tmp/epiforecast-alta20-20261112/fable-review.json`,
  sha256 `10c5c067c11ed840ec6ab5ff723f5e7c47b093e6829f8dfbda47345f6a7daba4`. Se transcribe sólo el campo `result`; se omiten los metadatos de sesión.
- Veredicto: **APROBADO_CON_CORRECCIONES**. Las correcciones se incorporaron a `PLAN_FINAL_2026-11-12.md`,
  sección «Revisión vinculante tras dictamen Fable 5.2 medium», que prevalece sobre la cartera inicial.
- El dictamen permite ejecutar las fases no bloqueadas; no pide un segundo pase. No es una aprobación clínica de
  los candidatos.

## Texto del dictamen

**Dictamen: APROBADO_CON_CORRECCIONES.** El procedimiento es fiel al skill y al código, pero la cartera de 32 no alcanza para 20 aceptados y hay seis correcciones que deben entrar antes de ejecutar. Revisión de solo lectura: no corrí extracción, pruebas ni consultas de red, y no escribí archivo de plan.

## ¿La cartera de 32 permite 20? No

Primera semana real según el archivo histórico del radar (`assets/boletin/history/p*.json` del frontend, primer punto de cada serie). Es evidencia para priorizar; el manifiesto de extracción debe confirmarla.

| Situación | Candidatos |
| --- | --- |
| Sin pliegues en ninguna política vigente (7) | Picadura de abeja, Picadura de avispa, Mordedura de otras arañas y Picadura por otros artrópodos (empiezan en 2024-W01); Depleción del volumen (2025-W01); Fiebre paratifoidea y Otras helmintiasis (2017-W01, unas 209 semanas antes de 2021 frente a 260) |
| Viables por historia, 2013 o 2014 (25) | Los otros 25 |

- **Tasa histórica del gate:** 19 de 32 aperturas aceptadas (59 %); con historia larga, 9 de 16. Con 25 viables salen unos 14 aceptados, lejos de 20. Es una muestra pequeña, no un pronóstico.
- **La política no avisa:** `policy.py:187-195` compara `min_train_weeks` contra el `series_start` del YAML (2014-W01), no contra los datos. Las siete correrían sin error con un pliegue 2021 inválido.
- **Reserva limpia** (no sensible, historia desde 2013 o 2014, 18 más): Tuberculosis respiratoria, Tuberculosis otras formas, Hepatitis A, B, C y Otras hepatitis víricas, Mordeduras por perro, Mordeduras por otros mamíferos, Quemaduras, Accidente de transporte en vehículos con motor, Peatón lesionado, Candidiasis urogenital, Trastornos hipertensivos del embarazo (O10-O16), Diabetes en el embarazo, Displasia cervical leve y moderada, Displasia cervical severa, Absceso hepático amebiano, Intoxicación por monóxido de carbono.
- **Con 25 + 18 = 43 evaluables** la meta es plausible (unos 24 esperados), no segura.
- **Solo con decisión nominal del autor:** las cinco de transmisión sexual (sífilis adquirida, gonorrea, herpes genital, tricomoniasis, VPH), las dos hepáticas por alcohol y las tres desnutriciones (predominio infantil).
- **Excluidas:** VIH, intoxicación aguda por alcohol, violencias, arma de fuego, autolesión, defectos al nacimiento, parálisis flácida, ESAVI y plaguicidas (intención ambigua).

## Correcciones bloqueantes (antes de ejecutar)

1. **Sustituir la cartera.** Retirar las siete sin pliegues y sumar la reserva limpia hasta 43 o más. Mantener la regla del plan de no rebajar umbrales y de reportar el límite real.
2. **Criterio de baja incidencia sin definición escrita.** El paso 3 dice «solo si cumplen su definición», pero no existe umbral en código ni en docs (trampa 16: se mide y decide el autor). Leptospirosis, bocio, fiebre reumática, brucelosis, shigelosis y escarlatina (de 9 a 30 casos semanales nacionales) harán fallar ETS o Ridge. Hace falta una sola decisión del autor, previa a cualquier smoke, con criterio medible (por ejemplo, mediana semanal por serie base 2021-2024 y porcentaje de ceros, con F50 y Diabetes I como referencia). Sin ella, cada fallo de ETS deja al padecimiento detenido, no migrado.
3. **Reloj del boletín 44.** Con corte W42 (boletín 43) las semanas del gate son prospectivas solo si la emisión y el gate congelado preceden a la disponibilidad del 44. Consultar el índice oficial al inicio y otra vez justo antes de cada `benchmark --stage test`. Si el 44 ya existe, reextraer antes de abrir 2025, porque después no hay segunda apertura. Fijar un solo corte para todo el lote.
4. **PDF locales incompletos.** `data/raw_PDFs` del checkout principal llega a `2026_sem31`; faltan sem32 a sem43. Hidratar y verificar md5 contra el manifiesto `.dir` antes de extraer, o los raws nacerán con corte atrasado sin error.
5. **Comandos de verificación incompletos.** El build real de Netlify (`netlify.toml:16`) corre `test:dashboard`, `test:boletin`, `test:site`, y luego en `epibot/` `npm test`, `cifras:test` y `deploy:verify`. El paso 11 omite `test:dashboard` (reconstruye `assets/dashboard/catalog.json`) y `test:site` (shell, fichas, galería). Añadir también `node scripts/site_shell.mjs --check`.
6. **`publicacion.md` del skill es anterior al rediseño del 12-nov.** La navegación ya no se edita página por página: las fichas entran por `autoEnroll` de `assets/site/shell.config.json` y deben traer los marcadores `site:header` y `site:footer`. `tests/fichas.test.mjs` exige `site.css` antes de `disease.css`, `estado-ficha.js` y `<body class="disease-page">`. Usar como plantilla una ficha vigente posterior al rediseño (con sexo, y `cancer_cuello_utero_c53.html` para las sin sexo), no la receta antigua.

## Correcciones importantes

7. **`scripts/descubre_cuadro.py` no es genérico:** su `GROUPS` solo conoce `trastornos_nutricion`. El discovery de los cuadros nuevos se hace con `pdftotext` sobre todos los boletines, en scratch fuera del repo, o extendiendo el script con pruebas en una PR.
8. **Todos los candidatos necesitan grupo de cuadro nuevo.** Solo `bocio_e01` existe (`onboard: false`). Las páginas pasaron de tres bloques (11 o 12 columnas) a dos (8) hacia 2024_sem05-07, así que casi todos requerirán `periodos` con cambio entre `inner`, `first` y `last_block_columns` (precedente Neumonías). Anclar por el nombre propio del bloque, no por el vecino.
9. **Limitación del extractor con y sin sexo:** `_sin_sexo` exige que todos los bloques recortados sean de 3 columnas (`cuadro_extractor.py:220`). Hiperplasia de próstata y las categorías de embarazo necesitan grupo propio con recorte y `sex_breakdown: false`. Confirmar columnas en el PDF.
10. **Comparabilidad a medir antes de abrir 2025:**
    - Otras salmonelosis: la paratifoidea se separó en 2017.
    - Conjuntivitis: cambio de códigos en 2014.
    - Influenza: fusión de J09 con J10-J11.
    - Todas las infecciosas: caída de nivel 2020-2021 dentro de las ventanas de 3 y 5 años.
11. **Verdad imputada:** toda exclusión con `keep_period` que caiga en 2025 obliga a reportar la sensibilidad sin esas filas.
12. **`noModeladas` ya contiene candidatos:** `influenza`, `shigelosis`, `amebiasis`, `salmonelosis`, `tifoidea`, y de la reserva `hepatitis` y `tuberculosis` (`release_catalog.js:351-379`). Quitar solo el término del publicado, conservar el del rechazado y cambiar las pruebas que los usan de ejemplo.
13. **Colisiones de alias con guarda obligatoria:**
    - `influenza` frente a «Haemophilus influenzae».
    - `prostata` frente a `cancer_prostata_c61`, ya publicado.
    - `amebiasis` frente a absceso hepático amebiano.
    - `conjuntivitis` frente a la hemorrágica B30.3.
    - `faringitis` general frente al bloque estreptocócico y a IRA.
    - Helmintiasis, ascariasis y enterobiasis entre sí.
    - Subtipos de hepatitis y de tuberculosis.
    - Embarazo frente a `HIPERTENSION_AJENA` y `diabetesEnConsulta`.
14. **Radar y EPI:** `epibot/js/radar_boletin.js` responde hoy esas categorías con cifras impresas; al publicar debe ceder al release. Actualizar `data.json`, `meta.platform_published`, `verification.json` y `boletin.html` (trampa 32). Un rechazo sigue «Por incorporar», nunca «Rechazada».
15. **Consolidado:** `paso_semanal consolida` solo añade la semana nueva (publicacion.md §1.6). Para 20 o más, construir un único candidato aditivo sobre `candidato_con_neumonias` (sha `3e3cf0fd…`) con la historia completa de cada uno, y comprobar con `diferencias_base` y `revisa_consolidado` antes de declararlo base.
16. **Conteos y numerales:** `NUMERALES` de `rag.mjs:439` llega a «cuarenta»; con 55 cae a dígitos. Extenderlo y actualizar las cifras escritas a mano en `kb.js`, `test_rag_alcance.mjs`, `test_diabetes_release.mjs`, `tests/galeria_controller.test.mjs` y ambos README.
17. **Pruebas del backend que se rompen desde el alta:** `test_registry.py::test_cie_map` y la tupla de `tests/unit/registry_pre_c77.py`. Respetar el presupuesto de 497 omisiones y correr `pytest tests/unit` en el checkout principal tras publicar (trampa 30).
18. **Escala de la interfaz:** 55 pastillas en la Figura 1, filtros de galería, tarjetas de portada y un color por fila. Revisión visual en la vista previa, no solo pruebas.
19. **Respaldo de 20 shards** (`runs/publication/<id>`, fuera de git y DVC) inmediatamente después de cada `publication_activate`. Sin ellos `make semana-revisa` falla la semana siguiente para todos.
20. **Integrar por tandas:** backend primero y `main` verde entre tandas. El bot de CI commitea a `main` a diario (`69e761f3`), así que hay que rebasar y volver a comprobar HEAD antes de cada mutación.

## Lo que el plan ya hace bien

- Siete motores con `--engines` explícito y apertura única de 2025 con búsqueda previa de `benchmark_test_`.
- Rechazo conservado en `configured`, sin control ni exhibición sin orden nominal.
- 0/N presentado como INCOMPLETE; release por API; DVC selectivo.
- Invariantes legacy (432 y 4) y cierre sincronizado en `main`.

## Herramientas reutilizables

- **Backend:** `scripts/extrae_cuadro.py` (`--jobs`), `disease_run`, `build_release_for_disease` y `promote_release`, `publication_activate`, `publication_view`, `prospective_status`, `prospective_week`, `paso_semanal.py`, `doctor_padecimiento.py`.
- **Skill:** `crea_gate.py`, `sube_cache.py`, `agrega_manifiestos.py`, `retira_front.py`.
- **Frontend:** `install_publication.mjs`, `picos_heredados.mjs`, `site_shell.mjs --page`, `build_dashboard_catalog.mjs`, y el archivo histórico del radar como filtro de viabilidad previo y barato.

## Sin verificar

- Último boletín en gob.mx y estado de `origin`.
- Columnas y sexo reales de cada cuadro en los PDF.
- Medianas semanales por serie base.
- Disponibilidad de `GEMINI_API_KEY` y de credenciales de S3.
