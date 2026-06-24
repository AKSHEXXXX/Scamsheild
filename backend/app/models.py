from typing import Literal, Optional
from pydantic import BaseModel, Field

class ScanIn(BaseModel):
    image_base64: str
    os: str

class SandboxImageRequest(BaseModel):
    image: str = Field(max_length=5_000_000)
    device_id: Optional[str] = Field(default=None, max_length=256)
    fallback_reason: Optional[str] = Field(default=None, max_length=512)

class AnalyzeTextIn(BaseModel):
    text: str = Field(max_length=4096)
    os: Literal["iOS", "Android"]
    ocr_source: Optional[str] = Field(default="text_input", max_length=64)

class FindingOut(BaseModel):
    type: str
    severity: str
    title: str
    detail: str

class FlaggedUrl(BaseModel):
    url: str
    final_url: str
    reputation: str

class OcrMeta(BaseModel):
    ocr_method: str
    ocr_confidence: float
    ocr_fallback: bool

class AnalyzeOut(BaseModel):
    scan_id: str = ""
    scam_score: int
    verdict: str
    top_signal: str
    flagged_urls: list[str] = []
    findings: list[dict] = []
    warning_count: int = 0
    extracted_text: str = ""
    kind: str = ""
    flagged: bool = False
    meta: dict = {}

class ConfigOut(BaseModel):
    scan_credit_cap: int           # consumed by Android
    ad_frequency: int              # consumed by Android
    sensitivity_threshold: int     # consumed by Android
    config_version: str            # consumed by Android
    features: dict = {}            # available for Android feature flags (not yet consumed)
    model_version: str = ""        # informational — not consumed by Android
    score_thresholds: dict = {}    # informational — not consumed by Android

class ReportIn(BaseModel):
    report_type: str
    value: str
    channel: str
    description: Optional[str] = None
    os: Literal["iOS", "Android"]

class ReportOut(BaseModel):
    ok: bool
    report_id: str

class HistoryItem(BaseModel):
    scan_id: str
    kind: str
    verdict: str
    preview: str
    created_at: str

class HistoryCounts(BaseModel):
    messages: int
    screenshots: int
    reports: int

class HistoryOut(BaseModel):
    counts: HistoryCounts
    items: list[HistoryItem]

class ScanRequest(BaseModel):
    channel: str = "text"
    text: Optional[str] = None
    url: Optional[str] = None
    image_base64: Optional[str] = None
    file_base64: Optional[str] = None
    audio_base64: Optional[str] = None
    context: Optional[dict] = None
    os: str = "unknown"
    posture: Optional[dict] = None

class AgentResultItem(BaseModel):
    agent_id: int
    name: str
    score: float
    verdict: str
    signals: list[str] = []

class UnifiedScanResult(BaseModel):
    final_verdict: str
    score: int
    label: str
    top_reason: str
    agent_results: list[AgentResultItem]
    meta: dict = {}

class FeedbackIn(BaseModel):
    scan_id: str = Field(max_length=128)
    label: str = Field(max_length=16)
    reason: Optional[str] = Field(default=None, max_length=1024)

class FeedbackOut(BaseModel):
    ok: bool
