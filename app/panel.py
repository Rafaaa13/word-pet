#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""15 分钟极速背词：FSRS 长期排期 + 无上限全库通刷。"""
import html
import random
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QProgressBar,
                             QVBoxLayout, QWidget)

import core
import speech

CSS = """
QLabel { color:#23302b; background:transparent; }
QPushButton { border:1px solid #d4d9d5; border-radius:9px; padding:7px 9px;
              font-size:12px; color:#26322d; background-color:#f7f9f7; }
QPushButton:hover { border-color:#7b998b; background-color:#eef4f0; }
QPushButton#mode { color:#425149; background-color:#f7f9f7; border-color:#d4d9d5;
                   padding:6px 7px; font-size:11px; }
QPushButton#mode:hover { color:#1f503a; background-color:#e7f2ec; border-color:#7ba08e; }
QPushButton#mode:checked { color:#ffffff; background-color:#2f6f52; border-color:#275d46;
                          font-weight:700; }
QPushButton#again { background:#fff0ef; color:#a33c34; border-color:#efc7c3; }
QPushButton#hard { background:#fff8e7; color:#916416; border-color:#ead6a0; }
QPushButton#good { background:#edf8f2; color:#24704b; border-color:#b8dfc9; }
QPushButton#easy { background:#e8f1ff; color:#285a91; border-color:#b9d0ec; }
QPushButton#reveal { background:#253c33; color:white; border-color:#253c33; font-size:14px; }
QPushButton#close { background:transparent; border:none; color:#7f8a85; font-size:15px; }
QProgressBar { background:#e6ebe8; border:none; border-radius:3px; height:6px; }
QProgressBar::chunk { background:#3f8063; border-radius:3px; }
"""

MODES = (
    ("mixed", "智能混合"),
    ("sweep", "顺序通刷"),
    ("shuffle", "随机通刷"),
    ("review", "到期复习"),
    ("weak", "薄弱词"),
)


