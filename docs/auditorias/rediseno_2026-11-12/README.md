# Rediseño de la plataforma, 12 de noviembre de 2026

La portada y las 62 rutas públicas comparten navegación, tipografía, colores, pie y comportamiento móvil. La jerarquía es Galería de pronósticos, EpiBot y Dashboard, con Noticias y Congresos accesibles. La galería conserva los 35 padecimientos y las 3,577 series: carga fuentes bajo demanda, conserva filtros en la URL y enlaza al dashboard con el mismo contexto.

Opus 5.5 medium implementó; Fable 5.2 medium revisó en varias rondas; Codex orquestó, ejecutó verificaciones independientes y aceptó las correcciones. Los recibos reales de modelo y dictámenes están en `model-receipts.json`. El dictamen final permite integrar/publicar condicionado a comprobar CI y despliegue sobre los commits finales.

Validación: 62 rutas × 3 anchos = 186 renders, sin errores JavaScript, desbordamiento de documento ni señalamientos de contraste detectados. No equivale a una certificación WCAG. Navegación 124/124, reflujo 60/60, flujos principales 12/12, editoriales 8/8 y piloto 19/19. La evidencia incremental distingue el ajuste posterior de color WCP y la limpieza final de indentación en líneas vacías; no atribuye pruebas antiguas a hashes posteriores. Véanse `ui-final-delta.json` y `whitespace-verification.json`.

Backend: 2,744 passed, 489 skipped preexistentes, 66 deselected; Ruff y mypy limpios. Frontend: dashboard 131, radar 22, sitio 103 y WCP 27; suites EpiBot y gates de despliegue correctos, cobertura RAG 575/575. Los generadores reales de noticias, resultados, validación, bitácora y comparación preservan el chrome común; los fixtures de CI no dependen de un checkout hermano.

Integridad: 1,999 archivos protegidos comprobados, sin cambios inesperados. Única excepción derivada acordada: se retiran del índice RAG dos chunks de navegación duplicada de los visores Avance; se reutilizan íntegros los otros 575 textos, metadatos y vectores, sin proveedor ni embeddings nuevos. Catálogo, fuentes científicas y materiales sellados intactos.

Límites anteriores al rediseño: el censo semanal presenta 434 superficies sobrantes y `bento.json` ausente; se conserva su rechazo y se declaran solo los dos JSON nuevos del shell. No se ejecutó actualización semanal, entrenamiento ni publicación de padecimientos. Los ids duplicados del spinner Tableau son del proveedor y están reproducidos en el sitio anterior. La compresión de z-index 30–49 en `_z_local` es una observación futura no ejercitada por páginas actuales, no un bloqueo del rediseño.

La evidencia completa de trabajo se conserva además en el archivo privado `planes/REDISENO_PLATAFORMA_2026-11-12/DkByiE/`. El cierre externo debe registrar los dos commits de main, CI de Ubuntu, deploy Netlify del SHA frontend exacto, assets servidos, redirecciones MICAI y salud RAG; no basta HTTP 200. La reversión debe ser pareada, mediante revert de ambos commits, preservando datos y materiales sellados.
