#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层 + 记忆算法 + 文案渲染。桌宠界面和整点提醒脚本都只调用这里。

改文案 → 动 themes/<主题>/theme.json，不用动这个文件。
改每日目标 / 词库 / 时长 → 动 config.json，不用动这个文件。
"""
import json
import os
import random
from datetime import date, datetime, timedelta

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("WORDPET_HOME") or os.path.dirname(APP_DIR)
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_FILE = os.path.join(ROOT, "config.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
PREFS_FILE = os.path.join(DATA_DIR, "prefs.json")

LADDER = [1, 3, 7, 14, 30, 60, 120]      # 答对时的复习间隔阶梯（天）

DEFAULT_CONFIG = {
    "theme": "default",
    "wordbank": "gre-core-500.json",
    "dailyNewTarget": 20,
    "sessionMinutes": 15,
    "petHeight": 300,
    "hourlyNudge": True,
    "nudgeQuiz": True,
    "speech": True,
    "nightHour": 6,
}

# theme.json 里没写的字段都回落到这里，所以自定义主题只写想改的部分就行
FALLBACK_THEME = {
    "name": "小豆",
    "image": "pet.png",
    "greeting": "{name}就位。左键点我互动，右键出菜单，滚轮调大小。",
    "quips": ["单词不会自己爬进脑子。", "戳我一下，背十个词。", "今天的词，今天背完。"],
    "quiz": "随手抽查 · {word} {phonetic} —— {zh}",
    "progress": "今日新词 {n}/{target} · 复习 {r} 次 · {spent} 分钟\n"
                "待复习 {due} 个 · 连续打卡 {streak} 天",
    "nudge_prefix": "【{name}】",
    "nudge": {
        "night": ["凌晨 {hour} 点了，先睡吧，词明天再说。"],
        "night_left": "今日进度 {n}/{target}，还差 {left} 个。醒了再补也来得及。",
        "done": ["今日 {n} 个新词，全部搞定 ✓"],
        "done_extra": "复习 {r} 次 · {spent} 分钟 · 连续第 {streak} 天。去休息吧。",
        "going": ["已经拿下 {n} 个，还剩 {left} 个，别在这儿停。"],
        "going_extra": "今日复习 {r} 次 · {spent} 分钟 · 待复习 {due} 个。",
        "idle": ["今天还没开始。{left} 个新词等着，{mins} 分钟能搞定一批。"],
        "idle_due": "另外 {due} 个词到了复习点，再放就忘干净了。",
        "idle_streak": "连续第 {streak} 天，别断。",
    },
    "panel": {
        "title_study": "{mins} 分钟背词",
        "title_review": "到期复习",
        "finish_early": "提前收工",
        "finish_timeup": "时间到",
        "finish_batch": "这一批全部完成",
        "finish_none": "没有到期需要复习的词",
        "finish_all": "词库已经全部背完",
        "summary": "{msg}！\n本次：新词 {new} · 复习 {rev} · 用时 {sess} 分钟\n"
                   "今日：{n}/{target} · 连续 {streak} 天",
        "target_hit": "今日 {n} 个新词，全部完成。你比昨天的自己强。",
    },
}


# ------------------------------------------------------------------ 工具
class _Safe(dict):
    def __missing__(self, k):
        return "{%s}" % k


def fmt(s, ctx):
    try:
        return str(s).format_map(_Safe(ctx))
    except Exception:
        return str(s)


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


# ------------------------------------------------------------------ 主题
class Theme:
    def __init__(self, name):
        self.name = name
        self.dir = os.path.join(ROOT, "themes", name)
        self.data = _merge(FALLBACK_THEME, read_json(os.path.join(self.dir, "theme.json"), {}))

    @property
    def image(self):
        p = os.path.join(self.dir, self.data.get("image") or "pet.png")
        return p if os.path.exists(p) else os.path.join(ROOT, "themes", "default", "pet.png")

    def raw(self, path, default=""):
        cur = self.data
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def text(self, path, ctx=None, default=""):
        v = self.raw(path, default)
        if isinstance(v, list):
            v = random.choice(v) if v else ""
        return fmt(v, ctx or {})


# ------------------------------------------------------------------ 数据
class Store:
    """词库只读；data/state.json 读写（只存 progress + daily，不存设置）。"""

    def __init__(self):
        self.load()

    def load(self):
        self.cfg = _merge(DEFAULT_CONFIG, read_json(CONFIG_FILE, {}))
        self.theme = Theme(self.cfg.get("theme") or "default")
        raw = read_json(os.path.join(ROOT, "wordbanks", self.cfg["wordbank"]), {})
        self.words = raw.get("words", raw) if isinstance(raw, (dict, list)) else []
        if not isinstance(self.words, list):
            self.words = []
        st = read_json(STATE_FILE, None)
        if st is None:                                  # 首次运行：尝试接住旧版数据
            st = read_json(os.path.join(ROOT, "gre_state.json"), {})
        if not isinstance(st, dict):
            st = {}
        self.state = {"progress": st.get("progress") or {}, "daily": st.get("daily") or {}}

    def save(self):
        write_json(STATE_FILE, self.state)

    # ---- 查询
    @staticmethod
    def today():
        return date.today().isoformat()

    def today_rec(self):
        rec = self.state["daily"].setdefault(self.today(), {"n": 0, "r": 0, "sec": 0})
        for k in ("n", "r", "sec"):
            rec[k] = int(rec.get(k, 0) or 0)
        return rec

    def due_words(self):
        t, p = self.today(), self.state["progress"]
        ws = [w for w in self.words
              if w.get("word") in p and str(p[w["word"]].get("due", "9999")) <= t]
        ws.sort(key=lambda w: str(p[w["word"]].get("due", "")))
        return ws

    def new_words(self):
        p = self.state["progress"]
        return [w for w in self.words if w.get("word") not in p]

    def streak(self):
        daily = self.state["daily"]
        rec = daily.get(self.today()) or {}
        i = 0 if int(rec.get("n", 0)) + int(rec.get("r", 0)) > 0 else 1
        s = 0
        while i < 400:
            d = daily.get((date.today() - timedelta(days=i)).isoformat()) or {}
            if int(d.get("n", 0)) + int(d.get("r", 0)) > 0:
                s, i = s + 1, i + 1
            else:
                break
        return s

    # ---- 打分：认识就往阶梯上走一格，不认识就明天重来
    def grade(self, word, know):
        p = self.state["progress"]
        today = date.today()
        rec = p.get(word)
        is_new = rec is None
        rec = rec or {"ivl": 0, "reps": 0, "lapses": 0}
        if know:
            cur = int(rec.get("ivl", 0) or 0)
            rec["ivl"] = next((v for v in LADDER if v > cur), min(max(cur, 1) * 2, 365))
            rec["reps"] = int(rec.get("reps", 0)) + 1
        else:
            rec["ivl"] = 0
            rec["lapses"] = int(rec.get("lapses", 0)) + 1
        rec["due"] = (today + timedelta(days=rec["ivl"] or 1)).isoformat()
        rec["last"] = today.isoformat()
        p[word] = rec
        return is_new

    # ---- 所有文案占位符的取值都从这里来
    def ctx(self, **extra):
        rec = self.today_rec()
        target = int(self.cfg.get("dailyNewTarget", 20))
        c = {
            "name": self.theme.raw("name", "小豆"),
            "n": rec["n"], "r": rec["r"], "target": target,
            "left": max(0, target - rec["n"]),
            "spent": int(round(rec["sec"] / 60)),
            "due": len(self.due_words()), "streak": self.streak(),
            "mins": int(self.cfg.get("sessionMinutes", 15)),
            "hour": datetime.now().hour,
            "total": len(self.words), "learned": len(self.state["progress"]),
        }
        c.update(extra)
        return c


# ------------------------------------------------------------------ 文案
def progress_text(store):
    return store.theme.text("progress", store.ctx())


def quiz_text(store):
    p = store.state["progress"]
    pool = store.due_words() or store.new_words() or store.words
    if not pool:
        return "词库是空的，先去 wordbanks/ 放一个词库。"
    w = random.choice(pool)
    return store.theme.text("quiz", store.ctx(**{k: w.get(k, "") for k in
                                                 ("word", "phonetic", "pos", "zh", "en")}))


def nudge_text(store, with_quiz=None):
    """整点提醒文案。桌宠气泡和命令行提醒共用同一套，改一处两边都变。"""
    t, c = store.theme, store.ctx()
    lines = []
    if c["hour"] < int(store.cfg.get("nightHour", 6)):
        lines.append(t.text("nudge.night", c))
        if c["left"]:
            lines.append(t.text("nudge.night_left", c))
    elif c["left"] == 0 and c["n"] > 0:
        lines += [t.text("nudge.done", c), t.text("nudge.done_extra", c)]
    elif c["n"] > 0:
        lines += [t.text("nudge.going", c), t.text("nudge.going_extra", c)]
    else:
        lines.append(t.text("nudge.idle", c))
        if c["due"]:
            lines.append(t.text("nudge.idle_due", c))
        if c["streak"]:
            lines.append(t.text("nudge.idle_streak", c))
    if with_quiz if with_quiz is not None else store.cfg.get("nudgeQuiz", True):
        lines.append(quiz_text(store))
    lines = [x for x in lines if x]
    return fmt(t.raw("nudge_prefix", ""), c) + "\n".join(lines)
