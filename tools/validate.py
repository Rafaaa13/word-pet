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
                "hour", "total", "learned", "word", "phonetic", "pos", "zh", "en",
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


def check_wordbank(store):
    path = os.path.join(core.ROOT, "wordbanks", store.cfg["wordbank"])
    if not os.path.exists(path):
        bad("词库文件不存在：wordbanks/%s" % store.cfg["wordbank"])
        return
    if not store.words:
        bad("词库解析出 0 个词，检查是否为 {\"words\": [...]} 结构")
        return
    seen, dup, missing, thin = set(), [], [], 0
    for i, w in enumerate(store.words):
        if not isinstance(w, dict):
            missing.append("第 %d 条不是对象" % (i + 1)); continue
        for k in WORD_KEYS:
            if not str(w.get(k, "")).strip():
                missing.append("第 %d 条缺 %s" % (i + 1, k))
        word = str(w.get("word", "")).strip().lower()
        (dup.append(word) if word in seen else seen.add(word))
        if sum(1 for k in NICE_KEYS if str(w.get(k, "")).strip()) < 3:
            thin += 1
    if missing:
        bad("词库有 %d 处必填字段问题，例如：%s" % (len(missing), "；".join(missing[:3])))
    if dup:
        bad("词库有 %d 个重复单词，例如：%s" % (len(dup), ", ".join(dup[:5])))
    if not missing and not dup:
        ok("词库 %s：%d 个词，字段完整" % (store.cfg["wordbank"], len(store.words)))
    if thin:
        print("·  其中 %d 个词的音标/词性/例句偏少，能用但体验一般" % thin)
    banks = sorted(n for n in os.listdir(os.path.join(core.ROOT, "wordbanks"))
                   if n.endswith(".json"))
    ok("可选词库：%s" % " / ".join(banks))


def check_logic(store):
    """核心逻辑自测，用内存里的副本，不落盘。"""
    import copy
    s = copy.deepcopy(store)
    s.state = {"progress": {}, "daily": {}}
    w = s.words[0]["word"]
    assert s.grade(w, True) is True, "第一次打分应判定为新词"
    ivl1 = s.state["progress"][w]["ivl"]
    s.grade(w, True)
    assert s.state["progress"][w]["ivl"] > ivl1, "连对时间隔应该变长"
    s.grade(w, False)
    assert s.state["progress"][w]["ivl"] == 0, "答错应该重置间隔"
    assert s.grade(w, True) is False, "已学过的词不该再算新词"
    s.today_rec()["n"] = 1
    assert s.streak() == 1, "连续天数计算异常"
    assert core.fmt("{n}/{target} {zzz}", {"n": 1, "target": 2}) == "1/2 {zzz}", "占位符兜底异常"
    for fn in (core.progress_text, core.quiz_text, core.nudge_text):
        out = fn(s)
        assert out and "{" not in out, "%s 渲染出未替换的占位符：%s" % (fn.__name__, out)
    ok("核心逻辑自测通过（间隔阶梯 / 打卡 / 文案渲染）")


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