class StudyPanel(QWidget):
    def __init__(self, store, mode, pet):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.store, self.mode, self.pet = store, mode, pet
        self.bank_id = store.bank_id
        self.bank_meta = dict(store.bank_meta)
        self.words = list(store.words)
        self.progress_map = store.progress
        self.setFixedWidth(450)
        self._drag = None
        self.timer = None
        self.untimed = False
        self.current = None
        self.retry_once = set()
        self.round_order = []
        self.round_cursor = 0
        self.round_mode = None
        self.done_flag = self.revealed = False
        self._build_ui()
        self._reset_session()
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(1000)

    def _build_ui(self):
        self.setStyleSheet(CSS)
        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 18); root.setSpacing(9)
        head = QHBoxLayout()
        self.lbl_title = QLabel("极速背词"); f = self.lbl_title.font(); f.setBold(True); self.lbl_title.setFont(f)
        self.lbl_stats = QLabel(""); self.lbl_stats.setStyleSheet("color:#708079;font-size:11px;")
        self.lbl_timer = QLabel("15:00"); self.lbl_timer.setStyleSheet("color:#2f6f52;font-weight:700;font-size:15px;")
        close = QPushButton("✕"); close.setObjectName("close"); close.setFixedWidth(28); close.clicked.connect(self._request_close)
        head.addWidget(self.lbl_title); head.addWidget(self.lbl_stats); head.addStretch(1); head.addWidget(self.lbl_timer); head.addWidget(close)
        root.addLayout(head)

        mode_wrap = QVBoxLayout(); mode_wrap.setSpacing(4)
        mode_rows = (QHBoxLayout(), QHBoxLayout())
        for row in mode_rows: row.setSpacing(4)
        self.mode_buttons = {}
        for index, (value, label) in enumerate(MODES):
            button = QPushButton(label); button.setObjectName("mode"); button.setCheckable(True)
            button.clicked.connect(lambda _, selected=value: self._set_mode(selected))
            mode_rows[0 if index < 3 else 1].addWidget(button); self.mode_buttons[value] = button
        self.btn_untimed = QPushButton("不限时：关"); self.btn_untimed.setCheckable(True)
        self.btn_untimed.toggled.connect(self._toggle_untimed); mode_rows[1].addWidget(self.btn_untimed)
        mode_wrap.addLayout(mode_rows[0]); mode_wrap.addLayout(mode_rows[1]); root.addLayout(mode_wrap)
        self._sync_mode_buttons()

        self.progress = QProgressBar(); self.progress.setTextVisible(False); self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        self.lbl_phase = QLabel(""); self.lbl_phase.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_phase.setStyleSheet("color:#839089;font-size:11px;margin-top:6px;"); root.addWidget(self.lbl_phase)
        self.lbl_word = QLabel(""); wf = QFont(); wf.setPointSize(30); wf.setBold(True)
        self.lbl_word.setFont(wf); self.lbl_word.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_word.setMinimumHeight(55); root.addWidget(self.lbl_word)
        self.lbl_phon = QLabel(""); self.lbl_phon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_phon.setStyleSheet("color:#74827b;font-size:13px;"); root.addWidget(self.lbl_phon)
        self.detail = QLabel(""); self.detail.setTextFormat(Qt.TextFormat.RichText); self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop); self.detail.setMinimumHeight(180)
        self.detail.setStyleSheet("background:#f4f6f4;border-radius:12px;padding:14px;"); root.addWidget(self.detail)
        self.lbl_big = QLabel(""); self.lbl_big.setTextFormat(Qt.TextFormat.RichText); self.lbl_big.setWordWrap(True)
        self.lbl_big.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_big.setMinimumHeight(230); root.addWidget(self.lbl_big)
        self.btn_reveal = QPushButton("显示答案  Space"); self.btn_reveal.setObjectName("reveal"); self.btn_reveal.clicked.connect(self.reveal); root.addWidget(self.btn_reveal)
        grades = QHBoxLayout(); grades.setSpacing(7)
        self.grade_buttons = []
        for title, name, rating in (("1 重来", "again", 1), ("2 困难", "hard", 2),
                                    ("3 记得", "good", 3), ("4 秒答", "easy", 4)):
            b = QPushButton(title); b.setObjectName(name); b.clicked.connect(lambda _, r=rating: self.grade(r)); grades.addWidget(b); self.grade_buttons.append(b)
        root.addLayout(grades)
        done = QHBoxLayout(); self.btn_more = QPushButton("继续下一轮"); self.btn_more.clicked.connect(self._reset_session)
        self.btn_done = QPushButton("收工"); self.btn_done.clicked.connect(self.close); done.addWidget(self.btn_more); done.addWidget(self.btn_done); root.addLayout(done)
        self.footer = QLabel("Space 翻面 · 1–4 评分 · S 朗读 · M 换模式 · Esc 结算")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter); self.footer.setStyleSheet("color:#97a19c;font-size:10px;"); root.addWidget(self.footer)

    def _toggle_untimed(self, on):
        self.untimed = bool(on)
        self.btn_untimed.setText("不限时：开" if on else "不限时：关")
        self.deadline = time.monotonic() + int(self.store.cfg.get("sessionMinutes", 15)) * 60

    def _sync_mode_buttons(self):
        for value, button in self.mode_buttons.items():
            button.setChecked(value == self.mode)

    def _set_mode(self, mode):
        if mode not in self.mode_buttons or mode == self.mode:
            self._sync_mode_buttons(); return
        self.mode = mode
        self._sync_mode_buttons()
        self._reset_session()

    def _reset_session(self):
        self.store.load()
        self.bank_id = self.store.bank_id
        self.bank_meta = dict(self.store.bank_meta)
        self.words = list(self.store.words)
        self.progress_map = self.store.progress
        continuing = self.mode in ("sweep", "shuffle") and self.round_mode == self.mode \
                     and 0 < self.round_cursor < len(self.round_order)
        self.done_flag = False; self.revealed = False; self.current = None
        self.done_new = self.done_rev = self.session_sec = self._tick_i = 0
        self.first_seen = self.first_good = self.rescued = 0
        self.seen_words, self.failed_words = set(), set()
        self.retry_once.clear()
        if not continuing:
            self.round_no = getattr(self, "round_no", 0) + 1
            self.round_mode = self.mode
            self.round_order = self._build_queue()
            self.round_cursor = 0
        self.queue = self.round_order[self.round_cursor:] if self.mode in ("sweep", "shuffle") else self._build_queue()
        mins = int(self.store.cfg.get("sessionMinutes", 15)); self.deadline = time.monotonic() + mins * 60
        label = dict(MODES).get(self.mode, "极速背词"); self.lbl_title.setText(label.split(" · ")[0])
        if self.queue: self.next_card()
        else: self.finish("这个模式目前没有可刷词卡")

    def _eligible(self, words):
        return [w for w in words if self.store.can_review_today(w.get("word", ""))]

    def _build_queue(self):
        words = self._eligible(list(self.store.words)); due = self.store.due_words()
        if self.mode == "review": return due
        if self.mode == "weak":
            weak = [w for w in words if int(self.store.progress.get(w.get("word"), {}).get("rating", 4)) <= 2]
            random.shuffle(weak); return weak
        if self.mode == "shuffle": random.shuffle(words); return words
        if self.mode == "sweep": return words
        # 智能混合：40 只是里程碑，不再限制入队。全部到期词之后接全部未学词。
        new = self.store.new_words()
        queue = []
        while due or new:
            for _ in range(2):
                if due: queue.append(due.pop(0))
            if new: queue.append(new.pop(0))
            if not due and new: queue.extend(new); break
        return queue

    def next_card(self):
        while self.queue and not self.store.can_review_today(self.queue[0].get("word", "")):
            self.queue.pop(0)
        if not self.queue:
            if self.mode in ("sweep", "shuffle"):
                self.round_cursor = len(self.round_order)
            self.finish("本轮已刷完，可立即开始下一遍")
            return
        self.current = self.queue.pop(0); self.revealed = False
        self.lbl_word.setText(self.current.get("word", ""))
        self.lbl_phon.setText("%s  %s" % (self.current.get("phonetic", ""), self.current.get("pos", "")))
        self.lbl_phase.setText("第 %d 遍 · 今日此词剩余 %d 次评分" %
                               (self.round_no, self.store.remaining_reviews_today(self.current.get("word", ""))))
        self._set_state("card")

    def _answer_html(self):
        w = self.current or {}; syn = w.get("equivalents") or w.get("synonyms") or []
        if isinstance(syn, str): syn = [x.strip() for x in syn.split(",") if x.strip()]
        bits = ["<div style='font-size:18px;font-weight:700;color:#22352c;'>%s</div>" % html.escape(str(w.get("zh", "")))]
        if w.get("en"): bits.append("<div style='font-size:12px;color:#65736c;margin-top:6px;'>%s</div>" % html.escape(str(w["en"])))
        if w.get("mnemonic"):
            bits.append("<div style='font-size:12px;line-height:1.55;margin-top:12px;padding:9px 10px;background:#fff8e6;border-left:3px solid #d7a84b;border-radius:6px;color:#6b5120;'><b>巧记</b>　%s</div>" % html.escape(str(w["mnemonic"])))
        if syn: bits.append("<div style='font-size:12px;margin-top:12px;'><b>等价词</b>　%s</div>" % "　".join(html.escape(str(x)) for x in syn))
        return "".join(bits)

    def reveal(self):
        if not self.current or self.done_flag or self.revealed: return
        self.revealed = True; self.detail.setText(self._answer_html()); self.lbl_phase.setText("按第一次回忆的真实质量评分")
        self._set_state("revealed")

    def grade(self, rating):
        if not self.current or not self.revealed or self.done_flag: return
        word = self.current.get("word", ""); first = word not in self.seen_words
        was_new = word not in self.store.progress
        result = self.store.grade(word, rating)
        if result is None:
            self.queue = [w for w in self.queue if w.get("word") != word]
            self.next_card(); return
        if first:
            self.seen_words.add(word); self.first_seen += 1
            if rating >= 3: self.first_good += 1
            else: self.failed_words.add(word)
            rec = self.store.today_rec()
            if was_new: rec["n"] += 1; self.done_new += 1
            else: rec["r"] += 1; self.done_rev += 1
        elif word in self.failed_words and rating >= 3:
            self.failed_words.remove(word); self.rescued += 1
        if self.mode in ("sweep", "shuffle") and first:
            self.round_cursor = min(len(self.round_order), self.round_cursor + 1)
        # 每词每轮至多快速重插一次，避免 Again/Hard 永久霸占队列。
        retry_key = (self.mode, word)
        can_retry = self.store.can_review_today(word)
        if rating == 1 and can_retry and retry_key not in self.retry_once:
            self.retry_once.add(retry_key); self.queue.insert(min(4, len(self.queue)), self.current)
        elif rating == 2 and can_retry and retry_key not in self.retry_once:
            self.retry_once.add(retry_key); self.queue.insert(min(9, len(self.queue)), self.current)
        self.store.save(); self.next_card()

    def _label_due(self, rec):
        seconds = max(0, (self.store._parse_due(rec.get("due")) - self.store.now()).total_seconds())
        if seconds < 3600: return "%d 分钟" % max(1, round(seconds / 60))
        if seconds < 86400: return "%d 小时" % max(1, round(seconds / 3600))
        return "%d 天" % max(1, round(seconds / 86400))

    def _update_grade_hints(self):
        if not self.current: return
        previews = self.store.preview_grades(self.current.get("word", ""))
        if previews is None:
            return
        names = ("1 重来", "2 困难", "3 记得", "4 秒答")
        for i, b in enumerate(self.grade_buttons, 1): b.setText(names[i - 1] + "\n" + self._label_due(previews[i]))

    def finish(self, msg):
        self.done_flag = True; self.store.save(); recall = round(100 * self.first_good / max(1, self.first_seen))
        target = int(self.store.cfg.get("dailyNewTarget", 40)); today = self.store.today_rec()["n"]
        self.lbl_big.setText("<div style='font-size:22px;font-weight:700;'>%s</div>"
                             "<div style='font-size:13px;margin-top:12px;'>第 %d 遍 · 接触 %d 词 · 新词 %d · 复习 %d</div>"
                             "<div style='font-size:30px;font-weight:700;color:#2f7655;margin-top:18px;'>%d%%</div>"
                             "<div style='font-size:12px;color:#738079;'>首次回忆率</div>"
                             "<div style='font-size:12px;margin-top:12px;'>今日 %d 词 · 目标 %d 已%s · 超额不限量</div>"
                             % (html.escape(msg), self.round_no, self.first_seen, self.done_new, self.done_rev,
                                recall, today, target, "完成" if today >= target else "进行中"))
        self._set_state("done")

    def _set_state(self, state):
        card = state in ("card", "revealed")
        for w, show in ((self.lbl_word, card), (self.lbl_phon, card), (self.lbl_phase, card),
                        (self.detail, state == "revealed"), (self.btn_reveal, state == "card"),
                        *[(b, state == "revealed") for b in self.grade_buttons],
                        (self.lbl_big, state == "done"), (self.btn_more, state == "done"), (self.btn_done, state == "done")):
            w.setVisible(show)
        target = int(self.store.cfg.get("dailyNewTarget", 40)); today = self.store.today_rec()["n"]
        self.lbl_stats.setText("今日 %d · 目标 %d%s" % (today, target, " ✓" if today >= target else ""))
        total = self.first_seen + len(self.queue); self.progress.setValue(round(100 * self.first_seen / max(1, total)))
        if state == "revealed": self._update_grade_hints()
        if self.mode in ("sweep", "shuffle") and self.round_order:
            self.progress.setValue(round(100 * self.round_cursor / len(self.round_order)))
        self.adjustSize()

    def _tick(self):
        if self.done_flag: return
        self.store.today_rec()["sec"] += 1; self.session_sec += 1; self._tick_i += 1
        if self._tick_i % 20 == 0: self.store.save()
        left = self.deadline - time.monotonic()
        if self.untimed:
            self.lbl_timer.setText("+%02d:%02d" % (self.session_sec // 60, self.session_sec % 60))
        elif left <= 0:
            self.lbl_timer.setText("00:00"); self.finish("本轮时间到")
        else:
            self.lbl_timer.setText("%02d:%02d" % (int(left) // 60, int(left) % 60))

    def _request_close(self): self.close() if self.done_flag else self.finish("提前结算")
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Space: self.reveal()
        elif k in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4): self.grade(k - Qt.Key.Key_0)
        elif k == Qt.Key.Key_S and self.current: speech.speak(self.current.get("word", ""), self.store.cfg.get("speech", True))
        elif k == Qt.Key.Key_M:
            values = [value for value, _ in MODES]
            self._set_mode(values[(values.index(self.mode) + 1) % len(values)])
        elif k == Qt.Key.Key_Escape: self._request_close()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._drag = (e.globalPosition().toPoint(), self.pos())
    def mouseMoveEvent(self, e):
        if self._drag: self.move(self._drag[1] + (e.globalPosition().toPoint() - self._drag[0]))
    def mouseReleaseEvent(self, e): self._drag = None
    def closeEvent(self, e):
        try: self.timer.stop(); self.store.save()
        except Exception: pass
        if self.pet is not None and self.pet.panel is self: self.pet.panel = None
        e.accept()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#cdd5d1"), 1.2)); p.setBrush(QColor("#fffefb")); p.drawRoundedRect(1, 1, self.width()-2, self.height()-2, 18, 18)
