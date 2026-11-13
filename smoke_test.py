# -*- coding: utf-8 -*-
"""冒烟测试：确认服务与接口都活着。
用法：先 python app.py，再开一个窗口 python smoke_test.py
"""
import io
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:%s" % (sys.argv[1] if len(sys.argv) > 1 else "8000")


def post(path, payload):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ok = True
    try:
        with urllib.request.urlopen(BASE + "/api/health", timeout=10) as r:
            health = json.loads(r.read().decode("utf-8"))
        print("[1/4] 服务在线 ✅  大模型：%s" % ("已配置" if health.get("llm") else "未配置（规则模式）"))
    except Exception as exc:
        print("[1/4] 服务未启动 ❌ ", exc)
        sys.exit(1)

    items = [
        {"source": "班级群", "text": "@全体成员 明天下午3点前把实验报告电子版交给学委，逾期按0分处理"},
        {"source": "短信", "text": "【阿里云】尊敬的nic*860：2026 Qoder 高校创造力大赛正式启动！2000份参与奖，报名及作品提交截至11月30日。拒收请回复"},
        {"source": "同学", "text": "哈哈哈哈笑死我了"},
    ]
    try:
        data = post("/api/analyze", {"items": items, "mode": "rule"})
        print("[2/4] 接口可用 ✅  引擎：%s，返回 %d 条" % (data["engine"], len(data["results"])))
        for r in data["results"]:
            print("      %-4s %3d分  %s  %s" % (r["category"], r["score"], r["deadline"] or "无截止时间", r["action"]))
        if len(data["results"]) != len(items):
            ok = False
            print("      ⚠️ 返回条数与输入不一致")
    except Exception as exc:
        ok = False
        print("[2/4] 接口异常 ❌ ", exc)

    try:
        with urllib.request.urlopen(BASE + "/", timeout=10) as r:
            html = r.read().decode("utf-8", "ignore")
        assert "信息筛选官" in html, "首页内容异常"
        print("[3/4] 前端页面可访问 ✅")
    except Exception as exc:
        ok = False
        print("[3/4] 前端页面异常 ❌ ", exc)

    # 自动模式：打开页面就该有结果（读 Windows 通知中心）
    try:
        with urllib.request.urlopen(BASE + "/api/today", timeout=30) as r:
            today = json.loads(r.read().decode("utf-8"))
        if today.get("ok") and today.get("count"):
            cats = {}
            for x in today["results"]:
                cats[x["category"]] = cats.get(x["category"], 0) + 1
            print("[4/4] 自动模式 ✅  扫描于 %s，共 %d 条 %s"
                  % (today.get("scanned_at"), today["count"], cats))
        else:
            print("[4/4] 自动模式 ⚠️  没扫到通知：%s（页面会自动降级，仍可手动粘贴）"
                  % (today.get("note") or "通知中心为空"))
    except Exception as exc:
        ok = False
        print("[4/4] 自动模式接口异常 ❌ ", exc)

    print("\n" + ("全部通过，可以开始录演示视频了 🎉" if ok else "有失败项，先修好再演示"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
