import logging
import time
import re
from collections import Counter
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, HTTPException, Query, Depends
from app.rbac import require_admin_auth, require_permission, _get_service_client
from app.data_intel.dashboard_queries import _db as mongo_db

router = APIRouter(tags=["admin"])
logger = logging.getLogger("scamshield.admin")

VALID_CHANNELS = {"text", "url", "upi", "qr", "image", "file", "audio", "message", "screenshot"}
VALID_VERDICTS = {"high_risk", "suspicious", "low_risk"}
VALID_AGENT_IDS = {f"agent{i}" for i in range(1, 16)}

_agent_reset_cooldowns: dict[str, float] = {}
AGENT_RESET_MAX_PER_MINUTE = 3
AGENT_RESET_WINDOW = 60


def _log_audit(admin: dict, action: str, resource_type: str = "",
               resource_id: str = "", details: dict = None):
    try:
        sb = _get_service_client()
        sb.table("admin_audit_log").insert({
            "user_id": admin["admin_id"],
            "email": admin["email"],
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
        }).execute()
    except Exception as e:
        logger.warning("audit log failed: %s", e)


def _mask_pii(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    truncated = text[:max_len]
    truncated = re.sub(r'\b\d{10,}\b', '[PHONE]', truncated)
    truncated = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', truncated)
    truncated = re.sub(r'\b[A-Z]{2}\d{1,2}[A-Z]{1,2}\d{4}\b', '[VEHICLE]', truncated)
    return truncated


# ── B1: /api/v1/admin/summary ──────────────────────────────────────────

@router.get("/api/v1/admin/summary")
def admin_summary(admin: dict = Depends(require_permission("dashboard:view"))):
    _log_audit(admin, "view_summary", "dashboard")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sb = _get_service_client()

    try:
        metrics = sb.table("daily_metrics").select("*").eq("date", today).execute()
        if metrics.data:
            row = metrics.data[0]
            return {
                "total_scans_today": row["total_scans"],
                "scam_scans_today": row["scam_scans"],
                "safe_scans_today": row["safe_scans"],
                "high_risk_scans_today": row["high_risk_scans"],
                "suspicious_scans_today": row["suspicious_scans"],
                "low_risk_scans_today": row["low_risk_scans"],
                "unique_active_users_today": row["unique_users"],
                "avg_score_today": float(row["avg_score"]),
                "by_channel_today": row.get("by_channel", {}),
            }
    except Exception as e:
        logger.warning("daily_metrics query failed, falling back: %s", e)

    db = mongo_db()
    if db is not None:
        try:
            start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            pipeline = [
                {"$match": {"created_at": {"$gte": start}}},
                {"$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "high_risk": {"$sum": {"$cond": [{"$eq": ["$verdict", "high_risk"]}, 1, 0]}},
                    "suspicious": {"$sum": {"$cond": [{"$eq": ["$verdict", "suspicious"]}, 1, 0]}},
                    "low_risk": {"$sum": {"$cond": [{"$eq": ["$verdict", "low_risk"]}, 1, 0]}},
                    "scam": {"$sum": {"$cond": [{"$in": ["$verdict", ["high_risk", "suspicious"]]}, 1, 0]}},
                    "safe": {"$sum": {"$cond": [{"$eq": ["$verdict", "low_risk"]}, 1, 0]}},
                    "avg_score": {"$avg": "$score"},
                    "unique_users": {"$addToSet": "$user_id"},
                }},
            ]
            result = list(db.scans.aggregate(pipeline))
            if result:
                r = result[0]
                return {
                    "total_scans_today": r.get("total", 0),
                    "scam_scans_today": r.get("scam", 0),
                    "safe_scans_today": r.get("safe", 0),
                    "high_risk_scans_today": r.get("high_risk", 0),
                    "suspicious_scans_today": r.get("suspicious", 0),
                    "low_risk_scans_today": r.get("low_risk", 0),
                    "unique_active_users_today": len(r.get("unique_users", [])),
                    "avg_score_today": round(r.get("avg_score", 0) or 0, 2),
                }
        except Exception as e:
            logger.warning("MongoDB fallback query failed: %s", e)

    return {
        "total_scans_today": 0, "scam_scans_today": 0, "safe_scans_today": 0,
        "high_risk_scans_today": 0, "suspicious_scans_today": 0,
        "low_risk_scans_today": 0, "unique_active_users_today": 0,
        "avg_score_today": 0,
    }


