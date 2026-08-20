#!/bin/bash
# Gate de compilacion del master. Tres pasadas.
# Bloquea por: codigo de salida != 0, cualquier error '!' de LaTeX, referencias sin
# resolver, u overfull > 15pt. El .log viene en latin-1: leerlo con grep directo falla
# en silencio, y `nonstopmode` produce PDF aunque LaTeX haya fallado -- por eso el
# codigo de salida y los '!' se revisan aparte.
D=/private/tmp/claude-501/-Users-haowei-Documents-Integrador/4985b251-c2b9-46be-81ad-b5240c54fa67/scratchpad/micai_build
mkdir -p "$D"; cp -f llncs.cls splncs04.bst paper_camera_ready.tex "$D/"
cp -rf Figures "$D/" 2>/dev/null || true
cd "$D" || exit 2
rc=0
for i in 1 2 3; do
  pdflatex -interaction=nonstopmode paper_camera_ready.tex >/dev/null 2>&1 || rc=$?
done
RC=$rc python3 - <<'PY'
import os, re, sys
t = open("paper_camera_ready.log", encoding="latin-1").read()
err = [l for l in t.splitlines() if l.startswith("!")]
ov  = [float(x) for x in re.findall(r"Overfull \\[hv]box \(([0-9.]+)pt", t)]
und = len(re.findall(r"[Uu]ndefined (?:citation|reference|control)", t))
pg  = re.findall(r"Output written on .*?\((\d+) pages", t)
rc  = int(os.environ.get("RC", "0"))
graves = [v for v in ov if v > 15]
print(f"  paginas    : {pg[0] if pg else '??'}")
print(f"  rc pdflatex: {rc}")
print(f"  errores '!': {len(err)}")
for l in err[:5]:
    print(f"     {l[:95]}")
print(f"  undefined  : {und}")
print(f"  overfull   : {len(ov)}  (>15pt: {len(graves)}" + (f", peor {max(ov):.2f}pt)" if ov else ")"))
malo = rc != 0 or err or und or graves or not pg
print("  GATE       :", "FALLA" if malo else "PASA")
sys.exit(1 if malo else 0)
PY
