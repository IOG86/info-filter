# -*- coding: utf-8 -*-
"""一键设置向导（控制台版）：逐项问你「同意 / 不同意」，同意的才执行。

用法：
    py 一键设置.py            # 逐项询问
    py 一键设置.py --yes      # 全部同意（不询问）
    py 一键设置.py --dry      # 只看会做什么，不真的执行
    py 一键设置.py --undo     # 把之前改过的设置恢复原样
"""
import sys as _sys

try:                                   # 中文 Windows 控制台默认 GBK
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixes  # noqa: E402

MARK = {"needed": "建议执行", "done": "已完成  ", "optional": "可选    ", "unsupported": "不支持  "}


def main():
    args = _sys.argv[1:]
    if "--undo" in args:
        r = fixes.undo()
        print("已恢复 %d 项设置。" % r.get("count", 0) if r.get("ok") else "恢复失败：%s" % r.get("msg"))
        return 0

    dry = "--dry" in args
    auto_yes = "--yes" in args
    actions = fixes.preview()

    print("=" * 64)
    print("信息筛选官 · 一键设置")
    print("=" * 64)
    print("下面每一项都会问你同不同意，只有同意的才会执行。")
    print("改动只涉及 Windows 通知设置，且全部可以 --undo 撤销。\n")

    chosen = []
    for a in actions:
        print("[%s] %s" % (MARK.get(a["status"], a["status"]), a["title"]))
        print("       %s" % a["desc"])
        if a.get("detail"):
            print("       当前：%s" % a["detail"])
        if a["status"] == "done":
            print("       → 已经做过了，跳过\n")
            continue
        if a["status"] == "unsupported":
            print("       → 当前环境不支持，跳过\n")
            continue
        if dry or auto_yes:
            answer = "y"
            print("       → 自动同意\n")
        else:
            try:
                answer = input("       同意执行吗？[y/N/q] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n已取消。")
                return 1
        if answer in ("q", "quit"):
            print("已取消。")
            return 1
        if answer in ("y", "yes"):
            chosen.append(a["id"])

    if not chosen:
        print("没有选中任何操作。")
        return 0

    print("\n" + "-" * 64)
    if dry:
        results = fixes.run(chosen, dry=True)
    else:
        print("正在执行 %d 项操作…" % len(chosen))
        results = fixes.run(chosen)

    ok = 0
    for r in results:
        print(("  ✅ " if r.get("ok") else "  ❌ ") + str(r.get("msg")))
        ok += 1 if r.get("ok") else 0
    print("-" * 64)
    print("完成 %d/%d。日志：%s" % (ok, len(results), fixes.LOG_PATH))
    if not dry and ok:
        print("改完建议重新双击「信息筛选官.exe」，页面点「重新扫一遍」看效果。")
        print("想反悔？运行：py 一键设置.py --undo")
    return 0


if __name__ == "__main__":
    _sys.exit(main())
