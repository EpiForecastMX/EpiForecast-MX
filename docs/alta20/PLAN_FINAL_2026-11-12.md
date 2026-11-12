# Incorporar al menos 20 padecimientos adicionales al sitio

Orden del autor, 12-nov-2026: diseñar plan, validarlo con Fable 5.2 medium y ejecutar con Opus 5.5 medium; recorrido normal autorizado, incluidos entrenamiento, releases, DVC, integración y publicación. No sustituir esos modelos.

## Base comprobada
Backend main 985e51728618293821fc9c79c1c64d601c3c14d8, frontend main 4fc25e5eda27eaefd5170c6c928e50b500b80260. Árboles limpios, un solo worktree y sin stashes. ls-remote confirmó ambos SHA en origin. Registry: 35 publicados (4 legacy, 31 runner). Radar local W43 con 187 categorías; no confundir categorías con nuevos modelos. Fuente: assets/boletin/2026-w43-r1/catalogo.csv y data.json del frontend. Leer estado real antes de modificar, el skill y las reglas recientes de ambos repositorios.

## Meta medible
Al menos 20 identidades nuevas respecto del inventario inicial, con releases aceptados y publicados y superficies servidas verificadas. Objetivo mínimo final 55 padecimientos, sin contar agregados, duplicados, rechazos ni simples tarjetas sin pronóstico. No garantizar que un candidato aprobará antes de medirlo. Si no hay 20 aceptables, seguir con reservas y reportar el límite real; no rebajar umbrales para satisfacer la cifra.

## Cartera inicial pendiente de viabilidad histórica
Tomar nombre y códigos exactos del radar y confirmar contra PDF antes del alta. Primera cartera (32):
1. Otitis media aguda
2. Faringitis y amigdalitis estreptocócicas
3. Conjuntivitis
4. Insuficiencia venosa periférica
5. Hiperplasia de próstata
6. Amebiasis intestinal
7. Otras infecciones intestinales debidas a protozoarios
8. Otras helmintiasis
9. Enterobiasis
10. Ascariasis
11. Otras salmonelosis
12. Intoxicación alimentaria bacteriana
13. Giardiasis
14. Fiebre tifoidea
15. Fiebre paratifoidea
16. Shigelosis
17. Escabiosis
18. Erisipela
19. Escarlatina
20. Influenza
21. Parotiditis infecciosa
22. Varicela
23. Brucelosis
24. Leptospirosis
25. Bocio endémico
26. Fiebre reumática aguda
27. Intoxicación por picadura de alacrán
28. Picadura de abeja
29. Picadura de avispa
30. Mordedura de otras arañas
31. Picadura por otros artrópodos
32. Depleción del volumen (deshidratación)

Son candidatos, no una selección clínica validada. Hacer primero la evaluación de sensibilidad de cada uno. Excluir cualquiera relacionado con autolesión, violencias, adicciones o salud de menores o que requiera aprobación clínica nominal. Una categoría de población general no debe confundirse automáticamente con una pediátrica; si hay ambigüedad aplicar el criterio del skill y usar otra reserva. No dar de alta los sensibles sin revisión clínica y comunicación nominal. Reservas del catálogo deben cumplir los mismos criterios.

