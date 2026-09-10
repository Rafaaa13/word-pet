#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动入口：python3 app/main.py
自检（不开窗口、跑一遍核心流程）：QT_QPA_PLATFORM=offscreen python3 app/main.py --smoke
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox             # noqa: E402

import core                                                        # noqa: E402
from pet import Pet                                                # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    store = core.Store()
    if not store.words:
        QMessageBox.critical(None, "背词桌宠",
                             "没读到词库：\n%s\n\n请检查 config.json 里的 wordbank 名字，"
                             "或运行 python3 tools/validate.py 查原因。"
                             % os.path.join(core.ROOT, "wordbanks", store.cfg["wordbank"]))
        sys.exit(1)
    if not os.path.exists(core.STATE_FILE):
        store.save()
    pet = Pet(store)
    pet.show()
    QTimer.singleShot(300, lambda: pet._rebuild())        # 拿到真实 DPI 后重建高清图
    QTimer.singleShot(1500, lambda: pet.show_bubble(
        store.theme.text("greeting", store.ctx()) + "\n" + core.progress_text(store), 10000))
    sys.exit(app.exec())


def smoke():
    """离屏自检：把所有窗口和核心流程都跑一遍，退出码 0 表示通过。"""
    app = QApplication(sys.argv)          # 必须持有引用，否则会被回收
    store = core.Store()
    assert store.words, "词库为空"
    pet = Pet(store)
    pet.show()
    for k in ("jump", "squash", "shake", "bob", "alert"):
        pet.start_anim(k)
        pet._anim_params()
    pet.on_click()
    pet.show_bubble("测试气泡\n第二行")
    pet._show_progress()
    print("nudge:", core.nudge_text(store).replace("\n", " / "))
    pet.open_study("mixed")
    panel = pet.panel
    assert panel.queue or panel.done_flag, "队列构造失败"
    panel.reveal()
    panel.grade(True)
    panel.grade(False)
    panel._tick()
    panel.finish("smoke")
    panel._again()
    panel.close()
    pet.set_scale(1.0)
    pet._save_prefs()
    store.load()
    assert store.state["progress"], "打分没有写入 progress"
    print("today:", store.today_rec(), "| words:", len(store.words),
          "| theme:", store.theme.name)
    print("SMOKE OK")
    del app
    return 0


if __name__ == "__main__":
    sys.exit(smoke() if "--smoke" in sys.argv else main())
