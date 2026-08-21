from packages.schemas.models import GeneratedExperiment
from services.coder.bundle import build_source_bundle
from services.coder.generator import (
    ensure_import_requirements,
    normalize_python311_requirements,
    package_generated_experiment,
)


def test_generated_experiment_gets_nonnegotiable_runtime_wrapper() -> None:
    files = package_generated_experiment(
        GeneratedExperiment(
            run_py="print('actual calculation')",
            requirements_txt="numpy==2.3.1",
            rationale="Small CPU reproduction",
        )
    )
    payload, digest = build_source_bundle(files)
    assert payload and len(digest) == 64
    assert "OUTPUT_GCS_URI" in files["replicator_entrypoint.py"]
    assert "if_generation_match=0" in files["replicator_entrypoint.py"]
    assert "stderr.log" in files["replicator_entrypoint.py"]
    assert 'out / "metrics.json"' in files["replicator_entrypoint.py"]
    assert "ENTRYPOINT" in files["Dockerfile"]


def test_python311_requirement_gate_repairs_incompatible_numba() -> None:
    repaired = normalize_python311_requirements("numpy==1.23.5\nnumba==0.56.4\n")
    assert repaired == "numpy==1.23.5\nnumba==0.59.1"


def test_import_gate_adds_missing_matplotlib_pin() -> None:
    repaired = ensure_import_requirements("import matplotlib.pyplot as plt", "numpy==1.26.4")
    assert repaired == "numpy==1.26.4\nmatplotlib==3.8.4"
