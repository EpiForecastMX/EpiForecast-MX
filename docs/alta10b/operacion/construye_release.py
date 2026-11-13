"""Construye, promueve y verifica el release de cada id (registry en trained con runner_runs y commiteado).
Uso (en el worktree): construye_release.py <id>...  Imprime id release_id; falla cerrado."""
import sys
from pathlib import Path
from epiforecast import registry
from epiforecast.runner.release_entry import build_release_for_disease
from epiforecast.runner.release_store import promote_release
from epiforecast.runner.release_loader import verify_bundle
for i in sys.argv[1:]:
    pol = registry.require(i).selection_policy
    built = build_release_for_disease(i, runs_root=Path('runs'), policy_path=Path(f'config/evaluation/{pol}.yaml'),
                                      output_root=Path('runs/_release_build'))
    promoted = promote_release(built.path, releases_root=Path('artifacts/releases'), disease_id=i)
    root = getattr(promoted, 'path', None) or getattr(promoted, 'root', None)
    v = verify_bundle(Path(root))
    print(i, v.release_id, v.chain.get('acceptance_outcome', 'accepted'), dict(v.engines), flush=True)
