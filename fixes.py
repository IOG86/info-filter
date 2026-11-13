# -*- coding: utf-8 -*-
"""一键设置 / 修复：把"用户需要手动做的事"变成可勾选、可撤销的自动操作。

原则：
  · 每个操作都要用户明确同意才执行（前端是勾选 + 「同意并执行」）
  · 执行前先把原值备份到 setup_backup.json，随时可以一键撤销
  · 只碰 Windows 通知相关的注册表项 + 快捷方式，绝不碰微信/QQ 的数据
  · 默认 dry_run 可预览，不做任何修改
"""
import json
import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_PATH = os.path.join(BASE_DIR, "setup_backup.json")
LOG_PATH = os.path.join(BASE_DIR, "setup_log.txt")

PUSH_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\PushNotifications"
NOTIF_SETTINGS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings"

_winreg = None
try:
    import winreg as _winreg
except ImportError:
    pass


# ---------------------------------------------------------------- 工具
def _log(line):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), line))
    except OSError:
        pass


def _reg_get(root, path, name):
    if _winreg is None:
        return None
    try:
        with _winreg.OpenKey(root, path) as key:
            return _winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _reg_set(root, path, name, value):
    with _winreg.CreateKeyEx(root, path, 0, _winreg.KEY_SET_VALUE) as key:
        _winreg.SetValueEx(key, name, 0, _winreg.REG_DWORD, int(value))


def _reg_delete(root, path, name):
    if _winreg is None:
        return
    try:
        with _winreg.OpenKey(root, path, 0, _winreg.KEY_SET_VALUE) as key:
            _winreg.DeleteValue(key, name)
    except OSError:
        pass


def _load_backup():
    try:
        with open(BACKUP_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"created": datetime.now().isoformat(timespec="seconds"), "items": {}}


def _save_backup(data):
    try:
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _remember(key, path, name, value):
    """记录修改前的原值（只记第一次），用于撤销。"""
    data = _load_backup()
    if key not in data["items"]:
        data["items"][key] = {"path": path, "name": name,
                              "old": None if value is None else int(value),
                              "existed": value is not None}
        _save_backup(data)


# ---------------------------------------------------------------- 快捷方式工具
def _desktop_dir():
    return os.path.join(os.path.expanduser("~"), "Desktop")


def _startup_dir():
    return os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Microsoft",
                        "Windows", "Start Menu", "Programs", "Startup")


def _target_exe():
    """要开机启动/建快捷方式的目标：优先打包后的 exe。"""
    if getattr(sys, "frozen", False):
        return sys.executable
    for name in ("信息筛选官.exe",):
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            return p
    return os.path.join(BASE_DIR, "信息筛选官.exe")


def _make_shortcut(where, name="信息筛选官.lnk"):
    target = _target_exe()
    lnk = os.path.join(where, name)
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath='%s';"
        "$s.WorkingDirectory='%s';"
        "$s.IconLocation='%s';"
        "$s.Description='把消息变成今天要做的事';"
        "$s.Save()" % (lnk, target, BASE_DIR, target)
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   capture_output=True, timeout=30)
    return os.path.exists(lnk), lnk


# ---------------------------------------------------------------- 操作清单
ACTIONS = [
    {"id": "toast_master", "title": "打开 Windows 通知总开关",
     "desc": "系统把通知整个关掉时，任何 App 都不会留记录。会写一项注册表（可撤销）。"},
    {"id": "app_notify", "title": "把被关掉的 App 通知重新打开",
     "desc": "扫描通知设置里 Enabled=0 的 App，改成开启（逐个备份原值，可撤销）。"},
    {"id": "open_notif_settings", "title": "打开 Windows 通知设置页",
     "desc": "让你亲手检查每个 App 的「允许通知 / 横幅 / 在通知中心显示」。"},
    {"id": "open_phone_link", "title": "打开「手机连接」配对页",
     "desc": "连安卓手机并允许「访问手机通知」，微信 4.x 的消息就能镜像成系统通知。"},
    {"id": "desktop_shortcut", "title": "在桌面创建「信息筛选官」快捷方式",
     "desc": "以后双击桌面图标就能用。"},
    {"id": "autostart", "title": "开机自动启动",
     "desc": "把快捷方式放进启动文件夹，开机后自动在后台筛消息。"},
]


