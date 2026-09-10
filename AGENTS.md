# AGENTS.md — 给 AI 助手看的路由表

读完这一页就够了，不要通读 `app/` 下的代码。代码约 1100 行，全部读一遍浪费上下文，
而 99% 的定制需求只需要动 JSON。

## 改需求 → 只动这个文件

| 用户想要 | 动这里 | 别动 |
| --- | --- | --- |
| 换形象/换图片 | `themes/<主题>/pet.png` + `config.json` 的 `theme` | 任何 .py |
| 改说话风格、口头禅、提醒语 | `themes/<主题>/theme.json` | `app/core.py` |
| 新建一个人格 | `python3 tools/new_theme.py <名字> --image <图>` 然后改生成的 theme.json | 手写目录 |
| 换词库 / 加词 | `wordbanks/*.json`，规范见 `wordbanks/SCHEMA.md` | `app/panel.py` |
| 导入 CSV/TXT 词表 | `python3 tools/import_words.py <文件> --name <库名>` | 手写 JSON |
| 每天背几个、一轮几分钟、要不要发音 | `config.json` | `app/core.py` |
| 检查改完有没有坏 | `python3 tools/validate.py` | 手工试错 |
| 整点提醒 | `app/nudge.py`（只读脚本）+ `claude/hourly-nudge/SKILL.md` | 自己写提醒逻辑 |

## 占位符（theme.json 里能用的变量）

`{name}` 桌宠自称 · `{n}` 今日新词数 · `{target}` 今日目标 · `{left}` 还差几个 ·
`{r}` 今日复习次数 · `{spent}` 今日分钟 · `{due}` 待复习数 · `{streak}` 连续天数 ·
`{mins}` 单轮时长 · `{hour}` 当前小时 · `{total}` 词库总词数 · `{learned}` 已学词数

只在 `quiz` 里额外可用：`{word}` `{phonetic}` `{pos}` `{zh}` `{en}`
只在 `panel.summary` 里额外可用：`{msg}` `{new}` `{rev}` `{sess}`

写错的占位符会原样显示出来，`tools/validate.py` 会提前抓出来。
`quips`、`nudge.*` 的值可以写成数组，程序每次随机挑一条。theme.json 里没写的字段
会回落到 `app/core.py` 的 `FALLBACK_THEME`，所以只想改两句话就只写那两句。

## 代码在哪（真要改行为时再看）

`app/core.py` 数据读写 + 记忆间隔 + 文案渲染（改逻辑看这里，约 250 行）·
`app/pet.py` 桌宠窗口、动画、右键菜单 · `app/panel.py` 背词卡片面板 ·
`app/bubble.py` 气泡样式 · `app/speech.py` 朗读 · `app/main.py` 入口和自检

## 硬规则

- `data/state.json` 是用户的背词进度，只有背词面板能写。定时任务、脚本、AI 都不许写，
  写进去会把进度冲掉。要读进度就跑 `python3 app/nudge.py`，它是只读的。
- 改完任何 JSON 都要跑 `python3 tools/validate.py`，通过再交付。
- 全流程自检（不弹窗）：`QT_QPA_PLATFORM=offscreen .venv/bin/python app/main.py --smoke`
- 不要把 `data/`、`.venv/` 提交到 git。
