# -*- coding: utf-8 -*-
import sys as _sys
try:                                   # 中文 Windows 控制台默认 GBK，emoji 会崩
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
"""诊断：为什么没读到微信 / QQ / 钉钉 / 飞书的消息？
用法：py diagnose.py
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collector  # noqa: E402

IM_KEYWORDS = {
    "微信": ("wechat", "weixin"),
    "企业微信": ("wxwork", "wecom"),
    "QQ": ("qq", "tim"),
    "钉钉": ("dingtalk",),
    "飞书": ("feishu", "lark"),
    "Telegram": ("telegram",),
    "邮件客户端": ("outlook", "hxoutlook", "thunderbird"),
}

IM_PATHS = {
    "微信": [r"C:\Program Files\Tencent\Weixin\Weixin.exe",
             r"C:\Program Files (x86)\Tencent\Weixin\Weixin.exe",
             r"C:\Program Files\Tencent\WeChat\WeChat.exe",
             r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe"],
    "企业微信": [r"C:\Program Files (x86)\WXWork\WXWork.exe",
                 r"C:\Program Files\WXWork\WXWork.exe"],
    "QQ": [r"C:\Program Files\Tencent\QQNT\QQ.exe",
           r"C:\Program Files (x86)\Tencent\QQ\Bin\QQScLauncher.exe"],
    "钉钉": [r"C:\Program Files (x86)\DingDing\DingtalkLauncher.exe",
             r"C:\Program Files\DingDing\DingtalkLauncher.exe"],
    "飞书": [r"C:\Program Files\LarkShell\Lark.exe",
             r"C:\Program Files (x86)\LarkShell\Lark.exe",
             r"C:\Program Files\Feishu\Feishu.exe"],
}

REG_KEYS = {
    "微信": ("wechat", "weixin"),
    "企业微信": ("wxwork", "wecom"),
    "QQ": ("qq", "tim"),
    "钉钉": ("dingtalk",),
    "飞书": ("feishu", "lark"),
}

FIX_TIPS = {
    "微信": "微信 4.x 是自绘通知，读不到；用「手机连接」镜像手机微信通知，或装旧版微信 3.x",
    "企业微信": "企业微信 → 设置 → 通知 → 打开新消息通知",
    "QQ": "QQ → 设置 → 消息通知 → 打开「允许系统通知 / 桌面通知」",
    "钉钉": "钉钉 → 设置 → 消息通知 → 打开「桌面通知」",
    "飞书": "飞书 → 设置 → 通知 → 打开「桌面通知」",
}


def _notif_registry_apps():
    """Windows 通知设置里注册过的 App（HKCU，标准库 winreg）。
    注意：列表只在 App 首次弹过系统通知之后才会出现，所以"未注册"不等于"不支持"。"""
    try:
        import winreg
    except ImportError:
        return []
    path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings"
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                out.append(winreg.EnumKey(k, i))
    except OSError:
        pass
    return out


def _wechat_installed():
    for p in IM_PATHS["微信"]:
        if os.path.exists(p):
            return p
    return None


def _phone_link_ready():
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages")
    if not os.path.isdir(base):
        return False
    return any("YourPhone" in n for n in os.listdir(base))


def section(title):
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)


def print_im_matrix(parsed, reg_apps):
    """逐个 IM 报告：装了没 / 是否注册系统通知 / 最近读到几条。"""
    print("（「已注册」= Windows 通知设置里有它；列表只在 App 首次弹通知后才出现）\n")
    print("  %-8s %-9s %-11s %s" % ("App", "是否安装", "系统通知", "最近读到"))
    print("  " + "-" * 56)
    for app, paths in IM_PATHS.items():
        installed = any(os.path.exists(p) for p in paths)
        regs = [a for a in reg_apps if any(k in a.lower() for k in REG_KEYS[app])]
        cnt = sum(1 for p in parsed if collector._app_name(p["app"])[0] == app)
        print("  %-8s %-9s %-11s %s" % (
            app,
            "✅ 已装" if installed else "— 未装",
            "✅ 已注册" if regs else "❌ 未注册",
            ("✅ %d 条" % cnt) if cnt else "0 条",
        ))
        if cnt == 0 and (installed or regs):
            print("         ↳ %s" % FIX_TIPS[app])
            if regs:
                print("         ↳ AppId: %s" % regs[0][:52])
    print()
    print("  怎么读这张表：")
    print("   · 已装 + 已注册 + 读到 > 0  → 这条链路已经通了")
    print("   · 已装 + 未注册            → 该版本自绘通知（微信 4.x），或还没弹过系统通知")
    print("   · 未装                     → 跳过，不影响其它来源")


def main():
    section("1. 通知库")
    print("路径:", collector.DB_PATH)
    if not collector.available():
        print("❌ 找不到通知库。")
        print("   这台机器上没有 Windows 通知历史（不是 Windows？或通知总开关被关了？）")
        print("   检查：设置 → 系统 → 通知 → 打开「通知」总开关")
        return 1
    size = os.path.getsize(collector.DB_PATH)
    mtime = datetime.fromtimestamp(os.path.getmtime(collector.DB_PATH))
    print("大小: %d KB   最后写入: %s" % (size // 1024, mtime.strftime("%Y-%m-%d %H:%M")))
    if (datetime.now() - mtime) > timedelta(hours=48):
        print("⚠️ 这个库超过 48 小时没更新过 —— 说明最近几乎没通知弹出来。")

    db, tmp = collector._copy_db()
    if not db:
        print("❌ 通知库被系统锁定，复制失败。")
        return 1

    try:
        con = sqlite3.connect(db, timeout=3)
        rows = con.execute(
            "SELECT n.ArrivalTime, h.PrimaryId, n.Payload FROM Notification n "
            "LEFT JOIN NotificationHandler h ON h.RecordId = n.HandlerId "
            "ORDER BY n.Id DESC LIMIT 500").fetchall()
        con.close()
    except sqlite3.Error as exc:
        print("❌ 读取失败:", exc)
        return 1

    section("2. 一共扫到多少条")
    parsed = []
    for arrival, app_id, payload in rows:
        dt = collector._to_dt(arrival)
        texts = collector._texts(payload)
        texts = [t for t in texts if t.strip()]
        parsed.append({"dt": dt, "app": str(app_id or ""), "text": "：".join(texts)[:80]})
    print("原始记录: %d 条" % len(parsed))
    now = datetime.now()
    for label, delta in (("最近 24 小时", timedelta(hours=24)), ("最近 7 天", timedelta(days=7))):
        n = sum(1 for p in parsed if p["dt"] and p["dt"] >= now - delta)
        print("%s: %d 条" % (label, n))
    recent = [p for p in parsed if p["dt"] and p["dt"] >= now - timedelta(days=7) and p["text"]]
    if recent:
        newest = max(p["dt"] for p in recent)
        print("最新一条通知时间: %s" % newest.strftime("%Y-%m-%d %H:%M"))

    reg_apps = _notif_registry_apps()

    section("3. 按来源统计（这些才是我们真能读到的）")
    counts = {}
    for p in parsed:
        name = collector._app_name(p["app"])[0]
        counts[name] = counts.get(name, 0) + 1
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("  %-14s %d 条" % (name, n))
    if not counts:
        print("  （一条都没有）")

    section("4. 有没有即时通讯类 App 的通知")
    found_im = {}
    for p in parsed:
        low = p["app"].lower()
        for label, keys in IM_KEYWORDS.items():
            if any(k in low for k in keys):
                found_im.setdefault(label, set()).add(p["app"])
    if not found_im:
        print("❌ 没有任何微信/QQ/钉钉/飞书类通知记录。")
        wx = _wechat_installed()
        wx_reg = [a for a in reg_apps if "weixin" in a.lower() or "wechat" in a.lower()]
        print()
        if wx:
            print("这台机器装了微信（%s），但系统通知库里没有它的记录。" % wx)
        if not wx_reg:
            print("而且 Windows 通知设置里也没有微信这一项（共 %d 个 App 注册了通知）。" % len(reg_apps))
            print()
            print("→ 结论：微信 4.x 用的是「自己绘制的弹窗」，不走 Windows 系统通知，")
            print("   所以它不会写进 wpndatabase.db，任何读系统通知的程序都拿不到。")
            print("   这不是本程序的 bug，是微信的实现方式决定的；旧的 3.x 走系统通知，可以读到。")
        print()
        print("可行的替代路径（按推荐顺序）：")
        print("  ① 手机通知镜像：设置 → 蓝牙和其他设备 → 手机连接 → 连安卓手机 → 允许「访问手机通知」")
        if _phone_link_ready():
            print("     本机检测到 Phone Link 已安装 ✅ —— 只差配对手机和授权通知。")
        else:
            print("     本机未检测到 Phone Link。")
        print("  ② 手动兜底：页面左下角「手动补一条 / 自己粘一批」。")
        print("  ③ 不推荐：破解微信数据库 —— 违反用户协议，作品可能被判违规。")
    else:
        for label, ids in found_im.items():
            print("✅ 发现 %s 的通知：%d 条，AppId 示例：%s"
                  % (label, sum(1 for p in parsed if p["app"] in ids), list(ids)[0][:50]))

    section("5. 各 IM App 适配状态（QQ / 钉钉 / 飞书 / 企业微信）")
    print_im_matrix(parsed, reg_apps)

    section("6. 如果某条链路是 0 条，按顺序检查")
    print("""
