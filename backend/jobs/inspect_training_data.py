"""
Inspect exported training data and produce a human-readable stats report.

Usage:
    python jobs/inspect_training_data.py [--data-dir ./data] [--output output/training_data_report.md]
"""
import os, sys, csv, re, argparse
from collections import Counter
from pathlib import Path


def _load_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]{3,}", text.lower())


def _tld_from_url(url: str) -> str:
    from urllib.parse import urlparse
    try:
        domain = urlparse(url).netloc or urlparse("//" + url).netloc
        parts = domain.split(".")
        return "." + parts[-1].lower() if len(parts) >= 2 else ""
    except Exception:
        return ""


def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return (urlparse(url).netloc or urlparse("//" + url).netloc).lower()
    except Exception:
        return ""


def _top_ngrams(rows: list, text_field: str, n: int = 20) -> list[tuple[str, int]]:
    all_tokens = []
    for r in rows:
        all_tokens.extend(_tokenize(r.get(text_field, "")))
    return Counter(all_tokens).most_common(n)


def _top_tlds(rows: list, url_field: str, n: int = 20) -> list[tuple[str, int]]:
    tlds = Counter()
    for r in rows:
        tlds[_tld_from_url(r.get(url_field, ""))] += 1
    return tlds.most_common(n)


def _top_domains(rows: list, url_field: str, n: int = 20) -> list[tuple[str, int]]:
    domains = Counter()
    for r in rows:
        d = _domain_from_url(r.get(url_field, ""))
        if d:
            domains[d] += 1
    return domains.most_common(n)


def _write_report(report_path: str, text_rows: list, url_rows: list):
    lines = []
    lines.append("# Training Data Report")
    lines.append(f"\nGenerated: {__import__('datetime').datetime.now(timezone=__import__('datetime').timezone.utc).isoformat() + 'Z'}")
    lines.append("")

    # Text stats
    lines.append("## Text Training Data")
    lines.append("")
    text_scam = [r for r in text_rows if r.get("label") == "1"]
    text_legit = [r for r in text_rows if r.get("label") == "0"]
    total_text = len(text_rows)
    lines.append(f"- **Total rows:** {total_text}")
    lines.append(f"- **Scam (label=1):** {len(text_scam)} ({len(text_scam)/max(total_text,1)*100:.1f}%)")
    lines.append(f"- **Legit (label=0):** {len(text_legit)} ({len(text_legit)/max(total_text,1)*100:.1f}%)")
    if total_text and len(text_scam) and len(text_legit):
        lines.append(f"- **Balance ratio (scam/legit):** {len(text_scam)/max(len(text_legit),1):.2f}")
    lines.append("")

    # Text MFW for scam
    if text_scam:
        lines.append("### Top 20 tokens (scam)")
        lines.append("")
        lines.append("| Token | Count |")
        lines.append("|-------|-------|")
        for token, count in _top_ngrams(text_scam, "text", 20):
            lines.append(f"| {token} | {count} |")
        lines.append("")

    # Text MFW for legit
    if text_legit:
        lines.append("### Top 20 tokens (legit)")
        lines.append("")
        lines.append("| Token | Count |")
        lines.append("|-------|-------|")
        for token, count in _top_ngrams(text_legit, "text", 20):
            lines.append(f"| {token} | {count} |")
        lines.append("")

    # URL stats
    lines.append("## URL Training Data")
    lines.append("")
    url_scam = [r for r in url_rows if r.get("label") == "1"]
    url_legit = [r for r in url_rows if r.get("label") == "0"]
    total_url = len(url_rows)
    lines.append(f"- **Total rows:** {total_url}")
    lines.append(f"- **Scam (label=1):** {len(url_scam)} ({len(url_scam)/max(total_url,1)*100:.1f}%)")
    lines.append(f"- **Legit (label=0):** {len(url_legit)} ({len(url_legit)/max(total_url,1)*100:.1f}%)")
    if total_url and len(url_scam) and len(url_legit):
        lines.append(f"- **Balance ratio (scam/legit):** {len(url_scam)/max(len(url_legit),1):.2f}")
    lines.append("")

    # URL top domains for scam
    if url_scam:
        lines.append("### Top 20 domains (scam)")
        lines.append("")
        lines.append("| Domain | Count |")
        lines.append("|--------|-------|")
        for domain, count in _top_domains(url_scam, "url", 20):
            lines.append(f"| {domain} | {count} |")
        lines.append("")

        lines.append("### Top 20 TLDs (scam)")
        lines.append("")
        lines.append("| TLD | Count |")
        lines.append("|-----|-------|")
        for tld, count in _top_tlds(url_scam, "url", 20):
            lines.append(f"| {tld or '(none)'} | {count} |")
        lines.append("")

    # URL top domains for legit
    if url_legit:
        lines.append("### Top 20 domains (legit)")
        lines.append("")
        lines.append("| Domain | Count |")
        lines.append("|--------|-------|")
        for domain, count in _top_domains(url_legit, "url", 20):
            lines.append(f"| {domain} | {count} |")
        lines.append("")

        lines.append("### Top 20 TLDs (legit)")
        lines.append("")
        lines.append("| TLD | Count |")
        lines.append("|-----|-------|")
        for tld, count in _top_tlds(url_legit, "url", 20):
            lines.append(f"| {tld or '(none)'} | {count} |")
        lines.append("")

    lines.append("---")
    total_all = total_text + total_url
    if total_all:
        lines.append(f"**Total labeled samples across all channels: {total_all}**")
    lines.append("")

    out = "\n".join(lines)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Report written to {report_path}")
    print(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", help="Directory containing exported CSVs")
    parser.add_argument("--output", default="output/training_data_report.md")
    parser.add_argument("--export-first", action="store_true", help="Run export before inspecting")
    args = parser.parse_args()

    if args.export_first:
        os.chdir(os.path.join(os.path.dirname(__file__), ".."))
        sys.path.insert(0, os.getcwd())
        from jobs.export_training_data import main as export_main
        export_main()

    data_dir = args.data_dir
    text_path = os.path.join(data_dir, "text_training.csv")
    url_path = os.path.join(data_dir, "url_training.csv")

    text_rows = _load_csv(text_path) if os.path.exists(text_path) else []
    url_rows = _load_csv(url_path) if os.path.exists(url_path) else []

    if not text_rows and not url_rows:
        print(f"No training data found in {data_dir}/. Run export_training_data.py first or use --export-first.")
        sys.exit(1)

    _write_report(args.output, text_rows, url_rows)


if __name__ == "__main__":
    main()
