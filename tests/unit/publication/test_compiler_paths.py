"""Guards puros de las rutas de staging del compilador."""

from pathlib import Path

import pytest

from epiforecast.publication.compiler import check_staging_root
from epiforecast.runner.artifact_identity import ArtifactValidationError

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]


def _repo_root() -> Path:
    assert (REPO / "pyproject.toml").is_file(), "la raíz calculada no es la del repo"
    return REPO


@pytest.mark.parametrize("publico", ["reports", "data", "epibot", "models", "artifacts"])
def test_candidate_no_puede_escribir_en_una_ruta_publica_del_repo(publico):
    repo = _repo_root()
    with pytest.raises(ArtifactValidationError, match="ruta pública"):
        check_staging_root(repo / publico / "staging", repo)


def test_candidate_acepta_un_staging_fuera_de_las_rutas_publicas(tmp_path):
    repo = _repo_root()
    assert check_staging_root(tmp_path / "staging", repo) == (tmp_path / "staging").resolve()
