"""Prepare a fixed convenience subset from the repository's CROHME archive."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

from arithmetic import judge_latex


def main():
    from PIL import Image, ImageDraw
    root = Path(__file__).resolve().parent
    destination = root / "example/arithmetic_samples"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(root / "data.zip")) as archive:
        rows = []
        for line in archive.read("data/2016/caption.txt").decode("utf-8").splitlines():
            parts = line.split()
            latex = " ".join(parts[1:])
            truth = judge_latex(latex)
            if truth["status"] not in ("correct", "incorrect"):
                continue
            member = "data/2016/img/{}.bmp".format(parts[0])
            content = archive.read(member)
            target = destination / "{}.bmp".format(parts[0])
            target.write_bytes(content)
            with Image.open(io.BytesIO(content)) as image:
                size = list(image.size)
            rows.append({"image": target.relative_to(root).as_posix(), "expected_latex": latex,
                         "expected_status": truth["status"], "expected_left_value": truth["left_value"],
                         "expected_right_value": truth["right_value"], "source_member": member,
                         "image_sha256": hashlib.sha256(content).hexdigest(), "size": size})
            if len(rows) == 20:
                break
    manifest = {"selection": "First 20 numeric equations in data/2016/caption.txt that are in the arithmetic parser's scope; selected before prediction.",
                "limitations": "Convenience subset, not random or representative, not full CROHME evaluation, not user photographs. Source captions are the OCR references; mathematical truth is reviewed separately.",
                "samples": rows}
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheet = Image.new("RGB", (1200, 110 * 10), "white")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        x, y = (index % 2) * 600, (index // 2) * 110
        with Image.open(str(root / row["image"])) as source:
            image = source.convert("RGB")
            image.thumbnail((570, 76))
            sheet.paste(image, (x + 8, y + 26))
        draw.text((x + 8, y + 4), "{}: {} ({})".format(index + 1, Path(row["image"]).stem, row["expected_status"]), fill="black")
    (root / "repro_outputs").mkdir(exist_ok=True)
    sheet.save(str(root / "repro_outputs/sample_contact_sheet.png"))
    print("Prepared {} unmodified CROHME sample images.".format(len(rows)))


if __name__ == "__main__":
    main()
