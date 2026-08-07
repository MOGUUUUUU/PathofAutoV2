# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PathofAutoV2 是一套用于《流放之路》（Path of Exile）游戏经济自动化的 Python 脚本集合。各模块独立运行，无构建系统或测试框架。所有机器人为 **Windows 专用**（依赖 pyautogui 屏幕操作、winsound 提示音、tkinter GUI）。

## 运行脚本

```bash
# 远征商人自动购买机器人（Gwennen/Tugen/Dannig 三合一）
python expedition/expedition.py

# 宝珠制作机器人（合并版，双 Tab 选择简化/完整模式）
python poborbbot/POBorbBotMerged.py

# 打包宝珠机器人为独立 exe
cd poborbbot && pyinstaller POBorbBotMerged.spec

# 从 poe.ninja 抓取实时价格写入 price.json
python essence/ninja.py

# 运行精华利润蒙特卡洛模拟
python essence/main.py

# 运行精华转换期望值计算器
python essence/emulator.py

# 运行法斯特交易所价格读取器
python faust/faust_v2.py

# 小米 MiMo TTS 语音克隆，批量重构物品过滤器音效
python convert_voices.py [音色样本.wav] [输入mp3目录] [输出目录]
```

## 依赖库（需手动安装）

```
pyautogui pyperclip keyboard paddleocr opencv-python numpy pillow matplotlib requests lameenc
```

- `matplotlib` 仅 `essence/emulator.py` 使用；`Pillow` 用于 expedition 录入模式弹窗；`lameenc`（MP3 编码）仅 `convert_voices.py` 使用
- `winsound`、`tkinter`、`audioop` 为 Python 内置模块；`audioop` 已随 Python 3.13 移除，`convert_voices.py` 需用 Python ≤ 3.12 运行

## 架构要点

### 各子模块

- **`expedition/`** — 远征商人自动购买。`expedition.py` 是唯一入口：一个 tkinter Notebook，含 Home/Gwennen/Tugen/Dannig 四个 Tab。`gwennen.json` 是旧版遗留配置，当前统一读 `expedition.json`。
- **`poborbbot/`** — 宝珠制作自动化。`POBorbBotMerged.py` 为合并版（推荐使用），`POBorbBot.py`（7种宝珠）和 `POBorbBotV2.py`（3种宝珠）为旧版，共用根目录 `poe_orb_config.json`。
- **`faust/`** — 交易所价格读取机器人，使用 PaddleOCR（中文模型）识别游戏内 UI 文字，hardcode 了 1920x1080 屏幕坐标，腾讯服专用。`orc.py` 是 PaddleOCR 检测框的独立调试脚本。
- **`essence/`** — 精华货币分析：`ninja.py` 抓取 poe.ninja 价格写入 `price.json`；`main.py` 做蒙特卡洛模拟；`emulator.py` 做期望值计算，读取 `essence_tencent.json`。
- **`scarabBot/`** — 圣甲虫转换机器人（未完成），依赖不存在的 `executor` 模块，**无法运行**。
- **`convert_voices.py`** — 根目录独立脚本：用小米 MiMo TTS 接口（`mimo-v2-tts`）做语音克隆，把指定目录下的 mp3 文件名批量重新合成，已存在的输出自动跳过。API key 优先读 `MIMO_API_KEY` 环境变量。

### 通用模式

- 屏幕坐标均为绝对像素值，用户通过 GUI 中按 `=` 键捕获（`pyautogui.position()`）
- 物品信息读取统一用 `Ctrl+Alt+C` 复制到剪贴板（`pyperclip.paste()`）后解析
- 宝珠/购买机器人均用 `F3` 热键启停
- 随机延迟（`rand_sleep` 中的 `random.random()` jitter）模拟人类操作
- 配置持久化为 JSON 文件（脚本同目录或仓库根目录）
- 多 Tab 程序切换 Tab 时自动停止另一个 Tab 正在运行的 bot，`F3`/`=` 始终作用于当前激活 Tab

---

## expedition/expedition.py

### 类结构

- `ExpeditionBotBase` — 公共基类：配置、坐标、主循环、`read_item`（Ctrl+Alt+C），以及图像模板匹配（截图 → 均分切格子 → `cv2.matchTemplate` 打分 → 按阈值过滤）和 debug 图保存
- `GwennenBot` / `TugenBot` / `DannigBot` — 继承基类，覆写 `buy_item` 与 `run`：
  - `TugenBot` 额外实现砍价（`bargain`：对价格框做二分压低，比例/阈值可配置）与录入模式（截图 → GUI 弹窗选格子 → 保存到 `pict/` → 重载模板）
  - `DannigBot` 额外实现"只购买日志"模式（`single_row_only`：从最后一行向上探测第一个有物品的行）
