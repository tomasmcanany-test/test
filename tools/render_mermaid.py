"""Render the Mermaid graph in '04_MOCs/Research Threads - Graph.md' to PNG & SVG.

Uses the public mermaid.ink rendering service (no local install required).
Saves outputs into 06_Attachments/.
"""
import base64
import re
import urllib.parse
import urllib.request
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
NOTE = VAULT / "04_MOCs" / "Research Threads - Graph.md"
OUT = VAULT / "06_Attachments"
OUT.mkdir(exist_ok=True)

def extract_mermaid(text: str) -> str:
    blocks = re.findall(r"```mermaid\s*\n(.*?)```", text, flags=re.DOTALL)
    if not blocks:
        raise SystemExit("No ```mermaid``` block found.")
    return blocks[0].strip()

def fetch(prefix: str, out_name: str, query: str = ""):
    target = prefix + urllib.parse.quote(base64.b64encode(code.encode("utf-8"))) + query
    req = urllib.request.Request(
        target,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    path = OUT / out_name
    path.write_bytes(data)
    print(f"OK  {path.name}  ({len(data)} bytes, HTTP {resp.status})")
    return path

code = extract_mermaid(NOTE.read_text(encoding="utf-8"))
print(f"Mermaid block: {len(code)} chars")

png = fetch("https://mermaid.ink/img/", "research-threads-graph.png", "?type=png")
svg = fetch("https://mermaid.ink/svg/", "research-threads-graph.svg")
print("Done.")