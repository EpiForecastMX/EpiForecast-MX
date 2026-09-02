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

``prepare-worktrees``
    Crea el par de worktrees DESECHABLES —uno por repositorio, desprendidos en los HEAD
    sellados— y los registra bajo una raíz nueva con lock. Es el único destino que
    ``apply`` admite.

``apply``
    Recibe un manifiesto **explícito** y la raíz del par registrado; verifica con git que
    cada destino es ese worktree, limpio y en el HEAD exacto, e instala los bytes sellados.
    No acepta rutas libres, no regenera nada y cualquier fallo deja el par inválido.

``check-completeness`` / ``discard-worktrees``
    Miden la instalación sobre el par (rastreados, sin rastrear, faltantes, sobrantes,
    alterados y lápidas) y retiran el par cuando ya no hace falta.

Uso:
    python -m scripts.refresh_staging snapshot --raiz <dir> --salida <json>
    python -m scripts.refresh_staging run-gates --trabajo <dir> --head-backend <sha> \\
        --destino-backend <dir> --destino-dashboard <dir>
    python -m scripts.refresh_staging seal --trabajo <dir> --semilla <json> \\
        --head-backend <sha> --head-dashboard <sha> --digest-consolidado <sha> \\
        --semana-anterior <a,s> --semana-nueva <a,s> --padecimientos "A,B,C" \\
        [--boletin nombre:url:bytes:sha256 ...] [--destino-final <dir>]
    python -m scripts.refresh_staging prepare-worktrees --manifiesto <json> \\
        --repo-backend <dir> --repo-dashboard <dir> --destinos <raiz-nueva>
    python -m scripts.refresh_staging apply --manifiesto <json> --destinos <raiz>
    python -m scripts.refresh_staging check-completeness --manifiesto <json> --destinos <raiz>
    python -m scripts.refresh_staging discard-worktrees --destinos <raiz>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from epiforecast.publication.gate_runner import ejecuta_gates  # noqa: E402
from epiforecast.publication.release_worktrees import (  # noqa: E402
    ESTADO_APLICADO,
    RegistroDestinos,
    aplica,
    descarta_worktrees,
    prepara_worktrees,
)
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
    calcula_baseline,
    inventaria,
    poda_a_cambiados,
    sella,
    sha256_de,
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


def _cmd_prepare_worktrees(args: argparse.Namespace) -> int:
    registro = prepara_worktrees(
        Path(args.manifiesto),
        {"backend": Path(args.repo_backend), "dashboard": Path(args.repo_dashboard)},
        Path(args.destinos),
    )
    for espacio, destino in sorted(registro.destinos.items()):
        print(f"    {espacio:<10} {destino.ruta}  @ {destino.head[:12]}")
    print(f"    registro   : {registro.raiz / 'registro.json'} ({registro.estado})")
    return 0


def _cmd_apply(args: argparse.Namespace) -> int:
    ruta = Path(args.manifiesto)
    manifiesto = Manifiesto.lee(ruta)
    instalados = aplica(ruta.parent, manifiesto, Path(args.destinos))
    print(f"    instalados {len(instalados):,} artefactos del staging {manifiesto.run_id[:16]}")
    print(
        f"    semana     {manifiesto.entrada.semana_anterior} -> {manifiesto.entrada.semana_nueva}"
    )
    print(
        f"    destinos   : {Path(args.destinos)} (par desechable; nada tocó los worktrees reales)"
    )
    return 0


def _cmd_discard_worktrees(args: argparse.Namespace) -> int:
    registro = descarta_worktrees(Path(args.destinos))
    print(f"    par {registro.run_id[:16]} descartado; registro conservado en {registro.raiz}")
    return 0


