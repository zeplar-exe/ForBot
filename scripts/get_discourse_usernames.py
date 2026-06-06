"""
Extract unique usernames from Discourse JSONL files.

Usage:
    python get_discourse_usernames.py posts.jsonl
    python get_discourse_usernames.py ./discourse/
"""

import argparse
import json
from pathlib import Path


def extract_usernames(path: Path) -> set[str]:
    usernames = set()
    files = list(path.glob("*.jsonl")) if path.is_dir() else [path]
    for f in files:
        with f.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if "username" in obj:
                    usernames.add(obj["username"])
    return usernames


def main():
    parser = argparse.ArgumentParser(description="Extract unique usernames from Discourse JSONL files.")
    parser.add_argument("path", type=Path, help="JSONL file or directory of JSONL files")
    args = parser.parse_args()

    if not args.path.exists():
        parser.error(f"{args.path} does not exist")

    usernames = extract_usernames(args.path)
    for name in sorted(usernames):
        print(name)


if __name__ == "__main__":
    main()