@router.get("/api/v1/admin/referrals/summary")
def admin_referrals_summary(admin: dict = Depends(require_permission("dashboard:view"))):
    _log_audit(admin, "view_referrals_summary", "referrals")
    sb = _get_service_client()

    referrals_resp = sb.table("referrals").select("id,owner_id,code,created_at").execute()
    redemptions_resp = sb.table("referral_redemptions").select(
        "id,referral_id,redeemed_by,redeemed_at,scans_credited"
    ).execute()

    referrals = referrals_resp.data or []
    redemptions = redemptions_resp.data or []
    referral_by_id = {r["id"]: r for r in referrals if r.get("id")}

    total_codes = len(referrals)
    total_redemptions = len(redemptions)
    total_bonus_scans_credited = sum(r.get("scans_credited", 0) for r in redemptions)
    unique_referrers = len({r.get("owner_id") for r in referrals if r.get("owner_id")})
    unique_redeemers = len({r.get("redeemed_by") for r in redemptions if r.get("redeemed_by")})

    redemptions_last_7_days = 0
    redemptions_last_30_days = 0
    now = datetime.now(timezone.utc)
    for row in redemptions:
        redeemed_at = row.get("redeemed_at")
        if not redeemed_at:
            continue
        try:
            ts = datetime.fromisoformat(redeemed_at.replace("Z", "+00:00"))
        except Exception:
            continue
        age = now - ts
        if age <= timedelta(days=30):
            redemptions_last_30_days += 1
        if age <= timedelta(days=7):
            redemptions_last_7_days += 1

    counts = Counter()
    for row in redemptions:
        ref = referral_by_id.get(row.get("referral_id"))
        if not ref:
            continue
        owner_id = ref.get("owner_id")
        if owner_id:
            counts[owner_id] += 1

    top_referrers = []
    for owner_id, redeemed_count in counts.most_common(10):
        code = None
        for r in referrals:
            if r.get("owner_id") == owner_id:
                code = r.get("code")
                break
        top_referrers.append({
            "owner_id": owner_id,
            "code": code,
            "redeemed_count": redeemed_count,
            "bonus_scans_credited": redeemed_count * 5,
        })

    return {
        "total_codes": total_codes,
        "total_redemptions": total_redemptions,
        "total_bonus_scans_credited": total_bonus_scans_credited,
        "unique_referrers": unique_referrers,
        "unique_redeemers": unique_redeemers,
        "redemptions_last_7_days": redemptions_last_7_days,
        "redemptions_last_30_days": redemptions_last_30_days,
        "top_referrers": top_referrers,
    }


# ── B2: /api/v1/admin/scans ────────────────────────────────────────────

