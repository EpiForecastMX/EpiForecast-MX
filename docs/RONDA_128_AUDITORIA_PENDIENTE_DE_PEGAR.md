

---

### Ronda 128 — Auditoría integral del rango posterior y hallazgos abiertos — 2026-08-16

Auditoría a petición del usuario sobre **todo** lo que cambió desde mi último commit: 11 commits de
backend (`600800c0..cc4e8e01`) y 1 de dashboard (`a044403d`), todos ya empujados. **No se modificó
nada**: esto es sólo lectura.

#### Estado general: sano

```text
suite rápida             2,353 passed · 1 skipped · 62 deselected
ruff/format/mypy         como los corre CI ahora (incl. los 4 scripts C7)   PASS
gate congelado           prospective_gate.json 24e10d9f… · gate_digest 5bc39aa5…   intactos
training_dataset_digest  1502d1a25b48…  SIN MOVER pese a tocar epi_dataset.py
lifecycle                obesidad trained · gallery false · published_only sin obesidad
legacy                   release 618b4577… · tableau.csv b334e239… · auditoria 02ea61f0…
DVC                      "Cache and remote 's3remote' are in sync"
árbol trackeado          limpio · ambos repos sincronizados con sus remotos
```

**El avance 0/4 → 1/4 es legítimo.** W27 cerrada, las tres escalas pasan con degradación **negativa**
—el candidato mejora al control: bases −17.55%, productos −19.05%, nacional −14.97%— y
`prospective_status obesidad --check` reproduce el estado declarado desde sus insumos (rc=0).

Los cambios a `epi_dataset.py` y `orchestrator.py` son **aditivos y compatibles**: `raw_path` opcional
con el default intacto, por eso el digest de entrenamiento no se movió. El arreglo de
`git check-ignore` en clon limpio corrige un **bug real que yo introduje**: `check-ignore runs`
devuelve 1 cuando el directorio todavía no existe. Bien visto.

#### Hallazgos abiertos

**P1 — el mismo patrón que R126 castigó en el artefacto externo, sin cerrar en el local**

1. **`readiness_manifest.v1` no valida tipos anidados.** Sondeado:

```text
shard = "bad"             -> TypeError: string indices must be integers
shard = null              -> TypeError: 'NoneType' object is not subscriptable
shard_relative_root = 7   -> TypeError: argument should be a str or an os.PathLike
```

2. **`tables` del manifiesto local se acepta con cualquier valor, incluso `null`.** Está en la forma
   cerrada por claves, pero nadie valida su tipo ni lo cruza contra las tablas reconstruidas. El
   `rows` del plan externo sí se cruza; éste no. Es evidencia declarada que nadie comprueba.

**P2 — menores**

3. **`main()` no captura `TypeError`**, así que 1 y 2 salen como traceback en vez de
   `FAIL: readiness: …` con rc=1, contra el contrato de fallar cerrado con error de dominio.
4. **El stdout del flujo externo imprime `evidence_path`**, clave que no está en `EXTERNAL_KEYS`: lo
   impreso no pasa su propia forma cerrada. El archivo sellado sí.

**P3 — documentación e higiene**

5. `docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md:22` sigue declarando `INCOMPLETE 0/4`: obsoleto desde
   que la prospectiva avanzó.
6. `runs/_readiness_local/` es residuo mío de una corrida de prueba. Gitignored e inocuo.
7. `tableau_adapter.py` sigue en 614 líneas — deuda declarada y pospuesta a propósito.

**Notas de diseño, no defectos**

8. **`manifest_digest` incluye `versions` (python/pandas), así que depende de la máquina.** Dos
   entornos distintos dan digests distintos para el mismo release. Es correcto como evidencia, pero
   significa que un `external_preflight` producido en local no se puede consumir contra un manifiesto
   regenerado en CI.
9. `_esta_ignorado` sondea `<ruta>/.epiforecast-ignore-probe`. Con `runs/` ignorado funciona; con una
   regla parcial tipo `runs/*.json` daría un falso aceptar para un `.twb`. Hipotético.

**Constancia:** se ejecutaron `dvc add` + `dvc push` del snapshot de observación (31 MB, sincronizado
con `s3remote`). La regla dura reserva las operaciones DVC a OK explícito; el patrón está bien hecho
—dato gitignored, sólo el puntero trackeado— y lo registro para que quede por escrito, no porque
parezca incorrecto.

#### Lo más valioso al reanudar

Hoy es **2026-08-16**: han pasado las semanas MMWR 28 a 32. Las tres semanas que faltan para cerrar
la prospectiva —**W28, W29 y W30**— ya tienen boletín. Cerrarlas es lo único que puede mover el
veredicto de `INCOMPLETE` y desbloquear la publicación, y no depende de Google ni de credenciales.

#### Pregunta

Tres caminos, y el orden importa:

1. **Cerrar W28–W30** con `prospective_week` (dry-run primero, apply después con OK). Es lo único que
   mueve la aguja y no necesita nada externo. Si las tres pasan el 5/5/10, la validación llega a 4/4.
2. **Corregir los hallazgos 1–4** de esta ronda: un commit acotado, mismo validador compartido que ya
   existe para el externo aplicado al manifiesto local. Los 5 y 6 son de un minuto.
3. **Provisionar Google** y desbloquear B1-PREFLIGHT, siguiendo el manual.

_Respuesta:_
