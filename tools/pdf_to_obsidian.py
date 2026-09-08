#!/usr/bin/env python3
"""
PDF -> Obsidian knowledge pipeline for the Drosophila terminalia vault.

This tool converts research article PDFs into structured Obsidian markdown
notes with YAML frontmatter, tags, and automatic wikilinks to the vault's
concept notes. It is designed to be idempotent and safe to re-run.

Pipeline stages for each PDF:
  1. Extract full text from the PDF (pypdf).
  2. Detect a DOI and try to enrich metadata from Crossref (title, authors,
     year, journal, abstract). Falls back to heuristic first-page parsing.
  3. Generate a structured Obsidian note with YAML frontmatter.
  4. Auto-link any known concepts/tags found in the text.
  5. Optionally generate an LLM summary if an API key is configured.
  6. Move the processed PDF into the archive folder.

Usage:
  # Process every PDF in the inbox folder
  python pdf_to_obsidian.py --inbox 00_Inbox --vault ..

  # Process a single PDF
  python pdf_to_obsidian.py --pdf path/to/paper.pdf --vault ..

  # Watch the inbox and process new files as they appear
  python pdf_to_obsidian.py --inbox 00_Inbox --vault .. --watch

Dependencies (see requirements.txt):
  pypdf, requests, pyyaml
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DEFAULT_CONFIG = {
    "vault": ".",
    "inbox": "00_Inbox",
    "sources": "01_Sources",
    "concepts": "02_Concepts",
    "organisms": "03_Organisms",
    "mocs": "04_MOCs",
    "attachments": "06_Attachments",
    "archive": "07_Archive",
    "template": "05_Templates/Source Note Template.md",
    "concepts_index": "tools/concepts_index.json",
    "papers_index": "tools/papers_index.json",
    "doi_regex": r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",
    "crossref_timeout": 15,
    "llm": {
        "enabled": False,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
}


def _load_config(path: Path) -> dict:
    """Load a YAML/JSON config file merged over the defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if path and path.exists():
        text = path.read_text(encoding="utf-8")
        try:
            loaded = yaml.safe_load(text) if yaml else json.loads(text)
        except Exception:
            loaded = None
        if isinstance(loaded, dict):
            _deep_update(cfg, loaded)
    return cfg


def _deep_update(target: dict, source: dict) -> None:
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_update(target[k], v)
        else:
            target[k] = v


# --------------------------------------------------------------------------- #
# Text extraction
# --------------------------------------------------------------------------- #

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF. Returns '' if the PDF cannot be read."""
    if PdfReader is None:
        raise RuntimeError("pypdf is required. Run: pip install -r requirements.txt")
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n\n".join(pages)


# --------------------------------------------------------------------------- #
# DOI / Crossref metadata
# --------------------------------------------------------------------------- #

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def find_doi(text: str) -> str | None:
    """Find the first DOI-like string in the text."""
    match = DOI_RE.search(text or "")
    return match.group(0).rstrip(".,;") if match else None


def fetch_crossref(doi: str, timeout: int = 15) -> dict | None:
    """Fetch bibliographic metadata for a DOI from Crossref."""
    if requests is None:
        return None
    url = f"https://api.crossref.org/works/{doi}"
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "pdf-to-obsidian/1.0 (mailto:you@example.com)"})
        if resp.status_code != 200:
            return None
        data = resp.json().get("message", {})
        return {
            "title": (data.get("title") or [""])[0],
            "authors": [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in data.get("author", [])
            ],
            "year": _extract_year(data.get("issued", {})),
            "journal": (data.get("container-title") or [""])[0],
            "doi": doi,
            "abstract": _strip_jats(data.get("abstract", "")),
            "type": data.get("type", ""),
        }
    except Exception:
        return None


def _extract_year(issued: dict) -> str | None:
    parts = issued.get("date-parts") or []
    if parts and parts[0]:
        return str(parts[0][0])
    return None


def _strip_jats(text: str) -> str:
    """Remove JATS XML tags from an abstract string."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- #
# Heuristic first-page metadata
# --------------------------------------------------------------------------- #

