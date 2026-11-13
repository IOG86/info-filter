# -*- coding: utf-8 -*-
import sys as _sys
try:                                   # 中文 Windows 控制台默认 GBK，emoji 会崩
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
"""采集层适配测试：用构造的 Toast XML 验证 微信/QQ/钉钉/飞书/企业微信/手机镜像 的识别。
不需要真的装这些 App，也不需要真的收到消息。
用法：py test_collector.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collector as C  # noqa: E402


def toast(*texts):
    body = "".join("<text>%s</text>" % t for t in texts)
    return ("<toast><visual><binding template=\"ToastGeneric\">%s</binding></visual></toast>"
            % body)


CASES = [
    # (说明, AppId, payload, 期望来源, 期望 hidden, 期望文本包含)
    ("微信 3.x 私聊", "WeChat", toast("张三", "明天下午3点前把实验报告交给学委，逾期0分"),
     "微信", False, "实验报告"),
    ("微信 3.x 带归属文本", "WeChat", toast("张三", "明天交报告", "微信"),
     "微信", False, "张三：明天交报告"),
    ("微信 小程序/服务号", "WeChatAppEx", toast("教务通知", "选课系统今晚关闭"),
     "微信", False, "选课系统"),
    ("QQ（桌面版）", "QQ", toast("班群-李四", "@你 材料明天交给学委"),
     "QQ", False, "材料"),
    ("QQNT", "QQNT_xxxx!App", toast("李四", "@你 交表"),
     "QQ", False, "交表"),
    ("TIM", "TIM", toast("老师", "论文格式要改"),
     "TIM", False, "论文"),
    ("钉钉", "DingTalk", toast("辅导员", "今晚8点班会，务必参加", "钉钉"),
     "钉钉", False, "班会"),
    ("飞书", "Feishu", toast("课程群", "作业提交截止 11月20日"),
     "飞书", False, "11月20日"),
    ("飞书 Lark 版", "Lark", toast("社团", "周五例会"),
     "飞书", False, "例会"),
    ("企业微信", "WXWork", toast("部门群", "周报今天交"),
     "企业微信", False, "周报"),
    ("邮件", "Microsoft.OutlookForWindows", toast("教务处", "关于期末考试安排的通知"),
     "邮箱", False, "期末考试"),
    ("Teams", "MSTeams_8wekyb3d8bbwe!MSTeams", toast("王老师", "会议 10 分钟后开始", "Teams"),
     "Teams", False, "会议"),
    # 手机连接镜像：来源应细化成 手机镜像·微信 / 手机镜像·QQ
    ("Phone Link 镜像微信", "Microsoft.YourPhone_8wekyb3d8bbwe!App",
     toast("张三", "明天交报告", "微信"), "手机镜像·微信", False, "明天交报告"),
    ("Phone Link 镜像 QQ", "Microsoft.YourPhone_8wekyb3d8bbwe!App",
     toast("李四", "@你 交表", "QQ"), "手机镜像·QQ", False, "交表"),
    ("Phone Link 镜像未知 App", "Microsoft.YourPhone_8wekyb3d8bbwe!App",
     toast("系统", "流量使用提醒"), "手机镜像", False, "流量"),
    # 隐私模式：只有"你收到一条新消息"
    ("微信 隐私模式", "WeChat", toast("张三", "你收到一条新消息", "微信"),
     "微信", True, "新消息"),
    ("微信 群消息聚合（12条）", "WeChat", toast("班群", "12条新消息", "微信"),
     "微信", True, "12条"),
    ("QQ 隐私模式", "QQ", toast("李四", "[新消息]", "QQ"),
     "QQ", True, "新消息"),
    # 无信息量的通知应被丢弃
    ("纯数字无效通知", "WeChat", toast("1"), None, False, None),
    ("空通知", "WeChat", "<toast></toast>", None, False, None),
]


def main():
    passed = failed = 0
    for desc, app_id, payload, exp_source, exp_hidden, exp_contains in CASES:
        got = C.parse_payload(payload, app_id)
        errs = []
        if exp_source is None:
            if got is not None:
                errs.append("应被丢弃，却返回了 %r" % (got.get("source"),))
        else:
            if got is None:
                errs.append("被误丢弃")
            else:
                if got["source"] != exp_source:
                    errs.append("来源=%s，期望=%s" % (got["source"], exp_source))
                if bool(got["hidden"]) != exp_hidden:
                    errs.append("hidden=%s，期望=%s" % (got["hidden"], exp_hidden))
                if exp_contains and exp_contains not in got["text"]:
                    errs.append("正文缺 %r：%r" % (exp_contains, got["text"][:40]))
        if errs:
            failed += 1
            print("❌ %-22s %s" % (desc, "；".join(errs)))
        else:
            passed += 1
            detail = "" if got is None else " → %s | %s" % (got["source"], got["text"][:26])
            print("✅ %-22s%s" % (desc, detail))

    print("\n结果：%d 通过 / %d 失败" % (passed, failed))

    # 真实机器上再跑一次集成检查（没有通知库也不算失败）
    if C.available():
        r = C.collect(hours=24)
        print("\n本机实测：%s 条，来源分布 %s，消息详情被隐藏 %d 条"
              % (r.get("count", 0), r.get("im_found") or "无即时通讯类", r.get("hidden_count", 0)))
    else:
        print("\n本机没有通知库，跳过集成检查。")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
