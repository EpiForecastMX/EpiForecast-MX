"""Clasificador de intents y fuzzy matching."""

import re

# Mapa de typos comunes
TYPO_MAP = {
    "scritps": "scripts",
    "srcripts": "scripts",
    "scrips": "scripts",
    "sripts": "scripts",
    "scirpts": "scripts",
    "sciprt": "script",
    "scirpt": "script",
    "scritpt": "script",
    "sript": "script",
    "scrpt": "script",
    "diem": "dime",
    "dieme": "dime",
    "porfavor": "por favor",
    "ejeuctar": "ejecutar",
    "ejecutra": "ejecutar",
    "ejecurar": "ejecutar",
    "entreanr": "entrenar",
    "entrenra": "entrenar",
    "proonstico": "pronostico",
    "targest": "targets",
    "tragets": "targets",
    "taragets": "targets",
    "aydua": "ayuda",
    "ayuad": "ayuda",
    "auuda": "ayuda",
    "comados": "comandos",
    "coamndos": "comandos",
    "piepline": "pipeline",
    "pipelien": "pipeline",
    "estadsiticas": "estadisticas",
    "estadisitcas": "estadisticas",
    "hsitorial": "historial",
    "hisotrial": "historial",
    "carptea": "carpeta",
    "crapta": "carpeta",
    "carepeta": "carpeta",
    "arhcivo": "archivo",
    "archvio": "archivo",
    "comapara": "compara",
    "comaparar": "comparar",
    "comapra": "compara",
    "buenaaas": "buenas",
    "buenaas": "buenas",
    "holaa": "hola",
    "holaaa": "hola",
    "holaaaa": "hola",
    "hooola": "hola",
    "buenass": "buenas",
    "buenso": "buenos",
    "benas": "buenas",
    "beunas": "buenas",
    "nches": "noches",
    "tardes": "tardes",
    "diass": "dias",
}

GREETINGS = {
    "hola",
    "hey",
    "hi",
    "hello",
    "buenas",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "que onda",
    "sup",
    "ey",
    "saludos",
    "que tal",
    "como estas",
}

EXIT_WORDS = {
    "salir",
    "sal",
    "salte",
    "salirse",
    "salme",
    "salgase",
    "exit",
    "quit",
    "q",
    "bye",
    "adios",
    "chao",
    "fuera",
    "cerrar",
    "terminar",
    "fin",
    "reset",
    "apagar",
    "off",
    "me voy",
    "nos vemos",
    "vamonos",
    "ya me voy",
    "me salgo",
    "cierrate",
    "cierra",
}
# Prefijos que implican salir (captura "salte de aqui", "cerrar sesion", etc.)
_EXIT_PREFIXES = ("sal ", "salte ", "salirse ", "fuera ", "cerrar ", "me salgo ", "ya ", "cierr")
RESTART_WORDS = {"restart", "re-start", "reiniciar", "reinicia"}
CLEAR_WORDS = {"limpia", "clear", "cls", "limpiar"}


def normalize_typos(text: str) -> str:
    """Corrige typos comunes en la entrada."""
    result = text
    for typo, fix in TYPO_MAP.items():
        if typo in result:
            result = result.replace(typo, fix)
    return result