def heuristic_metadata(text: str) -> dict:
    """
    Best-effort metadata extraction from the first page when no DOI/Crossref
    metadata is available. This is intentionally conservative; it never
    fabricates facts, it only captures text that is already on the page.
    """
    first_page = (text or "").split("\n\n")[0]
    lines = [ln.strip() for ln in first_page.splitlines() if ln.strip()]

    title = ""
    authors: list[str] = []
    journal = ""
    year = ""

    # Heuristic: the title is usually the longest early line(s) in title case.
    # We take the first line that looks like a title (not an email/URL/DOI),
    # then join short continuation lines that look like the rest of a wrapped
    # title (they are not separated by blank lines and are not a full sentence).
    for idx, ln in enumerate(lines[:6]):
        if not ln or re.search(r"@|http|doi|^\d", ln, re.IGNORECASE):
            continue
        if len(ln) > 25:
            title = ln
            # Join continuation lines that look like wrapped title text.
            # Stop at lines with commas (author/affiliation lines) or sentence
            # punctuation, and cap the joined length to stay conservative.
            for cont in lines[idx + 1:idx + 4]:
                if (not cont or len(cont) < 8 or len(cont) > 80
                        or "," in cont
                        or re.search(r"@|http|doi|^\d", cont, re.IGNORECASE)):
                    break
                if cont.endswith((".", "?", "!")):
                    break
                title = f"{title} {cont}"
            break

    # Year: first 4-digit number in 1900-2099 range.
    for ln in lines[:15]:
        m = re.search(r"\b(19|20)\d{2}\b", ln)
        if m:
            year = m.group(0)
            break

    # Authors: lines before the title that look like "A. B. Lastname, ..."
    for ln in lines[:10]:
        if re.match(r"^[\w.\- ]+,", ln) and len(ln) < 120:
            authors = [a.strip() for a in ln.split(",") if a.strip()]
            if authors:
                break

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "doi": "",
        "abstract": "",
    }


# --------------------------------------------------------------------------- #
# Concept linking
# --------------------------------------------------------------------------- #

def load_concepts_index(path: Path) -> dict:
    """Load the concept index mapping term -> concept note filename."""
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


# --------------------------------------------------------------------------- #
# Paper linking
# --------------------------------------------------------------------------- #

def load_papers_index(path: Path) -> list[dict]:
    """Load the paper index (list of {title, doi, note, aliases} records)."""
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("papers", [])
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _norm_span(text: str) -> str:
    """Collapse case/punctuation so substring matching is robust."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower())


def build_paper_links(text: str, papers_index: list[dict],
                      exclude_doi: str = "", exclude_title: str = "") -> list[str]:
    """
    Return Obsidian display names for papers referenced in ``text``.

    A record matches if its DOI appears in the text, any author-year alias
    appears, or its (substantial) title appears. The current paper's own DOI or
    title can be excluded so a note never links to itself. Matches are returned
    once, in index order, as display names suitable for ``[[name]]`` links.
    """
    if not papers_index:
        return []
    lower = (text or "").lower()
    norm = _norm_span(text)
    ex_doi = (exclude_doi or "").lower()
    ex_title = _norm_span(exclude_title)
    found: list[str] = []
    seen: set[str] = set()
    for entry in papers_index:
        note = entry.get("note") or entry.get("title") or ""
        if not note:
            continue
        doi = (entry.get("doi") or "").lower()
        # Never link a paper to itself.
        if ex_doi and doi == ex_doi:
            continue
        if ex_title and len(ex_title.split()) >= 5 and ex_title in _norm_span(note):
            continue
        matched = bool(doi) and doi in lower
        if not matched:
            for alias in entry.get("aliases", []):
                if _norm_span(alias) in norm:
                    matched = True
                    break
        if not matched:
            t = _norm_span(entry.get("title") or "")
            if t and len(t.split()) >= 5 and t in norm:
                matched = True
        if matched and note not in seen:
            seen.add(note)
            found.append(note)
    return found


def build_concept_links(text: str, concepts_index: dict) -> tuple[list[str], list[str]]:
    """
    Return (tags, links) for concepts found in the text.
    tags   -> Obsidian tags (lowercased, spaces -> dashes)
    links  -> wikilinks to concept notes
    """
    tags: list[str] = []
    links: list[str] = []
    lower = (text or "").lower()
    for term, note_file in concepts_index.items():
        if term.lower() in lower:
            tags.append(term.lower().replace(" ", "-"))
            links.append(note_file)
    # De-duplicate while preserving order
    tags = list(dict.fromkeys(tags))
    links = list(dict.fromkeys(links))
    return tags, links


# --------------------------------------------------------------------------- #
# LLM summarization (optional)
# --------------------------------------------------------------------------- #

def llm_summary(text: str, cfg: dict) -> dict | None:
    """Generate a structured summary via an OpenAI-compatible endpoint."""
    llm = cfg.get("llm", {})
    if not llm.get("enabled") or requests is None:
        return None
    api_key = os.environ.get(llm.get("api_key_env", "OPENAI_API_KEY"))
    if not api_key:
        return None

    excerpt = text[:12000]
    prompt = (
        "You are a research assistant building a knowledge base on Drosophila "
        "melanogaster terminalia developmental evolution and genetics. From the "
        "article excerpt below, produce a JSON object with exactly these keys: "
        '"summary" (2-4 sentences), "key_findings" (list of 3-6 bullet findings), '
        '"methods" (short string), "concepts" (list of relevant concept terms). '
        "Return only valid JSON.\n\nARTICLE:\n" + excerpt
    )
    try:
        resp = requests.post(
            f"{llm.get('base_url').rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": llm.get("model"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown fences if present
        content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
        return json.loads(content)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Note generation
# --------------------------------------------------------------------------- #

def clean_text(text: str) -> str:
    """Strip HTML tags and collapse whitespace/newlines (e.g. Crossref titles)."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(name: str) -> str:
    name = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[\s_]+", "-", name)


