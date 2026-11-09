"""Paso semanal del carril del runner: todos los padecimientos publicados desde un release, juntos.

Un boletín nuevo exige, para cada padecimiento con ``lifecycle: published`` y backend
``runner_release`` del registry (la lista NO se escribe a mano):

    revisa     prerequisitos: puntero, bundle sellado, shard original y estado prospectivo válido
    observa    registro prospectivo de la semana (``prospective_week``) en seco o con ``--write``;
               un FAIL no corta el registro de los demás, pero la semana no se publica
    consolida  une al consolidado semanal las filas de la semana, sólo añadiendo, y verifica paridad
    vistas     regenera cada vista desde su shard ORIGINAL y la instala en el frontend

Falla cerrado: un FAIL prospectivo, un prerequisito ausente o una paridad rota detienen la semana
para todos (rc distinto de cero). Nada de esto sube a DVC, fusiona ni despliega: eso lo decide el
autor. El carril legacy (Depresión, Parkinson, Alzheimer, Dengue) sigue en el productor v5.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from epiforecast import registry

_ROOT = Path(__file__).resolve().parents[1]
RC_FAIL = 3  # el mismo código que prospective_week usa para un veredicto FAIL
CONSOLIDADO_COLS = (
    "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,Acumulado_mujeres,"
    "Acumulado_anio_anterior"
)


def publicados() -> list[str]:
    """Padecimientos que avanzan con el boletín: publicados desde un release del runner."""
    return [d.id for d in registry.release_published()]


def _json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def release_de(disease: str, root: Path = _ROOT) -> str:
    puntero = root / "config" / "publication" / disease / "public_release_pointer.json"
    return str(_json(puntero)["release_id"])


def shard_original(disease: str, root: Path = _ROOT) -> Path:
    """Shard compilado al publicar. Obesidad se activó con ``--out runs/publication``."""
    rel = release_de(disease, root)
    propio = root / "runs" / "publication" / disease / "compile_a" / disease / rel
    if propio.is_dir():
        return propio
    return root / "runs" / "publication" / "compile_a" / disease / rel


def observacion_actual(disease: str, root: Path = _ROOT) -> str:
    estado = root / "config" / "publication" / disease / "prospective_status.json"
    return str(_json(estado)["observation_dataset_id"])


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reporte_de(stdout: str) -> dict[str, Any] | None:
    """El reporte JSON de ``prospective_week`` dentro de su stdout.

    Con ``--write`` el estado prospectivo imprime antes su resumen en texto, así que el JSON no es
    todo el stdout: se busca el objeto que lleva ``verdict``.
    """
    dec = json.JSONDecoder()
    for i, ch in enumerate(stdout):
        if ch != "{" or (i and stdout[i - 1] != "\n"):
            continue
        try:
            obj, _ = dec.raw_decode(stdout, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "verdict" in obj:
            return obj
    return None


def _py() -> list[str]:
    return [sys.executable, "-m"]


def revisa(root: Path = _ROOT) -> list[str]:
    """Problemas que impiden correr la semana, uno por línea; lista vacía si todo está listo."""
    problemas: list[str] = []
    for d in publicados():
        try:
            rel = release_de(d, root)
        except (OSError, KeyError, ValueError) as exc:
            problemas.append(f"{d}: sin puntero público ({exc})")
            continue
        if not (root / "artifacts" / "releases" / d / rel).is_dir():
            problemas.append(f"{d}: falta el bundle {rel} (dvc pull de su .dvc)")
        try:
            obs = observacion_actual(d, root)
        except (OSError, KeyError, ValueError) as exc:
            problemas.append(f"{d}: sin estado prospectivo ({exc})")
            continue
        if not (root / "artifacts" / "observations" / d / obs).is_dir():
            problemas.append(f"{d}: falta la observación declarada {obs} (dvc pull de su .dvc)")
        if not shard_original(d, root).is_dir():
            problemas.append(f"{d}: falta el shard original de {rel} en runs/publication")
        rc = subprocess.run(
            [*_py(), "scripts.prospective_status", d, "--check"],
            cwd=root,
            capture_output=True,
            text=True,
        ).returncode
        if rc != 0:
            problemas.append(f"{d}: prospective_status --check rc={rc}")
    return problemas


def observa(
    pdf: Path,
    *,
    write: bool,
    first_available: str | None,
    runs_root: Path | None,
    salida: Path,
    root: Path = _ROOT,
) -> int:
    """Corre ``prospective_week`` para cada publicado. En seco recorre todos; con write se detiene."""
    salida.mkdir(parents=True, exist_ok=True)
    filas: list[dict[str, Any]] = []
    rc_total = 0
    for d in publicados():
        cmd = [*_py(), "scripts.prospective_week", "--disease", d, "--pdf", str(pdf)]
        if runs_root:
            cmd += ["--runs-root", str(runs_root)]
        if write:
            cmd.append("--write")
            if first_available:
                cmd += ["--first-available", first_available]
        else:
            cmd.append("--dry-run")
        res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        (salida / f"{d}.json").write_text(res.stdout, encoding="utf-8")
        fila: dict[str, Any] = {"disease": d, "rc": res.returncode}
        rep = reporte_de(res.stdout)
        if rep is not None:
            fila |= {
                "verdict": rep.get("verdict"),
                "weeks": f"{rep.get('weeks_available')}/{rep.get('weeks_required')}",
                "cutoff": rep.get("observation_cutoff"),
            }
        else:
            fila["error"] = (res.stderr.strip().splitlines() or ["sin salida"])[-1]
        filas.append(fila)
        print(json.dumps(fila, ensure_ascii=False), flush=True)
        if res.returncode != 0:
            rc_total = res.returncode if rc_total in (0, RC_FAIL) else rc_total
            # Un FAIL (rc 3) deja su evidencia y detiene la PUBLICACIÓN de la semana, no el registro
            # de los demás: si se cortara aquí, al retirar el FAIL quedarían observaciones pendientes
            # y el consolidado no tendría sus filas. Cualquier otro error sí detiene el registro.
            if write and res.returncode != RC_FAIL:
                break
    (salida / "resumen.json").write_text(
        json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rc_total


def filas_de_semana(raw: Path, anio: int, semana: int) -> list[str]:
    """Filas de (año, semana) del raw de observación, en el esquema del consolidado.

    El raw sin desglose por sexo (``Acumulado_total``) se proyecta con hombres y mujeres vacíos.
    Se lee como CSV para respetar nombres con coma (p. ej. «tráquea, bronquios y pulmón»).
    """
    import csv
    import io

    from epiforecast.publication.consolidado_base import entero

    with raw.open(encoding="utf-8", newline="") as fh:
        lector = csv.DictReader(fh)
        sin_sexo = "Acumulado_total" in (lector.fieldnames or [])
        out: list[str] = []
        for r in lector:
            if entero(r["Anio"], "Anio") != anio or entero(r["Semana"], "Semana") != semana:
                continue
            buf = io.StringIO()
            csv.writer(buf, lineterminator="").writerow(
                [
                    r["Anio"],
                    r["Semana"],
                    r["Entidad"],
                    r["Padecimiento"],
                    r["Casos_semana"],
                    "" if sin_sexo else r["Acumulado_hombres"],
                    "" if sin_sexo else r["Acumulado_mujeres"],
                    r["Acumulado_anio_anterior"],
                ]
            )
            out.append(buf.getvalue())
    return out


def consolida(
    n: int,
    anio: int,
    base: Path,
    legacy_base: Path,
    legacy_cand: Path,
    out: Path,
    root: Path = _ROOT,
) -> int:
    """Consolidado de la semana N: base completa + filas legacy nuevas + 32 filas por padecimiento."""
    b_legacy = legacy_base.read_bytes()
    if legacy_cand.read_bytes()[: len(b_legacy)] != b_legacy:
        print("✖ el candidato legacy no conserva su base byte a byte", file=sys.stderr)
        return 2
    lineas = [legacy_cand.read_bytes()[len(b_legacy) :].decode("utf-8")]
    vigentes: dict[str, Path] = {}
    for d in publicados():
        obs = observacion_actual(d, root)
        raws = sorted(
            (root / "artifacts" / "observations" / d / obs / "inputs").glob("data_raw_*.csv")
        )
        if len(raws) != 1:
            print(f"✖ {d}: raw de observación ausente o ambiguo en {obs}", file=sys.stderr)
            return 2
        vigentes[d] = raws[0]
    from epiforecast.publication.consolidado_base import diferencias_base

    try:
        viejas = diferencias_base(base, vigentes, (anio, n))
    except ValueError as exc:
        print(f"✖ base o raw con una clave inválida: {exc}", file=sys.stderr)
        return 2
    if viejas:
        for d, periodos in viejas.items():
            muestra = ", ".join(f"{a}-W{s:02d}" for a, s in periodos[:4])
            print(
                f"✖ {d}: la base difiere de su observación vigente o repite filas en "
                f"{len(periodos)} semanas ({muestra}); ¿es un consolidado sustituido o alterado?",
                file=sys.stderr,
            )
        return 2
    for d, raw in vigentes.items():
        try:
            filas = filas_de_semana(raw, anio, n)
        except ValueError as exc:
            print(f"✖ {d}: clave inválida en el raw: {exc}", file=sys.stderr)
            return 2
        if len(filas) != 32:
            print(f"✖ {d}: {len(filas)} filas en {anio}-W{n} (se esperan 32)", file=sys.stderr)
            return 2
        lineas.append("".join(f + "\n" for f in filas))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base.read_bytes() + "".join(lineas).encode("utf-8"))
    if out.read_bytes()[: len(base.read_bytes())] != base.read_bytes():
        print("✖ el consolidado no conserva su base byte a byte", file=sys.stderr)
        return 2
    from epiforecast.publication.contratos_datos import ContratoCobertura, revisa_consolidado

    c = ContratoCobertura.canonico()
    r = revisa_consolidado(out, c, c.padecimientos)
    print(
        json.dumps(
            {"paridad": r.pasa, "problemas": list(r.problemas), "cortes": len(r.cifras["cortes"])},
            ensure_ascii=False,
        )
    )
    return 0 if r.pasa else 2


def vistas(n: int, frontend: Path, root: Path = _ROOT) -> int:
    """Vista de la semana desde el shard ORIGINAL de cada publicado, instalada en el frontend."""
    for d in publicados():
        shard = shard_original(d, root)
        rel = release_de(d, root)
        instalado = frontend / "publication" / d / rel
        for origen, nombre in (("epibot", "knowledge.json"), ("web", "series.csv")):
            fuente, copia = shard / origen / nombre, instalado / nombre
            if not fuente.exists() or not copia.exists() or _sha(fuente) != _sha(copia):
                print(
                    f"✖ {d}: {nombre} instalado no coincide con el shard original", file=sys.stderr
                )
                return 2
        vista = root / "runs" / "publication" / f"vista_{d}_W{n}.json"
        cmd = [
            *_py(),
            "scripts.publication_view",
            d,
            "--shard-root",
            str(shard),
            "--out",
            str(vista),
        ]
        if subprocess.run(cmd, cwd=root).returncode != 0:
            print(f"✖ {d}: publication_view falló", file=sys.stderr)
            return 2
        inst = [
            "node",
            "scripts/install_publication.mjs",
            "--shard",
            str(shard),
            "--pointer",
            str(root / "config" / "publication" / d / "public_release_pointer.json"),
            "--vista",
            str(vista),
        ]
        if subprocess.run(inst, cwd=frontend / "epibot").returncode != 0:
            print(f"✖ {d}: install_publication falló", file=sys.stderr)
            return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lista", help="padecimientos que avanzan esta semana")
    sub.add_parser("revisa", help="prerequisitos de todos los publicados")
    o = sub.add_parser("observa", help="registro prospectivo de todos los publicados")
    o.add_argument("--pdf", type=Path, required=True)
    o.add_argument("--write", action="store_true")
    o.add_argument("--first-available", default=None)
    o.add_argument("--runs-root", type=Path, default=None)
    o.add_argument("--salida", type=Path, required=True)
    c = sub.add_parser("consolida", help="consolidado de la semana, sólo añadiendo")
    c.add_argument("--n", type=int, required=True, help="semana observada (boletín N trae W(N-1))")
    c.add_argument("--anio", type=int, default=2026)
    c.add_argument("--base", type=Path, required=True)
    c.add_argument("--legacy-base", type=Path, required=True)
    c.add_argument("--legacy-candidato", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("vistas", help="vistas de la semana instaladas en el frontend")
    v.add_argument("--n", type=int, required=True)
    v.add_argument("--frontend", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "lista":
        print("\n".join(publicados()))
        return 0
    if a.cmd == "revisa":
        problemas = revisa()
        for p in problemas:
            print(f"✖ {p}")
        print(f"{len(publicados())} publicados del runner; {len(problemas)} problemas")
        return 1 if problemas else 0
    if a.cmd == "observa":
        return observa(
            a.pdf,
            write=a.write,
            first_available=a.first_available,
            runs_root=a.runs_root,
            salida=a.salida,
        )
    if a.cmd == "consolida":
        return consolida(a.n, a.anio, a.base, a.legacy_base, a.legacy_candidato, a.out)
    return vistas(a.n, a.frontend)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    sys.exit(main())
