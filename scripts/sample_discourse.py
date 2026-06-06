"""Sample Discourse JSONL data into a single output file.

Usage:
	python sample_discourse.py
	python sample_discourse.py --total-sample 5000 --seed 42
	python sample_discourse.py --source-dir ./discourse --pattern "*_posts.jsonl"
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

def collect_jsonl_files(source_dir: Path, pattern: str) -> list[Path]:
	files = sorted([p for p in source_dir.glob(pattern) if p.is_file()])
	if not files:
		raise FileNotFoundError(
			f"No files matched pattern '{pattern}' in '{source_dir}'."
		)
	return files


def sample_rows(files: list[Path], k: int, rng: random.Random) -> list[dict]:
	# Reservoir sampling keeps memory usage bounded regardless of input size.
	reservoir: list[dict] = []
	seen = 0

	for file_path in files:
		with file_path.open("r", encoding="utf-8") as infile:
			for line_num, line in enumerate(infile, start=1):
				text = line.strip()
				if not text:
					continue

				try:
					row = json.loads(text)
				except json.JSONDecodeError:
					print(f"Skipping invalid JSON in {file_path}:{line_num}")
					continue

				seen += 1
				if len(reservoir) < k:
					reservoir.append(row)
					continue

				pick = rng.randint(0, seen - 1)
				if pick < k:
					reservoir[pick] = row

	rng.shuffle(reservoir)
	return reservoir


def write_jsonl(rows: list[dict], out_file: Path) -> None:
	out_file.parent.mkdir(parents=True, exist_ok=True)
	with out_file.open("w", encoding="utf-8") as outfile:
		for row in rows:
			outfile.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
	parser = argparse.ArgumentParser(
		description="Sample rows from Discourse JSONL files into one JSONL output file."
	)
	parser.add_argument(
		"--source-dir",
		default="./discourse",
		help="Directory containing source JSONL files.",
	)
	parser.add_argument(
		"--pattern",
		default="*.jsonl",
		help="Glob pattern used to select input files.",
	)
	parser.add_argument(
		"--total-sample",
		type=int,
		default=15000,
		help="Total number of rows to sample across all inputs.",
	)
	parser.add_argument(
		"--out",
		default="discourse_sample.jsonl",
		help="Output JSONL file path.",
	)
	parser.add_argument(
		"--seed",
		type=int,
		default=None,
		help="Optional random seed for reproducible sampling.",
	)
	args = parser.parse_args()

	if args.total_sample <= 0:
		raise ValueError("--total-sample must be a positive integer.")

	source_dir = Path(args.source_dir)
	out_file = Path(args.out)
	if not source_dir.is_absolute():
		source_dir = (SCRIPT_DIR / source_dir).resolve()
	if not out_file.is_absolute():
		out_file = (SCRIPT_DIR / out_file).resolve()
	rng = random.Random(args.seed)

	files = collect_jsonl_files(source_dir, args.pattern)
	sampled = sample_rows(files, args.total_sample, rng)
	write_jsonl(sampled, out_file)

	print(f"Input files: {len(files)}")
	print(f"Sampled rows written: {len(sampled)}")
	print(f"Output file: {out_file}")


if __name__ == "__main__":
	main()