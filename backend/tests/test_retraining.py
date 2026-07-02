"""Tests for continuous retraining pipeline (SCA-46)."""
import json
import asyncio
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeCollection:
    def __init__(self):
        self._data = {}
        self.find_one = MagicMock(return_value=None)
        self.insert_one = MagicMock()
        self.update_one = MagicMock()
        self.count_documents = MagicMock(return_value=0)
        self.find = MagicMock()
        self.find.return_value.sort.return_value.limit.return_value = []


@ pytest.fixture
def mock_db():
    db = MagicMock()
    col = {}
    def get_col(name):
        if name not in col:
            col[name] = FakeCollection()
        return col[name]
    db.__getitem__.side_effect = get_col
    return db


@pytest.fixture
def mock_drive_result():
    return {
        "status": "complete",
        "f1": 0.96,
        "auc": 0.97,
        "artifacts": ["agent_01_v20260702.pkl", "agent_02_v20260702.pkl"],
        "version": "20260702_130000",
    }


@pytest.fixture
def mock_manifest():
    return {
        "version": "1.2.3",
        "agents": {
            "agent_01": {"artifact": "models/agent_01_old.pkl", "status": "ready"},
            "agent_02": {"artifact": "models/agent_02_old.pkl", "status": "ready"},
        },
    }


# ---------------------------------------------------------------------------
# Test 1: retrain_config doc auto-created when missing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrain_config_auto_created(monkeypatch, mock_db):
    monkeypatch.setattr("jobs.retraining_trigger.MongoDBClient.db", lambda: mock_db)

    import jobs.retraining_trigger as rt
    rt.BATCH_THRESHOLD = 500
    rt_col = mock_db["retrain_config"]
    rt_col.find_one.return_value = None

    sr_col = mock_db["scam_reports"]
    sr_col.count_documents.return_value = 0

    mock_trig = MagicMock()
    monkeypatch.setattr(rt, "_trigger_fn", mock_trig)
    result = await rt._check_and_fire()

    assert result is False, "Should not fire with 0 reports"
    assert rt_col.insert_one.called
    args = rt_col.insert_one.call_args[0][0]
    assert args["_id"] == "state"
    assert args["last_count"] == 0


# ---------------------------------------------------------------------------
# Test 2: trigger does NOT fire at 499 reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_does_not_fire_at_499(monkeypatch, mock_db):
    monkeypatch.setattr("jobs.retraining_trigger.MongoDBClient.db", lambda: mock_db)

    import jobs.retraining_trigger as rt
    rt.BATCH_THRESHOLD = 500
    rt_col = mock_db["retrain_config"]
    rt_col.find_one.return_value = {"_id": "state", "last_count": 0, "last_run": None}

    sr_col = mock_db["scam_reports"]
    sr_col.count_documents.return_value = 499

    mock_trig = MagicMock()
    monkeypatch.setattr(rt, "_trigger_fn", mock_trig)
    result = await rt._check_and_fire()

    assert result is False, "Trigger fired at 499"
    assert not mock_trig.called
    assert not rt_col.update_one.called


# ---------------------------------------------------------------------------
# Test 3: trigger fires at exactly 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_fires_at_500(monkeypatch, mock_db):
    monkeypatch.setattr("jobs.retraining_trigger.MongoDBClient.db", lambda: mock_db)

    import jobs.retraining_trigger as rt
    rt.BATCH_THRESHOLD = 500
    rt_col = mock_db["retrain_config"]
    rt_col.find_one.return_value = {"_id": "state", "last_count": 0, "last_run": None}

    sr_col = mock_db["scam_reports"]
    sr_col.count_documents.return_value = 500
    sr_col.find.return_value.sort.return_value.limit.return_value = [
        {"_id": f"rec{i}", "text": "test"} for i in range(500)
    ]

    async def fake_trigger(records):
        pass

    monkeypatch.setattr(rt, "_trigger_fn", fake_trigger)
    result = await rt._check_and_fire()

    assert result is True, "Trigger should fire at 500"
    assert rt_col.update_one.called