def preview(dry_only_check=True):
    """返回每个操作当前状态：needed / done / optional，供界面展示。"""
    out = []
    if _winreg is None:
        return [dict(a, status="unsupported", detail="非 Windows 或没有权限模块") for a in ACTIONS]

    toast = _reg_get(_winreg.HKEY_CURRENT_USER, PUSH_KEY, "ToastEnabled")
    disabled = _disabled_apps()

    for action in ACTIONS:
        row = dict(action)
        aid = action["id"]
        if aid == "toast_master":
            if toast is None:
                row.update(status="optional", detail="当前是默认开启（没有显式设置）")
            elif int(toast) == 0:
                row.update(status="needed", detail="检测到总开关被关闭")
            else:
                row.update(status="done", detail="已开启")
        elif aid == "app_notify":
            if disabled:
                row.update(status="needed",
                           detail="发现 %d 个被关闭的 App：%s" % (len(disabled), "、".join(disabled[:3])))
            else:
                row.update(status="optional", detail="没有发现被关闭的通知")
        elif aid == "open_notif_settings":
            row.update(status="optional", detail="打开设置页由你手动确认")
        elif aid == "open_phone_link":
            row.update(status="optional", detail="需要安卓手机 + 手机连接 App")
        elif aid == "desktop_shortcut":
            lnk = os.path.join(_desktop_dir(), "信息筛选官.lnk")
            row.update(status="done" if os.path.exists(lnk) else "optional", detail=lnk)
        elif aid == "autostart":
            lnk = os.path.join(_startup_dir(), "信息筛选官.lnk")
            row.update(status="done" if os.path.exists(lnk) else "optional", detail=lnk)
        out.append(row)
    return out


