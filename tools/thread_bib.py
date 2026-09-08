"""Thread-tag the reference .bib from references/papers_thread_index.csv.

Reads the paper -> research-thread table (CSV) and, for every entry in
references/drosophila_terminalia.bib, appends two custom BibTeX fields:

    keywords = {...}   - human-readable thread label(s)
    note     = {...}   - machine-readable thread IDs (primary + secondary)

Entries are matched by DOI (unique per paper). Safe to re-run: existing
keywords/note fields are replaced rather than duplicated.
"""
import csv
import re
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
CSV = VAULT / "references" / "papers_thread_index.csv"
BIB = VAULT / "references" / "drosophila_terminalia.bib"

# ---- build doi -> thread mapping from the CSV ----
by_doi: dict[str, dict] = {}
with CSV.open(encoding="utf-8", newline="") as fh:
    for row in csv.DictReader(fh):
        if row.get("doi"):
            by_doi[row["doi"].strip().lower()] = row
print(f"CSV rows loaded by DOI: {len(by_doi)}")

THREAD_LABELS = {
    "T1": "GRN co-option & novelty",
    "T2": "dsx / sex determination",
    "T3": "evo-devo & sexual selection",
    "T4": "atlases & nomenclature",
}

def thread_label(tid: str) -> str:
    return THREAD_LABELS.get(tid, tid)

def format_keywords(row: dict) -> str:
    labels = [thread_label(row["primary_thread"])]
    sec = row.get("secondary_threads") or ""
    for sid in filter(None, (s.strip() for s in sec.split(","))):
        labels.append(thread_label(sid))
    # de-duplicate while preserving order
    seen, out = set(), []
    for lab in labels:
        if lab not in seen:
            seen.add(lab)
            out.append(lab)
    return ", ".join(out)

def format_note(row: dict) -> str:
    primary = row["primary_thread"]
    note = f"Research thread: {primary}"
    sec = row.get("secondary_threads") or ""
    sec_ids = [s.strip() for s in sec.split(",") if s.strip()]
    if sec_ids:
        note += f"; secondary: {', '.join(sec_ids)}"
    return note

# ---- update .bib entries ----
text = BIB.read_text(encoding="utf-8")

# entry -> raw body split (head @type{key, ... fields ... })
entries = re.finditer(
    r"^@(\w+)\s*\{\s*([^,]+)\s*,\s*(.*?)\n\}", text, flags=re.DOTALL | re.MULTILINE
)

updated, skipped = 0, []
out_chunks = []
pos = 0
for m in entries:
    start, end = m.start(), m.end()
    out_chunks.append(text[pos:start])
    pos = end

    kind, key, body = m.group(1), m.group(2).strip(), m.group(3)

    # locate DOI and any existing keywords/note fields in this body
    doi_hit = re.search(r"\bdoi\s*=\s*[{\"]([^}\"]+)[}\"]", body)
    kw_re = re.compile(r"^\s*keywords\s*=\s*\{[^}]*\}\,\s*$", re.MULTILINE)
    note_re = re.compile(r"^\s*note\s*=\s*\{[^}]*\}\,\s*$", re.MULTILINE)

    if not doi_hit:
        skipped.append(key)
        out_chunks.append(text[start:end])
        continue
    doi = doi_hit.group(1).strip().lower()
    row = by_doi.get(doi)
    if not row:
        skipped.append(key)
        out_chunks.append(text[start:end])
        continue

    # drop old thread fields so re-runs stay idempotent
    body = kw_re.sub("", body)
    body = note_re.sub("", body)

    kws = format_keywords(row)
    note = format_note(row)
    extra = f"\n  keywords = {{{kws}}},\n  note     = {{{note}}},"
    # insert before the closing brace (end of body)
    body = body.rstrip() + extra
    out_chunks.append(f"@{kind}{{{key},\n{body}\n}}")
    updated += 1

out_chunks.append(text[pos:])
result = "".join(out_chunks)

BIB.write_text(result, encoding="utf-8")
print(f"Updated {updated} entries; skipped {len(skipped)}: {skipped}")