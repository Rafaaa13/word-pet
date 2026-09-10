#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""桌宠头顶的对话气泡：无边框、置顶、不抢焦点、超时自动消失。
只管样式和定位，文案由 core.py 提供。"""
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QLabel, QWidget

INK, EDGE, PAPER = "#3b2f28", "#8a7563", "#FFFDF2"


class Bubble(QWidget):
    PAD_L, PAD_T, PAD_R, PAD_B, TAIL = 14, 10, 14, 10, 12
    MAX_W = 300

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool
                            | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color:%s; font-size:13px; background:transparent;" % INK)
        self.tail_down = True
        self.tail_px = 30
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def popup(self, text, anchor: QRect, msec=6000):
        text = str(text or "")
        fm = self.label.fontMetrics()
        lw = min(self.MAX_W, max(60, max(fm.horizontalAdvance(s)
                                        for s in text.split("\n")) + 6))
        lh = fm.boundingRect(QRect(0, 0, lw, 2000),
                             int(Qt.TextFlag.TextWordWrap.value), text).height() + 2
        w = lw + self.PAD_L + self.PAD_R
        h = lh + self.PAD_T + self.PAD_B + self.TAIL

        scr = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        geo = scr.availableGeometry()
        x = max(geo.left() + 4, min(anchor.center().x() - w // 2, geo.right() - w - 4))
        y = anchor.top() - h - 6
        self.tail_down = True
        if y < geo.top() + 4:                      # 上面放不下就翻到下面，尾巴跟着翻
            y, self.tail_down = anchor.bottom() + 6, False
        self.tail_px = max(20, min(anchor.center().x() - x, w - 20))

        self.label.setText(text)
        self.label.setGeometry(self.PAD_L,
                               self.PAD_T + (0 if self.tail_down else self.TAIL), lw, lh)
        self.setFixedSize(w, h)
        self.move(x, y)
        self.show()
        self.raise_()
        self.update()
        self.hide_timer.start(msec)

    def mousePressEvent(self, e):
        self.hide()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, t = self.width(), self.height(), self.TAIL
        body = QRect(0, 0, w, h - t) if self.tail_down else QRect(0, t, w, h - t)
        path = QPainterPath()
        path.addRoundedRect(float(body.x()), float(body.y()),
                            float(body.width()), float(body.height()), 12.0, 12.0)
        tx = self.tail_px
        if self.tail_down:
            path.moveTo(tx - 9, body.bottom()); path.lineTo(tx, h - 1)
            path.lineTo(tx + 9, body.bottom())
        else:
            path.moveTo(tx - 9, body.top() + 1); path.lineTo(tx, 1)
            path.lineTo(tx + 9, body.top() + 1)
        path.closeSubpath()
        p.setPen(QPen(QColor(EDGE), 1.5))
        p.setBrush(QColor(PAPER))
        p.drawPath(path)