@router.get("/api/v1/admin/scans")
def admin_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: Optional[str] = Query(None, pattern="^[a-z_]+$"),
    verdict: Optional[str] = Query(None, pattern="^[a-z_]+$"),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    from_date: Optional[str] = Query(None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: Optional[str] = Query(None, alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    admin: dict = Depends(require_permission("scans:list")),
):
    if channel and channel not in VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")
    if verdict and verdict not in VALID_VERDICTS:
        raise HTTPException(status_code=400, detail=f"Invalid verdict: {verdict}")

    from_dt = None
    to_dt = None
    if from_date:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if to_date:
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    if from_dt and to_dt and (to_dt - from_dt).days > 90:
        raise HTTPException(status_code=400, detail="Date window cannot exceed 90 days")

    _log_audit(admin, "list_scans", "scans", "",
               {"page": page, "page_size": page_size, "channel": channel, "verdict": verdict})

    db = mongo_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    match: dict = {}
    if channel:
        match["channel"] = channel
    if verdict:
        match["verdict"] = verdict
    if min_score is not None or max_score is not None:
        score_filter = {}
        if min_score is not None:
            score_filter["$gte"] = min_score
        if max_score is not None:
            score_filter["$lte"] = max_score
        match["score"] = score_filter
    if from_dt or to_dt:
        date_filter = {}
        if from_dt:
            date_filter["$gte"] = from_dt
        if to_dt:
            date_filter["$lte"] = to_dt
        match["created_at"] = date_filter

    try:
        total = db.scans.count_documents(match)
        if total > 100000:
            logger.warning("admin scans query returning large result: %d rows (user=%s)", total, admin["email"])
        skip = (page - 1) * page_size
        docs = list(db.scans.find(
            match,
            {"scan_id": 1, "created_at": 1, "channel": 1, "verdict": 1,
             "score": 1, "warning_count": 1, "flagged": 1, "input_preview": 1},
        ).sort("created_at", -1).skip(skip).limit(page_size))
    except Exception as e:
        logger.warning("admin scans query failed: %s", e)
        raise HTTPException(status_code=500, detail="Scans query failed")

    items = []
    for d in docs:
        preview = _mask_pii(d.get("input_preview", ""), 80)
        ts = d.get("created_at")
        items.append({
            "scan_id": d.get("scan_id", ""),
            "timestamp": str(ts) if ts else "",
            "channel": d.get("channel", ""),
            "verdict": d.get("verdict", ""),
            "score": d.get("score", 0),
            "warning_count": d.get("warning_count", 0),
            "flagged": d.get("flagged", False),
            "input_preview": preview,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── B3: /api/v1/admin/scan/{scan_id} ───────────────────────────────────

@router.get("/api/v1/admin/scan/{scan_id}")
def admin_scan_detail(
    scan_id: str,
    admin: dict = Depends(require_permission("scans:view_detail")),
):
    _log_audit(admin, "view_scan_detail", "scan", scan_id)

    db = mongo_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        doc = db.scans.find_one({"scan_id": scan_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Scan not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("admin scan detail query failed: %s", e)
        raise HTTPException(status_code=500, detail="Scan query failed")

    result = doc.get("result", {})
    agent_decisions = []
    for ar in result.get("agent_results", []):
        agent_decisions.append({
            "agent_id": ar.get("agent_id", 0),
            "name": ar.get("name", ""),
            "score": ar.get("score", 0),
            "verdict": ar.get("verdict", ""),
            "signals": ar.get("signals", []),
        })

    feedback_entries = []
    try:
        fb_docs = list(db.feedback.find(
            {"scan_id": scan_id},
            {"user_id": 1, "label": 1, "reason": 1, "created_at": 1},
        ).sort("created_at", -1))
        for fb in fb_docs:
            feedback_entries.append({
                "user_id": str(fb.get("user_id", ""))[:12] + "...",
                "label": fb.get("label", ""),
                "reason": fb.get("reason", ""),
                "created_at": str(fb.get("created_at", "")),
            })
    except Exception:
        pass

    ts = doc.get("created_at")
    preview = _mask_pii(doc.get("input_preview", ""), 200)
    return {
        "scan_id": doc.get("scan_id", ""),
        "timestamp": str(ts) if ts else "",
        "channel": doc.get("channel", ""),
        "verdict": doc.get("verdict", ""),
        "score": doc.get("score", 0),
        "warning_count": doc.get("warning_count", 0),
        "flagged": doc.get("flagged", False),
        "input_preview": preview,
        "top_signal": result.get("top_signal", ""),
        "agent_decisions": agent_decisions,
        "feedback": feedback_entries,
    }


# ── B4: /api/v1/admin/agents ───────────────────────────────────────────

@router.get("/api/v1/admin/agents")
def admin_agents(admin: dict = Depends(require_permission("agents:view"))):
    _log_audit(admin, "view_agents", "agent")
    from app.ml.model_loader import get_agent_status, get_agent_folder_status, get_agent_health

    statuses = get_agent_status()
    folder_status = get_agent_folder_status()
    health = get_agent_health()
    agents_list = []
    seen_ids = set()

    for aid in sorted(statuses.keys(), key=int):
        s = statuses[aid]
        hid = f"agent{aid}"
        h = health.get(hid, {})
        status = "DISABLED" if h.get("disabled") else s.get("status", "UNKNOWN")
        agents_list.append({
            "id": int(aid),
            "name": s.get("name", ""),
            "status": status,
            "status_detail": s.get("status_detail", ""),
            "health": h,
        })
        seen_ids.add(int(aid))

    for fname, finfo in sorted(folder_status.items()):
        if finfo["id"] not in seen_ids:
            agents_list.append({
                "id": finfo["id"],
                "name": finfo["name"],
                "status": finfo["status"],
                "status_detail": finfo["status_detail"],
                "health": {},
            })
            seen_ids.add(finfo["id"])

    return {"agents": agents_list, "total": len(agents_list)}


# ── B5: /api/v1/admin/agents/reset ─────────────────────────────────────

@router.post("/api/v1/admin/agents/reset")
def admin_agents_reset(
    body: dict,
    admin: dict = Depends(require_permission("agents:reset")),
):
    agent_id = (body or {}).get("agent_id", "")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")
    if agent_id not in VALID_AGENT_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid agent_id. Must be one of: {', '.join(sorted(VALID_AGENT_IDS))}")

    now = time.time()
    last = _agent_reset_cooldowns.get(agent_id, 0)
    if now - last < AGENT_RESET_WINDOW:
        count = sum(1 for t in _agent_reset_cooldowns.values() if now - t < AGENT_RESET_WINDOW)
        if count >= AGENT_RESET_MAX_PER_MINUTE:
            raise HTTPException(status_code=429, detail=f"Agent reset rate limit exceeded. Max {AGENT_RESET_MAX_PER_MINUTE} per {AGENT_RESET_WINDOW}s per agent.")
    _agent_reset_cooldowns[agent_id] = now

    from app.ml.model_loader import reset_agent
    reset_agent(agent_id)
    _log_audit(admin, "agent_reset", "agent", agent_id)
    return {"ok": True, "agent_id": agent_id}


# ── B6: /api/v1/admin/quarantine-events ────────────────────────────────

@router.get("/api/v1/admin/quarantine-events")
def admin_quarantine_events(admin: dict = Depends(require_permission("agents:view"))):
    _log_audit(admin, "view_quarantine_events", "agent")
    db = mongo_db()
    if db is None:
        return {"events": []}

    try:
        docs = list(db.admin_events.find(
            {"type": {"$regex": "^quarantine"}},
        ).sort("created_at", -1).limit(50))
        events = []
        for d in docs:
            events.append({
                "type": d.get("type", ""),
                "agent_id": d.get("agent_id", ""),
                "timestamp": str(d.get("created_at", "")),
                "details": d.get("details", ""),
            })
        return {"events": events}
    except Exception:
        pass

    try:
        sb = _get_service_client()
        result = sb.table("admin_audit_log") \
            .select("*") \
            .eq("action", "agent_reset") \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute()
        events = []
        for row in result.data or []:
            events.append({
                "type": "agent_reset",
                "agent_id": row.get("resource_id", ""),
                "timestamp": row.get("created_at", ""),
                "details": f"Reset by {row.get('email', 'unknown')}",
            })
        return {"events": events}
    except Exception:
        return {"events": []}


# ── B7: /api/v1/admin/feedback ────────────────────────────────────────

@router.get("/api/v1/admin/feedback")
def admin_feedback(
    label: Optional[str] = Query(None, pattern="^(scam|legit|unsure)$"),
    limit: int = Query(50, ge=1, le=200),
    admin: dict = Depends(require_permission("feedback:view")),
):
    _log_audit(admin, "view_feedback", "feedback", "", {"label": label, "limit": limit})

    db = mongo_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    match: dict = {}
    if label:
        match["label"] = label

    try:
        docs = list(db.feedback.find(match).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.warning("admin feedback query failed: %s", e)
        raise HTTPException(status_code=500, detail="Feedback query failed")

    items = []
    for d in docs:
        scan_id = d.get("scan_id", "")
        model_verdict = ""
        model_score = 0
        try:
            scan = db.scans.find_one({"scan_id": scan_id}, {"verdict": 1, "score": 1})
            if scan:
                model_verdict = scan.get("verdict", "")
                model_score = scan.get("score", 0)
        except Exception:
            pass

        verdict_to_delta = {"high_risk": "scam", "suspicious": "scam", "low_risk": "safe"}
        expected = verdict_to_delta.get(model_verdict, "unknown")
        user_label = d.get("label", "")
        if user_label == expected:
            delta = "agrees"
        elif user_label == "scam" and model_verdict in ("low_risk",):
            delta = "possible_fn"
        elif user_label == "legit" and model_verdict in ("high_risk", "suspicious"):
            delta = "possible_fp"
        else:
            delta = "disagrees"

        items.append({
            "scan_id": scan_id,
            "user_id": str(d.get("user_id", ""))[:12] + "...",
            "channel": d.get("channel", ""),
            "label": user_label,
            "reason": d.get("reason", ""),
            "created_at": str(d.get("created_at", "")),
            "model_verdict": model_verdict,
            "model_score": model_score,
            "delta": delta,
        })

    return {"items": items, "total": len(items)}


# ── B8: /api/v1/admin/me ───────────────────────────────────────────────

@router.get("/api/v1/admin/me")
def admin_me(admin: dict = Depends(require_admin_auth)):
    _log_audit(admin, "view_me", "user", admin["admin_id"])
    return {
        "email": admin["email"],
        "name": admin["name"],
        "roles": admin["roles"],
        "permissions": admin["permissions"],
    }