# ---------------------------------------------------------------------------
# Test 4: trigger does NOT double-fire (last_count updated before job)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_no_double_fire(monkeypatch, mock_db):
    monkeypatch.setattr("jobs.retraining_trigger.MongoDBClient.db", lambda: mock_db)

    import jobs.retraining_trigger as rt
    rt.BATCH_THRESHOLD = 500
    rt_col = mock_db["retrain_config"]
    rt_col.find_one.return_value = {"_id": "state", "last_count": 0, "last_run": None}

    sr_col = mock_db["scam_reports"]
    sr_col.count_documents.return_value = 500

    update_call_args = []

    def fake_update_one(filter_, update):
        update_call_args.append((filter_, update))

    rt_col.update_one.side_effect = fake_update_one

    async def fake_trigger(records):
        pass

    monkeypatch.setattr(rt, "_trigger_fn", fake_trigger)
    result = await rt._check_and_fire()

    assert result is True
    assert len(update_call_args) >= 1
    last_count_set = update_call_args[0][1]["$set"]["last_count"]
    assert last_count_set == 500, "last_count should be 500 before job fires"


# ---------------------------------------------------------------------------
# Test 5: quality_gate passes when F1=0.96, AUC=0.97
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quality_gate_passes():
    from jobs.quality_gate import quality_gate
    result = {"f1": 0.96, "auc": 0.97}
    with patch("jobs.quality_gate.send_slack", return_value=None) as mock_slack:
        outcome = await quality_gate(result)
    assert outcome is True
    assert mock_slack.called
    assert "PASSED" in mock_slack.call_args[0][0]


# ---------------------------------------------------------------------------
# Test 6: quality_gate fails when F1=0.91 (below 0.94)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quality_gate_fails_f1_low():
    from jobs.quality_gate import quality_gate
    result = {"f1": 0.91, "auc": 0.96}
    with patch("jobs.quality_gate.send_slack", return_value=None) as mock_slack:
        outcome = await quality_gate(result)
    assert outcome is False
    assert mock_slack.called
    assert "ABORTED" in mock_slack.call_args[0][0]


# ---------------------------------------------------------------------------
# Test 7: quality_gate fails when AUC=0.93 (below 0.95)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quality_gate_fails_auc_low():
    from jobs.quality_gate import quality_gate
    result = {"f1": 0.95, "auc": 0.93}
    with patch("jobs.quality_gate.send_slack", return_value=None) as mock_slack:
        outcome = await quality_gate(result)
    assert outcome is False
    assert mock_slack.called
    assert "ABORTED" in mock_slack.call_args[0][0]


# ---------------------------------------------------------------------------
# Test 8: model_promoter bumps version 1.2.3 -> 1.2.4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_model_promoter_bumps_version(mock_drive_result, mock_manifest):
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": MagicMock()}
    mock_s3.get_object.return_value["Body"].read.return_value = json.dumps(mock_manifest).encode()

    from jobs.model_promoter import promote_model
    with patch("jobs.model_promoter._s3_client", mock_s3):
        with patch("utils.slack_alerts.send_slack", return_value=None):
            with patch("app.database_ext.MongoDBClient.db", return_value=MagicMock()):
                await promote_model(mock_drive_result)

    put_calls = [c for c in mock_s3.put_object.call_args_list]

    manifest_put = None
    for call_args in put_calls:
        if len(call_args) >= 2:
            kwargs = call_args[1]
        elif len(call_args) == 1:
            kwargs = call_args[0]
        else:
            continue
        if isinstance(kwargs, dict) and kwargs.get("Key") == "manifest.json":
            body = kwargs["Body"]
            manifest_put = json.loads(body) if isinstance(body, str) else body
            break

    assert manifest_put is not None, "manifest.json should have been uploaded"
    if isinstance(manifest_put, dict):
        assert manifest_put["version"] == "1.2.4"


# ---------------------------------------------------------------------------
# Test 9: model_promoter restores manifest_prev.json on R2 write failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_model_promoter_rollback(mock_drive_result, mock_manifest):
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": MagicMock()}
    mock_s3.get_object.return_value["Body"].read.return_value = json.dumps(mock_manifest).encode()

    call_count = 0

    def fake_put_object(**kwargs):
        nonlocal call_count
        call_count += 1
        if kwargs.get("Key") == "manifest.json":
            raise Exception("R2 write failed")

    mock_s3.put_object.side_effect = fake_put_object

    from jobs.model_promoter import promote_model

    with patch("jobs.model_promoter._s3_client", mock_s3):
        with patch("utils.slack_alerts.send_slack", return_value=None):
            with patch("app.database_ext.MongoDBClient.db", return_value=MagicMock()):
                await promote_model(mock_drive_result)

    assert mock_s3.copy_object.called, "copy_object should have been called for rollback"
    copy_kwargs = mock_s3.copy_object.call_args[1]
    assert copy_kwargs["Key"] == "manifest.json"
    assert copy_kwargs["CopySource"]["Key"] == "manifest_prev.json"
