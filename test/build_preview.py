"""Embed a public snapshot in a self-contained, offline-capable test HTML."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(snapshot_path, output_path):
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("mode") != "test":
        raise ValueError("Only version-1 test snapshots may be rendered")
    template = (HERE / "overview.template.html").read_text(encoding="utf-8")
    if template.count("__CITY_DATA__") != 1:
        raise ValueError("Template must contain exactly one data placeholder")
    # Prevent closing a script block through source-supplied strings.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template.replace("__CITY_DATA__", payload), encoding="utf-8")
    print(f"Test preview: {output_path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=HERE / "overview-data.json")
    parser.add_argument("--output", type=Path, default=HERE / "overview.html")
    args = parser.parse_args()
    build(args.snapshot, args.output)


if __name__ == "__main__":
    main()
