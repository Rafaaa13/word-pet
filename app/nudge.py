#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整点提醒用的命令行脚本：打印一条带真实进度的提醒，然后退出。
只读，绝不修改任何进度数据 —— 定时任务和 Claude 都只跑这个，不需要 PyQt。
    python3 app/nudge.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core                                                        # noqa: E402

if __name__ == "__main__":
    print(core.nudge_text(core.Store()))
