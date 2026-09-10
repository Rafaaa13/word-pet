#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台朗读单词：macOS 用 say，Windows 用系统自带 SAPI，Linux 用 spd-say/espeak。
系统没有可用的朗读程序时静默跳过，不影响背词。"""
import re
import shutil
import subprocess
import sys

_ENGINE = "?"          # "?" 未探测，None 不可用
_VOICE = ""
_SAFE = re.compile(r"[^A-Za-z0-9 ,.'\-]")


def _detect():
    global _ENGINE, _VOICE
    if sys.platform == "darwin":
        _ENGINE = "say"
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True,
                                 text=True, timeout=3).stdout
            _VOICE = next((v for v in ("Samantha", "Alex", "Daniel", "Karen") if v in out), "")
        except Exception:
            _VOICE = ""
    elif sys.platform.startswith("win"):
        _ENGINE = "sapi" if shutil.which("powershell") else None
    else:
        _ENGINE = next((c for c in ("spd-say", "espeak-ng", "espeak") if shutil.which(c)), None)


def speak(text, enabled=True):
    global _ENGINE
    if not enabled or not text:
        return
    if _ENGINE == "?":
        _detect()
    if not _ENGINE:
        return
    word = _SAFE.sub("", str(text))[:60].strip()
    if not word:
        return
    if _ENGINE == "say":
        cmd = ["say"] + (["-v", _VOICE] if _VOICE else []) + [word]
    elif _ENGINE == "sapi":
        cmd = ["powershell", "-NoProfile", "-Command",
               "Add-Type -AssemblyName System.Speech;"
               "(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
               ".Speak('%s')" % word.replace("'", "")]
    else:
        cmd = [_ENGINE, word]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        _ENGINE = None
