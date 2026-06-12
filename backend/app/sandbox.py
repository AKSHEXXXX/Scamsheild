import re
import httpx
from app.database import supabase

URL_RE = re.compile(r"https?://[^\s\)\"\'\>\<\]]+")

async def sandbox_urls(text: str) -> list[dict]:
    found_urls = URL_RE.findall(text)
    flagged = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=5) as client:
        for url in found_urls:
            url = url.rstrip(".,;:!?")
            try:
                r = await client.get(url)
                final = str(r.url)
                domain = httpx.URL(final).host
                bl_result = supabase.table("blacklisted_domains") \
                    .select("reputation") \
                    .eq("domain", domain) \
                    .execute()
                rep = bl_result.data[0]["reputation"] if bl_result.data else "unknown"
            except Exception:
                final = url
                rep = "unreachable"
            flagged.append({
                "url": url,
                "final_url": final,
                "reputation": rep
            })
    return flagged