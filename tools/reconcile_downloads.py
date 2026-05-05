#!/usr/bin/env python3
"""Reconcile manually-downloaded PDFs against a slug+title+doi manifest.

Companion to `download.py`. Phase 4 — OPT-IN, not part of the default
workflow. Only run when the user has explicitly asked for PDF acquisition.

Strategy (most reliable first):
  1. **Filename ↔ DOI substring match.** Many publishers encode the DOI suffix
     in the filename: `nrn755.pdf` → `10.1038/nrn755`, `science.1138071.pdf` →
     `10.1126/science.1138071`, `s41467-019-13761-7.pdf` → `10.1038/s41467-...`.
     If a filename's stem appears as a substring in exactly one manifest DOI,
     that's a high-confidence match.
  2. **Author surname + year + title-word overlap** in PDF first-page text.
     Require all three signals to converge before moving.
  3. **Refuse to move** when uncertain — leave the PDF in Downloads for the
     user to confirm rather than misfile.

Manifest format (JSON list):
[
  {"slug": "Treue1996_xref",
   "title": "Attentional modulation of visual motion processing in cortical areas MT and MST",
   "first_author": "Treue", "year": "1996",
   "doi": "10.1038/382539a0"},
  ...
]

Run:  python3 reconcile_downloads.py --manifest list.json --out-dir papers/attention/
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys, time
from difflib import SequenceMatcher


def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def pdf_first_page_text(path: pathlib.Path) -> str:
    try:
        r = subprocess.run(
            ["pdftotext", "-l", "1", "-layout", str(path), "-"],
            capture_output=True, timeout=30,
        )
        return r.stdout.decode("utf-8", errors="ignore")
    except Exception:
        return ""


# ---------- Strategy 1: filename ↔ DOI match ----------
def filename_doi_match(filename: str, manifest):
    """Return list of manifest entries whose DOI contains a substring of the
    filename stem (or vice versa)."""
    stem = pathlib.Path(filename).stem.lower()
    # Normalize filename: replace separators/strip publisher prefixes
    candidates = {stem,
                  stem.replace("_", "-"),
                  stem.replace("_", "."),
                  re.sub(r"^(s\d{5}-\d+-\d+-\d+).*", r"\1", stem),  # Springer
                  }
    # Strip common Elsevier prefix `1-s2.0-S0042698911001544-main`
    m = re.match(r"1-s2\.0-([sS]\d+)-main", stem)
    if m:
        candidates.add(m.group(1).lower())
    matches = []
    for entry in manifest:
        doi = entry["doi"].lower()
        # Drop the "10.<registrant>/" prefix to get the suffix
        suffix = doi.split("/", 1)[1] if "/" in doi else doi
        # Pieces of the suffix to test against the filename
        parts = {suffix, suffix.replace(".", "_")}
        # Final identifier token (e.g., "nrn755", "21176", "s41467-019-13761-7")
        for tok in re.findall(r"[a-z]*\d{3,}[a-z\d\-_.]*", suffix):
            parts.add(tok)
        for cand in candidates:
            if not cand:
                continue
            for piece in parts:
                if not piece:
                    continue
                # Match if either contains the other and the shorter is >=4 chars
                short, long = sorted([cand, piece], key=len)
                if len(short) >= 4 and short in long:
                    matches.append(entry)
                    break
            else:
                continue
            break
    # Dedupe by slug
    seen, uniq = set(), []
    for m in matches:
        if m["slug"] not in seen:
            seen.add(m["slug"])
            uniq.append(m)
    return uniq


# ---------- Strategy 2: author + year + title overlap ----------
def text_signals_match(pdf_text: str, manifest, page_n_chars: int = 3000):
    """Find manifest entries whose author surname AND year AND multiple title
    keywords all appear on the first page. Return scored list."""
    page = pdf_text[:page_n_chars]
    page_norm = normalize(page)
    scored = []
    for entry in manifest:
        au = (entry.get("first_author") or "").lower()
        au_first = au.split()[0] if au else ""
        yr = entry.get("year") or ""
        title = entry.get("title") or ""
        # Required signals
        if not au_first or au_first not in page_norm:
            continue
        if yr and yr not in page:
            continue
        # Title-word overlap (require >=2 long words match, exclude stopwords)
        STOP = {"the", "and", "for", "with", "from", "into", "that", "this",
                "their", "have", "been", "were", "will", "are", "but"}
        words = [w for w in normalize(title).split()
                 if len(w) >= 4 and w not in STOP]
        hits = sum(1 for w in words if w in page_norm)
        frac = hits / max(1, len(words))
        if hits < 2 or frac < 0.25:
            continue
        # Score = title fraction + tie-breaking bonus for early-position author
        au_pos = page_norm.find(au_first)
        early_bonus = 0.1 if au_pos != -1 and au_pos < 1500 else 0.0
        score = frac + early_bonus
        scored.append((score, entry))
    scored.sort(key=lambda x: -x[0])
    return scored


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--downloads-dir", default=str(pathlib.Path.home() / "Downloads"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--since-hours", type=float, default=12.0,
                    help="only consider PDFs modified in the last N hours")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    os.makedirs(args.out_dir, exist_ok=True)

    cutoff = time.time() - args.since_hours * 3600
    dl = pathlib.Path(args.downloads_dir)
    pdfs = sorted([p for p in dl.glob("*.pdf") if p.stat().st_mtime >= cutoff],
                  key=lambda p: -p.stat().st_mtime)

    print(f"Scanning {len(pdfs)} PDFs in {dl} (last {args.since_hours}h)\n")

    used_slugs = {pathlib.Path(p).stem
                  for p in pathlib.Path(args.out_dir).glob("*.pdf")}
    moved, skipped = [], []
    for pdf in pdfs:
        # --- Strategy 1: filename-DOI ---
        fn_matches = filename_doi_match(pdf.name, manifest)
        chosen, source = None, None
        if len(fn_matches) == 1:
            chosen, source = fn_matches[0], "filename-DOI"
        elif len(fn_matches) > 1:
            print(f"  [ambig-fn]  {pdf.name} → {len(fn_matches)} filename-DOI candidates: "
                  + ", ".join(m["slug"] for m in fn_matches[:3]))

        # --- Strategy 2: text signals ---
        if chosen is None:
            text = pdf_first_page_text(pdf)
            if not text:
                print(f"  [no-text]   {pdf.name} (pdftotext returned nothing)")
                skipped.append(pdf)
                continue
            scored = text_signals_match(text, manifest)
            if scored:
                top_score, top_entry = scored[0]
                # Require clear lead over runner-up
                second_score = scored[1][0] if len(scored) > 1 else 0.0
                if top_score - second_score >= 0.15 or len(scored) == 1:
                    chosen, source = top_entry, f"text (score {top_score:.2f})"
                else:
                    print(f"  [tie]       {pdf.name} → {top_entry['slug']} ({top_score:.2f}) "
                          f"vs {scored[1][1]['slug']} ({second_score:.2f}); skipping")

        if chosen is None:
            print(f"  [no-match]  {pdf.name}")
            skipped.append(pdf)
            continue

        slug = chosen["slug"]
        if slug in used_slugs:
            print(f"  [dup-slug]  {pdf.name} → {slug} (target already filled)")
            skipped.append(pdf)
            continue
        target = pathlib.Path(args.out_dir) / f"{slug}.pdf"
        used_slugs.add(slug)
        action = "WOULD MOVE" if args.dry_run else "MOVED     "
        print(f"  [{action}] {pdf.name} → {slug}.pdf  ({source})")
        if not args.dry_run:
            shutil.move(str(pdf), target)
        moved.append((pdf.name, slug, source))

    unmatched = [e["slug"] for e in manifest if e["slug"] not in used_slugs]
    print(f"\n=== matched: {len(moved)} this run; manifest still missing {len(unmatched)} of {len(manifest)} ===")
    if unmatched and len(unmatched) <= 60:
        print("Still missing:")
        for s in unmatched:
            print(f"  - {s}")
    if skipped:
        print(f"Skipped {len(skipped)} PDFs in Downloads (left in place).")


if __name__ == "__main__":
    main()