def _estado_git(ruta: Path) -> dict[str, str]:
    """`git status --porcelain --untracked-files=all` como {ruta_relativa: XY}.

    `core.quotepath=false` evita que git devuelva los acentos como escapes octales
    (`\303\251` por `é`), que no casarían contra el inventario y darían falsos
    positivos justo en las entidades con tilde. Se incluyen los archivos sin rastrear:
    con `--untracked-files=no` un archivo nuevo escrito fuera del sello era invisible.
    """
    salida = subprocess.run(
        [
            "git",
            "-C",
            str(ruta),
            "-c",
            "core.quotepath=false",
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
    )
    if salida.returncode != 0:
        raise StagingError(f"no se pudo leer el estado de {ruta}: {salida.stderr.strip()}")
    entradas: dict[str, str] = {}
    for linea in salida.stdout.splitlines():
        if not linea.strip():
            continue
        codigo, resto = linea[:2], linea[3:].strip().strip('"')
        # Los renombrados llegan como "antes -> despues"; interesa el destino.
        if " -> " in resto:
            resto = resto.split(" -> ", 1)[1]
        entradas[resto] = codigo
    return entradas


def _digest_en_head(ruta: Path, rel: str) -> str | None:
    """SHA256 del blob rastreado en HEAD para `rel`, o None si no existe ahí."""
    salida = subprocess.run(
        ["git", "-C", str(ruta), "cat-file", "-p", f"HEAD:{rel}"], capture_output=True
    )
    if salida.returncode != 0:
        return None
    return hashlib.sha256(salida.stdout).hexdigest()


def _cmd_check_completeness(args: argparse.Namespace) -> int:
    """Comprueba que instalar el sello cambió EXACTAMENTE lo que el sello declara.

    Se mide sobre el par desechable ya aplicado, donde antes de instalar no había nada
    fuera del HEAD. Seis conjuntos, todos exactos: rastreados modificados y sin rastrear
    nuevos (los declarados), faltantes (declarados que git no ve cambiar o no están),
    sobrantes (cambios que el sello no declara), alterados (declarados con otro digest) y
    lápidas (tienen que estar ausentes y, si estaban en HEAD, verse borradas).
    """
    manifiesto = Manifiesto.lee(Path(args.manifiesto))
    registro = RegistroDestinos.lee(Path(args.destinos))
    if registro.run_id != manifiesto.run_id:
        raise StagingError("el par de destinos es de otra corrida")
    if registro.estado != ESTADO_APLICADO:
        raise StagingError(
            f"el par está {registro.estado!r}; la completitud se mide sobre un par aplicado"
        )

    problemas: list[str] = []
    for espacio, destino in sorted(registro.destinos.items()):
        ruta = Path(destino.ruta)
        observado = _estado_git(ruta)
        declarados = {
            rel.split("/", 1)[1]: digest
            for rel, digest in manifiesto.inventario.items()
            if rel.split("/", 1)[0] == espacio
        }
        lapidas = {
            rel.split("/", 1)[1]
            for rel in manifiesto.tombstones
            if rel.split("/", 1)[0] == espacio
        }
        faltantes: list[str] = []
        alterados: list[str] = []
        lapidas_mal: list[str] = []
        rastreados = 0
        sin_rastrear = 0
        for rel, digest in sorted(declarados.items()):
            objetivo = ruta / rel
            if objetivo.is_symlink() or not objetivo.is_file():
                faltantes.append(rel)
                continue
            if sha256_de(objetivo) != digest:
                alterados.append(rel)
                continue
            codigo = observado.get(rel)
            if codigo == "??":
                sin_rastrear += 1
            elif codigo is not None:
                rastreados += 1
            elif _digest_en_head(ruta, rel) != digest:
                # Distinto del HEAD y git no lo ve cambiar: no puede ser.
                faltantes.append(rel)
        for rel in sorted(lapidas):
            # Una lápida está bien si el archivo no existe y, cuando HEAD lo rastreaba, git lo
            # ve borrado. Cualquier otra combinación es una retirada que no ocurrió.
            presente = os.path.lexists(ruta / rel)
            rastreada_y_no_borrada = (
                _digest_en_head(ruta, rel) is not None and observado.get(rel, "").strip() != "D"
            )
            if presente or rastreada_y_no_borrada:
                lapidas_mal.append(rel)
        sobrantes = sorted(
            rel for rel in observado if rel not in declarados and rel not in lapidas
        )

        print(
            f"    {espacio}: rastreados {rastreados:,} · sin rastrear {sin_rastrear:,} · "
            f"faltantes {len(faltantes):,} · sobrantes {len(sobrantes):,} · "
            f"alterados {len(alterados):,} · lápidas {len(lapidas):,}"
            f"{' (mal ' + str(len(lapidas_mal)) + ')' if lapidas_mal else ''}"
        )
        for etiqueta, lista in (
            ("FALTANTE", faltantes),
            ("SOBRANTE", sobrantes),
            ("ALTERADO", alterados),
            ("LÁPIDA MAL", lapidas_mal),
        ):
            for rel in lista[:10]:
                print(f"      {etiqueta}: {rel}")
            if lista:
                problemas.append(f"{espacio}: {len(lista)} {etiqueta.lower()}(s)")

    if problemas:
        raise StagingError("; ".join(problemas))
    print("    completitud: el par contiene exactamente lo que el sello declara")
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

    p_wt = sub.add_parser(
        "prepare-worktrees", help="crea y registra el par de worktrees desechables del sello"
    )
    p_wt.add_argument("--manifiesto", required=True)
    p_wt.add_argument("--repo-backend", default=str(REPO_ROOT))
    p_wt.add_argument("--repo-dashboard", required=True)
    p_wt.add_argument("--destinos", required=True, help="raíz NUEVA para el par y su registro")
    p_wt.set_defaults(func=_cmd_prepare_worktrees)

    # `apply` no admite rutas de destino: sólo la raíz del par registrado. Un flag que
    # reciba un directorio cualquiera es un flag que instala en un directorio cualquiera.
    p_app = sub.add_parser("apply", help="instala un staging sellado en su par registrado")
    p_app.add_argument("--manifiesto", required=True)
    p_app.add_argument("--destinos", required=True)
    p_app.set_defaults(func=_cmd_apply)

    p_chk = sub.add_parser(
        "check-completeness", help="verifica que lo instalado coincide con lo sellado"
    )
    p_chk.add_argument("--manifiesto", required=True)
    p_chk.add_argument("--destinos", required=True)
    p_chk.set_defaults(func=_cmd_check_completeness)

    p_dis = sub.add_parser("discard-worktrees", help="retira el par desechable registrado")
    p_dis.add_argument("--destinos", required=True)
    p_dis.set_defaults(func=_cmd_discard_worktrees)

    args = parser.parse_args(argv)
    try:
        resultado: int = args.func(args)
        return resultado
    except StagingError as exc:
        print(f"ABORTA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
