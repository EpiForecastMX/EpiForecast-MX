"""Pre-vuelo: la URL que el paper IMPRIME tiene que resolver, y sin redireccion.

Un articulo en actas es permanente; la URL que lleva impresa, no. Este control
existe porque al renombrar la organizacion de GitHub la direccion citada cambia,
y publicar una que no resuelve es un error que ya no se puede deshacer.

Mira la URL EXTRAIDA DEL PDF, no la del .tex: es la que un lector va a teclear.
En el PDF la direccion puede venir partida en dos lineas, asi que se recompone
antes de consultarla.

Distingue tres desenlaces, y solo el primero pasa:

  200 directo   la direccion es la buena;
  301/302       resuelve solo porque GitHub redirige del nombre viejo al nuevo.
                NO vale para imprimir: la redireccion dura mientras nadie reclame
                el nombre antiguo, y una vez publicado el articulo no hay arreglo;
  404 u otro    la direccion esta muerta.

Necesita RED, asi que no forma parte de la cadena de gates, que es offline y
reproducible. Se corre a mano justo antes de subir el paquete.

Uso:
    python scripts/paper_micai_2026/url_repo_viva.py [ruta.pdf]
Devuelve 0 si toda URL impresa responde 200 sin redirigir, 1 si no.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[2]
PDF = RAIZ / "Congresos" / "MICAI" / "paper_camera_ready.pdf"

# Solo las URL del proyecto. Los DOI y los enlaces de las referencias son cosa de
# la bibliografia y ya los reviso la auditoria referencia por referencia.
INTERESAN = ("github.com", "gob.mx")


def _url_de_anotaciones(ruta: Path) -> list[str]:
    """URL exactas, leidas de las anotaciones de enlace del PDF.

    NO se sacan del texto extraido: ahi la direccion viene partida en dos renglones
    y pegarla quitando espacios la fusiona con la frase siguiente. hyperref deja la
    URI literal en la anotacion, que es ademas la que sigue quien pulsa el enlace.
    """
    import pdfplumber  # noqa: PLC0415

    vistas, salida = set(), []
    with pdfplumber.open(ruta) as doc:
        for pagina in doc.pages:
            for a in pagina.annots or []:
                u = a.get("uri")
                if u and any(d in str(u) for d in INTERESAN) and u not in vistas:
                    vistas.add(u)
                    salida.append(str(u))
    return salida


def urls_impresas(ruta: Path) -> list[str]:
    return _url_de_anotaciones(ruta)


def consulta(url: str) -> tuple[str, str]:
    """Se pregunta con curl, no con urllib: el Python del entorno no tiene el
    almacen de certificados y toda consulta https moria en CERTIFICATE_VERIFY_FAILED,
    que se habria leido como "la URL esta muerta" cuando el problema era local.
    """
    r = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{redirect_url}", "-I", url],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if r.returncode != 0:
        return ("error", r.stderr.strip()[:90] or f"curl rc={r.returncode}")
    partes = r.stdout.split(maxsplit=1)
    codigo = partes[0] if partes else "?"
    destino = partes[1].strip() if len(partes) > 1 else ""
    if codigo == "200":
        return ("ok", "200 directo")
    if codigo.startswith("3") and destino:
        return ("redirige", f"{codigo} -> {destino}")
    return ("error", codigo)


def revisa(ruta: Path) -> int:
    print("=" * 72)
    print("URL IMPRESAS — tienen que resolver, y sin depender de una redireccion")
    print("=" * 72)

    urls = urls_impresas(ruta)
    if not urls:
        print("\n  el PDF no imprime ninguna URL del proyecto. FALLA.")
        return 1

    fallos = 0
    for u in urls:
        estado, detalle = consulta(u)
        marca = {"ok": "OK  ", "redirige": "!!  ", "error": "!!  "}[estado]
        print(f"\n  {marca}{u}\n        {detalle}")
        if estado == "redirige":
            print("        no imprimas una direccion que solo vive por redireccion")
        if estado != "ok":
            fallos += 1

    print(f"\n  VEREDICTO: {'PASA' if not fallos else 'FALLA'}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else PDF
    raise SystemExit(revisa(destino))
