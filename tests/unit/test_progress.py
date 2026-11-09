from frontend.components.progress import (
    is_final,
    outcome,
    progress_fraction,
    progress_text,
)


def status(stage=None, done=0, total=0, **kwargs):
    progress = {"stage": stage, "done": done, "total": total} if stage else None
    return {"status": "processing", "progress": progress, **kwargs}


def test_progress_fraction():
    assert progress_fraction({"status": "processing"}) == 0.0
    assert progress_fraction(status("queued")) == 0.0
    assert progress_fraction(status("reading", 0, 1)) == 0.0
    assert progress_fraction(status("extraction", 0, 1)) == 0.05
    assert progress_fraction(status("extraction", 5, 10)) == 0.35
    assert progress_fraction(status("risk", 1, 2)) == 0.825
    assert progress_fraction(status("extraction", 12, 10)) == 0.65  # never above its share


def test_progress_text():
    assert "3/10 passages" in progress_text(status("extraction", 3, 10))
    assert "Lecture" in progress_text(status("reading", 0, 1))
    assert "En attente" in progress_text(status("queued"))
    assert progress_text({"status": "processing"}) == "Analyse en cours"


def test_is_final():
    assert is_final({"status": "needs_review"}) is True
    assert is_final({"status": "failed"}) is True
    assert is_final({"status": "processing"}) is False


def test_outcome():
    assert outcome({"status": "failed"})[0] == "error"
    assert outcome({"status": "needs_review", "run_status": "completed"})[0] == "success"
    assert outcome({"status": "processed", "run_status": "completed"})[0] == "success"
    assert outcome({"status": "uploaded"}) == (None, "")
    partial = outcome({"status": "needs_review", "run_status": "completed_with_errors"})
    assert partial[0] == "warning" and "incomplets" in partial[1]