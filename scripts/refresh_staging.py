"""Interfaz de línea de órdenes del staging sellado del refresh semanal.

Cuatro subórdenes, que corresponden a los momentos del flujo, en este orden:

``snapshot``
    Antes de generar. Registra el digest de la semilla clonada del destino, para poder
    distinguir después lo que produjo el refresh de lo que ya estaba ahí.

``run-gates``
    Después de generar y ANTES de sellar. Ejecuta, sobre el árbol candidato completo, el
    ``argv`` exacto de cada gate que la política del HEAD declara, y deja la evidencia
    —índice, stdout, stderr, digests— en ``<trabajo>/gates/``. El veredicto se deriva del
    código de salida; no existe forma de suministrarlo.

``seal``
    Retira del staging lo que no cambió, inventaría lo que queda, recompone el árbol y
    exige que la evidencia de ``run-gates`` apunte exactamente a esa composición y a la
    política del HEAD. Escribe el manifiesto con las entradas que lo gobiernan.

``apply``
    Recibe un manifiesto **explícito**, verifica que todo siga como se selló e instala
    esos bytes. No regenera nada y no admite un escape que permita publicar algo
    distinto de lo revisado.

Uso:
    python -m scripts.refresh_staging snapshot --raiz <dir> --salida <json>
    python -m scripts.refresh_staging run-gates --trabajo <dir> --head-backend <sha> \\
        --destino-backend <dir> --destino-dashboard <dir>
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
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from epiforecast.publication.gate_runner import ejecuta_gates  # noqa: E402
from epiforecast.publication.weekly_staging import (  # noqa: E402
    DIR_EVIDENCIA,
    RUTA_POLITICA,
    VEREDICTO_REQUERIDO,
    AutoridadLapidas,
    Boletin,
    Manifiesto,
    PoliticaCenso,
    SelloEntrada,
    StagingError,
    aplica,
    calcula_baseline,
    inventaria,
    poda_a_cambiados,
    sella,
    snapshot_digests,
    verifica,
    verifica_evidencia_en_disco,
    verifica_sidecar,
)


def _reutiliza_o_aborta(destino: Path, candidato: Manifiesto) -> Manifiesto:
    """Un run ya sellado es inmutable: o es idéntico y se reutiliza, o es un conflicto.

    Antes esto era `if destino.exists(): shutil.rmtree(destino)`. Repetir una corrida con
    el mismo contenido —o un destino forzado— destruía la evidencia ya revisada y colocaba
    otra bajo el mismo nombre. Y comparar sólo el inventario no bastaba: dos corridas con
    las mismas salidas pueden venir de entradas distintas. Se compara el payload entero,
    que es exactamente lo que gobierna.
    """
    ruta = destino / "manifest.json"
    if not ruta.is_file():
        raise StagingError(
            f"{destino} ya existe pero no contiene un manifiesto; retíralo a mano tras "
            "revisarlo. Este mandato no borra corridas."
        )
    verifica_sidecar(ruta)
    previo = Manifiesto.lee(ruta)

    if previo.payload_canonico() != candidato.payload_canonico():
        campos = sorted(
            clave
            for clave, valor in candidato.payload_canonico().items()
            if previo.payload_canonico().get(clave) != valor
        )
        raise StagingError(
            f"{destino.name} ya existe con otro contenido; difieren: {', '.join(campos)}"
        )

    if inventaria(destino / "outputs") != previo.inventario:
        raise StagingError(
            f"la corrida sellada {destino.name} ya no coincide con su propio manifiesto; "
            "no se reutiliza"
        )
    verifica_evidencia_en_disco(destino, previo)
    return previo


REPO_ROOT = Path(__file__).resolve().parent.parent
# Política canónica, rastreada por Git. `seal` la lee del commit que sella, en esta ruta
# fija: no hay flag que permita señalar otra.
POLITICA_CANONICA = REPO_ROOT / RUTA_POLITICA


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


def _cmd_run_gates(args: argparse.Namespace) -> int:
    """Corre los gates de la política del HEAD sobre el árbol candidato COMPLETO.

    Va antes de `seal` porque `seal` poda: los gates tienen que medir la composición
    entera, que es la que `apply` reconstruiría. La política se lee del mismo HEAD que
    después se sella; no hay flag para elegir otra ni para elegir los comandos.
    """
    trabajo = Path(args.trabajo)
    politica = PoliticaCenso.del_head(Path(args.destino_backend), args.head_backend)
    evidencia = ejecuta_gates(
        trabajo,
        politica,
        destinos_vivos=(Path(args.destino_backend), Path(args.destino_dashboard)),
    )
    for nombre, registro in evidencia.gates.items():
        causa = f" ({registro.causa}: {registro.detalle})" if registro.causa else ""
        print(f"    gate {nombre:<12} {registro.veredicto}{causa}")
    print(f"    composición     : {evidencia.composicion[:16]}…")
    print(f"    política        : {evidencia.politica_version} {evidencia.politica_sha256[:16]}…")
    print(f"    evidencia       : {trabajo / DIR_EVIDENCIA}")
    if evidencia.veredicto != VEREDICTO_REQUERIDO:
        print("ABORTA: al menos un gate no pasó; no hay nada que sellar", file=sys.stderr)
        return 1
    return 0


def _cmd_seal(args: argparse.Namespace) -> int:
    trabajo = Path(args.trabajo)
    outputs = trabajo / "outputs"
    semilla = json.loads(Path(args.semilla).read_text(encoding="utf-8"))

    # La evidencia se comprueba a fondo dentro de `sella`; aquí sólo se exige que exista
    # ANTES de podar, porque podar es destructivo y un `seal` sin gates dejaría el árbol
    # candidato reducido a cambios, ya no medible entero.
    carpeta_evidencia = trabajo / DIR_EVIDENCIA
    if carpeta_evidencia.is_symlink() or not carpeta_evidencia.is_dir():
        raise StagingError(
            f"no hay evidencia de gates en {carpeta_evidencia}; corre `run-gates` sobre el "
            "árbol completo ANTES de sellar: seal poda el staging y los gates tienen que "
            "haber medido la composición entera"
        )

    poda = poda_a_cambiados(outputs, semilla)
    inventario = poda.cambiados
    if not inventario and not poda.eliminados_reales:
        # Una corrida que sólo RETIRA archivos sí es una corrida: si se saliera aquí, sus
        # lápidas se perderían en silencio y el sitio conservaría lo obsoleto.
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
    # Las lápidas se DERIVAN de lo que el candidato retiró de verdad; no las declara nadie
    # a mano. Declararlas admitía dos errores simétricos —inventar una retirada y olvidar
    # otra— y sólo el primero se detectaba: una eliminación no declarada se ignoraba en
    # silencio y el sitio conservaba lo obsoleto. Lo que sí decide una persona es la
    # política: qué rutas pueden retirarse.
    # La política se lee del commit que se sella, no del disco: una política temporal o
    # sin versionar permitiría fabricar el permiso al mismo tiempo que se usa.
    politica = PoliticaCenso.del_head(Path(args.destino_backend), args.head_backend)
    tombstones = tuple(sorted(poda.eliminados_reales))
    if no_autorizadas := sorted(poda.eliminados_reales - politica.retirables):
        raise StagingError(
            f"el candidato retiró {len(no_autorizadas)} archivo(s) que la política no "
            f"permite borrar: {no_autorizadas[:5]}. Declara la ruta en "
            "`retirables` de la política si de verdad debe salir del sitio, o revisa por "
            "qué el generador dejó de producirla"
        )
    autoridad = AutoridadLapidas(
        eliminados_reales=poda.eliminados_reales,
        allowlist=politica.retirables,
    )
    destinos = {
        "backend": Path(args.destino_backend),
        "dashboard": Path(args.destino_dashboard),
    }

    # Completar y verificar el trabajo PRIMERO; publicarlo después. Al revés —renombrar y
    # luego sellar— un fallo intermedio dejaba una corrida con nombre final y sin
    # manifiesto, indistinguible de una sellada a medias. Los resultados de los gates no
    # se pasan: `sella` los relee de `<trabajo>/gates/`.
    manifiesto = sella(
        trabajo,
        entrada,
        semilla=semilla,
        baseline=calcula_baseline(destinos, set(inventario) | set(tombstones)),
        politica=politica,
        tombstones=tombstones,
        operaciones_dvc=tuple(args.operacion_dvc or ()),
        autoridad_lapidas=autoridad,
    )
    verifica(
        trabajo,
        manifiesto,
        head_backend=args.head_backend,
        head_dashboard=args.head_dashboard,
    )

    destino = Path(args.destino_final or (trabajo.parent / manifiesto.run_id[:16]))
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        # `mkdir` reclama el nombre en exclusiva; el `rename` posterior sólo puede tener
        # éxito sobre un directorio vacío, así que publica sin poder pisar una corrida.
        destino.mkdir()
    except FileExistsError:
        previo = _reutiliza_o_aborta(destino, manifiesto)
        print(f"    staging ya sellado e idéntico: {previo.run_id[:16]} (se reutiliza)")
        print(f"    el trabajo nuevo queda en    : {trabajo}")
        return 0

    try:
        trabajo.rename(destino)
    except OSError:
        destino.rmdir()
        raise
    print(f"    staging sellado : {manifiesto.run_id[:16]}")
    print(f"    artefactos      : {len(manifiesto.inventario):,}")
    print(f"    lápidas         : {len(manifiesto.tombstones):,}")
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

    p_gates = sub.add_parser(
        "run-gates", help="ejecuta los gates de la política sobre el árbol candidato completo"
    )
    p_gates.add_argument("--trabajo", required=True)
    p_gates.add_argument("--head-backend", required=True)
    p_gates.add_argument("--destino-backend", default=str(REPO_ROOT))
    p_gates.add_argument("--destino-dashboard", required=True)
    p_gates.set_defaults(func=_cmd_run_gates)

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
    p_seal.add_argument("--destino-backend", default=str(REPO_ROOT))
    p_seal.add_argument("--destino-dashboard", required=True)
    # No existe `--resultados-pruebas`: los resultados los produce `run-gates` y `seal` los
    # relee de su sitio. Un flag que reciba resultados es un flag que recibe un PASS escrito.
    p_seal.add_argument("--operacion-dvc", action="append")
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
