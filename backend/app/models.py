from pydantic import BaseModel
from typing import Optional

class ScanIn(BaseModel):
    image_base64: str
    os: str

class AnalyzeTextIn(BaseModel):
    text: str
    os: str

class FindingOut(BaseModel):
    type: str
    severity: str
    title: str
    detail: str

class FlaggedUrl(BaseModel):
    url: str
    final_url: str
    reputation: str

class AnalyzeOut(BaseModel):
    scan_id: str
    kind: str
    risk_score: int
    verdict: str
    warning_count: int
    extracted_text: str
    findings: list[FindingOut]
    flagged_urls: list[FlaggedUrl]

class ConfigOut(BaseModel):
    scan_credit_cap: int
    ad_frequency: int
    sensitivity_threshold: int
    config_version: int

class ReportIn(BaseModel):
    report_type: str
    value: str
    channel: str
    description: Optional[str] = None
    os: str

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