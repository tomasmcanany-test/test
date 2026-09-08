# Drosophila Terminalia — Knowledge Vault

An **Obsidian vault** + automated **PDF → note pipeline** for building a
curated, cross-linked knowledge base on **Drosophila melanogaster terminalia
developmental evolution and genetics**.

This is designed to be a *living* reference you can query for authoritative
knowledge: every source paper becomes a structured note, every concept gets its
own note, and everything is linked into a graph you can navigate in Obsidian.

## What's inside

| Folder | Purpose |
|--------|---------|
| `00_Inbox/` | **Drop research PDFs here** to be processed |
| `01_Sources/` | Generated article notes (one per PDF) |
| `02_Concepts/` | Concept/term notes (Hox genes, genital disc, dsx, …) |
| `03_Organisms/` | Species notes (e.g., *D. melanogaster*) |
| `04_MOCs/` | Maps of Content — the hub that ties everything together |
| `05_Templates/` | Obsidian templates for new notes |
| `06_Attachments/` | Extracted figures/images |
| `07_Archive/` | Processed PDFs (moved here after conversion) |
| `08_Reviews/` | In-depth literature reviews with figure-by-figure analysis |
| `tools/` | The automation pipeline, figure extraction, and Zotero tool |

## Quick start

1. **Open the vault in Obsidian** — File → Open folder as vault → select this
   folder. Enable "Automatically update internal links" if prompted.
2. **Install the pipeline dependencies** (Python 3.9+):
   ```bash
   cd tools
   pip install -r requirements.txt
   ```
3. **Drop research PDFs** into `00_Inbox/` (or use the **drag-and-drop UI**).

   **Option A — command line:**
   ```bash
   python tools/pdf_to_obsidian.py --vault .
   ```

   **Option B — drag-and-drop web UI:**
   ```bash
   python tools/webui.py
   # then open http://127.0.0.1:5000 in your browser
   ```

   Each PDF becomes a structured note in `01_Sources/`, auto-linked to relevant
   concepts and the [[Drosophila Terminalia - MOC]].

See **[`tools/README.md`](tools/README.md)** for learn how to:
- enable **LLM summarization** (OpenAI or any compatible endpoint, e.g. LM Studio)
- use **Crossref** to auto-fill title/authors/year/DOI/abstract
- run in **watch mode** to process PDF as soon as they're dropped in
- extend the **concept index** so new terms auto-link

## How the the knowledge graph works

- **MOC** = [[Drosophila Terminalia - MOC]] is the front door.
- **Concepts** (e.g., [[Genital Disc]], [[Doublesex (dsx)]]) are authoritative
  reference notes with definitions, key facts, and cross-links.
- **Sources** = individual papers, each linked to the concepts they discuss.
- In Obsidian's **Graph View** you can explore how papers and concepts connect.

## Notes on accuracy

- Concept and organism notes here are written as a starting skeleton and should
  be **verified and expanded** against primary literature as you add sources.
- Source notes capture what the paper itself says (abstract/excerpt + optional
  LLM summary); they are *attributed* to their source, so you can always trace
  a claim back to the paper.

## Roadmap ideas

- Add a Dataview query to auto-list all sources tagged per concept.
- Add templates for "gene", "mututant", and "method" note types.
- Integrate a citation manager (Zotero) export as a secondary metadata source.
