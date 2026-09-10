#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""背词面板：一张卡一个词，空格看释义，1 认识 / 2 不认识，倒计时结束自动结算。
所有提示文字来自 themes/<主题>/theme.json 的 panel 段。"""
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

import speech

CSS = """
QLabel { color:#3b2f28; background:transparent; }
QPushButton { background:#f2e8dc; border:1px solid #cbb9a6; border-radius:9px;
              padding:7px 14px; font-size:13px; color:#4a3b30; }
QPushButton:hover { background:#e8d9c6; }
QPushButton#know { background:#2f9e63; color:white; border-color:#27794d; }
QPushButton#forget { background:#c0564f; color:white; border-color:#94423d; }
QPushButton#close { background:transparent; border:none; font-size:15px; color:#8a7563; }
"""


class StudyPanel(QWidget):
    def __init__(self, store, mode, pet):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.store, self.mode, self.pet = store, mode, pet
        self.setFixedWidth(390)
        self._drag = None
        self.done_flag = False
        self.counted = set()
        self.done_new = self.done_rev = self.session_sec = self._tick_i = 0
        self.current = None
        self._build_ui()
        self._start_round()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _t(self, key, **extra):
        return self.store.theme.text("panel." + key, self.store.ctx(**extra))

    # ---- 界面
    def _build_ui(self):
        self.setStyleSheet(CSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 16)
        root.setSpacing(8)

        head = QHBoxLayout()
        self.lbl_title = QLabel("")
        f = self.lbl_title.font(); f.setBold(True); self.lbl_title.setFont(f)
        self.lbl_timer = QLabel("--:--")
        self.lbl_timer.setStyleSheet("color:#8a5a2b; font-weight:bold;")
        btn_close = QPushButton("✕"); btn_close.setObjectName("close")
        btn_close.setFixedWidth(28)
        btn_close.clicked.connect(self._request_close)
        head.addWidget(self.lbl_title); head.addStretch(1)
        head.addWidget(self.lbl_timer); head.addWidget(btn_close)
        root.addLayout(head)

        self.lbl_word = QLabel("")
        wf = QFont(); wf.setPointSize(28); wf.setBold(True)
        self.lbl_word.setFont(wf)
        self.lbl_word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.lbl_word)

        self.lbl_phon = QLabel("")
        self.lbl_phon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_phon.setStyleSheet("color:#8a7563; font-size:13px;")
        root.addWidget(self.lbl_phon)

        self.detail = QLabel("")
        self.detail.setTextFormat(Qt.TextFormat.RichText)
        self.detail.setWordWrap(True)
        root.addWidget(self.detail)

        self.lbl_big = QLabel("")                       # 结算画面
        self.lbl_big.setWordWrap(True)
        self.lbl_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.lbl_big)

        btns = QHBoxLayout(); btns.setSpacing(8)
        self.btn_say = QPushButton("🔊"); self.btn_say.setFixedWidth(46)
        self.btn_say.clicked.connect(self._say)
        self.btn_reveal = QPushButton("显示释义（空格）")
        self.btn_reveal.clicked.connect(self.reveal)
        self.btn_forget = QPushButton("不认识 ✗（2）"); self.btn_forget.setObjectName("forget")
        self.btn_forget.clicked.connect(lambda: self.grade(False))
        self.btn_know = QPushButton("认识 ✓（1）"); self.btn_know.setObjectName("know")
        self.btn_know.clicked.connect(lambda: self.grade(True))
        self.btn_stop = QPushButton("⏹ 结算退出")
        self.btn_stop.clicked.connect(lambda: self.finish(self._t("finish_early")))
        self.btn_again = QPushButton("再来一轮")
        self.btn_again.clicked.connect(self._again)
        self.btn_done = QPushButton("收工")
        self.btn_done.clicked.connect(self.close)
        for b in (self.btn_say, self.btn_reveal, self.btn_forget, self.btn_know,
                  self.btn_stop, self.btn_again, self.btn_done):
            btns.addWidget(b)
        root.addLayout(btns)

        self.footer = QLabel("")
        self.footer.setStyleSheet("color:#a4907c; font-size:11px;")
        root.addWidget(self.footer)

    # ---- 今天要背哪些词
    def _build_queue(self):
        self.store.load()
        due = self.store.due_words()
        if self.mode == "review":
            return due[:150]
        remaining = max(0, int(self.store.cfg.get("dailyNewTarget", 20))
                        - self.store.today_rec()["n"])
        return due[:80] + self.store.new_words()[:(remaining or 10)]

    def _start_round(self):
        self.queue = self._build_queue()
        mins = int(self.store.cfg.get("sessionMinutes", 15))
        self.deadline = time.monotonic() + mins * 60
        self.done_flag = False
        self.lbl_title.setText(self._t("title_review" if self.mode == "review"
                                       else "title_study"))
        if not self.queue:
            self.finish(self._t("finish_none" if self.mode == "review" else "finish_all"))
        else:
            self.next_card()

    # ---- 卡片流转
    def next_card(self):
        if not self.queue:
            self.finish(self._t("finish_batch"))
            return
        self.current = self.queue.pop(0)
        self.lbl_word.setText(self.current.get("word", ""))
        self.lbl_phon.setText("%s  %s" % (self.current.get("phonetic", ""),
                                          self.current.get("pos", "")))
        self._set_state("card")

    def _say(self):
        if self.current:
            speech.speak(self.current.get("word", ""), self.store.cfg.get("speech", True))

    def reveal(self):
        if not self.current or self.done_flag:
            return
        w = self.current
        self.detail.setText(
            "<div style='font-size:15px;'><b>%s</b></div>"
            "<div style='font-size:12px;color:#6b5a4c;margin-top:2px;'>%s</div>"
            "<div style='font-size:12px;color:#4a3b30;margin-top:8px;'><i>%s</i></div>"
            "<div style='font-size:12px;color:#8a7563;'>%s</div>"
            % (w.get("zh", ""), w.get("en", ""), w.get("example", ""), w.get("example_zh", "")))
        self._set_state("revealed")

    def grade(self, know):
        if not self.current or self.done_flag:
            return
        word = self.current.get("word", "")
        was_new = self.store.grade(word, know)
        if word not in self.counted:                    # 同一个词一天只计一次
            self.counted.add(word)
            rec = self.store.today_rec()
            if was_new:
                rec["n"] += 1; self.done_new += 1
            else:
                rec["r"] += 1; self.done_rev += 1
        if not know:                                    # 不认识就塞回队列近处再问一次
            self.queue.insert(min(3, len(self.queue)), self.current)
        self.store.save()
        self.next_card()

    def finish(self, msg):
        self.done_flag = True
        self.store.save()
        rec = self.store.today_rec()
        self.lbl_big.setText(self._t("summary", msg=msg, new=self.done_new,
                                     rev=self.done_rev,
                                     sess=int(round(self.session_sec / 60)),
                                     streak=max(self.store.streak(), 1)))
        self._set_state("done")
        if rec["n"] >= int(self.store.cfg.get("dailyNewTarget", 20)) and self.pet:
            self.pet.show_bubble(self._t("target_hit"), 8000)

    def _request_close(self):
        """✕ / Esc：背词中先出结算画面，再按一次才真正关闭。"""
        self.close() if self.done_flag else self.finish(self._t("finish_early"))

    def _again(self):
        self.done_new = self.done_rev = self.session_sec = 0
        self.counted.clear()
        self._start_round()

    def _set_state(self, s):
        card = s in ("card", "revealed")
        for w, vis in ((self.lbl_word, card), (self.lbl_phon, card),
                       (self.btn_say, card), (self.btn_stop, card),
                       (self.detail, s == "revealed"), (self.btn_know, s == "revealed"),
                       (self.btn_forget, s == "revealed"), (self.btn_reveal, s == "card"),
                       (self.lbl_big, s == "done"), (self.btn_again, s == "done"),
                       (self.btn_done, s == "done")):
            w.setVisible(vis)
        rec = self.store.today_rec()
        self.footer.setText("今日新词 %d/%d · 复习 %d · 本批还剩 %d"
                            % (rec["n"], int(self.store.cfg.get("dailyNewTarget", 20)),
                               rec["r"], len(self.queue)))
        self.adjustSize()

    # ---- 计时
    def _tick(self):
        if self.done_flag:
            return
        self.store.today_rec()["sec"] += 1
        self.session_sec += 1
        self._tick_i += 1
        if self._tick_i % 20 == 0:
            self.store.save()
        left = self.deadline - time.monotonic()
        if left <= 0:
            self.lbl_timer.setText("00:00")
            self.finish(self._t("finish_timeup"))
        else:
            self.lbl_timer.setText("%02d:%02d" % (int(left) // 60, int(left) % 60))

    # ---- 键盘 / 拖动 / 关闭
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Space:
            self.reveal()
        elif k in (Qt.Key.Key_1, Qt.Key.Key_J):
            self.grade(True)
        elif k in (Qt.Key.Key_2, Qt.Key.Key_F):
            self.grade(False)
        elif k == Qt.Key.Key_Escape:
            self._request_close()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = (e.globalPosition().toPoint(), self.pos())

    def mouseMoveEvent(self, e):
        if self._drag:
            gp, wp = self._drag
            self.move(wp + (e.globalPosition().toPoint() - gp))

    def mouseReleaseEvent(self, e):
        self._drag = None

    def closeEvent(self, e):
        try:
            self.timer.stop()
            self.store.save()
        except Exception:
            pass
        if self.pet is not None and self.pet.panel is self:
            self.pet.panel = None
        e.accept()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#cbb9a6"), 1.5))
        p.setBrush(QColor("#FFFDF6"))
        p.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 16, 16)