## Ejecución y gates
1. Inventariar ambos árboles, ramas, worktrees, stashes, runs y releases; preservar cambios ajenos por hash. Fetch --prune real antes de crear worktrees desde origin/main. Usar ramas temporales codex/ e integrar todo al final. Evitar intercalar nuevos cambios con sesiones concurrentes: volver a comprobar HEAD y status antes de mutar.
2. Confirmar último boletín oficial disponible por red, compararlo con PDFs locales, raw y radar; hidratar aditivamente solo lo necesario. No lanzar make update-week ni DVC global ni reentrenar los 35 existentes. La incorporación debe respetar el corte y la paridad de todos los publicados; si mantenerlos exige una nueva semana, aplicar el carril semanal autorizado sin reabrir entrenamiento o criterios de los existentes.
3. Viabilidad por candidato ANTES del alta: sensibilidad, primera semana real, semanas antes de cada pliegue contra min_train_weeks, continuidad, columnas/sexo, cambios de layout, escala anual y nacional reciente y comparabilidad. El extraction_group viene del registry. Política rolling_cv_v1 con siete motores por defecto. Políticas corta/baja incidencia solo si cumplen su definición previamente; ninguna política nueva ni cambio tras fallo sin decisión específica.
4. Dar alta configured, channels vacíos, nombres exactos del bloque, CIE, alias, perfil y cuadro. Cada bloque agregado cuenta uno. Configurar cambios de layout por periodos cuando el ancho no identifica posición. Extraer dos veces, exigir mismo SHA; revisar manifiesto por PDF, 32 entidades, ceros, acumulados, totales y anti-bloque vecino. Abrir PDF antes de excluir una semana. No interpretar exit 0 como datos válidos.
5. Copiar CSV validado de interim a data/raw/data_raw_<artifact_key>.csv y registrar SHA; validate-data lee RAW. Dataset v2 64 bases/111 productos si sexo desglosado o 32/37 sin desglose; reconciliación cero. Preservar entradas, runs y evidencia con hashes.
6. Oficial en worktree limpio con cambios commiteados, PYTHONPATH del worktree y venv backend. Antes del test buscar benchmark_test_ previo en todos los runs y worktrees: ninguna guarda impide reabrir 2025. No repetir la evaluación final. Smoke con todos los motores que ajustan; status del manifest exitoso además de exit code. Para rolling_cv_v1 usar exactamente seasonal_naive_lag52,seasonal_mean_3y,seasonal_median_3y,seasonal_mean_5y,seasonal_median_5y,ets_add_damped_log1p,ridge_harmonic_log1p. Benchmark full, select y test una sola vez. Ensayos mecánicos solo con un caso histórico en clon desechable, nunca con el nuevo.
7. Si rechazo, conservar configured y cifras/run, no refit, no cambiar política ni reabrir año. Continuar con reservas. Publicar un control o mostrar el rechazo exige orden nominal posterior a las cifras; el mandato general NO la proporciona. No copiar precedentes históricos como autorización. Actualizar noModeladas si hace falta evitar respuestas de otros padecimientos, sin exponer rechazos sin permiso.
8. Aceptados: refit, forecast 52, registry trained con runner_runs y digests correctos; build_release_for_disease y promote_release por API, verificar bundle e inmutabilidad, DVC add/push selectivo. Registry runner_release y release_id real. No modificar releases sellados existentes.
9. Congelar gate prospectivo antes de nuevas observaciones; registrar emisión y disponibilidad oficial. Inicializar status con dataset entrenamiento; 0/N se presenta INCOMPLETE, nunca PASS. No usar semanas ya públicas como prospectivas. Agregar al consolidado vigente de forma aditiva con prefijo byte-idéntico y paridad completa; preservar cadena y SHA. No avanzar ninguno de manera parcial a otro corte.
10. Publicar web/epibot/reports, no Tableau por defecto. Leer references/publicacion.md y código actual: los generadores cambiaron el 12-nov. Activar una vez, producir vista, instalar catálogo/punteros/shard, páginas con diseño vigente y sin intervalos inventados, alias y exclusiones, galería, navegación, portada, noticias/banner, sitemap y caché transitiva. Mantener invariantes legacy: DATA 432, hero_series 4, estructuras separadas. Reconstruir RAG con credencial existente sin imprimirla y verificar respuestas reales. Ajustar conteos desde catálogo, sin cifras manuales inconsistentes.
11. Verificación: backend lint/typecheck/test-fast y checks CI requeridos; frontend raíz test:boletin/test:wcp y epibot npm test/check/cifras:test/deploy:verify según scripts reales. Pruebas de conflictos de alias, consultas por estado/sexo y followups, bot/RAG sin datos ajenos, sin intervalos falsos, no regresión legacy y crisis. Preview y producción con identidad/hash de las 20+ vistas, páginas, bot y galería; comprobar respuestas de función RAG, no solo HTTP 200.
12. Integrar backend y frontend con CI verde, observar deploy y verificar bytes servidos. Retirar ramas ya contenidas y worktrees propios SOLO tras preservar runs/evidencia. Fetch --prune, HEAD==main==origin/main y ls-remote origin refs/heads/main, status limpio, ramas restantes, CI SHA final y versión pública. Cambios ajenos únicos se revisan e integran, nunca se borran. Si red/credenciales/decisión bloquean, registrar exactamente lo pendiente sin afirmar cierre.

## Contrato de ejecución
No lanzar trabajo en segundo plano y abandonarlo. Mantener informe de avance verificable, continuar hasta 20 nuevas aceptadas o agotar candidatos viables. Para decisiones de gobierno, continuar con otros candidatos y presentar solo las necesarias con evidencia. Nunca reset --hard, clean, force push, omitir hooks o alterar sellos.

## Revisión vinculante tras dictamen Fable 5.2 medium

Dictamen real: APROBADO_CON_CORRECCIONES, 12-nov-2026, registrado en fable-review.json, modelo claude-fable-5-2, sin denegaciones de herramientas. Esta sección PREVALECE sobre la cartera y detalles anteriores. El dictamen no es una aprobación clínica de los candidatos y sus datos históricos deben verificarse.

