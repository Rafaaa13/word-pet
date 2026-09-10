#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新建一个形象主题：复制一份 theme.json 模板，把图片放进去就能用。

    python3 tools/new_theme.py 皮卡丘 --image ~/Downloads/pikachu.png --pet-name 皮卡丘
    python3 tools/new_theme.py 皮卡丘                      # 先建骨架，图片之后自己放

之后启用：右键桌宠 →「🎨 换形象」，或把 config.json 的 theme 改成目录名。
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirname", help="主题目录名，建议用英文/拼音")
    ap.add_argument("--image", help="形象图片路径（PNG，最好透明背景）")
    ap.add_argument("--pet-name", help="桌宠自称，显示在气泡里")
    ap.add_argument("--from", dest="src", default="default", help="以哪个主题为模板")
    a = ap.parse_args()

    dst = os.path.join(ROOT, "themes", a.dirname)
    if os.path.exists(dst):
        sys.exit("themes/%s 已经存在了。" % a.dirname)
    src = os.path.join(ROOT, "themes", a.src, "theme.json")
    if not os.path.exists(src):
        sys.exit("模板主题不存在：themes/%s" % a.src)

    os.makedirs(dst)
    with open(src, encoding="utf-8") as f:
        theme = json.load(f)
    theme.pop("_note", None)
    theme["name"] = a.pet_name or a.dirname
    theme["image"] = "pet.png"
    theme["greeting"] = "%s报到。左键点我说话，右键出菜单，滚轮调大小。" % theme["name"]
    with open(os.path.join(dst, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, ensure_ascii=False, indent=2)

    if a.image and os.path.exists(os.path.expanduser(a.image)):
        shutil.copy(os.path.expanduser(a.image), os.path.join(dst, "pet.png"))
        print("图片已复制到 themes/%s/pet.png" % a.dirname)
    else:
        theme["image"] = "../default/pet.png"
        with open(os.path.join(dst, "theme.json"), "w", encoding="utf-8") as f:
            json.dump(theme, f, ensure_ascii=False, indent=2)
        print("还没给图片，暂时复用默认形象。把自己的 PNG 存成 themes/%s/pet.png，"
              "再把 theme.json 里的 image 改回 \"pet.png\"。" % a.dirname)

    print("已创建 themes/%s/theme.json —— 现在去改里面的 quips 和 nudge 文案就是你的人格了。"
          % a.dirname)
    print("检查：python3 tools/validate.py")


if __name__ == "__main__":
    main()
