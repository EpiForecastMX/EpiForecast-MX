# Autorización nominal: política de baja incidencia para diecisiete candidatos (12-nov-2026)

**Pregunta al autor**, con enlace a `docs/alta20/DECISIONES_PENDIENTES.md` (incidencia 2021-2024 por serie y
motor que falla por etapa): «¿Autorizas aplicar la política existente de cinco motores, excluyendo ETS y Ridge,
a los 17 candidatos detenidos y documentados, para continuar hacia 20?»

**Respuesta del autor**: «autorizo».

## Alcance

- Exclusivamente estos 17: faringitis_j02, protozoarios_a07, salmonelosis_a02, alimentaria_a05, tifoidea_a01,
  shigelosis_a03, escabiosis_b86, erisipela_a46, escarlatina_a38, parotiditis_b26, peaton_v01, varicela_b01,
  candidiasis_b37, displasia_leve_n87, displasia_severa_n87, embarazo_diabetes_o24, hepatitis_c_b17.
- Cambio: `selection_policy: rolling_cv_v1` → `rolling_cv_baja_incidencia_v1` (los cinco motores estacionales
  de esa política; mismos pliegues, semilla, banda, desempates y aceptación). Incluye quitar Ridge aun donde no
  falló (escabiosis, candidiasis y diabetes del embarazo, donde sólo falló ETS).
- Los benchmarks y selecciones previos con siete motores quedan invalidados para estos 17: se corren smoke,
  full y select nuevos con la política de cinco motores, sin `--engines`. Ninguno había abierto 2025.

## Lo que no autoriza

No cambia umbrales; no permite repetir la prueba de 2025 ni abrirla dos veces; no permite publicar controles
de rechazos (quemaduras, insuficiencia venosa e hiperplasia de próstata siguen rechazados y sin publicar); no
incorpora sensibles sin aprobación nominal distinta; vulvovaginitis sigue fuera sin su revisión específica.
