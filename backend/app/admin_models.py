from typing import Optional
from pydantic import BaseModel, Field

class AdminMeOut(BaseModel):
    email: str
    name: str
    roles: list[str]
    permissions: list[str]

class AgentResetIn(BaseModel):
    agent_id: str = Field(max_length=64)

class ScanSummaryOut(BaseModel):
    total_scans_today: int
    scam_scans_today: int
    safe_scans_today: int
    high_risk_scans_today: int
    suspicious_scans_today: int
    low_risk_scans_today: int
    unique_active_users_today: int
    trend_last_30_days: list[dict]

class ScanListItem(BaseModel):
    scan_id: str
    timestamp: str
    channel: str
    verdict: str
    score: int
    warning_count: int
    flagged: bool
    input_preview: str

class ScanListOut(BaseModel):
    items: list[ScanListItem]
    total: int
    page: int
    page_size: int

class AgentDecision(BaseModel):
    agent_id: int
    name: str
    score: float
    verdict: str
    signals: list[str] = []

class ScanDetailOut(BaseModel):
    scan_id: str
    timestamp: str
    channel: str
    verdict: str
    score: int
    warning_count: int
    flagged: bool
    input_preview: str
    top_signal: str
    agent_decisions: list[AgentDecision] = []
    feedback: list[dict] = []

class AgentHealthOut(BaseModel):
    id: int
    name: str
    status: str
    health: dict
    status_detail: str

class QuarantineEvent(BaseModel):
    type: str
    agent_id: str
    timestamp: str
    details: str

class FeedbackItem(BaseModel):
    scan_id: str
    user_id: str
    channel: str
    label: str
    reason: str
    created_at: str
    model_verdict: str
    model_score: int
    delta: str
