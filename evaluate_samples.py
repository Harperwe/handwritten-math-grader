"""Evaluate the fixed sample manifest, reporting OCR and arithmetic separately."""
import argparse
import csv
import json
import time
from pathlib import Path

from arithmetic import normalize_latex
from recognize_math import Recognizer


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=root / "example/arithmetic_samples/manifest.json")
    parser.add_argument("--output-dir", type=Path, default=root / "repro_outputs/sample_evaluation")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    recognizer = Recognizer()
    rows = []
    start = time.monotonic()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for sample in manifest["samples"]:
        result = recognizer.recognize(root / sample["image"])
        exact = normalize_latex(result["recognized_latex"]) == normalize_latex(sample["expected_latex"])
        grade_match = result["status"] == sample["expected_status"]
        row = dict(sample, **{k: v for k, v in result.items() if k not in sample})
        row.update(ocr_exact_match=exact, judgment_matches_ground_truth=grade_match,
                   ocr_and_judgment_correct=exact and grade_match)
        rows.append(row)
        print("{}: OCR={} grade={} status={}".format(Path(sample["image"]).stem, exact, grade_match, result["status"]), flush=True)
        # Retain completed observations if a later image fails.
        (args.output_dir / "predictions.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    count = len(rows)
    metrics = {"sample_count": count, "ocr_exact_matches": sum(r["ocr_exact_match"] for r in rows),
               "judgment_matches_ground_truth": sum(r["judgment_matches_ground_truth"] for r in rows),
               "ocr_and_judgment_correct": sum(r["ocr_and_judgment_correct"] for r in rows),
               "ungradable_count": sum(r["status"] == "ungradable" for r in rows),
               "duration_seconds": round(time.monotonic() - start, 3),
               "ocr_metric": "Entire-expression equality after removing whitespace and supported LaTeX formatting/operator variants; no symbolic equivalence matching.",
               "limitations": manifest["limitations"], "selection": manifest["selection"]}
    for name in ("ocr_exact_matches", "judgment_matches_ground_truth", "ocr_and_judgment_correct"):
        metrics[name + "_rate"] = metrics[name] / count if count else None
    (args.output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["image", "expected_latex", "recognized_latex", "expected_status", "status", "left_value", "right_value", "ocr_exact_match", "judgment_matches_ground_truth", "ocr_and_judgment_correct"]
    with (args.output_dir / "predictions.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(metrics, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
