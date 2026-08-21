from packages.schemas.models import GeneratedExperiment
from services.coder.bundle import build_source_bundle
from services.coder.generator import package_generated_experiment


def test_generated_experiment_gets_nonnegotiable_runtime_wrapper() -> None:
    files = package_generated_experiment(GeneratedExperiment(
        run_py="print('actual calculation')", requirements_txt="numpy==2.3.1",
        rationale="Small CPU reproduction"))
    payload, digest = build_source_bundle(files)
    assert payload and len(digest) == 64
    assert "OUTPUT_GCS_URI" in files["replicator_entrypoint.py"]
    assert "if_generation_match=0" in files["replicator_entrypoint.py"]
    assert "ENTRYPOINT" in files["Dockerfile"]
