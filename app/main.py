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
    """离屏自检：强制使用临时数据目录，不接触真实进度与窗口设置。"""
    import tempfile
    root = tempfile.mkdtemp(prefix="wordpet-smoke-")
    os.environ["WORDPET_HOME"] = root
    # core 已导入，显式改写运行路径并复制只读配置/词库/主题。
    import shutil
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("config.json", "wordbanks", "themes"):
        src = os.path.join(project_root, name)
        dst = os.path.join(root, name)
        shutil.copytree(src, dst) if os.path.isdir(src) else shutil.copy2(src, dst)
    core.ROOT = root
    core.DATA_DIR = os.path.join(root, "data")
    core.CONFIG_FILE = os.path.join(root, "config.json")
    core.STATE_FILE = os.path.join(root, "data", "state.json")
    core.PREFS_FILE = os.path.join(root, "data", "prefs.json")
    app = QApplication(sys.argv)
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
    panel.grade(core.GRADE_GOOD)
    panel.reveal()
    panel.grade(core.GRADE_AGAIN)
    panel._tick()
    for mode in ("sweep", "shuffle", "review", "weak"):
        panel._set_mode(mode)
        panel._build_queue()
    panel._toggle_untimed(True)
    assert panel.untimed, "不限时模式没有启用"
    panel.finish("smoke")
    panel._reset_session()
    panel.close()
    pet.set_scale(1.0)
    pet._save_prefs()
    store.load()
    assert store.progress, "打分没有写入 progress"
    print("today:", store.today_rec(), "| words:", len(store.words),
          "| theme:", store.theme.name)
    print("SMOKE OK")
    del app
    shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(smoke() if "--smoke" in sys.argv else main())