def _levenshtein(s1: str, s2: str) -> int:
    """Distancia de Levenshtein entre dos cadenas."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def fuzzy_suggest(word: str, candidates: list[str], max_dist: int = 2) -> str | None:
    """Sugiere el candidato mas cercano por distancia Levenshtein."""
    best = None
    best_dist = max_dist + 1
    for c in candidates:
        d = _levenshtein(word.lower(), c.lower())
        if d < best_dist:
            best_dist = d
            best = c
    return best if best_dist <= max_dist else None


_SHELL_INDICATORS = ("&&", "||", " | ", " > ", " >> ", " 2>", " < ", "$(", "`")
_SHELL_PREFIXES = (
    "cd ",
    "ls ",
    "cat ",
    "echo ",
    "grep ",
    "find ",
    "rm ",
    "cp ",
    "mv ",
    "mkdir ",
    "touch ",
    "chmod ",
    "chown ",
    "curl ",
    "wget ",
    "ssh ",
    "docker ",
    "git ",
    "pip ",
    "npm ",
    "node ",
    "python ",
    "python3 ",
    "pytest ",
    "bash ",
    "sh ",
    "zsh ",
    "sudo ",
    "export ",
    "source ",
    "tail ",
    "head ",
    "sed ",
    "awk ",
    "sort ",
    "uniq ",
    "wc ",
)


def classify_intent(cmd: str) -> str | None:
    """Clasifica la intencion del usuario. Retorna nombre de intent o None."""
    stripped = cmd.rstrip("!.?\u00bf\u00a1 ")

    def _match(*keywords: str) -> bool:
        return any(kw in cmd for kw in keywords)

    # Comandos shell directos (no son intents de EPI)
    if any(ind in cmd for ind in _SHELL_INDICATORS) or cmd.startswith(_SHELL_PREFIXES):
        return "shell_command"

    # Saludos (exacto o inicio con saludo conocido)
    if stripped in GREETINGS or any(cmd.startswith(g + " ") or cmd == g for g in GREETINGS):
        return "saludo"

    # Reiniciar (antes de salir, para no capturar restart como exit)
    if stripped in RESTART_WORDS:
        return "reiniciar"

    # Salir
    if stripped in EXIT_WORDS or cmd.startswith(_EXIT_PREFIXES):
        return "salir"

    # Limpiar pantalla
    if stripped in CLEAR_WORDS:
        return "limpiar"

    # Banner
    if stripped in ("banner", "inicio"):
        return "banner"

    # Dashboard / panel
    if stripped in ("dashboard", "panel", "tablero", "resumen general"):
        return "dashboard"

    # Targets (antes de chat, para capturar "que make hay?", "comandos disponibles", etc.)
    has_make_or_target = _match("make", "target", "comando")
    has_list_intent = _match(
        "disponible",
        "ejecutar",
        "cuales",
        "que hay",
        "hay",
        "puedo",
        "lista",
        "muestra",
        "dime",
        "cuantos",
    )
    if has_make_or_target and has_list_intent:
        return "targets"

    # Ayuda (capturar antes de chat para que "muestrame la ayuda" no vaya a IA)
    if _match("ayuda", "help") or stripped in ("?", "h"):
        return "ayuda"

    # Chat / pregunta IA
    if (
        cmd.endswith("?")
        or _match("pregunta", "chat", "explica")
        or cmd.startswith("que es ")
        or cmd.startswith("qual es ")
        or cmd.startswith("cual es ")
        or cmd.startswith("quien ")
        or cmd.startswith("quienes ")
        or cmd.startswith("cuantos ")
        or cmd.startswith("cuantas ")
        or cmd.startswith("cuanto ")
        or cmd.startswith("cuando ")
        or cmd.startswith("donde ")
        or cmd.startswith("por que ")
        or cmd.startswith("como funciona ")
        or cmd.startswith("como va ")
        or cmd.startswith("que dia")
        or cmd.startswith("que paso ")
        or cmd.startswith("dame ")
        or cmd.startswith("dime ")
        or cmd.startswith("dinos ")
        or cmd.startswith("sabes ")
        or cmd.startswith("muestrame ")
        or cmd.startswith("comparame ")
        or cmd.startswith("que tan ")
        or cmd.startswith("resumeme ")
        or cmd.startswith("a cuanto ")
        or cmd.startswith("y nosotros ")
        or cmd.startswith("y cuanto ")
        or cmd.startswith("y que ")
        or cmd.startswith("y como ")
        or cmd.startswith("y por que ")
        or cmd.startswith("y entonces ")
        or cmd.startswith("y cual ")
        or _match("metricas de", "metrica de", "smape de", "mase de", "rmse de")
        or _match("equipo", "integrantes", "autores", "creadores")
    ):
        return "chat"

    # Datos / explorador
    if stripped.startswith("datos") or _match(
        "explorador de datos", "resumen datos", "resumen boletin", "boletin"
    ):
        return "datos"

    # Modelos / navegador
    if (
        stripped.startswith("modelos")
        or stripped.startswith("modelo ")
        or _match("navegador de modelos", "modelos produccion")
    ):
        return "modelos"

    # Pronostico / visor
    if (
        stripped.startswith("pronostico ")
        or stripped.startswith("forecast ")
        or _match("visor de pronostico")
    ):
        return "pronostico"

    # Comparar modelos (tabla rapida)
    if stripped.startswith("compara ") or stripped.startswith("comparar "):
        return "comparar_modelos"

    # Scripts / archivos .py
    execution_verbs = (
        "corre",
        "ejecuta",
        "lanza",
        "run",
        "corriendo",
        "arranca",
        "inicia",
        "activa",
    )
    wants_to_run = any(cmd.startswith(v) or f" {v} " in f" {cmd} " for v in execution_verbs)
    if not wants_to_run and (
        _match(".py")
        or (
            _match("script")
            and _match(
                "lista",
                "ver",
                "muestra",
                "cual",
                "que",
                "hay",
                "tiene",
                "disponible",
                "dime",
                "dame",
                "carpeta",
                "cuanto",
            )
        )
        or (
            _match("archivo", "python")
            and _match(
                "lista",
                "ver",
                "muestra",
                "cual",
                "que",
                "dime",
                "dame",
            )
        )
        or (_match("carpeta") and _match("script"))
    ):
        return "scripts"

    # Calidad / Quality
    if stripped in ("calidad", "quality", "limpieza", "clean-py") or _match(
        "make lint", "make format", "make typecheck", "make quality", "make test-fast"
    ):
        return "calidad"

    # Ayuda (frases largas — el check basico ya esta arriba, antes de chat)
    if _match(
        "puedo hacer",
        "podemos hacer",
        "puedes hacer",
        "que hago",
        "para que sirve",
        "como te uso",
        "que sabes hacer",
        "que sabes",
        "que ofreces",
        "funciones",
        "funcionalidades",
        "capacidades",
        "instrucciones",
        "como empiezo",
        "por donde empiezo",
        "que haces",
        "como opero",
        "menu",
    ):
        return "ayuda"

    # Targets
    if _match(
        "target",
        "comando",
        "command",
        "disponible",
        "puedo ejecutar",
        "que hay",
        "opciones",
        "make disponible",
        "que make",
    ):
        return "targets"

    # Estadisticas
    if _match("stats", "estadistica", "estadisticas", "status", "metricas de sesion", "como voy"):
        return "stats"

    # Logs
    if _match("log", "bitacora", "registros"):
        return "logs"

    # Pipeline
    if _match("pipeline", "pipe", "flujo", "etapas", "fases"):
        return "pipeline"

    # Salud
    if _match("salud", "health", "diagnostico", "verificar", "chequeo"):
        return "salud"

    # Historial
    if _match("historial", "history", "hist"):
        return "historial"

    return None


def extract_folder_filter(cmd: str) -> str | None:
    """Extrae filtro de carpeta de un comando de scripts."""
    noise = {
        "carpeta",
        "folder",
        "directorio",
        "la",
        "el",
        "los",
        "las",
        "de",
        "del",
        "hay",
        "que",
    }

    # "en scripts", "de src", "dentro de tests", "carpeta scripts"
    prep_match = re.search(
        r"(?:en|dentro de|carpeta|folder|directorio)\s+(?:la\s+)?(?:carpeta\s+)?"
        r"['\"]?([a-zA-Z0-9_/.:-]+)",
        cmd,
    )
    if prep_match:
        candidate = prep_match.group(1).strip("'\"?!. /")
        if candidate and candidate not in noise and len(candidate) > 1:
            return candidate

    # "los de scripts", "solo de src"
    de_match = re.search(
        r"(?:los\s+de|solo\s+de|solo\s+los\s+de|carpetas\s+de)\s+"
        r"['\"]?([a-zA-Z0-9_/.:-]+)",
        cmd,
    )
    if de_match:
        candidate = de_match.group(1).strip("'\"?!. /")
        if candidate and len(candidate) > 1:
            return candidate

    # "solo <carpeta>"
    solo_match = re.search(r"solo\s+['\"]?([a-zA-Z0-9_/.:-]+)", cmd)
    if solo_match:
        candidate = solo_match.group(1).strip("'\"?!. /")
        script_noise = {
            "scripts",
            "script",
            ".py",
            "py",
            "python",
            "archivos",
            "archivo",
            "que",
            "los",
            "las",
            "del",
        }
        if candidate and candidate not in script_noise and len(candidate) > 1:
            return candidate

    return None
