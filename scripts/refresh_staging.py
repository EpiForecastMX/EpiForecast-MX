"""Interfaz de línea de órdenes del staging sellado del refresh semanal.

Tres subórdenes, que corresponden a los tres momentos del flujo:

``snapshot``
    Antes de generar. Registra el digest de la semilla clonada del destino, para poder
    distinguir después lo que produjo el refresh de lo que ya estaba ahí.

``seal``
    Después de generar. Retira del staging lo que no cambió, inventaría lo que queda y
    escribe el manifiesto con las entradas que lo gobiernan.

``apply``
    Recibe un manifiesto **explícito**, verifica que todo siga como se selló e instala
    esos bytes. No regenera nada y no admite un escape que permita publicar algo
    distinto de lo revisado.

Uso:
    python -m scripts.refresh_staging snapshot --raiz <dir> --salida <json>
    python -m scripts.refresh_staging seal --trabajo <dir> --semilla <json> \\
        --head-backend <sha> --head-dashboard <sha> --digest-consolidado <sha> \\
        --semana-anterior <a,s> --semana-nueva <a,s> --padecimientos "A,B,C" \\
        [--boletin nombre:url:bytes:sha256 ...] [--destino-final <dir>]
    python -m scripts.refresh_staging apply --manifiesto <json> \\
        --destino-backend <dir> --destino-dashboard <dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from epiforecast.publication.weekly_staging import (  # noqa: E402
    Boletin,
    Manifiesto,
    SelloEntrada,
    StagingError,
    aplica,
    calcula_run_id,
    poda_a_cambiados,
    sella,
    snapshot_digests,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _head(repo: Path) -> str:
    salida = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    if salida.returncode != 0:
        raise StagingError(f"no se pudo leer el HEAD de {repo}: {salida.stderr.strip()}")
    return salida.stdout.strip()


def _cmd_snapshot(args: argparse.Namespace) -> int:
    digests = snapshot_digests(Path(args.raiz))
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(digests, indent=2, sort_keys=True), encoding="utf-8")
    print(f"    semilla registrada: {len(digests):,} archivos -> {salida}")
    return 0


def _parse_boletin(crudo: str) -> Boletin:
    """Interpreta ``nombre:url:bytes:sha256``.

    Se separa desde el final: la URL contiene sus propios dos puntos, así que partir
    desde el principio la rompía por la mitad.
    """
    resto, tam, digest = crudo.rsplit(":", 2)
    nombre, _, url = resto.partition(":")
    if not (nombre and url and digest):
        raise StagingError(f"boletín mal formado (nombre:url:bytes:sha256): {crudo}")
    try:
        tamano = int(tam)
    except ValueError as exc:
        raise StagingError(f"tamaño no numérico en el boletín: {tam!r}") from exc
    return Boletin(nombre=nombre, url=url, bytes=tamano, sha256=digest)


def _cmd_seal(args: argparse.Namespace) -> int:
    trabajo = Path(args.trabajo)
    outputs = trabajo / "outputs"
    semilla = json.loads(Path(args.semilla).read_text(encoding="utf-8"))

    inventario = poda_a_cambiados(outputs, semilla)
    if not inventario:
        print("    el refresh no cambió ningún artefacto; no hay nada que sellar")
        return 0

    entrada = SelloEntrada(
        head_backend=args.head_backend,
        head_dashboard=args.head_dashboard,
        digest_consolidado=args.digest_consolidado,
        semana_anterior=args.semana_anterior,
        semana_nueva=args.semana_nueva,
        padecimientos_autorizados=tuple(
            p.strip() for p in args.padecimientos.split(",") if p.strip()
        ),
        boletines=tuple(_parse_boletin(b) for b in (args.boletin or [])),
    )

    run_id = calcula_run_id(entrada, inventario)
    destino = Path(args.destino_final or (trabajo.parent / run_id))
    if destino.exists():
        shutil.rmtree(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    trabajo.rename(destino)

    manifiesto = sella(destino, entrada)
    print(f"    staging sellado: {run_id}")
    print(f"    artefactos      : {len(manifiesto.inventario):,}")
    print(f"    manifiesto      : {destino / 'manifest.json'}")
    return 0


def _cmd_apply(args: argparse.Namespace) -> int:
    ruta = Path(args.manifiesto)
    manifiesto = Manifiesto.lee(ruta)
    raiz_staging = ruta.parent

    destinos = {
        "backend": Path(args.destino_backend),
        "dashboard": Path(args.destino_dashboard),
    }
    instalados = aplica(
        raiz_staging,
        manifiesto,
        destinos,
        head_backend=_head(Path(args.destino_backend)),
        head_dashboard=_head(Path(args.destino_dashboard)),
    )
    print(f"    instalados {len(instalados):,} artefactos del staging {manifiesto.run_id}")
    print(
        f"    semana     {manifiesto.entrada.semana_anterior} -> {manifiesto.entrada.semana_nueva}"
    )
    return 0


def _archivos_modificados(repo: Path) -> set[str]:
    """Rutas rastreadas que difieren del HEAD, relativas a la raíz del repositorio."""
    # `core.quotepath=false` evita que git devuelva los acentos como escapes octales
    # (`\303\251` por `é`), que no casarían contra el inventario y darían falsos
    # positivos justo en las entidades con tilde.
    salida = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.quotepath=false",
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        capture_output=True,
        text=True,
    )
    if salida.returncode != 0:
        raise StagingError(f"no se pudo leer el estado de {repo}: {salida.stderr.strip()}")
    rutas: set[str] = set()
    for linea in salida.stdout.splitlines():
        if not linea.strip():
            continue
        ruta = linea[3:].strip().strip('"')
        # Los renombrados llegan como "antes -> despues"; interesa el destino.
        if " -> " in ruta:
            ruta = ruta.split(" -> ", 1)[1]
        rutas.add(ruta)
    return rutas


def _cmd_check_completeness(args: argparse.Namespace) -> int:
    """Comprueba que instalar el sello cambia EXACTAMENTE lo que el sello declara.

    Un sello puede ser íntegro y aun así estar incompleto: si un generador escribió
    fuera del staging, su salida nunca entró al inventario y la instalación deja el
    destino a medio actualizar. Esto lo detecta comparando conjuntos, no contando.
    """
    manifiesto = Manifiesto.lee(Path(args.manifiesto))
    destinos = {
        "backend": Path(args.destino_backend),
        "dashboard": Path(args.destino_dashboard),
    }

    declarado: dict[str, set[str]] = {clave: set() for clave in destinos}
    for rel in manifiesto.inventario:
        partes = Path(rel).parts
        if partes[0] in declarado:
            declarado[partes[0]].add("/".join(partes[1:]))

    problemas: list[str] = []
    for clave, raiz in destinos.items():
        observado = _archivos_modificados(raiz)
        esperado = declarado[clave]
        # Un artefacto identico al del HEAD no aparece en el diff y no es un problema.
        sobran = sorted(observado - esperado)
        print(f"    {clave}: declarados {len(esperado):,} · modificados {len(observado):,}")
        if sobran:
            problemas.append(f"{clave}: {len(sobran)} archivo(s) cambiados fuera del inventario")
            for r in sobran[:10]:
                print(f"      FUERA DEL SELLO: {r}")

    if problemas:
        raise StagingError("; ".join(problemas))
    print("    completitud: todo lo que cambió está declarado en el sello")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="orden", required=True)

    p_snap = sub.add_parser("snapshot", help="registra el digest de la semilla")
    p_snap.add_argument("--raiz", required=True)
    p_snap.add_argument("--salida", required=True)
    p_snap.set_defaults(func=_cmd_snapshot)

    p_seal = sub.add_parser("seal", help="poda, inventaría y sella el staging")
    p_seal.add_argument("--trabajo", required=True)
    p_seal.add_argument("--semilla", required=True)
    p_seal.add_argument("--head-backend", required=True)
    p_seal.add_argument("--head-dashboard", required=True)
    p_seal.add_argument("--digest-consolidado", required=True)
    p_seal.add_argument("--semana-anterior", required=True)
    p_seal.add_argument("--semana-nueva", required=True)
    p_seal.add_argument("--padecimientos", required=True)
    p_seal.add_argument("--boletin", action="append")
    p_seal.add_argument("--destino-final")
    p_seal.set_defaults(func=_cmd_seal)

    p_app = sub.add_parser("apply", help="instala un staging sellado")
    p_app.add_argument("--manifiesto", required=True)
    p_app.add_argument("--destino-backend", default=str(REPO_ROOT))
    p_app.add_argument("--destino-dashboard", required=True)
    p_app.set_defaults(func=_cmd_apply)

    p_chk = sub.add_parser(
        "check-completeness", help="verifica que lo instalado coincide con lo sellado"
    )
    p_chk.add_argument("--manifiesto", required=True)
    p_chk.add_argument("--destino-backend", default=str(REPO_ROOT))
    p_chk.add_argument("--destino-dashboard", required=True)
    p_chk.set_defaults(func=_cmd_check_completeness)

    args = parser.parse_args(argv)
    try:
        resultado: int = args.func(args)
        return resultado
    except StagingError as exc:
        print(f"ABORTA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
