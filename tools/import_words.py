#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 CSV / TSV / TXT 词表转成桌宠能读的词库 JSON。

    python3 tools/import_words.py 我的词表.csv --name toefl-1000 --title "TOEFL 核心 1000"

支持三种输入，都不需要固定列序：
  1) 带表头的 CSV/TSV，表头可以是中文或英文（单词/word、释义/zh、音标/phonetic …）
  2) 无表头的两列：word<Tab或逗号>中文释义
  3) 每行一个单词（释义留空，之后再补）
重复单词自动去重，输出写到 wordbanks/<name>.json。
"""
import argparse
import csv
import datetime
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = ["word", "phonetic", "pos", "zh", "en", "example", "example_zh", "level"]
ALIAS = {
    "word": ["word", "单词", "词", "term", "vocab", "vocabulary"],
    "phonetic": ["phonetic", "音标", "发音", "ipa", "pron", "pronunciation"],
    "pos": ["pos", "词性", "part of speech"],
    "zh": ["zh", "释义", "中文", "中文释义", "意思", "翻译", "meaning_zh", "cn"],
    "en": ["en", "英文释义", "英文解释", "definition", "def", "meaning"],
    "example": ["example", "例句", "英文例句", "sentence"],
    "example_zh": ["example_zh", "例句翻译", "例句释义", "中文例句", "sentence_zh"],
    "level": ["level", "难度", "等级"],
}


def norm(s):
    return re.sub(r"[\s_\-]+", "", str(s or "")).strip().lower()


def map_header(row):
    m = {}
    for i, cell in enumerate(row):
        c = norm(cell)
        for field, names in ALIAS.items():
            if c in [norm(n) for n in names]:
                m[field] = i
                break
    return m if "word" in m else None


def parse(text):
    text = text.replace("﻿", "")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    delim = "\t" if lines[0].count("\t") >= lines[0].count(",") and "\t" in lines[0] else ","
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
    header = map_header(rows[0])
    out = []
    if header:
        for r in rows[1:]:
            rec = {f: (r[i].strip() if i < len(r) else "") for f, i in header.items()}
            if rec.get("word"):
                out.append(rec)
        return out
    for ln in lines:                       # 没表头：按 制表符/逗号/第一个空格 切两列
        parts = re.split(r"\t|,|\s{2,}", ln, maxsplit=1)
        if len(parts) == 1:
            parts = re.split(r"\s+", ln.strip(), maxsplit=1)
        word = parts[0].strip()
        if word:
            out.append({"word": word, "zh": (parts[1].strip() if len(parts) > 1 else "")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="CSV / TSV / TXT 词表文件")
    ap.add_argument("--name", help="输出文件名（不含 .json），默认取输入文件名")
    ap.add_argument("--title", help="词库显示名，写进 meta")
    ap.add_argument("--force", action="store_true", help="允许覆盖已存在的词库")
    a = ap.parse_args()

    with open(a.input, encoding="utf-8-sig", errors="replace") as f:
        rows = parse(f.read())
    if not rows:
        sys.exit("没解析出任何单词，检查一下文件内容。")

    seen, words = set(), []
    for r in rows:
        key = r["word"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        rec = {"id": len(words) + 1}
        for f in FIELDS:
            v = r.get(f, "")
            if f == "level":
                rec[f] = int(v) if str(v).strip().isdigit() else 1
            else:
                rec[f] = str(v).strip()
        words.append(rec)

    name = a.name or os.path.splitext(os.path.basename(a.input))[0]
    out = os.path.join(ROOT, "wordbanks", name + ".json")
    if os.path.exists(out) and not a.force:
        sys.exit("wordbanks/%s.json 已存在。换个 --name，或者加 --force 覆盖。" % name)
    data = {"meta": {"name": a.title or name, "count": len(words),
                     "source": os.path.basename(a.input),
                     "created": datetime.date.today().isoformat()},
            "words": words}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    thin = sum(1 for w in words if not w["zh"])
    print("已写入 wordbanks/%s.json：%d 个词（去重掉 %d 个）"
          % (name, len(words), len(rows) - len(words)))
    if thin:
        print("其中 %d 个词没有中文释义，建议让 Claude 按 wordbanks/SCHEMA.md 补齐。" % thin)
    print("启用它：把 config.json 的 wordbank 改成 \"%s.json\"，或右键桌宠→换词库。" % name)


if __name__ == "__main__":
    main()