- `HomeTabPanel` — 首页：使用说明 + 统一配置保存/加载（`expedition.json`）
- `ExpeditionTabPanel` — 工具标签页面板基类；各 `*TabPanel` 子类通过 `coord_labels`、`_build_extra_ui`、`_apply_coords`、`_get/_apply_extra_config` 定制

### 三种购买方式

| 商人 | 购买操作 | 背包清理 | 可选模式 |
|------|----------|----------|----------|
| Gwennen | Ctrl+左键 | 有保留关键词时清理（每 `check_interval` 次） | — |
| Tugen | 左键 → 可选砍价 → 点确认按钮 | 不清理 | 砍价、图像匹配过滤 + 录入模式 |
| Dannig | Ctrl+左键 | 不清理 | 只购买日志 |

### 图像识别与录入模式（Tugen）

- 目标图片默认存 `expedition/pict/`（按序号递增命名），GUI 也可手动添加任意图片
- 运行时先截商店区域，按行列均分格子，用 `cv2.matchTemplate`（`TM_CCOEFF_NORMED`）逐格比对，相似度 ≥ 阈值（默认 0.3）才进入文字读取
- 开启录入模式后每次刷新会弹窗展示商店截图 + 每格相似度，点击选中格子保存为模板，`F4` 跳过
- 每次匹配的标注图存 `expedition/debug/`，最多保留 10 张

### 配置文件

统一保存到 `expedition/expedition.json`，按工具名分节（Home 页启动时自动加载）：
```json
{
  "gwennen": { "coords": {...}, "shop_rows": 11, "shop_cols": 1, "buy_keywords": [...], "keep_keywords": [...], "check_interval": 30 },
  "tugen": { "coords": {...}, "bargain_enabled": true, "bargain_ratio": 0.5, "bargain_threshold": 20, "target_img_paths": [...], "img_threshold": 0.9, "capture_mode": true },
  "dannig": { "coords": {...}, "single_row_only": false }
}
```

### 坐标设置

商店格子按左上/右下角均分为 `shop_rows × shop_cols` 格（GUI 可调，默认 12×12）。各工具坐标：
- 全部：商店左上角、商店右下角、刷新按钮
- Gwennen 独有：背包左上角、背包右下角
- Tugen 独有：确认购买按钮、复位点；启用砍价还需价格框左上/右下、砍价确认按钮
- Dannig：仅 3 个基础坐标

### 热键

- `F3` — 开始/停止
- `=` — 捕获当前坐标类型
- `F4` — 录入模式弹窗中跳过

---

## poborbbot/POBorbBotMerged.py

### 类结构

```
PoeOrbBotBase          # 公共基类（配置读写、use_orb、check_item、beep）
├── PoeOrbBotSimple    # 简化版状态机（3种宝珠）
└── PoeOrbBotFull      # 完整版状态机（7种宝珠）

BotTabPanel            # 通用 Tab 面板，接受任意 bot 实例和 orb_names 字典
MainApp                # Notebook 双 Tab 主窗口
```

### 状态机

**简化版**：`蜕变 → 增幅 ⟷ 改造`（目标：匹配1个词缀）

**完整版**：`蜕变 → 改造循环（1词缀）→ 增幅（2词缀）→ 富豪（3词缀）→ 崇高（4词缀）→ 成功 / 剥离（退到3词缀重试）/ 重铸（归零重来）`

### 配置

- 读写仓库根目录 `poe_orb_config.json`，**合并版读 JSON 顶层键**；文件中 `full`/`simple` 子段是旧版 POBorbBot.py/V2 遗留，合并版不使用
- 改造石/增幅石可配置多个坐标（`alter_positions`/`augment_positions`），使用时随机选一个
- 完整版各宝珠可用 `use_augment`/`use_regal`/`use_extend`/`use_annulment`/`use_scouring` 配置开关（默认开启）
- `POBorbBotMerged.spec` 为 PyInstaller 打包配置

### Tab 切换行为

切换 Tab 时自动停止另一个 Tab 正在运行的 bot，`F3` 和 `=` 始终作用于当前激活 Tab。

## 注意事项

- `scarabBot/PoeScarabBot.py` 因 `from executor import Executor` 缺失依赖，运行时会抛 `ImportError`
- `price.json` 由 `essence/ninja.py` 抓取 poe.ninja 后写入，运行 `essence/main.py`、`emulator.py` 前需先填充
- `faust_v2.py` 中的屏幕坐标针对中文版游戏客户端布局（腾讯服）
- `POBorbBot.py` 和 `POBorbBotV2.py` 为旧版，新开发请基于 `POBorbBotMerged.py`
- `expedition/gwennen.json` 为旧版遗留，新开发请只改 `expedition.json`
- `convert_voices.py` 内嵌了一个硬编码的 API key 回退值（`MIMO_API_KEY` 环境变量优先），提交到仓库前应移除
