# -*- coding: utf-8 -*-
"""
自动采集层：把 Windows 通知中心里的通知读出来，变成待分析的消息。

只读系统本地的通知历史数据库（%LOCALAPPDATA%\\Microsoft\\Windows\\Notifications\\wpndatabase.db），
不连接任何 App 的协议、不读聊天记录、不需要 root、不模拟点击。

**谁发的消息，由 adapters/ 目录里的适配器决定**：
  adapters/wechat.py / wecom.py / qq.py / dingtalk.py / feishu.py
  adapters/phonelink.py / mail.py / misc.py
新增一个 App 支持 = 加一个适配器文件 + 在 adapters/registry.py 里登记一行。
"""
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta

try:
    from adapters import registry as ADAPTERS
except Exception:                              # 适配器包缺失时退化成通用识别
    ADAPTERS = None

NOTIF_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Notifications")
DB_NAME = "wpndatabase.db"
DB_PATH = os.path.join(NOTIF_DIR, DB_NAME)

# 「消息详情被隐藏」的典型文案：隐私模式下只能看到这句，没有真实内容
HIDDEN_PATTERNS = [
    r"你收到(了)?(一|1)条新消息",
    r"你有一(条|个)新消息",
    r"(\d+)\s*条新消息",
    r"\[新消息\]",
    r"收到一条新消息",
    r"点击查看(详情|消息)?$",
]

# 兜底用的通用规则（适配器都没命中时）
FALLBACK_NAMES = [
    (r"codex", "Codex"),
    (r"defender", "系统安全"),
    (r"widgets", "资讯"),
]


def available():
    """通知库在这台机器上是否可用。"""
    return os.path.exists(DB_PATH)


