# 背词桌宠 word-pet

一只待在桌面上的小家伙，每小时按你的真实进度催你背单词，点一下会跳、会说话。
自带 GRE 核心 500 词和三套人格，换形象换词库都只改一个 JSON，不用碰代码。

- 15 分钟一轮的卡片式背词，空格看释义，`1` 认识 / `2` 不认识
- 间隔复习：认识就 1 → 3 → 7 → 14 → 30 → 60 → 120 天往后排，不认识明天再见
- 整点提醒会报出真实数字（今天背了几个、几个到期、连续几天），不是干巴巴的闹钟
- 进度只存在本机 `data/state.json`，不联网、不上传

## 开始用（三步）

**macOS**：双击 `scripts/start-macos.command`
如果提示「无法打开，因为它来自身份不明的开发者」，右键该文件 →「打开」→「打开」。

**Windows**：双击 `scripts/start-windows.bat`
需要先装 [Python 3.9+](https://www.python.org/downloads/)，安装时勾选 *Add python.exe to PATH*。

首次启动会自动建虚拟环境并装 PyQt6（联网，1-2 分钟），之后就是秒开。
装完桌宠会出现在屏幕右下角。**左键点它**说话，**右键出菜单**，**滚轮调大小**，拖着能挪窗口。

右键菜单里有：开始背词、只复习到期的词、今日进度、抽查一个词、换形象、换词库、整点提醒开关、退出。

## 换形象

1. 找一张 PNG，**背景透明**效果最好（四周多余的透明边会自动裁掉，不用自己抠精确）
2. 建主题：
   ```bash
   python3 tools/new_theme.py pikachu --image ~/Downloads/pikachu.png --pet-name 皮卡丘
   ```
3. 右键桌宠 →「🎨 换形象」→ 选 pikachu

想让它说话像某个角色，就编辑 `themes/pikachu/theme.json`：`quips` 是点它时说的话，
`nudge` 是整点提醒的分场景文案（还没开始 / 进行中 / 已完成 / 深夜）。里面能用 `{n}`
`{left}` `{streak}` 这类占位符，完整清单在 `AGENTS.md`。改完跑一次：

```bash
python3 tools/validate.py
```

自带三套：`default`（中性，原创吉祥物）、`mikasa`（三笠口吻）、`coach`（严格教练，示范只换文案不换图）。

## 换词库

已有 CSV / TXT 词表：

```bash
python3 tools/import_words.py 我的词表.csv --name toefl-1000 --title "TOEFL 核心 1000"
```

列名中英文都认，也认「一行一个单词」和「word,释义」两列。然后右键桌宠 →「📚 换词库」。

想让 AI 生成一个词库，把 `wordbanks/SCHEMA.md` 发给它照着填就行，那份文件就是完整规范。

进度是按单词拼写记的，所以换库、换回来，原来的记录都还在。

## 常用设置

`config.json`，改完重启桌宠生效：

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `theme` | `default` | 用哪个形象主题（`themes/` 下的目录名） |
| `wordbank` | `gre-core-500.json` | 用哪个词库（`wordbanks/` 下的文件名） |
| `dailyNewTarget` | `20` | 每天背几个新词。别贪，20 个能坚持下来比 60 个放弃强 |
| `sessionMinutes` | `15` | 一轮多少分钟 |
| `petHeight` | `300` | 桌宠基准高度（px），觉得整体偏小就调大 |
| `hourlyNudge` | `true` | 整点自动提醒 |
| `nudgeQuiz` | `true` | 提醒里附带抽查一个词 |
| `speech` | `true` | 点 🔊 朗读单词（用系统自带语音） |
| `nightHour` | `6` | 几点之前算深夜，会换成劝你睡觉的话 |

## 让 AI 每小时提醒你（可选）

桌宠自己就会整点提醒。如果你用 Claude 桌面版，还想在对话里收到提醒，
把 `claude/hourly-nudge/SKILL.md` 存成一个定时任务即可，里面写好了完整指令。
它只会执行 `python3 app/nudge.py` 并原样转述输出 —— 只读，不会碰你的进度。

## 出问题了

| 现象 | 处理 |
| --- | --- |
| 双击没反应 | 打开终端，`cd` 到本目录，跑 `python3 tools/validate.py` 看报错 |
| 桌宠不见了 | 右键菜单勾上「窗口置顶」；或删掉 `data/prefs.json` 重启，位置会复位 |
| 提示找不到词库 | `config.json` 里的 `wordbank` 名字和 `wordbanks/` 下的文件名要一字不差 |
| 装 PyQt6 卡住 | 换源：`.venv/bin/pip install PyQt6 -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 想清空进度重来 | 删掉 `data/state.json`（这会丢掉全部背词记录，先备份） |
| 想搬到新电脑 | 整个文件夹拷过去，删掉 `.venv/`，重新双击启动器 |
| 从旧版桌宠迁移 | 把旧的 `gre_state.json` 放到本目录根下，首次启动会自动接住进度 |

## 目录结构

```
config.json          全部设置（用哪个形象、哪个词库、每天几个词）
app/                 程序：core 数据与文案 / pet 桌宠 / panel 背词面板 / nudge 提醒脚本
themes/<主题>/        theme.json（人格文案）+ pet.png（形象）
wordbanks/           词库 JSON + SCHEMA.md（词库格式规范）
tools/               validate 体检 / import_words 导词表 / new_theme 建主题
scripts/             双平台一键启动器
data/                你的进度和窗口偏好（本机私有，不进 git）
AGENTS.md            给 AI 助手的路由表：改什么动哪个文件
```

## 说明

代码以 MIT 许可开源，随便改随便发。`themes/mikasa/pet.png` 是同人图片素材，
版权不属于本项目，仅供个人自用；**如果你要把仓库公开上传，请先删掉这张图**
（删掉后 `mikasa` 主题会自动回落到默认形象，文案不受影响）。

自带的 500 词词库为学习用途整理，例句由 AI 生成，个别释义可能不够精准，
遇到错的直接改 `wordbanks/gre-core-500.json` 就好。
