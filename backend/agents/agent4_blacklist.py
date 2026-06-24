import pickle
import tldextract
from pathlib import Path

def load(model_dir: Path) -> dict:
    snapshot = pickle.load(open(model_dir / "url_blacklist.pkl", "rb"))
    if isinstance(snapshot, set):
        return {"domains": snapshot, "meta": {"total_domains": len(snapshot)}}
    return {
        "domains": snapshot.get("domains", set()),
        "meta": snapshot.get("meta", {"total_domains": 0}),
    }

def check(url: str, artifacts: dict) -> dict:
    if not url:
        return {"blacklist_hit": False, "blacklist_domain": None}
    u = url.strip()
    if "//" not in u:
        u = "http://" + u
    try:
        ext = tldextract.extract(u)
        domain = f"{ext.domain}.{ext.suffix}".lower() if ext.domain and ext.suffix else None
    except Exception:
        domain = None
    if domain and domain in artifacts["domains"]:
        return {"blacklist_hit": True, "blacklist_domain": domain}
    return {"blacklist_hit": False, "blacklist_domain": None}
