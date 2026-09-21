"""Download only the official ABB sources; TLS verification remains enabled."""
import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / "data/manuals"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for entry in manifest:
            target = directory / entry["filename"]
            if not target.exists():
                response = client.get(entry["source_url"])
                response.raise_for_status()
                if not response.content.startswith(b"%PDF-"):
                    raise ValueError(f"ABB returned non-PDF data: {entry['source_url']}")
                temporary = target.with_suffix(".part")
                temporary.write_bytes(response.content)
                temporary.replace(target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            expected = entry.get("verified_sha256")
            if expected and expected != digest:
                raise ValueError(f"PDF changed: reverify metadata for {target.name}")
            print(f"{target.name}: {target.stat().st_size} bytes; SHA256 {digest}")


if __name__ == "__main__":
    main()
