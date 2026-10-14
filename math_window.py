"""Local image selection GUI. Start with the existing CoMER Python interpreter."""
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "example/arithmetic_samples/UN_128_em_1003.bmp"


class InferenceWorker:
    """One serial worker owns the cached model; it never calls Tk methods."""

    def __init__(self, recognizer_factory=None):
        self.jobs = queue.Queue()
        self.events = queue.Queue()
        self.recognizer = None
        self.factory = recognizer_factory
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, image_path, invert):
        self.jobs.put((Path(image_path), bool(invert)))

    def close(self):
        self.jobs.put(None)

    def _run(self):
        while True:
            job = self.jobs.get()
            if job is None:
                return
            try:
                if self.recognizer is None:
                    self.events.put(("progress", "首次加载模型，请稍候…"))
                    factory = self.factory
                    if factory is None:
                        from recognize_math import Recognizer
                        factory = Recognizer
                    self.recognizer = factory()
                self.events.put(("progress", "正在识别图片并判题…"))
                result = self.recognizer.recognize(job[0], invert=job[1])
                self.events.put(("result", result))
            except Exception as error:
                self.events.put(("error", "{}: {}".format(type(error).__name__, error)))


class MathWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("手写算式识别与判题 · CoMER")
        self.root.geometry("1050x720")
        self.root.minsize(860, 600)
        self.root.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.worker = InferenceWorker()
        self.image_path = None
        self.preview_source = None
        self.preview_photo = None
        self.result = None
        self.busy = False
        self.closed = False
        self.invert = tk.BooleanVar(value=True)
        self.path_text = tk.StringVar(value="尚未选择图片")
        self.status_text = tk.StringVar(value="请选择裁剪好的单道算式图片。图片只在本机处理。")
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._poll)

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"))
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="手写算式识别与判题", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="选择图片 → 检查预览 → 开始识别 → 查看结果").pack(anchor="w", pady=(4, 14))
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x")
        self.choose_button = ttk.Button(toolbar, text="选择图片…", command=self.choose_image)
        self.choose_button.pack(side="left")
        self.sample_button = ttk.Button(toolbar, text="载入样例", command=lambda: self.load_image(SAMPLE, sample=True))
        self.sample_button.pack(side="left", padx=8)
        self.invert_check = ttk.Checkbutton(toolbar, text="白底黑字（识别前反色）", variable=self.invert, command=self._option_changed)
        self.invert_check.pack(side="left", padx=8)
        self.run_button = ttk.Button(toolbar, text="开始识别", command=self.start, state="disabled")
        self.run_button.pack(side="right")
        ttk.Label(outer, textvariable=self.path_text, wraplength=990).pack(anchor="w", pady=(10, 12))
        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)
        left = ttk.LabelFrame(content, text="图片预览", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.canvas = tk.Canvas(left, background="#f5f7fa", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self._draw_preview())
        right = ttk.LabelFrame(content, text="识别与判题结果", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        self.result_label = ttk.Label(right, text="等待识别", font=("Microsoft YaHei UI", 18, "bold"))
        self.result_label.pack(anchor="w", pady=(0, 12))
        self.result_text = tk.Text(right, wrap="word", height=13, relief="flat", background="#ffffff", padx=10, pady=10)
        self.result_text.pack(fill="both", expand=True)
        self._set_text("识别出的算式和计算结果将在这里显示。\n\n请核对识别文本是否与图片一致。识别错误可能导致判题错误。")
        self.save_button = ttk.Button(right, text="保存结果 JSON…", state="disabled", command=self.save_result)
        self.save_button.pack(anchor="e", pady=(10, 0))
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))
        ttk.Label(footer, textvariable=self.status_text, wraplength=990).pack(anchor="w")
        ttk.Label(footer, text="支持 PNG / JPG / BMP；仅处理单道算式，暂不支持整页作业、竖式或步骤批改。", wraplength=990).pack(anchor="w", pady=(5, 0))

    def _set_text(self, text):
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled")

    def _clear_result(self):
        self.result = None
        self.save_button.configure(state="disabled")
        self.result_label.configure(text="等待识别", foreground="#374151")
        self._set_text("点击“开始识别”获取这张图片的结果。\n\n判题基于识别文本，请与图片核对。")

    def _option_changed(self):
        self._clear_result()
        self.status_text.set("反色设置已改变，请重新点击“开始识别”。")

    def choose_image(self):
        path = filedialog.askopenfilename(parent=self.root, title="选择单道算式图片",
                                          filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")])
        if path:
            self.load_image(path)

    def load_image(self, path, sample=False):
        if self.busy:
            return
        path = Path(path).resolve()
        try:
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
                raise ValueError("请选择 PNG、JPG、JPEG 或 BMP 格式的图片。")
            with Image.open(str(path)) as image:
                width, height = image.size
                if min(width, height) < 16:
                    raise ValueError("图片过小，宽和高都至少需要 16 像素。")
                if width * height > 320000:
                    raise ValueError("图片过大（{}×{}）。请先裁剪为单道算式，并保持比例缩小到总像素不超过 320000；例如约 800×200。".format(width, height))
                if image.convert("L").getextrema()[0] == image.convert("L").getextrema()[1]:
                    raise ValueError("图片为空白，未发现可识别的笔迹。")
                rgba = image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                preview = Image.alpha_composite(background, rgba).convert("RGB")
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            messagebox.showerror("图片无法使用", str(error), parent=self.root)
            return
        self.image_path = path
        self.preview_source = preview
        self.invert.set(not sample)
        self.path_text.set("{}  ·  {} × {} 像素".format(path, width, height))
        self._clear_result()
        self._draw_preview()
        self.run_button.configure(state="normal")
        self.status_text.set("图片已载入。白底黑字请勾选反色；黑底白字请取消勾选。")

    def _draw_preview(self):
        self.canvas.delete("all")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.preview_source is None:
            self.canvas.create_text(width // 2, height // 2, text="点击“选择图片…”添加自己的算式", fill="#64748b", font=("Microsoft YaHei UI", 12))
            return
        preview = self.preview_source.copy()
        preview.thumbnail((max(1, width - 24), max(1, height - 24)), Image.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(preview)
        self.canvas.create_image(width // 2, height // 2, image=self.preview_photo, anchor="center")

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for control in (self.choose_button, self.sample_button, self.invert_check):
            control.configure(state=state)
        self.run_button.configure(state="disabled" if busy or self.image_path is None else "normal")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def start(self):
        if self.busy or self.image_path is None:
            return
        self._clear_result()
        self._set_busy(True)
        self.result_label.configure(text="识别中…")
        self.status_text.set("任务已开始，首次加载模型可能需要十几秒。")
        self.worker.submit(self.image_path, self.invert.get())

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self.worker.events.get_nowait()
                if kind == "progress":
                    self.status_text.set(payload)
                elif kind == "error":
                    self._set_busy(False)
                    self.result_label.configure(text="识别失败", foreground="#b91c1c")
                    self._set_text("本次识别未完成：\n\n" + payload)
                    self.status_text.set("识别失败，可以重新选择图片后重试。")
                elif kind == "result":
                    self._show_result(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _show_result(self, result):
        self.result = result
        self._set_busy(False)
        colors = {"correct": "#15803d", "incorrect": "#b91c1c", "ungradable": "#b45309", "computed": "#1d4ed8"}
        self.result_label.configure(text=result["label"], foreground=colors.get(result["status"], "#374151"))
        lines = ["识别文本（LaTeX）", result["recognized_latex"], "", "解析后的算式", result.get("normalized_expression") or "—", "",
                 "左侧 / 表达式计算值：{}".format(result.get("left_value") or "—"),
                 "右侧计算值：{}".format(result.get("right_value") or "—")]
        if result.get("error"):
            lines += ["", "无法判定原因：", result["error"]["message"]]
        lines += ["", "请核对识别文本：OCR 读错数字或符号时，判题结果也可能错误。"]
        self._set_text("\n".join(lines))
        self.save_button.configure(state="normal")
        self.status_text.set("识别完成。可以继续选择图片，或保存本次结果。")

    def save_result(self):
        if self.result is None:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="保存识别与判题结果", defaultextension=".json",
                                           initialfile=self.image_path.stem + "_result.json", filetypes=[("JSON 文件", "*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps(self.result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self.status_text.set("结果已保存到：" + path)
            except OSError as error:
                messagebox.showerror("保存失败", str(error), parent=self.root)

    def close(self):
        self.closed = True
        self.worker.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    MathWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
