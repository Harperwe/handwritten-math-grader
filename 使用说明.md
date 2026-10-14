# CoMER 单道手写算式识别与判题

本项目使用原 CoMER 预训练权重在 CPU 上识别裁剪好的单道公式，并对识别文本进行基础算术判定。原模型代码和 README 保留原样。新增判题模块不会修改识别结果去凑出正确答案。

## 本机运行

在本文件所在目录打开 PowerShell 或命令提示符。已准备的独立环境位于工作区的 `work/env-comer`，`.cmd` 快捷入口会自动定位它，无需改变 PowerShell 脚本执行策略。

```powershell
# 识别随附的真实手写算式样例，结果保存到 repro_outputs/latest.json
.\run_math.cmd

# 普通白纸黑字图片：先裁剪出一道题，使用显式反色选项
.\run_math.cmd --image 'D:\你的图片\算式.png' --invert --output repro_outputs\my_result.json

# 直接核对文字，用于区分 OCR 错误和判题错误；不代表图片识别测试
.\run_math.cmd --latex '0.1+0.2=0.3'
.\run_math.cmd --latex '\frac{1}{2}+\frac{1}{3}=\frac{5}{6}'
.\run_math.cmd --latex '2+3=6'
```

输出包含 `recognized_latex`（识别文本）、`normalized_expression`、`left_value`、`right_value`、`status` 和错误原因。分数使用精确有理数表示，例如 `1/3`。`correct` / `incorrect` 表示识别后的等式正确 / 错误；`computed` 表示没有等号，已计算表达式；`ungradable` 表示无法判定。命令执行失败返回退出码 2；数学题答错或不支持的数学表达式仍正常返回 JSON。

**判题基于识别出的表达式。请核对图片与 `recognized_latex` 是否一致。OCR 把数字识别错时，判题也可能受到影响。**

## 图片要求和支持范围

- 支持 PNG、JPG、JPEG、BMP；一张图只有一道公式，不能传入整页作业。
- CoMER 原生样例为黑底白字。普通白底黑字图显式加 `--invert`；已是黑底白字时不要加此选项。
- 转成灰度后沿用原 notebook 的 `ToTensor()`、全零 mask 和原解码。默认不反色、不缩放、不切分、不去噪。透明图片先合成到白色背景；`--invert` 仅为新增图片入口的可选转换。
- 图片每边至少 16 像素，总像素不超过 320000。过大的图片应由使用者先裁剪或另存较小尺寸；本入口不会悄悄缩放。
- 判题支持整数、小数、正负号、`+ - × ÷`、括号，以及数值 `\frac{分子}{分母}`。允许等号两侧都包含算式。
- 小数精确比较，不自动采用近似或舍入容差，例如 `1/3=0.333` 判为错误。
- 变量、幂、根号、求和、中文应用题、余数、竖式、解题步骤、隐式乘法和多个等号暂不支持。识别到这些内容会返回无法判定，原始文本仍保留。
- 不将字母 `x` 自动替换成乘号，不自动修复疑似 OCR 错字；解析失败、除零会给出明确原因。

## Python 入口与验证

```powershell
$comerPython = '..\..\work\env-comer\python.exe'
& $comerPython recognize_math.py --image example\arithmetic_samples\UN_128_em_1003.bmp --output repro_outputs\demo.json
& $comerPython recognize_math.py --latex '2+3=5'
& $comerPython -m unittest discover -s tests -v
& $comerPython verify_original_example.py
& $comerPython prepare_samples.py
& $comerPython evaluate_samples.py
```

`Recognizer` 对象只在构造时加载权重，可连续调用 `.recognize(path, invert=False)`。默认 CPU 线程数为 4，改变线程数不会修改模型结构或参数。

随附 20 张图片从原仓库 `data.zip` 的 CROHME 2016 数据按固定规则选出：选取标注中前 20 道在判题范围内的纯数值等式，选择发生在预测之前，图像字节保持原样。它们是方便验证流程的子集，不能代表完整 CROHME、实际作业照片或小学题目总体准确率；其中只有一道数学错误等式，不能据此评估可靠的错题检出率。清单和图像哈希在 `example/arithmetic_samples/manifest.json`。

原 notebook 示例包含变量和求和，适合核对识别模型复现，超出基础判题范围。它识别成功后得到“无法判定”是预期行为。

## 环境重建

仓库固定于 `ee15cdbe02467fd29f386fd554b4bc2185110fcc`，原始权重位于 `lightning_logs/version_0/checkpoints`。在新的机器上使用独立环境：

```powershell
conda create -n comer-arithmetic python=3.7.16 pip=22.3.1 -y
conda activate comer-arithmetic
python -m pip install -r requirements-cpu.txt
python recognize_math.py --image example\arithmetic_samples\UN_128_em_1003.bmp
```

`requirements-cpu.txt` 为推理所需的固定主要依赖；实际安装的完整版本快照在 `repro_outputs/environment-pip.txt`。直接从项目目录运行，无需执行原 `setup.py`，也无需安装其中列出的开发和完整评估工具。README 的 torchvision 0.2.2 与 PyTorch 1.8.1 不配套，此环境使用官方对应的 torchvision 0.9.1。只为推理安装必要依赖，没有训练模型或执行完整 CROHME 官方评分流程。

复现报告、运行日志、逐图结果、限制和兼容性记录在 `repro_outputs/`。

## 本次实测结果

- 原 notebook 的 CPU 识别输出与其保存的参考文本完全一致。
- 20 张固定 CROHME 数值等式样例：整式识别正确 19/20，端到端识别及判题正确 19/20；CPU 总推理耗时约 198 秒。
- 唯一识别错误发生在 `UN_114_em_304.bmp`：右侧 `+1` 被识别成 `1+1`，让一道正确等式被判为错误。没有修改模型预测来掩盖此问题。
- 7 组判题单元测试通过；显式反色的输入检查，以及空白、过小和过大图片拒绝检查通过。
- 上述 95% 是小型便利子集上的流程验证结果。真实纸上拍照准确率、完整 CROHME 论文指标和可靠的错题检出率均未验证。
