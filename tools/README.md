# pdf_to_obsidian — Automation Pipeline

Converts research article **PDFs** into structured **Obsidian** notes for the
Drosophila terminalia vault.

There are two ways to run it: the **command line** (below) or the
**drag-and-drop web UI** (`webui.py`).

## Install

```bash
cd tools
pip install -r requirements.txt
```

Requires Python 3.9+.

## Figure extraction (for literature reviews)

Extract figure images from a research PDF so they can be interpreted and
embedded alongside literature reviews:

```bash
python tools/extract_figures.py --pdf "07_Archive/paper.pdf" --out "06_Attachments/paper-slug"
```

Requires `pymupdf` (`pip install pymupdf`). Images above a size threshold are
saved as PNGs into the output folder (skip logos/icons with `--min`).

## Zotero integration

A reusable tool to **add papers to a Zotero collection** (e.g., to flag them for
you to download through your library access).

```bash
set ZOTERO_KEY=your_api_key
python tools/zotero_add.py --papers tools/papers.json --collection "Drosophila Terminalia"
```

- Papers are read from a JSON file (see `tools/papers.json` for the format).
- Creates (or reuses) the collection and adds each paper as a journal article.
- Tags papers (default: `terminalia`, `to-download`) so you can filter and find
  them in Zotero.

> **Security:** the key is read from the `ZOTERO_KEY` env var, never stored in
> the vault. Create a scoped, revocable key at
> https://www.zotero.org/settings/keys and revoke it when you're done.

## Drag-and-drop web UI

A small local web app where you can **drag and drop PDFs** onto a drop zone
instead of using the command line.

```bash
cd tools
python webui.py
# then open http://127.0.0.1:5000 in your browser
```

Options: `--port 8080`, `--host 0.0.0.0`, `--vault <path>`.

- Drop one or more PDFs onto the drop zone (or click to browse).
- Click **Process** — each PDF runs through the same pipeline as the CLI.
- Results show whether each note was created, with a **view** link to preview
  the generated markdown.
- The **Recent notes** panel lists all source notes in the vault.

> Note: the UI runs the pipeline locally on your machine. It is intended for
> local use only (bound to `127.0.0.1` by default).

## Usage

All commands run from the **vault root** (the folder containing `00_Inbox/`).

### Process every PDF in the inbox

```bash
python tools/pdf_to_obsidian.py --vault .
```

### Process a single PDF

```bash
python tools/pdf_to_obsidian.py --vault . --pdf path/to/paper.pdf
```

### Watch mode (auto-process new PDFs)

```bash
python tools/pdf_to_obsidian.py --vault . --watch
```

The script polls `00_Inbox/` every 5 seconds and processes any new `.pdf` as
soon as it appears. Stop with `Ctrl+C`.

## What the pipeline does for each PDF

1. **Extracts text** from the PDF (pypdf).
2. **Finds the DOI** and queries **Crossref** to auto-fill title, authors,
   year, journal, and abstract. If no DOI/Crossref match, it falls back to a
   conservative heuristic parse of the first page (it never fabricates facts).
3. **Builds a note** with YAML frontmatter (type, title, authors, year,
   journal, DOI, tags, source file, created date).
4. **Auto-links concepts** — scans the text against `concepts_index.json` and
   adds matching tags + wikilinks to concept notes.
5. **Auto-links related papers** — scans the text (reference lists, author-year
   citations, DOIs) against `papers_index.json` and adds a `## Related Papers`
   section of wikilinks, skipping the paper's own note (never self-links).
6. **Optionally summarizes** with an LLM (see below).
7. **Archives** the PDF into `07_Archive/`.

The note links back to the **[[Drosophila Terminalia - MOC]]** automatically.

## Configuration

Edit `config.yaml`. All paths are relative to the vault root.

```yaml
vault: "."
inbox: "00_Inbox"
sources: "01_Sources"
concepts: "02_Concepts"
organisms: "03_Organisms"
mocs: "04_MOCs"
attachments: "06_Attachments"
archive: "07_Archive"
template: "05_Templates/Source Note Template.md"
concepts_index: "tools/concepts_index.json"
papers_index: "tools/papers_index.json"
```

### Enable LLM summarization

The pipeline can generate a **Summary**, **Key Findings**, and **Methods** for
each paper using any OpenAI-compatible chat endpoint — including **LM Studio**
running locally.

1. In `config.yaml`, set:
   ```yaml
   llm:
     enabled: true
     base_url: "http://localhost:1234/v1"   # example: local LM Studio
     model: "your-model-name"
     api_key_env: "OPENAI_API_KEY"
   ```
2. Provide an API key via the environment variable named in `api_key_env`
   (for local LM Studio, any non-empty value works, e.g. `set OPENAI_API_KEY=local`).

When disabled (default), the pipeline uses the paper's abstract/excerpt instead.

### Extend the concept index

`concepts_index.json` maps a term to a concept note filename. When a paper's
text contains the term, the pipeline auto-tags and auto-links it.

```json
{
  "terminalia": "Drosophila Terminalia",
  "genital disc": "Genital Disc"
}
```

Add entries as your knowledge base grows — new terms will automatically link in
future runs.

### Extend the paper index

`papers_index.json` drives the `## Related Papers` auto-linking. Each record has:

- `title` — the paper's title (used for substring matching against extracted text)
- `doi` — the DOI (primary match; must appear literally in the text)
- `note` — the Obsidian note display name emitted as `[[note]]`
- `aliases` — author-year citation strings to match, e.g. `"Glassford et al., 2015"`

```json
{
  "_comment": "...",
  "papers": [
    {
      "title": "Co-option of an Ancestral Hox-Regulated Network ...",
      "doi": "10.1016/j.devcel.2015.08.005",
      "note": "Co-option of an Ancestral Hox-Regulated Network ...",
      "aliases": ["Glassford et al., 2015", "Glassford et al. 2015"]
    }
  ]
}
```

A paper is linked when its DOI, any of its aliases, or its title appears in the
text. The pipeline skips the current paper's own note so files never self-link.

## Idempotency & safety

- Re-running is safe: it never overwrites an existing note (it appends a number
  instead) and never deletes your PDFs (it moves them to `07_Archive/`).
- If a PDF has no extractable text (e.g., scanned/image-only), it is skipped
  and left in the inbox.
- Failures on one PDF don't stop the rest.

## Troubleshooting

- **`pypdf` not found** → run `pip install -r requirements.txt`.
- **No Crossref metadata** → the note falls back to first-page heuristics; you
  can fill in details manually.
- **LLM summary not appearing** → check `enabled: true` in config and that the
  API key env var is set.
