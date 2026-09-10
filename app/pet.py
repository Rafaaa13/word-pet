#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""桌宠本体：透明无边框、置顶、可拖动；点击触发动画 + 气泡；右键菜单可换形象/换词库。
换形象只要往 themes/ 里放一张 pet.png，不用改这个文件。"""
import math
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta

from PyQt6.QtCore import QPoint, QPointF, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

import core
from bubble import Bubble
from panel import StudyPanel


def autocrop(pm: QPixmap) -> QPixmap:
    """裁掉图片四周的透明边，这样任何随手找来的 PNG 都能撑满显示高度。"""
    if pm.isNull():
        return pm
    small = pm.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.FastTransformation).toImage()
    w, h = small.width(), small.height()
    if w < 2 or h < 2:
        return pm
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if small.pixelColor(x, y).alpha() > 12:
                x0, y0 = min(x0, x), min(y0, y)
                x1, y1 = max(x1, x), max(y1, y)
    if x1 < 0 or (x1 - x0 + 1) * (y1 - y0 + 1) > 0.985 * w * h:
        return pm
    sx, sy = pm.width() / w, pm.height() / h
    box = QRect(int(x0 * sx), int(y0 * sy),
                max(1, int((x1 - x0 + 1) * sx)), max(1, int((y1 - y0 + 1) * sy)))
    return pm.copy(box.intersected(pm.rect()))


class Pet(QWidget):
    def __init__(self, store):
        super().__init__(None)
        self.store = store
        prefs = core.read_json(core.PREFS_FILE, {})
        self.scale = min(2.4, max(0.4, float(prefs.get("scale", 0.8))))
        self.topmost = bool(prefs.get("topmost", True))
        self.hourly = bool(prefs.get("hourly", store.cfg.get("hourlyNudge", True)))
        self._saved_pos = prefs.get("pos")

        self._apply_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)

        self.bubble = Bubble()
        self.panel = None
        self.anim = None
        self.click_idx = 0
        self._press = self._wpos = None
        self._dragging = False
        self._last_quip = ""
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._on_anim_tick)

        self._disp = None
        self._pw = self._ph = 1.0
        self._mx = self._mt = self._mb = 0
        self._load_image()
        self._rebuild()
        self._restore_pos()

        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self._idle)
        self._reset_idle()
        self._schedule_hourly()

    # ---- 图像与窗口
    def _load_image(self):
        self.orig = autocrop(QPixmap(self.store.theme.image))

    def _apply_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.topmost:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _rebuild(self, keep_anchor=None):
        dpr = self.devicePixelRatioF() or 1.0
        th = max(60, int(int(self.store.cfg.get("petHeight", 300)) * self.scale))
        pm = self.orig.scaledToHeight(int(th * dpr), Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self._disp = pm
        self._ph = float(th)
        self._pw = pm.width() / dpr
        self._mx = int(self._pw * 0.14)          # 左右留白，给抖动动画和气泡尾巴
        self._mt = int(self._ph * 0.32)          # 顶部留白，给跳跃动画
        self._mb = 6
        self.setFixedSize(int(self._pw) + 2 * self._mx, int(self._ph) + self._mt + self._mb)
        if keep_anchor is not None:
            self.move(keep_anchor.x() - self.width() // 2, keep_anchor.y() - self.height())
        self._clamp_to_screen()
        self.update()

    def _restore_pos(self):
        if isinstance(self._saved_pos, list) and len(self._saved_pos) == 2:
            self.move(int(self._saved_pos[0]), int(self._saved_pos[1]))
            if QGuiApplication.screenAt(self.frameGeometry().center()):
                return
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 36, geo.bottom() - self.height() - 24)

    def _clamp_to_screen(self):
        scr = QGuiApplication.screenAt(self.frameGeometry().center()) \
            or QGuiApplication.primaryScreen()
        geo = scr.availableGeometry()
        self.move(max(geo.left() - self._mx, min(self.x(), geo.right() - self.width() + self._mx)),
                  max(geo.top(), min(self.y(), geo.bottom() - self.height() + self._mb)))

    def visual_rect_global(self):
        tl = self.mapToGlobal(QPoint(self._mx, self.height() - self._mb - int(self._ph)))
        return QRect(tl, QSize(int(self._pw), int(self._ph)))

    def _save_prefs(self):
        core.write_json(core.PREFS_FILE, {"scale": round(self.scale, 3),
                                          "pos": [self.x(), self.y()],
                                          "topmost": self.topmost, "hourly": self.hourly})

    # ---- 动画
    def start_anim(self, kind):
        dur = {"jump": 0.55, "squash": 0.5, "shake": 0.55, "bob": 1.2, "alert": 1.8}
        self.anim = {"type": kind, "t0": time.monotonic(), "dur": dur.get(kind, 0.5)}
        if not self.anim_timer.isActive():
            self.anim_timer.start()

    def _on_anim_tick(self):
        if self.anim is None:
            self.anim_timer.stop()
            return
        if time.monotonic() - self.anim["t0"] >= self.anim["dur"]:
            self.anim = None
            self.anim_timer.stop()
        self.update()

    def _anim_params(self):
        if self.anim is None:
            return 0.0, 0.0, 1.0, 1.0
        t = max(0.0, min(1.0, (time.monotonic() - self.anim["t0"]) / self.anim["dur"]))
        kind = self.anim["type"]
        dx = dy = 0.0
        sx = sy = 1.0
        if kind == "jump":
            dy = -0.22 * self._ph * 4 * t * (1 - t)
            sy = 1 + 0.05 * math.sin(math.pi * t)
            sx = 1 - 0.03 * math.sin(math.pi * t)
        elif kind == "squash":
            sy = 1 - 0.28 * math.sin(math.pi * t)
            sx = 1 + (1 - sy) * 0.7
        elif kind == "shake":
            dx = 0.05 * self._pw * math.sin(6 * math.pi * t) * (1 - t)
        elif kind == "bob":
            dy = -0.025 * self._ph * abs(math.sin(2 * math.pi * t))
        elif kind == "alert":                      # 整点提醒：连跳三下，比普通动画更醒目
            bounce = abs(math.sin(3 * math.pi * t))
            dy = -0.18 * self._ph * bounce * (1 - 0.35 * t)
            dx = 0.03 * self._pw * math.sin(9 * math.pi * t) * (1 - t)
            sy = 1 + 0.04 * bounce
        return dx, dy, sx, sy

    def paintEvent(self, e):
        if self._disp is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dx, dy, sx, sy = self._anim_params()
        p.translate(self.width() / 2 + dx, self.height() - self._mb + dy)
        p.scale(sx, sy)
        p.drawPixmap(QPointF(-self._pw / 2, -self._ph), self._disp)

    # ---- 交互
    def show_bubble(self, text, msec=6000):
        self.bubble.popup(text, self.visual_rect_global(), msec)

    def on_click(self):
        self.start_anim(["jump", "squash", "shake"][self.click_idx % 3])
        self.click_idx += 1
        if random.random() < 0.25:
            self.show_bubble(core.quiz_text(self.store), 9000)
        else:
            pool = self.store.theme.raw("quips", []) or ["……"]
            q = random.choice([x for x in pool if x != self._last_quip] or pool)
            self._last_quip = q
            self.show_bubble(core.fmt(q, self.store.ctx()), 5000)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._wpos = self.pos()
            self._dragging = False

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        delta = e.globalPosition().toPoint() - self._press
        if not self._dragging and delta.manhattanLength() > 6:
            self._dragging = True
            self.bubble.hide()
        if self._dragging:
            self.move(self._wpos + delta)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._dragging:
            self._clamp_to_screen()
            self._save_prefs()
        elif self._press is not None:
            self.on_click()
        self._press = None
        self._dragging = False

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d:
            self.set_scale(self.scale * (1.1 if d > 0 else 1 / 1.1))

    def set_scale(self, v):
        anchor = QPoint(self.x() + self.width() // 2, self.y() + self.height())
        self.scale = min(2.4, max(0.4, v))
        self._rebuild(keep_anchor=anchor)
        self._save_prefs()

    def set_topmost(self, on):
        self.topmost = on
        self._apply_flags()
        self.show()
        self._save_prefs()

    # ---- 右键菜单
    def contextMenuEvent(self, e):
        m = QMenu(self)
        mins = int(self.store.cfg.get("sessionMinutes", 15))
        m.addAction("📖 开始 %d 分钟背词" % mins).triggered.connect(
            lambda: self.open_study("mixed"))
        m.addAction("🔁 只复习到期的词").triggered.connect(lambda: self.open_study("review"))
        m.addAction("📊 今日进度").triggered.connect(self._show_progress)
        m.addAction("🎲 抽查一个词").triggered.connect(
            lambda: self.show_bubble(core.quiz_text(self.store), 9000))
        m.addSeparator()

        sub = m.addMenu("🎨 换形象")
        self._fill_switch(sub, "themes", "theme", self.store.cfg.get("theme"))
        sub = m.addMenu("📚 换词库")
        self._fill_switch(sub, "wordbanks", "wordbank", self.store.cfg.get("wordbank"))
        sz = m.addMenu("📏 调整大小（滚轮可微调）")
        for name, v in (("小", 0.55), ("中", 0.8), ("大", 1.15)):
            sz.addAction(name).triggered.connect(lambda _, vv=v: self.set_scale(vv))

        a = m.addAction("⏰ 整点提醒")
        a.setCheckable(True); a.setChecked(self.hourly)
        a.toggled.connect(self._set_hourly)
        a = m.addAction("📌 窗口置顶")
        a.setCheckable(True); a.setChecked(self.topmost)
        a.toggled.connect(self.set_topmost)
        m.addSeparator()
        m.addAction("📂 打开数据文件夹").triggered.connect(lambda: self._open_dir())
        m.addAction("❌ 退出桌宠").triggered.connect(self.quit_all)
        m.exec(e.globalPos())

    def _fill_switch(self, menu, folder, key, current):
        """把 themes/ 或 wordbanks/ 里的候选项列成可勾选菜单，选中即写回 config.json。"""
        d = os.path.join(core.ROOT, folder)
        if folder == "themes":
            items = sorted(n for n in os.listdir(d)
                           if os.path.isdir(os.path.join(d, n)) and not n.startswith("."))
        else:
            items = sorted(n for n in os.listdir(d) if n.endswith(".json"))
        for it in items:
            a = menu.addAction(it[:-5] if folder == "wordbanks" else it)
            a.setCheckable(True); a.setChecked(it == current)
            a.triggered.connect(lambda _, k=key, v=it: self._switch(k, v))

    def _switch(self, key, value):
        cfg = core.read_json(core.CONFIG_FILE, {})
        cfg[key] = value
        core.write_json(core.CONFIG_FILE, cfg)
        self.store.load()
        if key == "theme":
            self._load_image()
            self._rebuild(keep_anchor=QPoint(self.x() + self.width() // 2,
                                             self.y() + self.height()))
            self.start_anim("jump")
            self.show_bubble(self.store.theme.text("greeting", self.store.ctx()), 8000)
        else:
            self.show_bubble("词库换成 %s 了，一共 %d 个词。"
                             % (value[:-5], len(self.store.words)), 8000)

    def _open_dir(self):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", core.ROOT])
            elif sys.platform.startswith("win"):
                os.startfile(core.ROOT)                       # noqa: S606
            else:
                subprocess.Popen(["xdg-open", core.ROOT])
        except Exception:
            pass

    def _show_progress(self):
        self.store.load()
        self.show_bubble(core.progress_text(self.store), 9000)

    def _set_hourly(self, on):
        self.hourly = on
        self._save_prefs()

    # ---- 背词面板
    def open_study(self, mode):
        if self.panel is not None:
            self.panel.close()
        self.panel = StudyPanel(self.store, mode, self)
        self.panel.adjustSize()
        pr = self.frameGeometry()
        scr = QGuiApplication.screenAt(pr.center()) or QGuiApplication.primaryScreen()
        geo = scr.availableGeometry()
        x = pr.left() - self.panel.width() - 14
        if x < geo.left() + 4:
            x = pr.right() + 14
        x = max(geo.left() + 4, min(x, geo.right() - self.panel.width() - 4))
        y = max(geo.top() + 4, min(pr.top(), geo.bottom() - 320))
        self.panel.move(x, y)
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()
        self.panel.setFocus()

    # ---- 定时
    def _reset_idle(self):
        self.idle_timer.start(random.randint(45000, 90000))

    def _idle(self):
        if self.anim is None and self.panel is None and not self.bubble.isVisible():
            self.start_anim("bob")
        self._reset_idle()

    def _schedule_hourly(self):
        now = datetime.now()
        nxt = now.replace(minute=0, second=5, microsecond=0) + timedelta(hours=1)
        QTimer.singleShot(max(1000, int((nxt - now).total_seconds() * 1000)), self._fire_hourly)

    def _fire_hourly(self):
        if self.hourly and self.panel is None:
            self.store.load()
            self.raise_()
            self.start_anim("alert")                 # 先动起来吸引注意，气泡稍后跟上
            QTimer.singleShot(700, lambda: self.show_bubble(core.nudge_text(self.store), 15000))
        self._schedule_hourly()

    def quit_all(self):
        self._save_prefs()
        try:
            self.store.save()
        except Exception:
            pass
        self.bubble.close()
        if self.panel is not None:
            self.panel.close()
        QApplication.quit()
