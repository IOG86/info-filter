# -*- coding: utf-8 -*-
"""适配器注册表 + 首次运行自检（"脚本先跑一下"就是跑这里）"""
import os

from .base import Adapter
from .wechat import WeChatAdapter
from .wecom import WeComAdapter
from .qq import QQAdapter
from .dingtalk import DingTalkAdapter
from .feishu import FeishuAdapter
from .phonelink import PhoneLinkAdapter
from .mail import MailAdapter, TeamsAdapter
from .misc import MISC_ADAPTERS

# 顺序敏感：即时通讯优先，其次手机镜像，最后邮件/系统类
ADAPTERS = [
    WeChatAdapter(), WeComAdapter(), QQAdapter(), DingTalkAdapter(), FeishuAdapter(),
    TeamsAdapter(), PhoneLinkAdapter(), MailAdapter(),
] + MISC_ADAPTERS

# 需要在界面上"报告状态"的适配器（用户真正关心的）
REPORTABLE_KEYS = ("wechat", "wecom", "qq", "dingtalk", "feishu", "phonelink", "mail")

BASE_ATTRIBUTION = {"qq", "qqnt", "tim", "微信", "wechat", "weixin", "钉钉", "dingtalk",
                    "飞书", "feishu", "lark", "企业微信", "wxwork", "wecom", "teams",
                    "outlook", "邮件", "mail"}


def resolve(app_id):
    """AppId → 适配器（没有匹配就返回 None，由调用方兜底）"""
    for adapter in ADAPTERS:
        if adapter.match(app_id):
            return adapter
    return None


def attribution_names():
    names = set(BASE_ATTRIBUTION)
    for adapter in ADAPTERS:
        for a in getattr(adapter, "attribution", ()):  # noqa: B007
            names.add(a.lower())
    return names


def _notif_registry_apps():
    """Windows 通知设置里注册过的 App。
    注意：只有 App 弹过至少一次系统通知，它才会出现在这个列表里。"""
    try:
        import winreg
    except ImportError:
        return []
    path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings"
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                out.append(winreg.EnumKey(key, i))
    except OSError:
        pass
    return out


def _p(text):
    """打印兜底：控制台是 GBK 时，emoji 会崩，降级成 ASCII。"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def scan(counts=None):
    """逐个适配器自检。counts = {来源名: 最近条数}"""
    counts = counts or {}
    reg_apps = _notif_registry_apps()
    rows = []
    for adapter in ADAPTERS:
        if adapter.key not in REPORTABLE_KEYS:
            continue
        installed = adapter.installed()
        registered = any(adapter.match(x) for x in reg_apps)
        recent = int(counts.get(adapter.name, 0))
        if recent > 0:
            status, hint = "ok", "已打通，能读到消息"
        elif registered:
            status, hint = "warn", "系统通知已注册，但最近没有消息进来"
        elif installed:
            status, hint = "setup", "装了，但没有注册系统通知"
        else:
            status, hint = "absent", "这台机器上没有装"
        rows.append({
            "key": adapter.key,
            "name": adapter.name,
            "kind": adapter.kind,
            "installed": installed,
            "registered": registered,
            "recent": recent,
            "status": status,
            "hint": hint,
            "fix": adapter.fix_tip,
            "note": getattr(adapter, "note", ""),
        })
    return rows


def bootstrap(verbose=True):
    """程序启动时跑一次：给终端一个可读的自检报告。"""
    rows = scan()
    ok = [r for r in rows if r["status"] == "ok"]
    todo = [r for r in rows if r["status"] in ("warn", "setup")]
    if verbose:
        _p("适配器自检（首次运行会自动做一次）：")
        for r in rows:
            mark = {"ok": "[OK]", "warn": "[!]", "setup": "[X]", "absent": "[-]"}.get(
                r["status"], "[-]")
            _p("  %s %-8s %s" % (mark, r["name"], r["hint"]))
        if todo:
            _p("  需要处理的 %d 个：" % len(todo))
            for r in todo:
                _p("    - %s：%s" % (r["name"], r["fix"]))
    return {"rows": rows, "ok_count": len(ok), "todo_count": len(todo)}
