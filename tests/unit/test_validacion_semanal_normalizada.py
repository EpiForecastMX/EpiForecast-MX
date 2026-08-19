"""El informe de validación debe salir ya en la forma que exigen los hooks.

Se versiona en git, y `trailing-whitespace` y `end-of-file-fixer` lo reescribían al
confirmarlo. Con el refresh semanal sellado eso dejó de ser cosmético: el archivo
publicado dejaba de ser byte a byte el que se había revisado, porque el hook lo modificaba
entre el sello y el commit. El 2026-08-19 obligó a rehacer el sello a mitad de la
publicación.

Emitirlo ya normalizado hace que el hook no tenga nada que cambiar.
"""

from __future__ import annotations

from scripts.genera_validacion_semanal import _normaliza_para_hooks


def test_quita_los_espacios_al_final_de_cada_linea() -> None:
    crudo = "<html>\n  <body>   \n    <p>hola</p>\t\n  </body>\n</html>"

    salida = _normaliza_para_hooks(crudo)

    assert all(linea == linea.rstrip() for linea in salida.split("\n"))


def test_termina_con_exactamente_un_salto_de_linea() -> None:
    assert _normaliza_para_hooks("<html></html>").endswith("</html>\n")
    assert _normaliza_para_hooks("<html></html>\n\n\n").endswith("</html>\n")
    assert not _normaliza_para_hooks("<html></html>\n\n").endswith("\n\n")


def test_es_idempotente() -> None:
    """Aplicarlo dos veces da lo mismo: es la condición que el hook comprueba."""
    crudo = "<html>\n  <p>x</p>   \n</html>"
    una = _normaliza_para_hooks(crudo)

    assert _normaliza_para_hooks(una) == una


def test_no_altera_el_contenido() -> None:
    """Solo toca espacios al final; el marcado y los datos quedan intactos."""
    crudo = "<p>Depresión nacional: 1 234 casos</p>   \n<p>Generado: 19/08/2026 03:59 hrs</p>"

    salida = _normaliza_para_hooks(crudo)

    assert "Depresión nacional: 1 234 casos" in salida
    assert "Generado: 19/08/2026 03:59 hrs" in salida


def test_conserva_los_espacios_interiores() -> None:
    """Sangrías y separaciones dentro de la línea no son espacio final."""
    crudo = "    <div class='x'>  texto  </div>"

    salida = _normaliza_para_hooks(crudo)

    assert salida.startswith("    <div")
    assert "'x'>  texto  </div>" in salida


def test_una_salida_ya_limpia_no_cambia() -> None:
    limpio = "<html>\n<body>\n<p>x</p>\n</body>\n</html>\n"

    assert _normaliza_para_hooks(limpio) == limpio
