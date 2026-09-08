#!/usr/bin/env python3
"""
Drag-and-drop web UI for the PDF -> Obsidian pipeline.

Runs a small local web server where you can drag research PDFs onto a drop
zone; each PDF is processed by pdf_to_obsidian.py and turned into an Obsidian
note in the vault.

Usage:
    python webui.py            # start on http://127.0.0.1:5000
    python webui.py --port 8080
    python webui.py --vault .. # point at the vault root (default: parent dir)

Dependencies:
    flask  (pip install -r requirements.txt)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the pipeline module importable from this folder.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, render_template, request  # noqa: E402

from pdf_to_obsidian import _load_config, process_pdf  # noqa: E402

VAULT = Path(__file__).resolve().parent.parent
app = Flask(__name__)

CFG = _load_config(VAULT / "tools" / "config.yaml")
CFG["vault"] = str(VAULT)


def _rel(path: Path) -> str:
    """Return a vault-relative path for display."""
    try:
        return str(Path(path).resolve().relative_to(VAULT.resolve()))
    except ValueError:
        return str(path)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """Accept one or more PDFs, run the pipeline, and report results."""
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files received"}), 400

    inbox = Path(CFG["vault"]) / CFG["inbox"]
    inbox.mkdir(parents=True, exist_ok=True)

    results = []
    for f in files:
        name = Path(f.filename or "upload.pdf").name
        if not name.lower().endswith(".pdf"):
            results.append({"file": name, "status": "error", "message": "Not a PDF file"})
            continue
        dest = inbox / name
        try:
            f.save(dest)
        except Exception as exc:  # pragma: no cover
            results.append({"file": name, "status": "error", "message": f"Save failed: {exc}"})
            continue
        try:
            note = process_pdf(dest, CFG)
            if note:
                results.append({"file": name, "status": "ok", "note": _rel(note)})
            else:
                results.append({"file": name, "status": "error",
                                "message": "No extractable text (scanned PDF?)"})
        except Exception as exc:
            results.append({"file": name, "status": "error", "message": str(exc)})

    return jsonify({"results": results})


@app.route("/notes")
def notes():
    """List generated source notes (most recent first)."""
    sources = Path(CFG["vault"]) / CFG["sources"]
    if not sources.exists():
        return jsonify({"notes": []})
    items = []
    for p in sorted(sources.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append({"name": p.stem, "path": _rel(p)})
    return jsonify({"notes": items})


@app.route("/note")
def note():
    """Return the raw markdown content of a source note for preview."""
    rel = request.args.get("path", "")
    target = (VAULT / rel).resolve()
    # Only allow reading files inside the vault.
    if not str(target).startswith(str(VAULT.resolve())) or not target.exists():
        return jsonify({"error": "Not found"}), 404
    return target.read_text(encoding="utf-8"), 200, {"Content-Type": "text/plain; charset=utf-8"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drag-and-drop PDF -> Obsidian web UI")
    parser.add_argument("--vault", default=str(VAULT), help="Path to the vault root")
    parser.add_argument("--port", type=int, default=5000, help="Port to serve on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    args = parser.parse_args(argv)

    CFG["vault"] = args.vault
    print(f"[*] Vault: {args.vault}")
    print(f"[*] Drag-and-drop UI: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
