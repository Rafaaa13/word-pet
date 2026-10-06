#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层 + 记忆算法 + 文案渲染。桌宠界面和整点提醒脚本都只调用这里。

改文案 → 动 themes/<主题>/theme.json，不用动这个文件。
改每日目标 / 词库 / 时长 → 动 config.json，不用动这个文件。
"""
import json
import os
import random
from datetime import date, datetime, timedelta, timezone

import fsrs_adapter

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("WORDPET_HOME") or os.path.dirname(APP_DIR)
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_FILE = os.path.join(ROOT, "config.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
PREFS_FILE = os.path.join(DATA_DIR, "prefs.json")

MAX_INTERVAL_DAYS = 365
GRADE_AGAIN, GRADE_HARD, GRADE_GOOD, GRADE_EASY = 1, 2, 3, 4
DAILY_LIMIT_BY_GRADE = {GRADE_AGAIN: 6, GRADE_HARD: 5, GRADE_GOOD: 2, GRADE_EASY: 0}

DEFAULT_CONFIG = {
    "theme": "default",
    "wordbank": "zhangwei-zhenkao-7.json",
    "dailyNewTarget": 40,
    "sessionMinutes": 15,
    "newPerSession": 0,
    "desiredRetention": 0.98,
    "maximumIntervalDays": 3,
    "maxReviewsPerWordPerDay": 3,
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
    "progress": "{bank}\n今日接触 {n} 词 · Daily {target}{milestone} · 复习 {r} 次 · {spent} 分钟\n"
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
        self.bank_meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
        self.bank_id = str(self.bank_meta.get("id") or os.path.splitext(self.cfg["wordbank"])[0])
        self.words = raw.get("words", raw) if isinstance(raw, (dict, list)) else []
        if not isinstance(self.words, list):
            self.words = []
        self._last_quiz_word = getattr(self, "_last_quiz_word", None)
        self._quiz_cycle = getattr(self, "_quiz_cycle", [])
        self._attach_equivalents()
        st = read_json(STATE_FILE, None)
        from_legacy = st is None
        if from_legacy:                                  # 首次运行：尝试接住旧版数据
            st = read_json(os.path.join(ROOT, "gre_state.json"), {})
        if not isinstance(st, dict):
            st = {}
        raw_progress = st.get("progress") or {}
        raw_daily = st.get("daily") or {}
        banks = st.get("banks") if isinstance(st.get("banks"), dict) else {}
        migration_bank = "gre-core-500" if from_legacy else self.bank_id
        if raw_progress and not banks:                    # v1：旧版默认库的全局 progress
            banks[migration_bank] = raw_progress
        banks.setdefault(self.bank_id, {})
        self.state = {"version": 2, "banks": banks, "progress": banks[self.bank_id],
                      "daily": raw_daily}
        self._apply_sprint_cap()

    def _apply_sprint_cap(self):
        """把所有词库里历史上排得过远的卡片拉回冲刺上限内。"""
        cap = self.now() + timedelta(days=int(self.cfg.get("maximumIntervalDays", 3)))
        for progress in self.state["banks"].values():
            if not isinstance(progress, dict):
                continue
            for rec in progress.values():
                if not isinstance(rec, dict) or not rec.get("due"):
                    continue
                if self._parse_due(rec.get("due")) > cap:
                    rec["due"] = cap.isoformat(timespec="seconds")
                    if isinstance(rec.get("fsrs"), dict):
                        rec["fsrs"]["due"] = cap.isoformat(timespec="seconds")

    def _attach_equivalents(self):
        """镇考卡自动吸收等价词库；独立等价词库则保留自身词组。"""
        if not self.words or "equivalence" in self.bank_id:
            return
        path = os.path.join(ROOT, "wordbanks", "zhangwei-equivalence-2021.json")
        raw = read_json(path, {})
        rows = raw.get("words", []) if isinstance(raw, dict) else []
        eq = {str(x.get("word", "")).casefold(): x.get("equivalents") or x.get("synonyms") or []
              for x in rows if isinstance(x, dict)}
        for word in self.words:
            base = word.get("synonyms") or []
            if isinstance(base, str):
                base = [x.strip() for x in base.split(",") if x.strip()]
            extra = eq.get(str(word.get("word", "")).casefold(), [])
            word["synonyms"] = list(dict.fromkeys([*base, *extra]))

    @property
    def progress(self):
        return self.state["progress"]

    def save(self):
        self.state["banks"][self.bank_id] = self.state["progress"]
        payload = {"version": 2, "banks": self.state["banks"], "daily": self.state["daily"]}
        write_json(STATE_FILE, payload)

    # ---- 查询
    @staticmethod
    def today():
        return date.today().isoformat()

    def review_limit(self, word=None, day=None):
        day = day or self.today()
        if word:
            rec = self.progress.get(word) or {}
            if rec.get("daily_review_date") == day and rec.get("daily_review_limit") is not None:
                return max(0, int(rec.get("daily_review_limit") or 0))
        return max(1, int(self.cfg.get("maxReviewsPerWordPerDay", 3)))

    def review_count_today(self, word, day=None):
        day = day or self.today()
        rec = self.progress.get(word) or {}
        return int(rec.get("daily_reviews", 0) or 0) if rec.get("daily_review_date") == day else 0

    def can_review_today(self, word, day=None):
        return self.review_count_today(word, day) < self.review_limit(word, day)

    def remaining_reviews_today(self, word, day=None):
        return max(0, self.review_limit(word, day) - self.review_count_today(word, day))

    def _mark_review_today(self, rec, rating, day=None):
        day = day or self.today()
        count = int(rec.get("daily_reviews", 0) or 0) if rec.get("daily_review_date") == day else 0
        rec["daily_review_date"] = day
        rec["daily_review_limit"] = DAILY_LIMIT_BY_GRADE.get(int(rating), self.review_limit())
        rec["daily_reviews"] = count + 1
        return rec

    def today_rec(self):
        rec = self.state["daily"].setdefault(self.today(), {"n": 0, "r": 0, "sec": 0})
        for k in ("n", "r", "sec"):
            rec[k] = int(rec.get(k, 0) or 0)
        return rec

    @staticmethod
    def now():
        return datetime.now(timezone.utc).replace(microsecond=0)

    @staticmethod
    def _parse_due(value):
        try:
            parsed = datetime.fromisoformat(str(value))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            try:
                return datetime.combine(date.fromisoformat(str(value)), datetime.min.time(), timezone.utc)
            except (TypeError, ValueError):
                return datetime.max.replace(tzinfo=timezone.utc)

    def due_words(self, now=None):
        now = now or self.now()
        day = now.date().isoformat()
        p = self.progress
        ws = [w for w in self.words
              if w.get("word") in p and self.can_review_today(w["word"], day)
              and self._parse_due(p[w["word"]].get("due")) <= now]
        ws.sort(key=lambda w: self._parse_due(p[w["word"]].get("due")))
        return ws

    def new_words(self):
        p = self.progress
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

    # ---- FSRS 6 四档打分；旧进度首次评分时自动迁移
    def grade(self, word, rating, now=None):
        if isinstance(rating, bool):
            rating = GRADE_GOOD if rating else GRADE_AGAIN
        rating = max(GRADE_AGAIN, min(GRADE_EASY, int(rating)))
        p, now = self.progress, now or self.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        rec = p.get(word)
        is_new = rec is None
        if rec is not None and not self.can_review_today(word, now.date().isoformat()):
            return None
        p[word] = self._mark_review_today(
            fsrs_adapter.review(rec or {}, rating, now), rating, now.date().isoformat())
        return is_new

    def preview_grades(self, word, now=None):
        if word in self.progress and not self.can_review_today(word):
            return None
        return fsrs_adapter.preview(self.progress.get(word) or {}, now or self.now())

    # ---- 所有文案占位符的取值都从这里来
    def ctx(self, **extra):
        rec = self.today_rec()
        target = int(self.cfg.get("dailyNewTarget", 40))
        c = {
            "name": self.theme.raw("name", "小豆"),
            "n": rec["n"], "r": rec["r"], "target": target,
            "milestone": " ✓（不限量继续）" if rec["n"] >= target else "",
            "left": max(0, target - rec["n"]),
            "spent": int(round(rec["sec"] / 60)),
            "due": len(self.due_words()), "streak": self.streak(),
            "mins": int(self.cfg.get("sessionMinutes", 15)),
            "hour": datetime.now().hour,
            "total": len(self.words), "learned": len(self.progress),
            "bank": self.bank_meta.get("name", self.bank_id),
        }
        c.update(extra)
        return c


# ------------------------------------------------------------------ 文案
def progress_text(store):
    return store.theme.text("progress", store.ctx())


def quiz_word(store, rng=None):
    """从当前词库做无放回随机抽查；一轮走完前不重复，也不会连续同词。"""
    rng = rng or random
    valid = {str(w.get("word", "")).casefold(): w for w in store.words if w.get("word")}
    cycle = [key for key in getattr(store, "_quiz_cycle", []) if key in valid]
    if not cycle:
        cycle = list(valid)
        rng.shuffle(cycle)
        last = str(getattr(store, "_last_quiz_word", "") or "").casefold()
        if len(cycle) > 1 and cycle[-1] == last:
            cycle[0], cycle[-1] = cycle[-1], cycle[0]
    key = cycle.pop()
    store._quiz_cycle = cycle
    store._last_quiz_word = valid[key].get("word", "")
    return valid[key]


def quiz_text(store, rng=None):
    if not store.words:
        return "词库是空的，先去 wordbanks/ 放一个词库。"
    w = quiz_word(store, rng)
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
