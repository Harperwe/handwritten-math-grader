"""Run the unmodified official notebook code cells and check its saved output."""
import json
import os
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    notebook = json.loads((root / "example/example.ipynb").read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__"}
    previous_directory = Path.cwd()
    try:
        os.chdir(str(root / "example"))
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                # Only execute trusted code shipped with the pinned repository.
                exec(compile("".join(cell["source"]), "official_example.ipynb", "exec"), namespace)
    finally:
        os.chdir(str(previous_directory))
    expected = "x ^ { 2 } = \\sum \\limits _ { a = 1 } ^ { 3 } x _ { a } ^ { 2 }"
    result = {"expected": expected, "actual": namespace["pred_latex"],
              "matched": namespace["pred_latex"] == expected,
              "scope": "One official notebook sample; not a dataset accuracy measurement."}
    (root / "repro_outputs").mkdir(exist_ok=True)
    (root / "repro_outputs/official_example.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not result["matched"]:
        raise RuntimeError("Official notebook sample output mismatch.")
    print("OFFICIAL_NOTEBOOK_MATCHED")


if __name__ == "__main__":
    main()