1. Cartera: retirar de la lista inicial Picadura de abeja, Picadura de avispa, Mordedura de otras arañas, Picadura por otros artrópodos, Depleción del volumen, Fiebre paratifoidea y Otras helmintiasis por historia insuficiente según radar histórico. No correrlos bajo una política inadecuada ni crear otra. Quedan 25. Añadir como reservas preliminares 18: Tuberculosis respiratoria; Tuberculosis otras formas; Hepatitis A; Hepatitis B; Hepatitis C; Otras hepatitis víricas; Mordeduras por perro; Mordeduras por otros mamíferos; Quemaduras; Accidente de transporte en vehículos con motor; Peatón lesionado en accidente de transporte; Candidiasis urogenital; Trastornos hipertensivos del embarazo; Diabetes en el embarazo; Displasia cervical leve y moderada; Displasia cervical severa y CaCu in situ; Absceso hepático amebiano; Intoxicación por monóxido de carbono. Total preliminar 43. Todos pasan primero la evaluación de sensibilidad/comparabilidad/historia; excluir de inmediato las categorías que requieran revisión clínica nominal no aportada, sin darlas de alta. No garantizar 20 aceptadas. Esas reservas no sustituyen un dictamen clínico.
2. No existe criterio cuantitativo escrito para elegir la política de baja incidencia. No inventarlo. Proceder con rolling_cv_v1 y siete motores cuando sea adecuada la historia. Si falla un motor o se considera necesaria otra política, detener SOLO ese candidato, mostrar sus métricas al autor y seguir con los demás. No tomar una decisión de política después de ver el test. No abrir test hasta resolver su viabilidad.
3. Consultar el índice oficial al inicio y justo antes del test de cada candidato. Si hay boletín nuevo, determinar corte y paridad antes de modelar; nunca usar como prospectivo lo disponible al emitir. Mantener un único corte explícito del lote, sin afirmar prospectividad por mera fecha de registro. Si cambia raw antes del test, rehacer desarrollo y selección vinculados al nuevo dataset, sin abrir test prematuramente.
4. Los PDF del directorio principal llegan solo a sem31, según Fable. Inventariar, hidratar sem32..último disponible y verificar hash contra sus manifiestos o evidencia oficial antes de extraer. No basta con el PDF 43 del frontend.
5. Añadir verificación frontend raíz npm run test:dashboard, npm run test:boletin, npm run test:site y node scripts/site_shell.mjs --check, además de epibot npm test/check/cifras:test/deploy:verify y checks adicionales vigentes. test:dashboard reconstruye assets/dashboard/catalog.json: comprobar su consistencia antes de integrar.
6. El diseño del 12-nov gobierna sobre recipes antiguas de publicacion.md: shell.config.json autoEnroll, marcadores site:header/site:footer, site.css antes de disease.css, estado-ficha.js y body disease-page. Usar fichas actuales como plantilla y generadores actuales; comprobar visualmente 55+ categorías.
7. Discovery: descubre_cuadro.py no es genérico. Medir con pdftotext o extenderlo con pruebas pertinentes, sin asumir GROUPS universal. Cada candidato necesita grupo correcto (bocio ya tiene un bloque onboard:false). Medir periodos de transición de 11/12 a 8 columnas y posiciones de bloque, anclas propias. Para cuadros sin sexo declarar sex_breakdown:false y recortar bloque antes de _sin_sexo.
8. Comparabilidad: revisar separación de salmonelosis/paratifoidea en 2017, códigos de conjuntivitis, fusión de influenza y ruptura de nivel de infecciosas en pandemia. Una señal no se convierte en diagnóstico causal; incertidumbre bloqueante se eleva al autor y se sigue con otros candidatos. Toda exclusión/imputación en test requiere sensibilidad sin filas imputadas; no repetir el test para seleccionar.
9. Guardas de alias: influenza/Haemophilus; hiperplasia/cáncer de próstata; amebiasis/absceso; conjuntivitis/hemorrágica; faringitis/IRA; helmintiasis específicas; hepatitis y tuberculosis por subtipo; embarazo frente a guardas de diabetes e hipertensión. Pruebas de negativas y consultas mixtas. Retirar de noModeladas solo términos realmente cubiertos, nunca toda la familia de subtipos.
10. Actualizar radar/EPI, data.json/meta.platform_published, verification.json y boletin.html al publicar, conservando su verdad impresa. El radar cede al release. Candidatos rechazados no se exhiben como tales sin autorización nominal.
11. Construir consolidado aditivo de lote desde candidato_con_neumonias con toda la historia nueva y comprobar diferencias_base/revisa_consolidado. Guardar SHA de base y candidato. Integrar por tandas aceptadas coherentes, backend primero con main verde, sin romper paridad de corte y conservando avance adicional si no se alcanza aún 20.
12. Extender NUMERALES y conteos al total real, actualizar registry_pre_c77/test_cie_map y pruebas de estado, ambos README. Ejecutar también pytest tests/unit en checkout principal al cerrar publicación conforme al skill y presupuesto de skips vigente. No duplicar checks largos ya acreditados sin motivo.
13. Respaldar cada shard runs/publication/<id> en cuanto se active; es obligatorio para el siguiente paso semanal. Preservar manifiestos y todos los runs propios antes de retirar worktrees. Verificar al final readiness del carril semanal del conjunto publicado, no solo la apariencia pública.

Ejecución autorizada de las fases no bloqueadas sin solicitar nuevo OK general. Las decisiones nominales de política o sensibilidad y controles rechazados siguen fuera del alcance. Si faltan 20 por esas decisiones, dar cifras y preguntas concretas sin convertirlas en permisos genéricos.
