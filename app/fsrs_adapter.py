#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FSRS 6 调度适配层：把 py-fsrs 卡片安全地映射到本项目 JSON。"""
import json
from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, Scheduler, State

DESIRED_RETENTION = 0.98
MAXIMUM_INTERVAL = 3
LEARNING_STEPS = (timedelta(minutes=1), timedelta(minutes=3), timedelta(minutes=10))
RELEARNING_STEPS = (timedelta(minutes=1), timedelta(minutes=5))

_SCHEDULER = Scheduler(
    desired_retention=DESIRED_RETENTION,
    learning_steps=LEARNING_STEPS,
    relearning_steps=RELEARNING_STEPS,
    maximum_interval=MAXIMUM_INTERVAL,
    enable_fuzzing=False,
)


def utc_now():
    return datetime.now(timezone.utc)


def _aware(value, fallback):
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return fallback


def _legacy_card(rec, now):
    """将旧 ease/ivl 记录迁移成 FSRS 卡片；到期日保持不变。"""
    ivl = max(0.0, float(rec.get("ivl", 0) or 0))
    due = _aware(rec.get("due"), now)
    last = _aware(rec.get("last"), now - timedelta(days=max(1.0, ivl)))
    stage = rec.get("stage")
    state = State.Review if stage == "review" or ivl else State.Learning
    difficulty = min(10.0, max(1.0, 5.0 - (float(rec.get("ease", 2.3)) - 2.3) * 2))
    if state == State.Review:
        stability = max(0.1, ivl or 1.0)
        return Card(state=state, step=None, stability=stability, difficulty=difficulty,
                    due=due, last_review=last)
    return Card(state=State.Learning, step=max(0, int(rec.get("step", 0) or 0)),
                stability=None, difficulty=None, due=due, last_review=None)


def _cap_card(card, now):
    """冲刺模式硬上限：无论旧卡还是 FSRS 新结果，due 都不超过 3 天。"""
    latest = now + timedelta(days=MAXIMUM_INTERVAL)
    if card.due > latest:
        card.due = latest
    return card


def card_from_record(rec, now=None):
    now = now or utc_now()
    raw = rec.get("fsrs") if isinstance(rec, dict) else None
    if isinstance(raw, dict):
        try:
            return _cap_card(Card.from_json(json.dumps(raw)), now)
        except (TypeError, ValueError, KeyError):
            pass
    return _cap_card(_legacy_card(rec or {}, now), now)


def record_from_card(card, rating, old=None):
    out = dict(old or {})
    data = card.to_dict()
    out.update({
        "scheduler": "fsrs-6",
        "fsrs": data,
        "stage": {State.Learning: "learning", State.Review: "review",
                  State.Relearning: "relearning"}.get(card.state, "learning"),
        "step": card.step or 0,
        "due": card.due.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "last": (card.last_review or utc_now()).astimezone(timezone.utc).isoformat(timespec="seconds"),
        "ivl": max(0, int(round((card.due - (card.last_review or utc_now())).total_seconds() / 86400))),
        "stability": card.stability,
        "difficulty": card.difficulty,
        "rating": int(rating),
        "reps": int(out.get("reps", 0)) + 1,
        "lapses": int(out.get("lapses", 0)) + (1 if int(rating) == 1 else 0),
    })
    return out


def review(rec, rating, now=None):
    now = now or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    card = card_from_record(rec or {}, now)
    card, _ = _SCHEDULER.review_card(card, Rating(int(rating)), now)
    card = _cap_card(card, now)
    return record_from_card(card, rating, rec)


def preview(rec, now=None):
    now = now or utc_now()
    return {rating: review(rec or {}, rating, now) for rating in range(1, 5)}