def _copy_db():
    """Windows 会锁着这个库，先复制到临时目录再读。"""
    tmp = tempfile.mkdtemp(prefix="notif_")
    ok = False
    for name in (DB_NAME, DB_NAME + "-wal", DB_NAME + "-shm"):
        src = os.path.join(NOTIF_DIR, name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(tmp, name)
        for _ in range(3):                      # 偶发占用，重试几次
            try:
                shutil.copy2(src, dst)
                if name == DB_NAME:
                    ok = True
                break
            except OSError:
                pass
    return (os.path.join(tmp, DB_NAME) if ok else None), tmp


def _to_dt(value):
    """Windows 通知库的 ArrivalTime 可能是 FILETIME、毫秒或秒。"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    try:
        if v > 10 ** 16:                       # FILETIME（1601 年起，100ns）
            return datetime(1601, 1, 1) + timedelta(microseconds=v // 10)
        if v > 10 ** 11:                       # 毫秒时间戳
            return datetime.fromtimestamp(v / 1000.0)
        if v > 10 ** 8:                        # 秒级时间戳
            return datetime.fromtimestamp(v)
    except (OverflowError, OSError, ValueError):
        return None
    return None


def _fallback_name(primary_id):
    pid = str(primary_id or "")
    low = pid.lower()
    for pattern, name in FALLBACK_NAMES:
        if re.search(pattern, low):
            return name, False
    if not pid:
        return "系统", False
    if pid.startswith("{"):                      # 未注册的 AUMID（常见于绿色版软件）
        return "其他应用", False
    if ".exe" in low:
        base = pid.split(".exe")[0].split(".")[-1]
        return (base or "其他应用")[:16], False
    guess = re.split(r"[_!\.]", pid)[0]
    return (guess or "系统")[:16], False


def _app_name(primary_id):
    """AppId → (来源名, 是否即时通讯)。找不到适配器就走兜底规则。"""
    if ADAPTERS is not None:
        adapter = ADAPTERS.resolve(primary_id)
        if adapter is not None:
            return adapter.name, adapter.kind == "im"
    return _fallback_name(primary_id)


def _texts(payload):
    """从通知 XML 里按顺序抠出文本节点。"""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", "ignore")
    if not payload:
        return []
    out = []
    for raw in re.findall(r"<text[^>]*>(.*?)</text>", payload, re.S):
        txt = re.sub(r"<[^>]+>", "", raw)
        txt = (txt.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                  .replace("&quot;", '"').replace("&#39;", "'"))
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            out.append(txt)
    return out


def _strip_attribution(texts):
    """去掉 toast 末尾的「App 名字」归属文本（如微信、QQ、飞书）。"""
    if ADAPTERS is not None:
        names = ADAPTERS.attribution_names()
    else:
        names = {"微信", "wechat", "qq", "钉钉", "dingtalk", "飞书", "feishu", "lark"}
    while texts and texts[-1].strip().lower() in names:
        texts = texts[:-1]
    return texts


def is_hidden(texts):
    """隐私模式：通知里只有"你收到一条新消息"，没有真实内容。"""
    body = " ".join(texts[1:]) if len(texts) > 1 else " ".join(texts)
    for pattern in HIDDEN_PATTERNS:
        if re.search(pattern, body):
            return True
    return False


def parse_payload(payload, app_id=""):
    """
    解析一条通知。返回 dict 或 None（无文本的通知直接丢掉）。
    字段：source / title / body / text / hidden / is_im
    """
    raw_texts = _texts(payload)

    adapter = ADAPTERS.resolve(app_id) if ADAPTERS is not None else None
    if adapter is not None:
        # 归属文本要先留着，手机镜像靠它反推原始 App（微信/QQ/...）
        source = adapter.source_name(app_id, raw_texts)
        is_im = adapter.kind == "im"
    else:
        source, is_im = _fallback_name(app_id)

    texts = _strip_attribution(raw_texts)

    # 只剩"App 名字"这类无信息量的通知，丢掉
    texts = [t for t in texts if not re.fullmatch(r"[\d\s\.\-:：%（）()\[\]]+", t)]
    if not texts:
        return None

    hidden = is_hidden(texts)
    title = texts[0]
    body = "：".join(texts[1:]) if len(texts) > 1 else ""
    text = "：".join(texts) if len(texts) > 1 else texts[0]
    return {
        "source": source,
        "title": title,
        "body": body,
        "text": text[:300],
        "hidden": hidden,
        "is_im": is_im,
    }


def collect(hours=24, limit=80):
    """
    返回：
      {"ok", "items":[{source,text,title,hidden,ts,dup}], "count", "note",
       "scanned_at", "im_found", "source_counts", "hidden_count"}
    """
    now = datetime.now()
    meta = {"ok": False, "items": [], "note": "", "scanned_at": now.strftime("%m-%d %H:%M"),
            "im_found": {}, "source_counts": {}, "hidden_count": 0}
    if not available():
        meta["note"] = "这台机器上没有 Windows 通知历史（可能不是 Windows，或通知被关闭）。"
        return meta

    db, tmp = _copy_db()
    if not db:
        meta["note"] = "通知库被系统锁定，暂时读不到。"
        return meta

    rows = []
    try:
        con = sqlite3.connect(db, timeout=3)
        rows = con.execute(
            "SELECT n.ArrivalTime, h.PrimaryId, n.Payload FROM Notification n "
            "LEFT JOIN NotificationHandler h ON h.RecordId = n.HandlerId "
            "ORDER BY n.Id DESC LIMIT 500"
        ).fetchall()
        con.close()
    except sqlite3.Error as exc:
        meta["note"] = "通知库读取失败：%s" % exc
        return meta
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    seen = {}
    ordered = []
    for arrival, app_id, payload in rows:
        dt = _to_dt(arrival)
        if dt is None or dt < now - timedelta(hours=max(hours, 168)):
            continue                                  # 先粗筛一周内
        parsed = parse_payload(payload, app_id)
        if not parsed:
            continue
        key = re.sub(r"\s+", "", parsed["text"])[:60]
        if key in seen:
            seen[key]["dup"] += 1
            continue
        item = dict(parsed)
        item.update({"ts": dt.strftime("%m-%d %H:%M"), "_dt": dt, "dup": 0})
        seen[key] = item
        ordered.append(item)

    recent = [it for it in ordered if it["_dt"] >= now - timedelta(hours=hours)]
    if len(recent) < 4:                    # 今天通知太少，放宽到一周，别让页面空着
        recent = [it for it in ordered if it["_dt"] >= now - timedelta(hours=168)]
        if recent:
            meta["note"] = "最近 %d 小时通知较少，已放宽到最近一周。" % hours
    if not recent:
        meta["note"] = "没扫到可用的通知内容。你可以在下方手动粘贴几条试试。"
        return meta

    recent = sorted(recent, key=lambda x: x["_dt"], reverse=True)[:limit]
    im_count, src_count, hidden_count = {}, {}, 0
    for it in recent:
        src = it["source"]
        src_count[src] = src_count.get(src, 0) + 1
        if it.get("is_im") and not src.startswith("手机镜像"):
            im_count[src] = im_count.get(src, 0) + 1
        if it.get("hidden"):
            hidden_count += 1
        it.pop("_dt", None)
        it.pop("is_im", None)
    meta.update({"ok": True, "items": recent, "count": len(recent),
                 "im_found": im_count, "source_counts": src_count,
                 "hidden_count": hidden_count})
    return meta


if __name__ == "__main__":
    import json
    import sys
    r = collect(hours=int(sys.argv[1]) if len(sys.argv) > 1 else 24)
    print(json.dumps(r, ensure_ascii=False, indent=2))
