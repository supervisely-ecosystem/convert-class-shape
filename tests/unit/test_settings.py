import pytest

from src.settings import Settings


def test_project_from_modal_state(monkeypatch):
    for key in ("CONTEXT_PROJECTID", "context.projectId", "PROJECT_ID", "modal.state.inputProjectId"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("modal.state.slyProjectId", "376")
    assert Settings.from_env() == Settings(project_id=376)


def test_missing_project_fails_with_a_clear_message(monkeypatch):
    for key in (
        "CONTEXT_PROJECTID",
        "context.projectId",
        "modal.state.slyProjectId",
        "PROJECT_ID",
        "modal.state.inputProjectId",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="context menu"):
        Settings.from_env()
