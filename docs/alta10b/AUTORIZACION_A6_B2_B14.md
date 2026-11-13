# Autorización del autor: A6, B2 y B14 (12-nov-2026)

El autor respondió en el chat del supervisor, el 12-nov-2026 a las 19:21 hora del este (00:21 UTC del 13-nov):
«Autorizo A6, B2 y B14. Continúa con Opus y Fable hasta incorporar los 10 padecimientos y deja todo actualizado
y sincronizado en main.»

Root registró la respuesta para las herramientas en `AUTORIZACION_A6_B2_B14_20261112.json` (sha256 `918c654b4983744b6a3cfdad199e30b44a801fb6621f8026d1c0d33a2da050c0`),
con el esquema de `ESQUEMA_AUTORIZACION.md`. La validez viene de la respuesta del autor; el JSON sólo la registra.

- **A6**: publicar el control estacional `seasonal_naive_lag52` (nunca validado, sin contraste propio) de seis
  rechazos con su run exacto: desnutrición leve, otras salmonelosis, fiebre tifoidea, escarlatina, hepatitis vírica C y
  displasia cervical severa (`PROPUESTA_CONTROL_LEVE.md`, `PROPUESTA_CONTROLES_RESERVA_5.md`).
- **B2 y B14**: política `rolling_cv_baja_incidencia_v1` (cinco motores estacionales; mismos pliegues, semilla y
  reglas de aceptación) para dieciséis candidatos (`PROPUESTA_POLITICAS.md`): una prueba de 2025 por candidato.
- No autoriza controles de rechazos futuros ni cambia criterios. No se reabren las pruebas ya abiertas.
