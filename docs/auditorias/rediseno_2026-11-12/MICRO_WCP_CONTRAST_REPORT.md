# MICRO_WCP_CONTRAST_REPORT

- **Causa**: `Reports/wcp2026/wcp.css` (sellado) pinta el rótulo «Men» y su % (`.sex-labels>div:last-child`)
  con `--men:#47787c`: 4.44:1 sobre `#f0f3f7` (12 px, umbral 4.5).
- **Corrección**: único archivo de producto `wcp2026.html`. No tenía `<style>`, así que añadí uno mínimo justo
  después del `<link>` a `wcp.css`: `.sex-labels>div:last-child{color:#3f6e72}`. Es el mismo teal, algo más
  oscuro: 5.12:1 sobre `#f0f3f7` y 5.70:1 sobre blanco. Sólo cambia el color del texto: la barra y el punto
  conservan `--men`, y textos, valores e idioma no cambian. No hay CSP que lo impida (ni meta ni `netlify.toml`).
- **Intacto**: `Reports/wcp2026/**` (`git diff` vacío), PDF, PNG y datos, otros CSS, assets, config y
  versiones. Sin RAG, red, git ni regeneraciones.
- **Verificación**:
  - `deep-contrast.mjs` de Root con `work/fix/wcp-route.json` en 8765: 0 señalamientos a 1280 (158 textos)
    y a 360 (149). Evidencia en `micro-wcp-contrast/` y `evidence/fix_allpages/micro-wcp-contrast/`.
  - `check:wcp`: 27/27.
- **Hashes finales**:
  - `wcp2026.html`: `6ef1e4aa…78791`.
  - FE (101): `add4fda9b8be5e3f70e601ba210551d18d512e84f1ce59f3601ce69575f04a49`.
  - BE (22, sin cambio): `0565abec…81fb`.
  - Recibo: `1c38d7e67839449fff66c81ad8eae73aecd0589991c1e159adf55113be8fcb44`.
