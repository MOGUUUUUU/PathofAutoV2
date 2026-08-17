# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PathofAutoV2 是一组相互独立的《流放之路》（Path of Exile）经济自动化 Python 脚本，不是 Python 包，也没有统一构建系统。主要机器人依赖 `pyautogui`、全局热键、剪贴板和 tkinter，面向 Windows 游戏客户端运行；屏幕坐标和 OCR 区域都是绝对像素坐标。

仓库没有 README、依赖清单、锁文件、lint 配置、CI 或自动化测试。依赖未固定版本，需要手动安装：

```bash
python -m pip install pyautogui pyperclip keyboard opencv-python numpy paddleocr paddlepaddle matplotlib requests lameenc pyinstaller
```

`winsound`、`tkinter`、`audioop` 来自 Python/系统发行版。`convert_voices.py` 使用 Python 3.12 或更早版本，因为 Python 3.13 已移除 `audioop`。PaddleOCR 的主程序和调试脚本分别使用 `.ocr()` 与 `.predict()` API；升级依赖时需同时验证两处兼容性。

## 命令

除打包命令外，以下命令均从仓库根目录执行。多个脚本使用相对路径读写配置或数据，改变工作目录会改变文件位置或导致读取失败。

```bash
# 远征商人自动购买（Home/Gwennen/Tugen/Dannig 四个 Tab）
python expedition/expedition.py

# 宝珠制作（简化版/完整版两个 Tab，推荐入口）
python poborbbot/POBorbBotMerged.py

# 打包宝珠机器人为单文件 exe
cd poborbbot && pyinstaller POBorbBotMerged.spec

# 抓取 poe.ninja 数据并在仓库根目录生成 price.json
python essence/ninja.py

# 精华随机模拟（使用脚本内硬编码的示例数据）
python essence/main.py

# 精华转换期望值（读取仓库根目录 essence_tencent.json）
python essence/emulator.py

# 法斯特交易所 OCR 自动化
python faust/faust_v2.py

# 小米 MiMo TTS 批量重构音效
python convert_voices.py <音色样本.wav> <输入mp3目录> <输出目录>

# 无副作用的全仓库语法检查
python -m compileall -q convert_voices.py expedition poborbbot essence faust scarabBot

# 单文件语法检查（仓库没有可运行的单元测试）
python -m py_compile path/to/file.py
```

不要把启动 GUI 机器人当作 smoke test：入口会注册全局热键，部分脚本启动后会立即移动鼠标、点击、输入文本、删除游戏物品、调用外部 API 或写入运行时文件。验证自动化行为需要用户准备好对应游戏界面和坐标后进行。

## 架构

### 运行与持久化模式

- 自动化脚本通常由 tkinter 主线程、daemon 工作线程和共享的 `running` 布尔值组成。切换 Tab 或关闭窗口通过清除该标志协作停止工作线程。
- 游戏物品信息通过悬停后发送 `Ctrl+Alt+C`，再从 `pyperclip` 读取；购买和制作动作直接调用 `pyautogui`。
- `.gitignore` 忽略所有 `*.json`，所以 `poe_orb_config.json`、`price.json` 和 `expedition/expedition.json` 等运行时文件默认不会进入版本控制。`essence.json` 和 `essence_tencent.json` 是已经被跟踪的例外。
- `expedition.py` 将配置和 debug 图路径锚定到脚本目录；宝珠配置、精华数据和 Faust 的 `debug/` 使用当前工作目录。

### 远征机器人

`expedition/expedition.py` 是当前唯一入口。代码分为三层：

- `ExpeditionBotBase` 提供网格坐标计算、剪贴板读取、关键词匹配、刷新和图像过滤；`GwennenBot`、`TugenBot`、`DannigBot` 实现各自购买循环。
- `ExpeditionTabPanel` 及三个子类负责 GUI 状态、坐标和商人特有选项，并在启动时把界面值应用到 bot。
- `HomeTabPanel` 聚合三个 Tab 的设置，统一读写脚本目录下的 `expedition.json`；`MainApp` 管理当前 Tab 和 F3 热键。

商人差异：Gwennen 用 Ctrl+左键购买，并可定期扫描 5x12 背包、通过 `/destroy` 删除不符合保留关键词的物品；Tugen 左键选物品后可迭代压价，再点确认；Dannig 反向遍历格子，可只处理从底部找到的第一行非空物品。

Tugen 的可选图像过滤使用 ORB 特征：截图商店区域、按 `shop_rows x shop_cols` 切格子、用 Hamming BFMatcher 和 Lowe ratio 计算分数，再对通过阈值的格子读取文字。目标图片由 GUI 文件选择器添加；代码没有截图录入弹窗或 F4 录入模式。每轮匹配的标注图写到 `expedition/debug/`，只保留最新 10 张。

热键并不完全相同：F3 是 `keyboard` 注册的全局热键；远征程序的 `=` 通过 Tk 绑定，仅在窗口有焦点时捕获坐标。切换商人 Tab 会停止其他商人的 bot。

### 宝珠机器人

`poborbbot/POBorbBotMerged.py` 是新开发应修改的入口；`POBorbBot.py` 和 `POBorbBotV2.py` 是逻辑重复的旧版。

- `PoeOrbBotBase` 负责配置、宝珠点击、物品信息读取和词缀计数。
- `PoeOrbBotSimple` 实现“蜕变 -> 增幅/改造循环”，匹配至少一个目标词缀。
- `PoeOrbBotFull` 实现“蜕变 -> 改造 -> 增幅 -> 富豪 -> 崇高”，失败后按状态进入剥离或重铸。
- `BotTabPanel` 是两种模式共用的参数化界面；`MainApp` 负责 Tab 切换及全局 F3、`=` 热键。

两个 bot 实例都读写仓库根目录的同一个扁平 `poe_orb_config.json`，而不是按 `simple`/`full` 分节。改造石和增幅石允许多个坐标并在使用时随机选择；其他宝珠是单坐标。切换模式会停止另一个 bot。

### 其他脚本

- `faust/faust_v2.py` 用中文 PaddleOCR 在作者客户端布局的固定区域中寻找文字和价格，并把标注截图写到当前目录的 `debug/`。主入口会立刻操作游戏界面。`faust/orc.py` 是独立调试脚本，含作者机器上的硬编码图片绝对路径。
- `essence/ninja.py` 只负责把 poe.ninja 的 Essence/Fossil/DeliriumOrb 数据写到 `price.json`；仓库中没有脚本读取该文件。`essence/main.py` 使用内嵌示例数据，`essence/emulator.py` 独立读取 `essence_tencent.json`，三者不是顺序流水线。
- `convert_voices.py` 在模块顶层读取参数、样本文件并启动 10 个并发 API 请求，因此不可安全导入。当前硬编码 API key 会覆盖 `MIMO_API_KEY` 环境变量，这是实现缺陷。
- `scarabBot/PoeScarabBot.py` 是不可运行的原型：缺少 `executor` 模块，两个解析函数未实现，且没有入口。不要在此基础上假设已有完整转换流程。
