"""Motor principal de ejecucion: EpiEngine y SessionStats."""

from collections.abc import Callable
from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess

import google.generativeai as genai

from .theme import RISK_LEVELS


class SessionStats:
    """Estadisticas acumuladas de la sesion actual."""

    def __init__(self) -> None:
        self.started_at = datetime.now()
        self.commands_run: list[dict] = []
        self.successes = 0
        self.failures = 0
        self.cancelled = 0
        self.total_duration = timedelta()

    def record(self, cmd: str, success: bool, duration: timedelta) -> None:
        self.commands_run.append(
            {
                "cmd": cmd,
                "success": success,
                "duration": duration,
                "timestamp": datetime.now(),
            }
        )
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.total_duration += duration

    def cancel(self) -> None:
        self.cancelled += 1

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def uptime(self) -> str:
        delta = datetime.now() - self.started_at
        mins, secs = divmod(int(delta.total_seconds()), 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs}h {mins}m {secs}s"
        return f"{mins}m {secs}s"


class EpiEngine:
    """Motor robusto de ejecucion y logica de EpiForecast-MX."""

    def __init__(self) -> None:
        self.targets: dict[str, str] = {}
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name: str | None = None
        self.history: list[str] = []
        self.stats = SessionStats()

        # Mapeo de frases en espanol -> targets
        self.phrase_map: list[tuple[list[str], str, str]] = [
            # keywords_requeridos, target, explicacion
            (["compliance"], "quality", "Verificación de calidad y compliance del código."),
            (["calidad"], "quality", "Verificación de calidad del código."),
            (["quality"], "quality", "Verificación de calidad del código."),
            (["lint"], "lint", "Análisis estático del código."),
            (["format"], "format", "Formateo automático del código."),
            (["tipo", "check"], "typecheck", "Verificación de tipos con mypy."),
            (["typecheck"], "typecheck", "Verificación de tipos con mypy."),
            (["mypy"], "typecheck", "Verificación de tipos con mypy."),
            (["prueba"], "test", "Ejecuta la suite de pruebas completa."),
            (["test"], "test", "Ejecuta la suite de pruebas."),
            (["test", "rapid"], "test-fast", "Ejecuta pruebas rápidas (sin lentas)."),
            (["cobertura"], "coverage", "Reporte de cobertura de pruebas."),
            (["coverage"], "coverage", "Reporte de cobertura de pruebas."),
            (["entren", "todo"], "train-all", "Entrena todos los modelos."),
            (["entren", "prophet"], "train-prophet", "Entrena modelos Prophet."),
            (["entren", "deepar"], "train-deepar", "Entrena modelos DeepAR."),
            (["entren", "sagemaker"], "train-sagemaker", "Entrena en SageMaker."),
            (["entren", "stacking"], "train-stacking", "Entrena modelo Stacking."),
            (["entren"], "train", "Entrena los modelos."),
            (["train"], "train", "Entrena los modelos."),
            (["pronostic"], "predict", "Genera pronósticos."),
            (["predic"], "predict", "Genera predicciones."),
            (["predict"], "predict", "Genera predicciones."),
            (["forecast"], "predict", "Genera pronósticos."),
            (["extrae", "dato"], "get-dataset", "Extrae el dataset."),
            (["descarg", "dato"], "get-dataset", "Descarga el dataset."),
            (["dataset"], "get-dataset", "Obtiene el dataset."),
            (["inegi"], "get-inegi", "Descarga datos de INEGI."),
            (["preproces"], "preprocess", "Ejecuta preprocesamiento de datos."),
            (["transform"], "transform", "Transforma los datos."),
            (["filtr"], "filter", "Filtra datos por padecimiento."),
            (["mapea"], "mapper", "Ejecuta mapeo de datos."),
            (["limpi", "dato"], "clean", "Limpia datos procesados."),
            (["data", "pull"], "data-pull", "Descarga datos versionados (DVC pull)."),
            (["data", "push"], "data-push", "Sube datos versionados (DVC push)."),
            (["data", "status"], "data-status", "Estado de datos versionados (DVC status)."),
            (["jala", "dato"], "data-pull", "Descarga datos versionados."),
            (["sube", "dato"], "data-push", "Sube datos versionados."),
            (["estado", "dato"], "data-status", "Estado de datos versionados."),
            (["reporte"], "report", "Genera reporte HTML."),
            (["report"], "report", "Genera reporte HTML."),
            (["tableau"], "tableau", "Genera datos para Tableau."),
            (["bitacora"], "bitacora", "Genera bitácora del proyecto."),
            (["compar", "metric"], "compare-metrics", "Compara métricas entre modelos."),
            (["compar", "modelo"], "compare", "Compara modelos."),
            (["compar"], "compare", "Compara modelos."),
            (["setup", "mac"], "setup-mac", "Configura entorno en macOS."),
            (["setup", "linux"], "setup-linux", "Configura entorno en Linux."),
            (["setup"], "setup", "Configura el entorno del proyecto."),
            (["instal", "depend"], "requirements", "Instala dependencias."),
            (["requirements"], "requirements", "Instala dependencias."),
            (["dependencia"], "requirements", "Instala dependencias."),
            (["entorno", "crea"], "create-env", "Crea el entorno virtual."),
            (["crea", "env"], "create-env", "Crea el entorno virtual."),
            (["hooks"], "hooks", "Instala git hooks."),
            (["limpi", "python"], "clean-py", "Limpia archivos Python temporales."),
            (["clean"], "clean", "Limpia artefactos generados."),
            (["limpi"], "clean", "Limpia artefactos generados."),
            (["reset", "proyecto"], "reset", "Resetea el proyecto."),
            (["reinici", "proyecto"], "reset", "Resetea el proyecto."),
            (["pipeline", "model"], "model-pipeline", "Ejecuta pipeline completo de modelado."),
            (["model-pipeline"], "model-pipeline", "Ejecuta pipeline completo de modelado."),
            (["avance"], "avance5", "Genera artefactos de avance 5."),
        ]

    # -- Verificaciones -----------------------------------------------
    def check_environment(self) -> tuple[list[str], list[str]]:
        """Verifica dependencias. Retorna (errores, advertencias)."""
        errors: list[str] = []
        warnings_list: list[str] = []
        if not shutil.which("make"):
            errors.append("GNU Make no encontrado en PATH.")
        if not self.api_key:
            warnings_list.append("GEMINI_API_KEY no configurada — modo offline activado.")
        if not Path("Makefile").exists():
            errors.append("Makefile no encontrado en el directorio actual.")
        if not shutil.which("python") and not shutil.which("python3"):
            warnings_list.append("Python no detectado en PATH.")
        if not shutil.which("git"):
            warnings_list.append("Git no detectado — funciones de historial limitadas.")
        return errors, warnings_list

    def parse_makefile(self) -> None:
        """Extrae targets con descripciones del Makefile."""
        self.targets = {}
        try:
            with Path("Makefile").open() as f:
                content = f.read()
            for m in re.finditer(
                r"^([a-zA-Z0-9_-]+)\s*:.*?(?:##\s*(.*))?$",
                content,
                re.MULTILINE,
            ):
                name = m.group(1).strip()
                desc = (m.group(2) or "").strip() or "Sin descripción"
                skip = {
                    "PHONY",
                    ".PHONY",
                    ".DEFAULT_GOAL",
                    "all",
                    "help",
                    ".ONESHELL",
                    "ACTIVATE",
                    # Setup (ya configurado antes de usar EPI)
                    "requirements",
                    "setup",
                    "setup-linux",
                    "setup-mac",
                    "setup-linux-deps",
                    "create-env",
                    # Sub-etapas de preprocess (se ejecutan via make preprocess)
                    "get-dataset",
                    "filter",
                    "clean",
                    "transform",
                    "get-inegi",
                    "mapper",
                    # Calidad (herramientas de desarrollo, no operativas)
                    "lint",
                    "format",
                    "typecheck",
                    "test",
                    "test-fast",
                    "quality",
                    "hooks",
                    "clean-py",
                }
                if name not in skip and not name.startswith("."):
                    self.targets[name] = desc
            # Descripciones amigables para el operador
            desc_override = {
                "reset": "Reiniciar logs y carpetas temporales",
                "preprocess": "Flujo completo de preparación de datos",
                "train": "Entrenar modelo activo (CV + entrenamiento final)",
                "train-prophet": "Entrenar modelos Prophet",
                "train-deepar": "Entrenar modelos DeepAR",
                "train-stacking": "Entrenar Stacking (Prophet + ETS + LightGBM)",
                "train-ensemble": "Entrenar Ensemble (Prophet + XGBoost)",
                "train-all": "Entrenar los 4 modelos secuencialmente",
                "train-sagemaker": "Build Docker + lanzar DeepAR en SageMaker",
                "train-sagemaker-build": "Solo build de imagen Docker para SageMaker",
                "train-sagemaker-parallel": "3 jobs en paralelo en SageMaker",
                "train-sagemaker-fast": "Build + 3 jobs en paralelo en SageMaker",
                "train-sagemaker-local": "Test local con Docker (simula SageMaker)",
                "predict": "Generar pronósticos a 52 semanas",
                "predict-all": "Pronósticos con los 4 modelos",
                "tableau": "Construir dataset para Tableau",
                "report": "Generar reporte HTML de resultados",
                "bitacora": "Generar bitácora HTML del modelado",
                "compare": "Comparar Real vs los 4 modelos (gráficos)",
                "tabla-produccion": "Tabla de 333 modelos de producción (Excel)",
                "compare-metrics": "Comparativa de métricas (Excel + HTML)",
                "avance5": "Avance 5: Prophet Base vs Ensemble",
                "reporte-avance5": "Reporte Avance 5 (tablas + gráficos + Markdown)",
                "model-pipeline": "Flujo completo de modelado",
                "data-pull": "Descargar datos versionados desde S3",
                "data-push": "Subir datos versionados a S3",
                "data-add": "Agregar nuevo PDF semanal (PDF=ruta)",
                "data-commit": "Commitear datos + push a Git y S3",
                "data-weekly": "Flujo semanal completo (agregar + commit)",
                "data-status": "Ver estado de datos versionados (DVC)",
                "models-push": "Versionar modelos y subir a S3",
                "forecast-push": "Versionar pronósticos y subir a S3",
                "s3-sync": "Sincronizar CSVs directo a S3 (sin DVC)",
            }
            for t, d in desc_override.items():
                if t in self.targets:
                    self.targets[t] = d
        except Exception as e:
            logging.error(f"Error parseando Makefile: {e}")

    # -- IA -----------------------------------------------------------
    def find_model(self) -> str:
        if self.model_name:
            return self.model_name
        try:
            genai.configure(api_key=self.api_key)
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    self.model_name = m.name
                    return m.name
        except Exception:
            pass
        return "models/gemini-1.5-flash"

    def translate(self, prompt: str) -> dict:
        """Traduce lenguaje natural a comandos Make via IA, con fallback local."""
        prompt_lower = prompt.lower()

        # 1. Mapper local de frases -> targets
        best_match = None
        best_score = 0
        for keywords, target, explanation in self.phrase_map:
            if target not in self.targets:
                continue
            if all(kw in prompt_lower for kw in keywords):
                score = len(keywords)
                if score > best_score:
                    best_score = score
                    best_match = (target, explanation)

        if best_match:
            target, explanation = best_match
            return {
                "commands": [f"make {target}"],
                "is_valid": True,
                "error": None,
                "explanation": explanation,
            }

        # 2. Busqueda directa por nombre de target
        for target_name in self.targets:
            if target_name in prompt_lower.replace("-", " ").replace("_", " "):
                return {
                    "commands": [f"make {target_name}"],
                    "is_valid": True,
                    "error": None,
                    "explanation": f"Target '{target_name}' detectado en la instrucción.",
                }

        # 3. Fallback a Gemini
        if not self.api_key:
            return {
                "is_valid": False,
                "error": "No pude mapear esa instrucción a un target conocido.",
                "suggestion": "Escribe 'targets' para ver los comandos disponibles.",
            }

        model_uri = self.find_model()
        ctx_lines = "\n".join(
            [f"  - make {n}: {d}" for n, d in self.targets.items()],
        )
        system_msg = (
            "Eres el motor de inteligencia de EpiForecast-MX (IMSS).\n"
            "Conviertes instrucciones en espanol o ingles a comandos `make`.\n\n"
            f"TARGETS DISPONIBLES:\n{ctx_lines}\n\n"
            "REGLAS ESTRICTAS:\n"
            "1. Devuelve SOLO JSON valido.\n"
            "2. is_valid: false si es saludo, pregunta general o no mapea a ningun target.\n"
            "3. Puedes encadenar multiples targets si la instruccion lo requiere.\n"
            '4. Formato: {"commands": ["make <target>"], "is_valid": true, '
            '"error": null, "explanation": "breve explicacion"}\n'
            '5. Si no es valido: {"commands": [], "is_valid": false, '
            '"error": "razon clara", "suggestion": "sugerencia util"}'
        )
        try:
            model = genai.GenerativeModel(model_uri)
            response = model.generate_content(
                f"{system_msg}\n\nInstruccion del operador: {prompt}",
                generation_config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)
        except Exception as e:
            logging.error(f"Error en IA: {e}")
            return {
                "is_valid": False,
                "error": "IA no disponible. Usa el mapper local.",
                "suggestion": "Escribe 'targets' para ver comandos.",
            }

    # -- Riesgo -------------------------------------------------------
    def assess_risk(self, command: str) -> str:
        """Clasifica el nivel de riesgo de un comando."""
        cmd_lower = command.lower()
        for level in ["high", "medium", "low"]:
            if any(kw in cmd_lower for kw in RISK_LEVELS[level]):
                return level
        return "low"

    # -- Ejecucion ----------------------------------------------------
    def execute_with_output(
        self,
        cmd: str,
        live_callback: "Callable[[str], None] | None" = None,
    ) -> tuple[int, str, str, timedelta]:
        """Ejecuta un comando con streaming opcional de salida.

        Args:
            cmd: Comando a ejecutar.
            live_callback: Si se provee, se llama con cada linea de stdout
                           en tiempo real. La salida completa se acumula
                           igualmente para el result card.
        """
        start = datetime.now()
        try:
            if live_callback is None:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=72000,
                )
                duration = datetime.now() - start
                return result.returncode, result.stdout, result.stderr, duration

            # Streaming: leer stdout linea a linea
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            stdout_lines: list[str] = []
            assert proc.stdout is not None  # noqa: S101
            for line in proc.stdout:
                stdout_lines.append(line)
                live_callback(line.rstrip("\n"))
            proc.wait(timeout=72000)
            stderr = proc.stderr.read() if proc.stderr else ""
            duration = datetime.now() - start
            return proc.returncode or 0, "".join(stdout_lines), stderr, duration
        except subprocess.TimeoutExpired:
            duration = datetime.now() - start
            return -1, "", "Timeout: el comando excedió 20 horas.", duration
        except Exception as e:
            duration = datetime.now() - start
            return -1, "", str(e), duration
