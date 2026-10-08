#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令体检整个配置：config.json、主题、词库、文案占位符，外加核心逻辑自测。
    python3 tools/validate.py
不需要 PyQt，不会改任何数据。有 ✗ 就说明那一项要修，退出码非 0。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import core                                                        # noqa: E402

OK = ["✓"]
BAD = []
PLACEHOLDERS = {"name", "n", "r", "target", "left", "spent", "due", "streak", "mins",
                "hour", "total", "learned", "bank", "milestone", "word", "phonetic", "pos", "zh", "en",
                "msg", "new", "rev", "sess"}
WORD_KEYS = ("word", "zh")
NICE_KEYS = ("phonetic", "pos", "en", "example", "example_zh")


def ok(msg):
    print("✓", msg)


def bad(msg):
    BAD.append(msg)
    print("✗", msg)


def scan_placeholders(node, path=""):
    """把主题里所有 {xxx} 挑出来，凡是程序不认识的就报出来，免得线上显示成 {abc}。"""
    if isinstance(node, str):
        import re
        for m in re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", node):
            if m not in PLACEHOLDERS:
                bad("主题 %s 里的 {%s} 不是可用占位符（可用：%s）"
                    % (path or "?", m, " ".join(sorted(PLACEHOLDERS))))
    elif isinstance(node, dict):
        for k, v in node.items():
            scan_placeholders(v, "%s.%s" % (path, k) if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan_placeholders(v, "%s[%d]" % (path, i))


def check_config():
    raw = core.read_json(core.CONFIG_FILE, None)
    if raw is None:
        bad("读不到 config.json（是不是 JSON 写坏了？多了逗号最常见）")
        return {}
    for k, v in core.DEFAULT_CONFIG.items():
        if k in raw and not isinstance(raw[k], type(v)) and not (
                isinstance(v, (int, float)) and isinstance(raw[k], (int, float))):
            bad("config.json 里 %s 类型应该是 %s" % (k, type(v).__name__))
    unknown = [k for k in raw if k not in core.DEFAULT_CONFIG and not k.startswith("_")]
    if unknown:
        print("·  config.json 有程序不认识的键（不影响运行）：", ", ".join(unknown))
    try:
        import fsrs
        from importlib.metadata import version
        assert version("fsrs") == "6.3.2"
        ok("FSRS 6 调度器可用（fsrs 6.3.2）")
    except Exception as e:
        bad("FSRS 调度器不可用：%s" % e)
    ok("config.json 可读")
    return raw


def check_theme(store):
    t = store.theme
    if not os.path.isdir(t.dir):
        bad("主题目录不存在：themes/%s" % t.name)
        return
    if not os.path.exists(os.path.join(t.dir, "theme.json")):
        bad("themes/%s/theme.json 缺失" % t.name)
    if core.read_json(os.path.join(t.dir, "theme.json"), None) is None:
        bad("themes/%s/theme.json 解析失败（检查引号和逗号）" % t.name)
    img = t.image
    if not os.path.exists(img):
        bad("形象图片找不到：%s" % img)
    elif os.path.getsize(img) < 200:
        bad("形象图片疑似损坏（太小）：%s" % img)
    else:
        ok("主题 %s：形象图 %s（%.0f KB）"
           % (t.name, os.path.basename(img), os.path.getsize(img) / 1024))
    scan_placeholders(core.read_json(os.path.join(t.dir, "theme.json"), {}))
    for key in ("greeting", "quips", "quiz", "progress", "nudge.idle", "panel.summary"):
        if not t.raw(key):
            bad("主题缺少 %s（会回落到内置默认文案）" % key)
    others = sorted(n for n in os.listdir(os.path.join(core.ROOT, "themes"))
                    if os.path.isdir(os.path.join(core.ROOT, "themes", n)))
    ok("可选主题：%s" % " / ".join(others))


def wordbank_errors(raw):
    """校验两端共同的数据契约；缺少可选音标/例句/巧记不算错误。"""
    words = raw.get("words") if isinstance(raw, dict) else raw
    if not isinstance(words, list) or not words:
        return ["words 必须是非空数组"]
    errors, ids, spellings = [], set(), set()
    if isinstance(raw, dict) and isinstance(raw.get("meta"), dict):
        count = raw["meta"].get("count")
        if count is not None and (type(count) is not int or count != len(words)):
            errors.append("meta.count 与实际词数不符")
    for i, w in enumerate(words, 1):
        if not isinstance(w, dict):
            errors.append("第 %d 条不是对象" % i)
            continue
        for key in WORD_KEYS:
            if not isinstance(w.get(key), str) or not w[key].strip():
                errors.append("第 %d 条缺少有效的 %s" % (i, key))
        spelling = str(w.get("word", "")).strip().casefold()
        if spelling in spellings:
            errors.append("重复单词：%s" % spelling)
        spellings.add(spelling)
        ident = w.get("id")
        valid_id = (type(ident) is int and 0 < ident <= 9007199254740991) or (
            isinstance(ident, str) and bool(ident.strip()) and ident == ident.strip()
            and ident not in {"undefined", "null", "__proto__", "constructor", "prototype"})
        if not valid_id:
            errors.append("第 %d 条缺少有效 id（HTML 必须有唯一卡片键）" % i)
        elif str(ident) in ids:
            errors.append("重复 id：%s" % ident)
        else:
            ids.add(str(ident))
    return errors


def check_wordbank(store):
    """检查全部词库及仓库 HTML，不再仅检查当前配置的词库。"""
    import json
    from pathlib import Path
    folder = Path(core.ROOT) / "wordbanks"
    banks = sorted(folder.glob("*.json"))
    if not banks:
        bad("没有找到词库 JSON")
        return
    if store.cfg["wordbank"] not in {p.name for p in banks}:
        bad("当前配置的词库不存在：%s" % store.cfg["wordbank"])
    by_id = {}
    for path in banks:
        raw = core.read_json(str(path), None)
        errors = wordbank_errors(raw)
        if errors:
            bad("%s：%s" % (path.name, "；".join(errors[:5])))
            continue
        bank_id = raw.get("meta", {}).get("id", path.stem) if isinstance(raw, dict) else path.stem
        if bank_id in by_id:
            bad("重复词库 ID：%s" % bank_id)
        by_id[bank_id] = raw
        words = raw["words"] if isinstance(raw, dict) else raw
        ok("词库 %s：%d 个词，唯一 id / 必填字段正常" % (path.name, len(words)))
    html = Path(core.ROOT) / "GRE极速背词.html"
    if html.exists():
        try:
            text = html.read_text(encoding="utf-8")
            start = text.index("const BANKS=") + len("const BANKS=")
            embedded, _ = json.JSONDecoder().raw_decode(text[start:])
            assert isinstance(embedded, dict), "BANKS 必须是对象"
            for bank_id, raw in embedded.items():
                errors = wordbank_errors(raw)
                if errors:
                    bad("HTML %s：%s" % (bank_id, "；".join(errors[:5])))
                elif bank_id not in by_id or raw != by_id[bank_id]:
                    bad("HTML 词库与 JSON 不一致：%s" % bank_id)
                else:
                    ok("HTML 词库 %s：与 JSON 完全一致" % bank_id)
        except (ValueError, AssertionError) as exc:
            bad("HTML 词库解析失败：%s" % exc)


def check_logic(store):
    """核心逻辑自测，用内存里的副本，不落盘。"""
    import copy
    from datetime import datetime, timedelta, timezone
    s = copy.deepcopy(store)
    s.state = {"version": 2, "banks": {s.bank_id: {}}, "progress": {}, "daily": {}}
    w = s.words[0]["word"]
    t0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    assert s.grade(w, core.GRADE_AGAIN, t0) is True, "第一次打分应判定为新词"
    assert s.state["progress"][w]["scheduler"] == "fsrs-6", "应使用 FSRS 6 调度"
    # 动态当日上限：重来 6 次、困难 5 次、记得 2 次、秒答不重复。
    w_dynamic = s.words[2]["word"]
    assert s.grade(w_dynamic, core.GRADE_HARD, t0) is True
    assert s.review_count_today(w_dynamic, t0.date().isoformat()) == 1
    assert s.remaining_reviews_today(w_dynamic, t0.date().isoformat()) == 4
    assert s.grade(w_dynamic, core.GRADE_HARD, t0) is False
    assert s.grade(w_dynamic, core.GRADE_HARD, t0) is False
    assert s.grade(w_dynamic, core.GRADE_HARD, t0) is False
    assert s.grade(w_dynamic, core.GRADE_HARD, t0) is False
    assert not s.can_review_today(w_dynamic, t0.date().isoformat())
    w_easy = s.words[3]["word"]
    assert s.grade(w_easy, core.GRADE_EASY, t0) is True
    assert s.remaining_reviews_today(w_easy, t0.date().isoformat()) == 0
    assert s.grade(w_easy, core.GRADE_GOOD, t0) is None
    assert s.state["progress"][w]["stage"] == "learning", "重来后应留在学习阶段"
    assert s._parse_due(s.state["progress"][w]["due"]) == t0.replace(minute=1), "重来应 1 分钟后复测"
    previews = s.preview_grades("__new_sprint_test__", t0)
    assert s._parse_due(previews[core.GRADE_HARD]["due"]) <= t0 + timedelta(minutes=3), "困难应约 3 分钟后复测"
    assert all(s._parse_due(v["due"]) <= t0 + timedelta(days=3) for v in previews.values()), "任何评分都不得超过 3 天"
    s.grade(w, core.GRADE_GOOD, t0.replace(minute=1))
    assert s.state["progress"][w]["step"] == 1, "首次记得应进入第二学习步"
    due = s._parse_due(s.state["progress"][w]["due"])
    assert s.grade(w, core.GRADE_GOOD, due) is None, "记得设为2次后不得进行第三次评分"
    assert s.review_count_today(w, t0.date().isoformat()) == 2
    assert all(x.get("word") != w for x in s.due_words(t0)), "超限词当天不得再次进入到期队列"
    assert s.can_review_today(w, (t0 + timedelta(days=1)).date().isoformat()), "第二天应恢复复习额度"
    # Store 的每日上限和 FSRS 的毕业路径分开验证：冲刺上限会阻止同日第四次评分。
    fsrs_adapter = core.fsrs_adapter
    raw = {}
    ft = t0
    for g in (core.GRADE_AGAIN, core.GRADE_GOOD, core.GRADE_GOOD, core.GRADE_GOOD):
        raw = fsrs_adapter.review(raw, g, ft)
        ft = datetime.fromisoformat(raw["due"])
    assert raw["stage"] == "review", "完成 1/3/10 分钟学习步后应毕业到长期复习"
    w2 = s.words[1]["word"]
    s.grade(w2, core.GRADE_EASY, t0)
    assert 1 <= s.state["progress"][w2]["ivl"] <= 3, "秒答间隔应受 3 天冲刺上限约束"
    s.today_rec()["n"] = 1
    assert s.streak() == 1, "连续天数计算异常"
    assert core.fmt("{n}/{target} {zzz}", {"n": 1, "target": 2}) == "1/2 {zzz}", "占位符兜底异常"
    for fn in (core.progress_text, core.quiz_text, core.nudge_text):
        out = fn(s)
        assert out and "{" not in out, "%s 渲染出未替换的占位符：%s" % (fn.__name__, out)
    import random
    s._quiz_cycle = []
    picks = [core.quiz_word(s, random.Random(100 + i))["word"] for i in range(min(30, len(s.words)))]
    assert len(set(picks)) == len(picks), "连续抽查不应在词库走完前重复"
    if len(s.words) > 1:
        assert all(a != b for a, b in zip(picks, picks[1:])), "连续抽查不应出现同一个词"
    ok("核心逻辑自测通过（FSRS 6 冲刺 / 1·3·10 分钟 / 最大 3 天 / 无限通刷）")


def main():
    print("仓库根目录：", core.ROOT)
    check_config()
    store = core.Store()
    check_theme(store)
    check_wordbank(store)
    try:
        check_logic(store)
    except AssertionError as e:
        bad("逻辑自测失败：%s" % e)
    print("-" * 46)
    if BAD:
        print("有 %d 个问题要修：" % len(BAD))
        for b in BAD:
            print("  ✗", b)
        return 1
    print("全部通过。可以启动了：双击 scripts/ 里对应系统的启动器。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
