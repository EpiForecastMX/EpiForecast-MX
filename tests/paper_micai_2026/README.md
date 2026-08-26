# Gate del paquete MICAI 2026

Comando exacto de este gate:

```bash
.venv/bin/python -m pytest tests/paper_micai_2026 -q --no-cov
```

`--no-cov` es obligatorio: `pyproject.toml` exige 68 % de cobertura **del repositorio
completo**, y correr sólo este subconjunto la deja en ~0 %. El fallo que se ve sin la
bandera es el umbral global, no una prueba rota.

Qué cubre:

- la raíz de confianza (`RAIZ_SHA256.txt`) describe al `MANIFEST.json` versionado;
- el manifest nombra `c13e7163` y `b43ebdf2` y lista las 7 piezas;
- los CSV de resultados coinciden con `resultados/HASHES.json`;
- la partición regional es 4/7/6/15 sobre 32 estados;
- las 7 piezas del paquete verifican su SHA-256;
- las rutas vivas del árbol de trabajo están prohibidas;
- la Tabla 2 publicada reproduce (sMAPE 6,63 · desviación +4,40 · observado 48 300);
- el desfase de semana sigue confirmado (`incrementos_total(ds=w)` ↔ boletín `w+1`).

Las pruebas que necesitan el paquete de datos se **saltan solas** si no está
materializado (no se versiona, pesa ~500 MB). Para materializarlo:

```bash
.venv/bin/python scripts/paper_micai_2026/sella_bundle.py
```
