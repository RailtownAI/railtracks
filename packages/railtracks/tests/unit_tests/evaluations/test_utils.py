import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from railtracks.evaluations.result.evaluator_results import EvaluationResult
from railtracks.evaluations.utils import payload, save

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_evaluation_result() -> EvaluationResult:
    return EvaluationResult(
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
        evaluation_name="Test",
        agents=[
            {
                "agent_name": "AgentA",
                "agent_node_ids": [
                    {"session_id": uuid4(), "agent_node_id": uuid4()}
                ],
            }
        ],
        metrics_map={},
        evaluator_results=[],
    )


# ── payload ───────────────────────────────────────────────────────────────────


def test_payload_returns_dict():
    result = make_evaluation_result()
    p = payload(result)
    assert isinstance(p, dict)


def test_payload_contains_evaluation_id():
    result = make_evaluation_result()
    p = payload(result)
    assert "evaluation_id" in p
    assert p["evaluation_id"] == str(result.evaluation_id)


def test_payload_contains_evaluation_name():
    result = make_evaluation_result()
    p = payload(result)
    assert p["evaluation_name"] == "Test"


def test_payload_contains_timestamps():
    result = make_evaluation_result()
    p = payload(result)
    assert "created_at" in p
    assert "completed_at" in p


def test_payload_is_json_serializable():
    result = make_evaluation_result()
    p = payload(result)
    # Should not raise
    serialized = json.dumps(p)
    assert isinstance(serialized, str)


def test_payload_contains_agents():
    result = make_evaluation_result()
    p = payload(result)
    assert isinstance(p["agents"], list)
    assert p["agents"][0]["agent_name"] == "AgentA"


def test_payload_contains_evaluator_results():
    result = make_evaluation_result()
    p = payload(result)
    assert "evaluator_results" in p
    assert isinstance(p["evaluator_results"], list)


# ── save ──────────────────────────────────────────────────────────────────────


def test_save_writes_file(tmp_path, monkeypatch):
    import railtracks.evaluations.utils as utils_mod

    monkeypatch.setattr(utils_mod, "EVALS_DIR", tmp_path)

    result = make_evaluation_result()
    save([result])

    expected_file = tmp_path / f"{result.evaluation_id}.json"
    assert expected_file.exists()


def test_save_file_content_is_valid_json(tmp_path, monkeypatch):
    import railtracks.evaluations.utils as utils_mod

    monkeypatch.setattr(utils_mod, "EVALS_DIR", tmp_path)

    result = make_evaluation_result()
    save([result])

    fp = tmp_path / f"{result.evaluation_id}.json"
    content = json.loads(fp.read_text())
    assert content["evaluation_id"] == str(result.evaluation_id)


def test_save_duplicate_raises(tmp_path, monkeypatch):
    import railtracks.evaluations.utils as utils_mod

    monkeypatch.setattr(utils_mod, "EVALS_DIR", tmp_path)

    result = make_evaluation_result()
    save([result])

    with pytest.raises(Exception, match="already exists"):
        save([result])


def test_save_creates_parent_dirs(tmp_path, monkeypatch):
    import railtracks.evaluations.utils as utils_mod

    nested = tmp_path / "a" / "b" / "c"
    monkeypatch.setattr(utils_mod, "EVALS_DIR", nested)

    result = make_evaluation_result()
    save([result])

    assert (nested / f"{result.evaluation_id}.json").exists()


def test_save_multiple_results(tmp_path, monkeypatch):
    import railtracks.evaluations.utils as utils_mod

    monkeypatch.setattr(utils_mod, "EVALS_DIR", tmp_path)

    results = [make_evaluation_result(), make_evaluation_result()]
    save(results)

    for result in results:
        assert (tmp_path / f"{result.evaluation_id}.json").exists()