def run(action_ids, dry=False):
    """执行被同意的操作。dry=True 只返回"会做什么"，不修改。"""
    results = []
    if _winreg is None and any(a in ("toast_master", "app_notify") for a in action_ids):
        return [{"id": a, "ok": False, "msg": "当前环境不支持注册表操作"} for a in action_ids]

    for aid in action_ids:
        try:
            if aid == "toast_master":
                cur = _reg_get(_winreg.HKEY_CURRENT_USER, PUSH_KEY, "ToastEnabled")
                if dry:
                    results.append({"id": aid, "ok": True, "msg": "将把 ToastEnabled 设为 1（原值 %s）" % cur})
                    continue
                _remember("toast_master", PUSH_KEY, "ToastEnabled", cur)
                _reg_set(_winreg.HKEY_CURRENT_USER, PUSH_KEY, "ToastEnabled", 1)
                _log("toast_master -> 1 (原值 %s)" % cur)
                results.append({"id": aid, "ok": True, "msg": "通知总开关已打开"})

            elif aid == "app_notify":
                fixed = []
                for row in preview():
                    if row["id"] != "app_notify":
                        continue
                # 重新扫一遍被关闭的 App
                disabled = _disabled_apps()
                if dry:
                    results.append({"id": aid, "ok": True,
                                    "msg": "将开启 %d 个 App 的通知：%s" % (len(disabled), "、".join(disabled[:5]))})
                    continue
                for aumid in disabled:
                    path = NOTIF_SETTINGS_KEY + "\\" + aumid
                    old = _reg_get(_winreg.HKEY_CURRENT_USER, path, "Enabled")
                    _remember("app:" + aumid, path, "Enabled", old)
                    _reg_set(_winreg.HKEY_CURRENT_USER, path, "Enabled", 1)
                    _reg_set(_winreg.HKEY_CURRENT_USER, path, "ShowInActionCenter", 1)
                    fixed.append(aumid)
                _log("app_notify 已开启: %s" % ", ".join(fixed))
                results.append({"id": aid, "ok": True,
                                "msg": "已开启 %d 个 App 的通知：%s" % (len(fixed), "、".join(fixed[:5])) if fixed
                                else "没有需要开启的 App"})

            elif aid == "open_notif_settings":
                if dry:
                    results.append({"id": aid, "ok": True, "msg": "将打开 ms-settings:notifications"})
                    continue
                os.startfile("ms-settings:notifications")
                results.append({"id": aid, "ok": True, "msg": "已打开系统通知设置页"})

            elif aid == "open_phone_link":
                if dry:
                    results.append({"id": aid, "ok": True, "msg": "将打开「手机连接」设置页"})
                    continue
                opened = False
                for uri in ("ms-settings:mobile-devices", "ms-settings:phone",
                            "shell:AppsFolder\\Microsoft.YourPhone_8wekyb3d8bbwe!App"):
                    try:
                        os.startfile(uri)
                        opened = True
                        break
                    except OSError:
                        continue
                results.append({"id": aid, "ok": opened,
                                "msg": "已打开手机连接" if opened else "打不开，请在设置里手动找「手机连接」"})

            elif aid == "desktop_shortcut":
                if dry:
                    results.append({"id": aid, "ok": True, "msg": "将在桌面创建 信息筛选官.lnk"})
                    continue
                ok, path = _make_shortcut(_desktop_dir())
                _log("desktop_shortcut %s -> %s" % (ok, path))
                results.append({"id": aid, "ok": ok, "msg": "桌面快捷方式已创建" if ok else "创建失败"})

            elif aid == "autostart":
                if dry:
                    results.append({"id": aid, "ok": True, "msg": "将把快捷方式放进启动文件夹"})
                    continue
                ok, path = _make_shortcut(_startup_dir())
                _log("autostart %s -> %s" % (ok, path))
                results.append({"id": aid, "ok": ok, "msg": "已设为开机启动" if ok else "设置失败"})

            else:
                results.append({"id": aid, "ok": False, "msg": "未知操作"})
        except Exception as exc:                       # 单个失败不影响其它
            results.append({"id": aid, "ok": False, "msg": "执行失败：%s" % exc})
            _log("action %s failed: %s" % (aid, exc))
    return results


def _disabled_apps():
    out = []
    if _winreg is None:
        return out
    try:
        with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, NOTIF_SETTINGS_KEY) as key:
            for i in range(_winreg.QueryInfoKey(key)[0]):
                aumid = _winreg.EnumKey(key, i)
                try:
                    with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                                         NOTIF_SETTINGS_KEY + "\\" + aumid) as sub:
                        if int(_winreg.QueryValueEx(sub, "Enabled")[0]) == 0 and "SystemToast" not in aumid:
                            out.append(aumid)
                except OSError:
                    continue
    except OSError:
        pass
    return out


def undo():
    """把备份过的注册表项恢复原样。"""
    if _winreg is None:
        return {"ok": False, "msg": "当前环境不支持"}
    data = _load_backup()
    restored = []
    for key, item in list(data.get("items", {}).items()):
        try:
            if item.get("existed") and item.get("old") is not None:
                _reg_set(_winreg.HKEY_CURRENT_USER, item["path"], item["name"], item["old"])
            else:
                _reg_delete(_winreg.HKEY_CURRENT_USER, item["path"], item["name"])
            restored.append(item["path"].split("\\")[-1] + "\\" + item["name"])
        except Exception as exc:
            _log("undo %s failed: %s" % (key, exc))
    data["items"] = {}
    _save_backup(data)
    _log("undo 恢复 %d 项" % len(restored))
    return {"ok": True, "restored": restored, "count": len(restored)}


if __name__ == "__main__":
    import pprint
    if "--undo" in sys.argv:
        pprint.pprint(undo())
    elif "--run" in sys.argv:
        pprint.pprint(run([a["id"] for a in ACTIONS], dry="--dry" in sys.argv))
    else:
        pprint.pprint(preview())
