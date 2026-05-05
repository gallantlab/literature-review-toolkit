#!/usr/bin/env python3
"""Multi-source PDF downloader (Phase 4 — OPT-IN, not run by default).

The default review workflow does not download PDFs (see PLAYBOOK.md). Run
this tool only when the user has explicitly asked for PDF acquisition. A
dedicated replacement is planned; treat this as legacy that still works.

Tries: arxiv direct -> Unpaywall (non-PMC URLs first) -> EuropePMC.
Validates that downloaded bytes start with %PDF.
Writes a manual-followup list for failures.

Input format (JSON list):
[
  {"slug": "Tang2023_decoder",
   "doi": "10.1038/s41593-023-01304-9",  # optional
   "arxiv": "1809.10193",                 # optional
   "pmcid": "PMC11304553"},               # optional
  ...
]

Run:  python3 download.py --papers list.json --out-dir papers/topic_X/ \
                          --email you@example.edu
"""
import argparse, json, os, sys, time
import urllib.request, urllib.parse

HDRS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Chrome/120.0.0.0",
    "Accept": "application/pdf,*/*;q=0.8",
}

# Domains that reliably block bots — skip them; route to manual list
BLOCKED_HOSTS = (
    "pmc.ncbi.nlm.nih.gov",         # PoW challenge on /pdf/ URLs
    "ncbi.nlm.nih.gov/pmc",
    "biorxiv.org",                  # Cloudflare
    "medrxiv.org",                  # Cloudflare
    "pnas.org/doi/pdf",             # 403
    "pnas.org/doi/epdf",
    "academic.oup.com",             # 403
    "direct.mit.edu",               # 403
    "sciencedirect.com",            # 403
    "onlinelibrary.wiley.com",      # 403
    "cell.com/action/showPdf",      # 403
)


def is_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF"


def try_get(url, timeout=60):
    if any(b in url for b in BLOCKED_HOSTS):
        return None  # skip
    req = urllib.request.Request(url, headers=HDRS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        return data if is_pdf(data) else None
    except Exception:
        return None


def unpaywall_urls(doi, email):
    if not doi:
        return []
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=20) as r:
            d = json.loads(r.read())
        cands = []
        loc = d.get("best_oa_location") or {}
        if loc.get("url_for_pdf"):
            cands.append(loc["url_for_pdf"])
        for L in d.get("oa_locations", []):
            u = L.get("url_for_pdf")
            if u and u not in cands:
                cands.append(u)
        # non-PMC first, since PMC PDFs are blocked
        non_pmc = [c for c in cands if "pmc.ncbi" not in c and "/pmc/" not in c]
        pmc = [c for c in cands if c not in non_pmc]
        return non_pmc + pmc
    except Exception:
        return []


def download_one(paper, out_dir, email):
    slug = paper["slug"]
    dest = os.path.join(out_dir, f"{slug}.pdf")
    if os.path.exists(dest) and os.path.getsize(dest) > 5000:
        return ("exists", os.path.getsize(dest), None)

    sources = []  # (label, url) pairs
    if paper.get("arxiv"):
        sources.append(("arxiv", f"https://arxiv.org/pdf/{paper['arxiv']}.pdf"))
    if paper.get("doi"):
        for u in unpaywall_urls(paper["doi"], email):
            sources.append(("unpaywall", u))
    if paper.get("pmcid"):
        sources.append(("europepmc", f"https://europepmc.org/articles/{paper['pmcid']}?pdf=render"))

    for label, url in sources:
        data = try_get(url)
        if data:
            with open(dest, "wb") as f:
                f.write(data)
            return (label, len(data), url)

    return ("FAIL", 0, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True, help="JSON list file")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--email", required=True, help="contact email for Unpaywall")
    ap.add_argument("--manual-list", default=None, help="path for failures list")
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    papers = json.load(open(args.papers))

    results = []
    for p in papers:
        status, sz, src = download_one(p, args.out_dir, args.email)
        msg = f"  {status:10s} {p['slug']:50s} {sz:>10d} bytes"
        if src:
            msg += f"  {src[:80]}"
        print(msg)
        results.append({**p, "status": status, "size": sz, "source": src})
        time.sleep(args.sleep)

    n_ok = sum(1 for r in results if r["status"] != "FAIL")
    print(f"\n=== {n_ok}/{len(results)} downloaded ===", file=sys.stderr)

    fails = [r for r in results if r["status"] == "FAIL"]
    if fails and args.manual_list:
        with open(args.manual_list, "a") as f:
            f.write("\n# Papers needing manual download (paywall / Cloudflare):\n")
            for r in fails:
                f.write(f"\n  {r['slug']}\n")
                if r.get("doi"):
                    f.write(f"    DOI: https://doi.org/{r['doi']}\n")
                if r.get("pmcid"):
                    f.write(f"    PMC: https://pmc.ncbi.nlm.nih.gov/articles/{r['pmcid']}/\n")
                if r.get("arxiv"):
                    f.write(f"    arxiv: https://arxiv.org/abs/{r['arxiv']}\n")


if __name__ == "__main__":
    main()
