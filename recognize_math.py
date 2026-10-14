"""Single-image CPU inference using the original CoMER notebook operations."""
import argparse
import json
import sys
from pathlib import Path

from arithmetic import judge_latex

ROOT = Path(__file__).resolve().parent
DEFAULT_CHECKPOINT = ROOT / "lightning_logs/version_0/checkpoints/epoch=151-step=57151-val_ExpRate=0.6365.ckpt"


class Recognizer:
    def __init__(self, checkpoint=DEFAULT_CHECKPOINT, threads=4):
        import torch
        from comer.lit_comer import LitCoMER
        from torchvision.transforms import ToTensor
        from comer.datamodule import vocab
        checkpoint = Path(checkpoint).resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError("Checkpoint not found: {}".format(checkpoint))
        torch.set_num_threads(threads)
        self.torch, self.to_tensor, self.vocab = torch, ToTensor(), vocab
        self.model = LitCoMER.load_from_checkpoint(str(checkpoint), map_location="cpu").eval().to("cpu")
        self.checkpoint = str(checkpoint)

    def recognize(self, image_path, invert=False):
        from PIL import Image, ImageOps
        image_path = Path(image_path).resolve()
        if image_path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
            raise ValueError("Supported image types: PNG, JPG, JPEG, BMP.")
        with Image.open(str(image_path)) as source:
            if source.width * source.height > 320000 or min(source.size) < 16:
                raise ValueError("Use a cropped image with at most 320000 pixels and sides >= 16 pixels; no automatic resizing is performed.")
            if "A" in source.getbands() or "transparency" in source.info:
                rgba = source.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                image = Image.alpha_composite(background, rgba).convert("L")
            else:
                image = source.convert("L")
            if invert:
                image = ImageOps.invert(image)
            if image.getextrema()[0] == image.getextrema()[1]:
                raise ValueError("Image is blank (all grayscale pixels have the same value).")
            tensor = self.to_tensor(image)
        mask = self.torch.zeros_like(tensor, dtype=self.torch.bool)
        with self.torch.no_grad():
            hypothesis = self.model.approximate_joint_search(tensor.unsqueeze(0), mask)[0]
        latex = self.vocab.indices2label(hypothesis.seq)
        result = judge_latex(latex)
        result.update(image_path=str(image_path), checkpoint=self.checkpoint,
                      image_size=list(image.size), device="cpu", invert_input=invert)
        return result


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Recognize one cropped handwritten arithmetic image and judge the recognized expression.")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--image", type=Path, help="One cropped PNG/JPG/BMP image; native CoMER input is light ink on a dark background.")
    inputs.add_argument("--latex", help="Judge supplied text without loading CoMER (not an OCR test).")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, help="Optional UTF-8 JSON output file.")
    parser.add_argument("--threads", type=int, default=4, help="CPU inference threads (default: 4).")
    parser.add_argument("--invert", action="store_true", help="Explicitly invert a dark-ink/light-background image before the original tensor transform.")
    args = parser.parse_args(argv)
    if args.threads < 1:
        parser.error("--threads must be >= 1")
    try:
        if args.image is not None:
            result = Recognizer(args.checkpoint, args.threads).recognize(args.image, invert=args.invert)
        else:
            result = judge_latex(args.latex)
            result["source"] = "provided_text"
        payload = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 0
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        print(json.dumps({"status": "error", "error": {"type": type(error).__name__, "message": str(error)}}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
