"""Interfaz de línea de órdenes del staging sellado del refresh semanal.

Subórdenes, que corresponden a los momentos del flujo, en este orden:

``materialize``
    Antes de generar. Extrae con ``git archive`` el árbol administrado COMPLETO de los
    HEAD que se sellarán —los prefijos los decide la política del HEAD del backend— en
    un directorio de trabajo nuevo, y registra su semilla. Sustituye a la siembra parcial.

``hydrate``
    Después de materializar y antes de generar. Construye el sandbox del backend (código
    rastreado del HEAD más SOLO las entradas de ``config/publication/entradas_semanales.json``,
    copiadas con SHA256), guarda copias inmutables del consolidado base y de los boletines
    bajo ``<trabajo>/inputs/`` y exige el contrato exacto de cobertura (entidades, series,
    paridad de corte) antes de que ningún generador corra.

``snapshot``
    Registra el digest de una semilla ya montada (lo hace ``materialize``; se conserva
    para montajes manuales y pruebas).

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
    python -m scripts.refresh_staging materialize --trabajo <dir-nuevo> \\
        --repo-backend <dir> --head-backend <sha> --repo-dashboard <dir> --head-dashboard <sha>
    python -m scripts.refresh_staging hydrate --trabajo <dir> --head-backend <sha> \\
        --repo-backend <dir> --padecimientos "A,B,C" [--boletin nombre:url:bytes:sha256 ...]
    python -m scripts.refresh_staging snapshot --raiz <dir> --salida <json>
    python -m scripts.refresh_staging bump-cache --trabajo <dir> \\
        --destino-dashboard <dir> --head-dashboard <sha> [--data-version <valor>]
    python -m scripts.refresh_staging run-gates --trabajo <dir> --head-backend <sha> \\
        --destino-backend <dir> --destino-dashboard <dir>
    python -m scripts.refresh_staging seal --trabajo <dir> --semilla <json> \\
        --head-backend <sha> --head-dashboard <sha> \\
        --semana-anterior <a,s> --semana-nueva <a,s> --padecimientos "A,B,C" \\
        [--destino-final <dir>]
    python -m scripts.refresh_staging prepare-worktrees --manifiesto <json> \\
        --repo-backend <dir> --repo-dashboard <dir> --destinos <raiz-nueva>
    python -m scripts.refresh_staging apply --manifiesto <json> --destinos <raiz>
    python -m scripts.refresh_staging check-completeness --manifiesto <json> --destinos <raiz>
    python -m scripts.refresh_staging discard-worktrees --manifiesto <json> --destinos <raiz>
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

from epiforecast.publication.cadena_cache import (  # noqa: E402
    revisa_cadena_cache,
    sube_cadena_cache,
)
from epiforecast.publication.contratos_datos import (  # noqa: E402
    ContratoCobertura,
    exige_todo,
    revisa_candidato,
)
from epiforecast.publication.gate_runner import ejecuta_gates_con_acciones  # noqa: E402
from epiforecast.publication.hidratacion import hidrata  # noqa: E402
from epiforecast.publication.materializa import materializa_candidato  # noqa: E402
from epiforecast.publication.release_worktrees import (  # noqa: E402
    ESTADO_APLICADO,
    RegistroDestinos,
    aplica,
    composicion_del_par,
    descarta_worktrees,
    prepara_worktrees,
)
from epiforecast.publication.weekly_staging import (  # noqa: E402
    DIR_EVIDENCIA,
    DIR_INPUTS,
    RUTA_POLITICA,
    VEREDICTO_REQUERIDO,
    AutoridadLapidas,
    Boletin,
    EvidenciaGates,
    Manifiesto,
    PoliticaCenso,
    SelloEntrada,
    StagingError,
    calcula_baseline,
    calcula_composicion,
    inventaria,
    poda_a_cambiados,
    sella,
    sha256_de,
    snapshot_digests,
    valida_gates,
    verifica,
    verifica_evidencia_en_disco,
    verifica_inputs_en_disco,
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
    verifica_inputs_en_disco(destino, previo)
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


def _cmd_materialize(args: argparse.Namespace) -> int:
    resultado = materializa_candidato(
        Path(args.trabajo),
        {"backend": Path(args.repo_backend), "dashboard": Path(args.repo_dashboard)},
        {"backend": args.head_backend, "dashboard": args.head_dashboard},
    )
    print(f"    materializados {resultado.archivos:,} archivos rastreados -> {resultado.outputs}")
    print(f"    prefijos       : {', '.join(resultado.politica.prefijos_administrados)}")
    print(f"    política       : {resultado.politica.version} {resultado.politica.sha256[:16]}…")
    print(f"    semilla        : {resultado.semilla}")
    return 0


def _padecimientos(crudo: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in crudo.split(",") if p.strip())


def _cmd_hydrate(args: argparse.Namespace) -> int:
    repo = Path(args.repo_backend)
    resultado = hidrata(
        Path(args.trabajo),
        repo,
        args.head_backend,
        padecimientos_autorizados=_padecimientos(args.padecimientos),
        boletines=tuple(_parse_boletin(b) for b in (args.boletin or [])),
        contrato=ContratoCobertura.del_head(repo, args.head_backend),
    )
    print(f"    sandbox        : {resultado.sandbox}")
    print(f"    entradas       : {len(resultado.registro.entradas):,} copiadas con SHA256")
    for cobertura in resultado.coberturas:
        print(f"    cobertura {cobertura.fuente:<18} PASS {dict(cobertura.cifras)}")
    print(f"    registro       : {Path(args.trabajo) / DIR_INPUTS} + entradas.json")
    return 0


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


def _cmd_bump_cache(args: argparse.Namespace) -> int:
    """Sube DATA_VERSION y los `?v=` que la cadena exija, en el candidato, ANTES de run-gates.

    Los generadores cambian `knowledge.json`, `zoom_series.json` y a veces módulos del
    EpiBot; sin este paso el candidato era correcto y el navegador servía el anterior. Va
    antes de los gates porque cambia bytes de la composición.
    """
    trabajo = Path(args.trabajo)
    resultado = sube_cadena_cache(
        Path(args.destino_dashboard),
        args.head_dashboard,
        trabajo / "outputs" / "dashboard",
        data_version=args.data_version,
    )
    if not resultado.cadena.aplica:
        print("    el HEAD del dashboard no lleva EpiBot: no hay cadena de caché que subir")
        return 0
    for cambio in resultado.cambios:
        print(f"    subido          : {cambio}")
    if not resultado.cambios:
        print("    la cadena de caché ya estaba al día; nada que subir")
    print(
        f"    cadena OK       : {len(resultado.cadena.cambiados)} archivo(s) del EpiBot cambiados"
    )
    return 0


def _cmd_run_gates(args: argparse.Namespace) -> int:
    """Corre los gates de la política del HEAD sobre el árbol candidato COMPLETO.

    Va antes de `seal` porque `seal` poda: los gates tienen que medir la composición
    entera, que es la que `apply` reconstruiría. La política se lee del mismo HEAD que
    después se sella; no hay flag para elegir otra ni para elegir los comandos.
    """
    trabajo = Path(args.trabajo)
    politica = PoliticaCenso.del_head(Path(args.destino_backend), args.head_backend)
    resultado = ejecuta_gates_con_acciones(
        trabajo,
        politica,
        destinos_vivos={
            "backend": Path(args.destino_backend),
            "dashboard": Path(args.destino_dashboard),
        },
    )
    evidencia = resultado.evidencia
    for accion in resultado.acciones:
        print(f"    residuo previo  : {accion}")
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

    # La política se lee del commit que se sella, no del disco: una política temporal o
    # sin versionar permitiría fabricar el permiso al mismo tiempo que se usa.
    politica = PoliticaCenso.del_head(Path(args.destino_backend), args.head_backend)

    # La evidencia se valida ENTERA antes de podar —política, conjunto de gates, PASS y
    # composición del árbol completo—, no sólo su existencia. Podar es destructivo: un
    # `seal` que podara y después descubriera un FAIL dejaría el árbol candidato reducido
    # a cambios, ya no medible entero, y habría que regenerarlo para repetir los gates.
    carpeta_evidencia = trabajo / DIR_EVIDENCIA
    if carpeta_evidencia.is_symlink() or not carpeta_evidencia.is_dir():
        raise StagingError(
            f"no hay evidencia de gates en {carpeta_evidencia}; corre `run-gates` sobre el "
            "árbol completo ANTES de sellar: seal poda el staging y los gates tienen que "
            "haber medido la composición entera"
        )
    arbol_completo = inventaria(outputs)
    composicion_completa, _ = calcula_composicion({}, arbol_completo, ())
    valida_gates(EvidenciaGates.lee(trabajo), politica, composicion_completa)

    # Contratos sobre el árbol candidato COMPLETO, antes de podar: cobertura de lo que el
    # candidato publica (knowledge, zoom) y cadena de caché frente al HEAD del dashboard.
    contrato = ContratoCobertura.del_head(Path(args.destino_backend), args.head_backend)
    exige_todo(revisa_candidato(outputs / "dashboard", contrato))
    revisa_cadena_cache(
        Path(args.destino_dashboard), args.head_dashboard, outputs / "dashboard", semilla
    )

    poda = poda_a_cambiados(outputs, semilla)
    inventario = poda.cambiados
    if not inventario and not poda.eliminados_reales:
        # Una corrida que sólo RETIRA archivos sí es una corrida: si se saliera aquí, sus
        # lápidas se perderían en silencio y el sitio conservaría lo obsoleto.
        print("    el refresh no cambió ningún artefacto; no hay nada que sellar")
        return 0

    # Sólo lo que declara quien sella: HEADs, semanas y padecimientos. Digests del
    # consolidado, boletines e inventario de entradas los deriva `sella` de la hidratación.
    entrada = SelloEntrada(
        head_backend=args.head_backend,
        head_dashboard=args.head_dashboard,
        semana_anterior=args.semana_anterior,
        semana_nueva=args.semana_nueva,
        padecimientos_autorizados=_padecimientos(args.padecimientos),
    )
    # Las lápidas se DERIVAN de lo que el candidato retiró de verdad; no las declara nadie
    # a mano. Declararlas admitía dos errores simétricos —inventar una retirada y olvidar
    # otra— y sólo el primero se detectaba: una eliminación no declarada se ignoraba en
    # silencio y el sitio conservaba lo obsoleto. Lo que sí decide una persona es la
    # política: qué rutas pueden retirarse.
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
        # Decisión P0.11, opción C: esta ronda actualiza superficies públicas y deja el
        # dataset DVC pendiente. No existe flag para declarar operaciones DVC.
        operaciones_dvc=(),
        autoridad_lapidas=autoridad,
        contrato=contrato,
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
    registro = descarta_worktrees(Path(args.destinos), Path(args.manifiesto))
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

    # La prueba fuerte: el árbol administrado del par, recompuesto desde disco, tiene el
    # mismo digest que la composición que midieron los gates. Sin esto, «todo lo declarado
    # está» no dice que el par sea el árbol probado.
    politica = PoliticaCenso.del_head(
        Path(registro.destinos["backend"].ruta), manifiesto.entrada.head_backend
    )
    aplicada = composicion_del_par(
        {espacio: Path(d.ruta) for espacio, d in registro.destinos.items()}, politica
    )
    if aplicada != manifiesto.composicion:
        problemas.append(
            f"composición aplicada {aplicada[:12]}… ≠ sellada {manifiesto.composicion[:12]}…"
        )
    print(f"    composición: aplicada {aplicada[:16]}… · sellada {manifiesto.composicion[:16]}…")

    if problemas:
        raise StagingError("; ".join(problemas))
    print("    completitud: el par contiene exactamente lo que el sello declara")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="orden", required=True)

    p_mat = sub.add_parser(
        "materialize", help="extrae el árbol administrado completo de los HEAD sellados"
    )
    p_mat.add_argument("--trabajo", required=True, help="directorio NUEVO de trabajo")
    p_mat.add_argument("--repo-backend", default=str(REPO_ROOT))
    p_mat.add_argument("--head-backend", required=True)
    p_mat.add_argument("--repo-dashboard", required=True)
    p_mat.add_argument("--head-dashboard", required=True)
    p_mat.set_defaults(func=_cmd_materialize)

    p_hyd = sub.add_parser(
        "hydrate", help="sandbox del backend con las entradas de la allowlist y su contrato"
    )
    p_hyd.add_argument("--trabajo", required=True)
    p_hyd.add_argument("--repo-backend", default=str(REPO_ROOT))
    p_hyd.add_argument("--head-backend", required=True)
    p_hyd.add_argument("--padecimientos", required=True)
    p_hyd.add_argument("--boletin", action="append", help="nombre:url:bytes:sha256")
    p_hyd.set_defaults(func=_cmd_hydrate)

    p_snap = sub.add_parser("snapshot", help="registra el digest de la semilla")
    p_snap.add_argument("--raiz", required=True)
    p_snap.add_argument("--salida", required=True)
    p_snap.set_defaults(func=_cmd_snapshot)

    p_bump = sub.add_parser(
        "bump-cache", help="sube DATA_VERSION y los ?v= del EpiBot que la cadena exija"
    )
    p_bump.add_argument("--trabajo", required=True)
    p_bump.add_argument("--destino-dashboard", required=True)
    p_bump.add_argument("--head-dashboard", required=True)
    p_bump.add_argument("--data-version", help="valor explícito de DATA_VERSION (si no, +1)")
    p_bump.set_defaults(func=_cmd_bump_cache)

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
    p_seal.add_argument("--semana-anterior", required=True)
    p_seal.add_argument("--semana-nueva", required=True)
    p_seal.add_argument("--padecimientos", required=True)
    # Ni `--digest-consolidado` ni `--boletin`: los digests y los boletines salen de la
    # hidratación registrada en el staging. Un digest que se pasa es un digest que se
    # inventa.
    p_seal.add_argument("--destino-final")
    p_seal.add_argument("--destino-backend", default=str(REPO_ROOT))
    p_seal.add_argument("--destino-dashboard", required=True)
    # No existe `--resultados-pruebas`: los resultados los produce `run-gates` y `seal` los
    # relee de su sitio. Un flag que reciba resultados es un flag que recibe un PASS escrito.
    # Tampoco existe `--operacion-dvc` (P0.11, opción C): el manifiesto no autoriza DVC.
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

    # `discard` exige el manifiesto: sólo retira el par registrado para ESA corrida, y sólo
    # los worktrees que git reconoce como suyos. Sin manifiesto, cualquier raíz con un
    # registro plausible se llevaría por delante lo que dijera.
    p_dis = sub.add_parser("discard-worktrees", help="retira el par desechable registrado")
    p_dis.add_argument("--manifiesto", required=True)
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
