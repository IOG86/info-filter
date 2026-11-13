# -*- coding: utf-8 -*-
import sys as _sys
try:                                   # 中文 Windows 控制台默认 GBK，emoji 会崩
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
"""评测脚本：用 30 条真实感样例测「分类准确率」，输出可直接贴进参赛文档的表格。
用法：python evaluate.py
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app  # noqa: E402

CATS = ["立刻做", "值得看", "可忽略"]


def main():
    path = os.path.join(app.BASE_DIR, "samples.json")
    with io.open(path, encoding="utf-8") as f:
        samples = json.load(f)

    rows, correct = [], 0
    confusion = {a: {b: 0 for b in CATS} for a in CATS}

    for s in samples:
        r = app.analyze_one({"source": s["source"], "text": s["text"], "hidden": s.get("hidden", False)}, s["id"] - 1)
        ok = r["category"] == s["expect"]
        correct += 1 if ok else 0
        confusion[s["expect"]][r["category"]] += 1
        rows.append({
            "id": s["id"], "source": s["source"], "text": s["text"],
            "expect": s["expect"], "got": r["category"], "score": r["score"],
            "ok": ok, "deadline": r["deadline"] or "", "action": r["action"],
        })

    total = len(rows)
    acc = correct * 100.0 / total

    out = []
    out.append("## 评测结果\n")
    out.append("| 指标 | 数值 |")
    out.append("|---|---|")
    out.append("| 样例数 | %d |" % total)
    out.append("| 三分类准确率 | **%.1f%%**（%d/%d） |" % (acc, correct, total))
    todo_ok = sum(1 for x in rows if x["expect"] == "立刻做" and x["ok"])
    todo_all = sum(1 for x in rows if x["expect"] == "立刻做")
    skip_ok = sum(1 for x in rows if x["expect"] == "可忽略" and x["ok"])
    skip_all = sum(1 for x in rows if x["expect"] == "可忽略")
    out.append("| 该做没漏（立刻做召回） | %d/%d |" % (todo_ok, todo_all))
    out.append("| 噪音拦截率（可忽略命中） | %d/%d |" % (skip_ok, skip_all))
    out.append("")
    out.append("## 明细\n")
    out.append("| # | 来源 | 内容摘要 | 期望 | 实际 | 分数 | 截止 | 结论 |")
    out.append("|---|---|---|---|---|---|---|---|")
    for x in rows:
        brief = x["text"].replace("|", "｜")
        brief = brief[:22] + ("…" if len(brief) > 22 else "")
        out.append("| %d | %s | %s | %s | %s | %d | %s | %s |" % (
            x["id"], x["source"], brief, x["expect"], x["got"], x["score"],
            x["deadline"], "✅" if x["ok"] else "❌"))
    out.append("")
    out.append("## 混淆矩阵\n")
    out.append("| 期望 \\ 实际 | 立刻做 | 值得看 | 可忽略 |")
    out.append("|---|---|---|---|")
    for a in CATS:
        out.append("| %s | %d | %d | %d |" % (a, confusion[a]["立刻做"], confusion[a]["值得看"], confusion[a]["可忽略"]))

    text = "\n".join(out)
    print(text)
    with io.open(os.path.join(app.BASE_DIR, "评测结果.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("\n已写入 评测结果.md", file=sys.stderr)


if __name__ == "__main__":
    main()