1) 用的是电脑版吗？
   只有 Windows 桌面客户端的通知才会进这里。手机 App 的通知要靠「手机连接」镜像。

2) 聊天是不是设了「消息免打扰」？
   免打扰 = 不弹通知 = 不进通知中心 = 读不到。这是最常见的原因。
   验证：让同学在普通群里 @ 你一次（确保没免打扰）。

3) App 自己的通知开关
   微信：设置 → 通知 → 接收新消息通知；检查是否开了「不显示消息详情」
         （那样我们只能读到"你收到一条新消息"，程序会标成「隐私模式」并放进"值得看"）
   QQ / 钉钉 / 飞书：设置 → 消息通知 → 允许系统通知 / 桌面通知

4) Windows 的通知权限
   设置 → 系统 → 通知 → 找到对应 App → 允许通知 + 允许横幅 + 在通知中心显示

5) 历史库有延迟
   通知弹出后才会写库；程序每 60 秒扫一次，点页面「重新扫一遍」可立即重读。
""")

    section("7. 快速验证方法")
    print("""让同学给你发一条普通私聊（或群里 @ 你一次），然后点页面上的「重新扫一遍」。
看左栏有没有多一条、来源标签颜色对不对（微信绿 / QQ 蓝 / 钉钉深蓝 / 飞书靛蓝 / 手机镜像紫）。
还是没有 → 问题在 1~4，不在工具本身。""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
