from datetime import timedelta

from packages.schemas.models import Replication, ReplicationStatus, utcnow
from services.janitor.main import is_stalled


def test_janitor_marks_only_old_nonterminal_runs() -> None:
    old = utcnow() - timedelta(hours=4)
    cutoff = utcnow() - timedelta(hours=3)
    running = Replication(source_url="https://arxiv.org/abs/1706.03762",
        status=ReplicationStatus.RUNNING, updated_at=old)
    reported = running.model_copy(update={"status": ReplicationStatus.REPORTED})
    assert is_stalled(running, cutoff)
    assert not is_stalled(reported, cutoff)