def safe_filename(title: str, year: str = "") -> str:
    base = slugify(clean_text(title) or "untitled")
    base = base[:80].rstrip("-")
    if year:
        base = f"{base}-{year}"
    return base or "untitled"


def build_note(meta: dict, text: str, cfg: dict, concepts_index: dict,
               llm: dict | None, source_pdf: str,
               papers_index: list[dict] | None = None,
               exclude_doi: str = "", exclude_title: str = "") -> str:
    """Assemble the full Obsidian markdown note."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tags, links = build_concept_links(text, concepts_index)
    paper_links = build_paper_links(text, papers_index or [],
                                    exclude_doi=exclude_doi,
                                    exclude_title=exclude_title)
    title = clean_text(meta.get("title", ""))

    frontmatter = {
        "type": "source",
        "title": title,
        "authors": meta.get("authors", []),
        "year": meta.get("year", ""),
        "journal": meta.get("journal", ""),
        "doi": meta.get("doi", ""),
        "source_pdf": source_pdf,
        "created": now,
        "tags": ["source", "drosophila"] + tags,
    }

    # ---- Body ------------------------------------------------------------ #
    body = []
    body.append(f"# {title or 'Untitled'}")
    body.append("")

    if meta.get("authors"):
        body.append(f"**Authors:** {', '.join(meta['authors'])}")
    if meta.get("year"):
        body.append(f"**Year:** {meta['year']}")
    if meta.get("journal"):
        body.append(f"**Journal:** {meta['journal']}")
    if meta.get("doi"):
        body.append(f"**DOI:** [{meta['doi']}](https://doi.org/{meta['doi']})")
    if source_pdf:
        body.append(f"**Original paper:** ![[{source_pdf}]]")
    body.append("")

    # LLM summary (if available)
    if llm:
        if llm.get("summary"):
            body.append("## Summary")
            body.append(llm["summary"])
            body.append("")
        if llm.get("key_findings"):
            body.append("## Key Findings")
            for f in llm["key_findings"]:
                body.append(f"- {f}")
            body.append("")

    # Abstract (Crossref or heuristic)
    if meta.get("abstract"):
        body.append("## Abstract")
        body.append(clean_text(meta["abstract"]))
        body.append("")

    # Raw excerpt fallback when no abstract/summary exists
    if not meta.get("abstract") and not (llm and llm.get("summary")):
        excerpt = re.sub(r"\s+", " ", (text or ""))[:1500]
        if excerpt:
            body.append("## Excerpt")
            body.append(excerpt)
            body.append("")

    # Methods (LLM)
    if llm and llm.get("methods"):
        body.append("## Methods")
        body.append(llm["methods"])
        body.append("")

    # Related concepts
    if links:
        body.append("## Related Concepts")
        body.append(" ".join(f"[[{ln}]]" for ln in links))
        body.append("")

    # Related papers (auto-detected citations)
    if paper_links:
        body.append("## Related Papers")
        body.extend(f"- [[{p}]]" for p in paper_links)
        body.append("")

    # Backlink to the MOC
    body.append("## Map")
    body.append("[[Drosophila Terminalia - MOC]]")
    body.append("")

    # Tags
    if tags:
        body.append("---")
        body.append("")
        body.append(" ".join(f"#{t}" for t in tags))
        body.append("")

    # ---- Assemble -------------------------------------------------------- #
    fm_yaml = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) if yaml else json.dumps(frontmatter)
    return f"---\n{fm_yaml}---\n\n" + "\n".join(body).strip() + "\n"


# --------------------------------------------------------------------------- #
# Processing
# --------------------------------------------------------------------------- #

def process_pdf(pdf_path: Path, cfg: dict) -> Path | None:
    """Process a single PDF and write its Obsidian note. Returns note path."""
    print(f"[*] Processing: {pdf_path.name}")
    text = extract_pdf_text(pdf_path)
    if not text.strip():
        print(f"[!] No extractable text in {pdf_path.name}; skipping.")
        return None

    concepts_index = load_concepts_index(Path(cfg["vault"]) / cfg["concepts_index"])
    papers_index = load_papers_index(Path(cfg["vault"]) / cfg["papers_index"])

    # 1) Try Crossref via DOI
    doi = find_doi(text)
    meta = fetch_crossref(doi, cfg.get("crossref_timeout", 15)) if doi else None
    if meta is None:
        meta = heuristic_metadata(text)
    if not meta.get("doi") and doi:
        meta["doi"] = doi

    # 2) Optional LLM summary
    llm = llm_summary(text, cfg)

    # 3) Build the note
    note = build_note(meta, text, cfg, concepts_index, llm, pdf_path.name,
                      papers_index=papers_index,
                      exclude_doi=meta.get("doi", ""),
                      exclude_title=meta.get("title", ""))
    filename = safe_filename(meta.get("title", ""), meta.get("year", ""))
    out_dir = Path(cfg["vault"]) / cfg["sources"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{filename}.md"

    # Avoid clobbering an existing note; append a counter.
    counter = 1
    while out_path.exists():
        out_path = out_dir / f"{filename}-{counter}.md"
        counter += 1

    out_path.write_text(note, encoding="utf-8")
    print(f"[+] Wrote note: {out_path}")

    # 4) Archive the PDF
    archive_dir = Path(cfg["vault"]) / cfg["archive"]
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / pdf_path.name
    if not dest.exists():
        shutil.move(str(pdf_path), str(dest))
        print(f"[+] Archived PDF: {dest}")
    else:
        print(f"[!] Archive already contains {pdf_path.name}; leaving inbox file.")
    return out_path


def process_inbox(cfg: dict) -> int:
    inbox = Path(cfg["vault"]) / cfg["inbox"]
    inbox.mkdir(parents=True, exist_ok=True)
    count = 0
    for pdf in sorted(inbox.glob("*.pdf")):
        try:
            if process_pdf(pdf, cfg):
                count += 1
        except Exception as exc:  # keep going on individual failures
            print(f"[!] Failed on {pdf.name}: {exc}")
    return count


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert research PDFs into structured Obsidian notes."
    )
    parser.add_argument("--vault", default=".", help="Path to the vault root (default: .)")
    parser.add_argument("--config", default="tools/config.yaml", help="Path to config file")
    parser.add_argument("--inbox", help="Process all PDFs in the inbox folder")
    parser.add_argument("--pdf", help="Process a single PDF file")
    parser.add_argument("--watch", action="store_true",
                        help="Watch the inbox and process new PDFs as they appear")
    args = parser.parse_args(argv)

    cfg = _load_config(Path(args.vault) / args.config)
    cfg["vault"] = args.vault

    if args.pdf:
        process_pdf(Path(args.pdf), cfg)
        return 0

    if args.watch:
        print(f"[*] Watching {Path(cfg['vault']) / cfg['inbox']} for new PDFs...")
        try:
            while True:
                process_inbox(cfg)
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n[.] Stopped watching.")
        return 0

    count = process_inbox(cfg)
    print(f"[=] Processed {count} PDF(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
