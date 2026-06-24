import os
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException, Query

router = APIRouter(tags=["internal"])
logger = logging.getLogger("scamshield.dashboard")

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

def _require_internal_auth(authorization: Optional[str] = None):
    if not INTERNAL_API_KEY:
        logger.warning("INTERNAL_API_KEY not set — dashboard auth is disabled")
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.replace("Bearer ", "")
    if token != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/api/v1/internal/dashboard")
def internal_dashboard(
    authorization: str = Header(None),
    x_internal_key: Optional[str] = Header(None),
    minutes: int = Query(60, ge=1, le=43200, description="Lookback window in minutes"),
):
    _require_internal_auth(authorization or x_internal_key)

    from app.data_intel.dashboard_queries import (
        get_overview_metrics,
        get_quality_metrics,
        get_agent_quality_metrics,
        get_recent_anomalies,
        compute_feedback_stats,
        get_feedback_stats,
        get_bounty_results,
    )

    overview = get_overview_metrics(minutes)
    quality = get_quality_metrics(minutes)
    agents = get_agent_quality_metrics(minutes)
    anomalies = get_recent_anomalies(minutes)
    deploy_id = os.getenv("RAILWAY_DEPLOYMENT_ID", "local")

    delta = _compute_delta(deploy_id, overview, quality)

    feedback_stats = compute_feedback_stats()
    bounty = get_bounty_results(limit=5)

    return {
        "deployment_id": deploy_id,
        "time_window_minutes": minutes,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "overview": {
            "total_scans": overview["total_scans"],
            "by_channel": overview["by_channel"],
            "score_distribution": overview["score_distribution"],
        },
        "quality": {
            "approx_fn_fp": quality["approx_fn_fp"],
            "by_agent": agents,
        },
        "anomalies": anomalies,
        "feedback": {
            "feedback_counts_by_channel": feedback_stats.get("feedback_counts_by_channel", {}),
            "feedback_ratio_scams_vs_legit": feedback_stats.get("feedback_ratio_scams_vs_legit", 0),
            "total_scam": feedback_stats.get("total_scam", 0),
            "total_legit": feedback_stats.get("total_legit", 0),
            "total_unsure": feedback_stats.get("total_unsure", 0),
            "top_confusing_scans": feedback_stats.get("top_confusing_scans", []),
        },
        "bounty": {
            "last_5_runs": bounty,
        },
        "delta_vs_previous_deploy": delta,
    }


def _snapshot_path():
    data_dir = os.getenv("SNAPSHOT_DIR", "/tmp")
    return os.path.join(data_dir, "dashboard_snapshot.json")


def _compute_delta(deploy_id: str, overview: dict, quality: dict) -> dict:
    import json as _json
    snap_path = _snapshot_path()
    previous = None
    if os.path.exists(snap_path):
        try:
            with open(snap_path) as f:
                previous = _json.load(f)
        except Exception:
            pass

    current = {
        "deployment_id": deploy_id,
        "high_risk_ratio": overview.get("high_risk_ratio", 0),
        "by_channel": overview.get("by_channel", {}),
        "approx_fn_fp": quality.get("approx_fn_fp", {}),
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
    }
    try:
        os.makedirs(os.path.dirname(snap_path), exist_ok=True)
        with open(snap_path, "w") as f:
            _json.dump(current, f, indent=2, default=str)
    except Exception:
        pass

    if not previous:
        return {"message": "No previous deploy snapshot available"}

    prev_id = previous.get("deployment_id", "?")
    delta = {"previous_deploy": prev_id, "current_deploy": deploy_id}

    prev_by_ch = previous.get("by_channel", {})
    curr_by_ch = current.get("by_channel", {})
    ch_deltas = {}
    for ch in set(list(prev_by_ch.keys()) + list(curr_by_ch.keys())):
        prev_data = prev_by_ch.get(ch, {})
        curr_data = curr_by_ch.get(ch, {})
        prev_hr = prev_data.get("high_risk", 0)
        curr_hr = curr_data.get("high_risk", 0)
        prev_total = prev_data.get("total", 0)
        curr_total = curr_data.get("total", 0)
        prev_ratio = prev_hr / prev_total if prev_total > 0 else 0
        curr_ratio = curr_hr / curr_total if curr_total > 0 else 0
        ch_deltas[ch] = {
            "high_risk_ratio_change": round(curr_ratio - prev_ratio, 4),
            "total_change": curr_total - prev_total,
        }
    delta["high_risk_ratio_by_channel"] = ch_deltas

    prev_fnfp = previous.get("approx_fn_fp", {})
    curr_fnfp = current.get("approx_fn_fp", {})
    fnfp_deltas = {}
    for ch in set(list(prev_fnfp.keys()) + list(curr_fnfp.keys())):
        prev_data = prev_fnfp.get(ch, {})
        curr_data = curr_fnfp.get(ch, {})
        fnfp_deltas[ch] = {
            "fn_candidates_change": curr_data.get("fn_candidates", 0) - prev_data.get("fn_candidates", 0),
            "fp_candidates_change": curr_data.get("fp_candidates", 0) - prev_data.get("fp_candidates", 0),
        }
    delta["fn_fp_by_channel"] = fnfp_deltas

    delta["high_risk_ratio_change"] = round(
        current["high_risk_ratio"] - previous.get("high_risk_ratio", 0), 4
    )

    return delta
