# 词库格式（给人和给 AI 看的唯一依据）

一个词库就是 `wordbanks/` 下的一个 `.json` 文件。结构：

```json
{
  "meta": { "name": "GRE 核心 500", "count": 500 },
  "words": [
    {
      "id": 1,
      "word": "abate",
      "phonetic": "/əˈbeɪt/",
      "pos": "v.",
      "zh": "减轻；减少；缓和",
      "en": "to become less intense or widespread",
      "example": "The storm finally abated toward dawn, and the fishermen returned.",
      "example_zh": "暴风雨在黎明前终于减弱，渔民们回到了港口。",
      "level": 1
    }
  ]
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `word` | 是 | 单词本身，全库不重复（大小写不敏感） |
| `zh` | 是 | 中文释义，多个义项用 `；` 分隔 |
| `phonetic` | 建议 | 国际音标，前后带斜杠 |
| `pos` | 建议 | `n.` `v.` `adj.` `adv.` 等 |
| `en` | 建议 | 英文释义，一句话 |
| `example` | 建议 | 英文例句，含这个词的自然用法 |
| `example_zh` | 建议 | 例句中文翻译 |
| `id` | 否 | 从 1 递增，缺了不影响运行 |
| `level` | 否 | 1-3 难度，暂时只作标记 |

规则：文件必须是 UTF-8、合法 JSON；`words` 是数组；顺序就是初次学习顺序（建议按难度或字母序）。
改完一定跑一次 `python3 tools/validate.py`，它会检查必填字段、重复词和文件结构。

## 三种造词库的方式

**已有词表文件**（Excel 导出的 CSV、网上抄的 TXT 都行）：

```bash
python3 tools/import_words.py 我的词表.csv --name toefl-1000 --title "TOEFL 核心 1000"
```

列名中英文都认（单词/word、释义/zh、音标/phonetic、例句/example…），也认「一行一个词」和「word,释义」两列格式。

**让 AI 生成**：把下面这段话发给 Claude，一次别超过 100 词，分批生成再合并，省 token 也更稳。

> 按 `wordbanks/SCHEMA.md` 的格式生成 100 个 <考试名> 高频词的 JSON，只输出 `words` 数组的内容，
> 字段齐全（word/phonetic/pos/zh/en/example/example_zh/level），例句要自然、20 词以内，
> 中文释义简洁。已有的词不要重复：<贴上已有单词列表>。

**手动加几个词**：直接编辑 JSON，追加对象即可，`id` 接着往下写。

## 换库

改 `config.json` 的 `"wordbank": "文件名.json"`，或者右键桌宠 →「📚 换词库」。
进度按单词拼写记录在 `data/state.json`，所以换库不会丢原来的进度，换回来还在。
