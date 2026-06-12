from pydantic import BaseModel
from typing import Optional

class ScanIn(BaseModel):
    image_base64: str
    os: str

class ConfigOut(BaseModel):
    scan_credit_cap: int
    ad_frequency: int
    sensitivity_threshold: int
    config_version: int

class FlaggedUrl(BaseModel):
    url: str
    final_url: str
    reputation: str

class ScanOut(BaseModel):
    risk_score: int
    verdict: str
    extracted_text: str
    matched_keywords: list[str]
    flagged_urls: list[FlaggedUrl]