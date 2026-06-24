from pydantic import BaseModel, ConfigDict
from typing import Optional

class SignalsBlock(BaseModel):
    text_tfidf_prob: Optional[float] = None
    text_distilbert_prob: Optional[float] = None
    url_xgb_prob: Optional[float] = None
    blacklist_hit: Optional[bool] = None
    blacklist_domain: Optional[str] = None
    qr_xgb_prob: Optional[float] = None
    upi_rule_score: Optional[int] = None
    upi_rule_severity: Optional[str] = None
    upi_xgb_prob: Optional[float] = None
    brand_flag: Optional[bool] = None
    matched_brand: Optional[str] = None
    brand_v2_similarity: Optional[float] = None
    deepfake_prob: Optional[float] = None
    malware_prob: Optional[float] = None
    call_fraud_prob: Optional[float] = None
    regex_score: Optional[int] = None
    regex_severity: Optional[str] = None
    regex_triggered: Optional[list[str]] = None

class FindingItem(BaseModel):
    type: str
    severity: str
    title: str
    detail: str

class ScanResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    scan_id: str = ""
    scam_score: int
    verdict: str
    signals: SignalsBlock
    top_signal: str
    confidence: float
    flagged_urls: list[str] = []
    findings: list[FindingItem] = []
    warning_count: int = 0
    extracted_text: str = ""
    kind: str = ""
    flagged: bool = False
    meta: dict = {}
