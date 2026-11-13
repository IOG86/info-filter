# -*- coding: utf-8 -*-
"""
信息筛选官 · 零依赖本地原型
--------------------------------
用法：
    python app.py
浏览器打开 http://127.0.0.1:8000

两种分析模式：
  1) 规则模式（默认）：纯本地关键词 + 时间解析，不联网、不需要 Key
  2) 大模型模式（可选）：设置 DASHSCOPE_API_KEY 后启用（阿里云百炼 / 通义千问）
        PowerShell:  $env:DASHSCOPE_API_KEY="sk-xxxx"; python app.py
     失败会自动回退规则模式，演示永不挂。

只依赖 Python 标准库，不需要 pip install。
"""
import json
import os
import re
import sys
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import collector
except Exception:                      # 采集层坏了也不影响手动模式
    collector = None

try:
    from adapters import registry as ADAPTERS
except Exception:                      # 适配器包缺失时退化成通用识别
    ADAPTERS = None

try:
    import fixes                       # 一键设置/修复（可撤销）
except Exception:
    fixes = None

# 打包成 exe（--noconsole）后 stdout 是 None，print 会炸，先兜住
# 控制台编码兜底：中文 Windows 默认 GBK，打印 emoji 会直接抛 UnicodeEncodeError
try:
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

for _name in ("stdout", "stderr"):
    if getattr(sys, _name) is None:
        try:
            setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))
        except Exception:
            pass

# 冻结成 exe 后，资源被解包到 sys._MEIPASS
if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PORT = int(os.getenv("PORT", "8000"))

# 首次运行引导的状态文件（放在用户目录，卸载程序也不会留在桌面）
STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or BASE_DIR, "InfoFilter")
STATE_PATH = os.path.join(STATE_DIR, "onboarding.json")
AUTO_WINDOW_HOURS = int(os.getenv("AUTO_WINDOW_HOURS", "24"))
AUTO_TTL_SEC = 60                       # 自动模式的缓存时间
IS_FROZEN = getattr(sys, "frozen", False)

TODO, WATCH, SKIP = "立刻做", "值得看", "可忽略"

# ---------------------------------------------------------------- 词表
ACTION_VERBS = [
    "报名", "报名参加", "提交", "上交", "交给", "交表", "填写", "填表", "缴费", "缴纳",
    "回复", "签到", "打卡", "参加", "领取", "上传", "预约", "确认", "选课", "退改选",
    "复习", "面试", "考试", "开会", "班会", "答辩", "体测", "体检", "集合", "修改",
    "续费", "申报", "报到", "准备", "打印", "签字", "确认参加", "交报告", "交作业", "交材料", "交稿",
]

IMPORTANT_WORDS = [
    "学分", "绩点", "成绩", "考试", "补考", "挂科", "奖学金", "评优", "保研", "实习",
    "面试", "答辩", "毕业", "论文", "选课", "退课", "缴费", "体测", "体检", "报考",
    "报名", "签字", "盖章", "档案", "处分", "志愿", "比赛", "竞赛", "应聘", "录用",
    "四六级", "证书", "助学金", "勤工俭学", "退宿", "宿舍", "招聘", "宣讲", "申报",
    "材料", "证明", "实习", "课题", "项目", "作业", "报告", "实验",
]

PERSONAL_WORDS = ["@你", "@我", "你", "您", "本人", "学号", "姓名", "请回复", "收到请回复", "回我", "私聊"]

INFO_WORDS = ["通知", "提醒", "公布", "公告", "发布", "开放时间", "安排", "请注意", "临时", "调整为"]

NOISE_WORDS = [
    "哈哈哈", "接龙", "收到", "+1", "恭喜", "表情", "[图片]", "赞", "笑死", "好耶",
    "打卡成功", "晚安", "早安", "吃了吗", "拼单", "拼车", "投票", "助力", "砍一刀",
]

MARKETING_WORDS = [
    "促销", "优惠", "限时", "中奖", "抽奖", "免费", "红包", "返现", "贷款", "兼职",
    "高薪", "点击链接", "扫码进群", "速看", "领取", "现金激励", "内推机会", "参与奖",
    "大赛正式", "拒收", "日结",
]

RISK_WORDS = [
    "转账", "汇款", "验证码", "退款", "安全账户", "刷单", "冻结", "解冻", "法院",
    "传票", "垫付", "保证金", "私下交易", "兼职刷", "高额回报", "银行卡",
]

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7, "七": 7}

# 动词 → 人话任务描述（让「建议」看起来像人写的）
VERB_TASK = {
    "交给": "把材料交上去", "上交": "上交材料", "交表": "交表格", "提交": "提交材料",
    "填写": "填写表格", "填表": "填写表格", "上传": "上传文件", "回复": "回复对方",
    "签到": "到场签到", "打卡": "完成打卡", "参加": "按时参加", "报名": "完成报名",
    "报名参加": "完成报名", "缴费": "完成缴费", "缴纳": "完成缴费", "预约": "完成预约",
    "确认": "确认信息", "确认参加": "回复确认参加", "选课": "完成选课", "退改选": "完成退改选",
    "面试": "参加面试", "考试": "参加考试", "开会": "参会", "班会": "参加班会",
    "答辩": "参加答辩", "体测": "参加体测", "体检": "去做体检", "集合": "按时集合",
    "修改": "按意见修改", "续费": "完成续费", "申报": "提交申报材料", "报到": "按时报到",
    "准备": "提前准备", "打印": "打印材料", "领取": "领取物品", "签字": "签字确认",
    "交报告": "把报告交上去", "交作业": "把作业交上去", "交材料": "把材料交上去", "交稿": "交稿",
    "复习": "安排复习",
}


# ---------------------------------------------------------------- 截止时间解析
def _find_day(s, base):
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", s)
    if m:
        try:
            d = date(base.year, int(m.group(1)), int(m.group(2)))
            if (base - d).days > 60:          # 明显是明年的日期
                d = date(base.year + 1, d.month, d.day)
            return d, m.group(0)
        except ValueError:
            pass
    m = re.search(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)", s)
    if m:
        try:
            return date(base.year, int(m.group(1)), int(m.group(2))), m.group(0)
        except ValueError:
            pass
    m = re.search(r"(\d{1,3})\s*天\s*(?:后|以后|之后)", s)
    if m:
        return base + timedelta(days=int(m.group(1))), m.group(0)
    for pat, off in [("大后天", 3), ("后天", 2), ("明天|明日|明早|明晚", 1), ("今天|今日|今晚", 0)]:
        hit = re.search(pat, s)
        if hit:
            return base + timedelta(days=off), hit.group(0)
    m = re.search(r"(本周|这周|下周|周|星期)\s*([一二三四五六日天])", s)
    if m:
        target = CN_NUM[m.group(2)]
        delta = (target - base.isoweekday()) % 7
        if m.group(1) == "下周":
            delta = delta + 7 if delta else 7
        return base + timedelta(days=delta), m.group(0)
    return None, None


def _find_time(s):
    m = re.search(r"(上午|下午|晚上|傍晚|中午|早上|早|晚)?\s*(\d{1,2})\s*[:：点时]\s*(\d{1,2})?\s*分?", s)
    if not m:
        return None, None, None
    h = int(m.group(2))
    mi = int(m.group(3)) if m.group(3) else 0
    pre = m.group(1) or ""
    if pre in ("下午", "晚上", "傍晚", "晚") and h < 12:
        h += 12
    if h > 23 or mi > 59:
        return None, None, None
    return h, mi, m.group(0).strip()


def parse_deadline(text):
    """能解析出「哪一天」就当有截止时间；已过去一天以上的日期视为陈旧信息，忽略。"""
    base = datetime.now()
    m = re.search(r"(\d{1,3})\s*个?\s*小时\s*(?:后|以后|之后|之内|内)", text)
    if m:
        dt = base + timedelta(hours=int(m.group(1)))
        return {"text": "%d月%d日 %02d:%02d" % (dt.month, dt.day, dt.hour, dt.minute),
                "dt": dt, "hours": float(m.group(1)), "hit": m.group(0)}

    day, day_txt = _find_day(text, base.date())
    if day is None:
        return None
    h, mi, time_txt = _find_time(text)
    if h is None:
        h, mi = 23, 59
        time_txt = ""
    dt = datetime(day.year, day.month, day.day, h, mi)
    hours = (dt - base).total_seconds() / 3600.0
    if hours < -24:                      # 陈年日期，忽略
        return None
    label = "%d月%d日 %02d:%02d（周%s）" % (dt.month, dt.day, dt.hour, dt.minute,
                                          "一二三四五六日"[dt.isoweekday() - 1])
    return {"text": label, "dt": dt, "hours": hours, "hit": (day_txt or "") + time_txt}


# ---------------------------------------------------------------- 打分
def _urgency(hours):
    if hours is None:
        return 22
    if hours < 0:
        return 58            # 刚过期，仍值得补救
    if hours <= 6:
        return 100
    if hours <= 24:
        return 92
    if hours <= 48:
        return 80
    if hours <= 72:
        return 70
    if hours <= 168:
        return 56
    if hours <= 336:
        return 44
    return 32


def _importance(text):
    score, words = 30, []
    if any(w in text for w in IMPORTANT_WORDS):
        score += 24
        words.append("涉及学业/切身事务")
    if any(w in text for w in PERSONAL_WORDS):
        score += 12
        words.append("点名/需回应")
    if re.search(r"务必|必须|一定要|全体|所有|严禁|请于|请各", text):
        score += 10
        words.append("强要求")
    if any(w in text for w in INFO_WORDS):
        score += 8
        words.append("正式通知")
    return min(score, 100), words


def analyze_one(item, idx=0):
    text = (item.get("text") or "").strip()
    source = item.get("source") or "未标注来源"
    if not text:
        return None

    factors, tags = [], []
    dl = parse_deadline(text)
    hours = dl["hours"] if dl else None

    # --- 证据
    risk_hits = [w for w in RISK_WORDS if w in text]
    mass = re.search(r"拒收请回复|回T退订|退订|尊敬的", text)
    marketing = [w for w in MARKETING_WORDS if w in text]
    noise_hits = [w for w in NOISE_WORDS if w in text]
    verb = next((v for v in ACTION_VERBS if v in text), None)
    urgent = re.search(r"紧急|加急|立即|马上|尽快|务必|必须|今天|今晚|明天", text)
    cancel = re.search(r"取消|延期|改期|暂停|推迟", text)
    hard = re.search(r"逾期|不予受理|视为放弃|系统将关闭|关闭后|过期|无法补交", text)
    safety = re.search(r"停课|停电|停水|封闭|演练|注意安全|台风|暴雨", text)

    hidden = bool(item.get("hidden"))
    i, imp_words = _importance(text)
    u = _urgency(hours)
    score = 0.55 * u + 0.45 * i
    factors.extend(imp_words)

    if dl:
        factors.append("识别到截止时间 " + dl["text"])
        if hours is not None and 0 <= hours <= 24:
            factors.append("剩余不足 24 小时")
        elif hours is not None and 24 < hours <= 72:
            factors.append("剩余不足 3 天")
        elif hours is not None and hours < 0:
            factors.append("时间已过，可能还能补救")
    if hard:
        factors.append("含硬约束：“%s”" % hard.group(0))
        score += 8
    if urgent and not dl:
        factors.append("含强提醒词：“%s”" % urgent.group(0))
        score += 8

    # 隐私模式的通知正文就是"你收到一条新消息"，不能按闲聊处理
    if noise_hits and not hidden:
        score -= 26
        factors.append("含闲聊特征：“%s”" % noise_hits[0])
        tags.append("闲聊")
    if marketing:
        score -= 16
        factors.append("含营销话术：“%s”" % marketing[0])
        tags.append("营销")
    if mass:
        score -= 30
        factors.append("群发营销短信特征：“%s”" % mass.group(0))
        if "营销" not in tags:
            tags.append("营销")
    if risk_hits:
        factors.insert(0, "命中风险词：“%s”" % risk_hits[0])
        tags.append("风险")
    if hidden:
        factors.append("通知详情被隐藏（App 开了消息隐私模式）")
        tags.append("隐私模式")
    if "涉及学业/切身事务" in imp_words and "学业事务" not in tags:
        tags.append("学业事务")

    # --- 定级（规则优先，可解释）
    if risk_hits:
        cat = TODO
    elif mass or (marketing and not verb):
        cat = SKIP
    elif cancel:
        cat = WATCH
    elif noise_hits and not verb:
        cat = SKIP
    elif dl and safety and hours is not None and hours <= 72:
        cat = TODO
    elif verb and dl and hours is not None and (hours <= 200 or (hard and hours <= 240)):
        cat = TODO
    elif verb and dl:
        cat = WATCH
    elif verb and i >= 62:
        cat = WATCH
    elif dl and (i >= 45 or any(w in text for w in INFO_WORDS) or safety):
        cat = WATCH
    elif any(w in text for w in INFO_WORDS) or i >= 62:
        cat = WATCH
    else:
        cat = SKIP

    # 看不到正文的消息，宁可放进"值得看"，也不能静默丢掉
    if hidden and cat == SKIP and not risk_hits:
        cat = WATCH
        factors.append("原始内容被隐藏，宁可多看一眼")

    if cat == TODO:
        score = max(score, 68)
    elif cat == WATCH:
        score = min(max(score, 45), 64)
    else:
        score = min(score, 41)
    score = int(max(0, min(100, round(score))))

    # --- 行动建议
    if risk_hits:
        action = "疑似诈骗/诱导：不点链接、不转账，截图举报"
    elif cat == SKIP:
        action = "已折叠，无需处理" if not mass else "群发营销，可直接忽略"
    elif cat == WATCH:
        if cancel:
            action = "事情已取消/改期，知悉即可"
        elif dl:
            action = "记下 %s，不用马上做" % dl["text"]
        else:
            action = "有空看一眼即可"
    else:
        task = VERB_TASK.get(verb)
        if task and dl and hours is not None and hours >= 0:
            action = "%s 前%s" % (dl["text"], task)
        elif task:
            action = "尽快%s" % task
        elif dl:
            action = "在 %s 前确认相关安排" % dl["text"]
        else:
            action = "尽快确认相关信息"

    if hidden and cat in (TODO, WATCH):
        action = action + "（详情被隐藏，先点开原文看内容）"

    title = re.sub(r"\s+", " ", text)[:26]
    if len(text) > 26:
        title += "…"

    return {
        "id": "m%d" % (idx + 1),
        "source": source,
        "text": text,
        "title": title,
        "category": cat,
        "score": score,
        "deadline": dl["text"] if dl else None,
        "hours_left": round(hours, 1) if hours is not None else None,
        "action": action,
        "factors": factors[:4],
        "tags": [t for t in dict.fromkeys(tags)],
        "engine": "rule",
    }


# ---------------------------------------------------------------- 大模型（可选）
def llm_analyze(items):
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    base = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "qwen-plus")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["[%d] 来源：%s｜内容：%s" % (n, it.get("source", "未标注"), it.get("text", ""))
             for n, it in enumerate(items, 1)]
    prompt = (
        "现在时间：%s。你是大学生的信息筛选助手。下面是若干条来自群聊/邮件/公众号/短信的通知，"
        "请逐条判断它对一名大学生的真实价值，只输出 JSON 数组，不要任何解释或代码块标记。\n"
        "每条字段：index(序号), category(只能取 立刻做/值得看/可忽略), score(0-100 整数), "
        "deadline(有明确截止时间写成 M月D日 HH:MM，否则空字符串), action(不超过20字的行动建议), "
        "title(不超过18字的概括), reason(一句为什么这个优先级)。\n"
        "标准：需要我本人行动且有截止时间=立刻做；与我相关但不必马上做=值得看；闲聊/广告/营销=可忽略；"
        "诈骗或诱导信息=立刻做，并在 action 里提醒远离。\n\n" + "\n".join(lines)
    )
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.2}).encode("utf-8")
    req = urllib.request.Request(base, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(json)?|```$", "", content, flags=re.M).strip()
        m = re.search(r"\[[\s\S]*\]", content)
        arr = json.loads(m.group(0) if m else content)
    except Exception as exc:                 # 任何失败都回退规则模式
        print("[warn] 大模型调用失败，回退规则模式：", exc)
        return None

    by_index = {}
    for row in arr:
        try:
            by_index[int(row.get("index"))] = row
        except (TypeError, ValueError):
            continue
    out = []
    for n, item in enumerate(items, 1):
        base_r = analyze_one(item, n - 1)
        row = by_index.get(n) or {}
        cat = row.get("category")
        if cat not in (TODO, WATCH, SKIP):
            cat = base_r["category"]
        try:
            score = int(row.get("score", base_r["score"]))
        except (TypeError, ValueError):
            score = base_r["score"]
        out.append({
            "id": base_r["id"], "source": base_r["source"], "text": base_r["text"],
            "title": str(row.get("title") or base_r["title"])[:20],
            "category": cat, "score": max(0, min(100, score)),
            "deadline": str(row.get("deadline") or "") or base_r["deadline"],
            "hours_left": base_r["hours_left"],
            "action": str(row.get("action") or base_r["action"])[:40],
            "factors": base_r["factors"], "tags": base_r["tags"],
            "engine": "llm", "reason": str(row.get("reason") or "")[:60],
        })
    return out


# ---------------------------------------------------------------- 汇总简报
def build_brief(results):
    todo = sorted([r for r in results if r["category"] == TODO],
                  key=lambda r: (r["hours_left"] is None, r["hours_left"] if r["hours_left"] is not None else 0))
    watch = [r for r in results if r["category"] == WATCH]
    skip = [r for r in results if r["category"] == SKIP]
    lines = ["【今日信息简报】共收到 %d 条，需要你行动 %d 条，值得一看 %d 条，已折叠 %d 条。"
             % (len(results), len(todo), len(watch), len(skip))]
    if todo:
        lines += ["", "按时间排，先做这几件："]
        for n, r in enumerate(todo[:6], 1):
            dl = r.get("deadline") or ""
            when = "（%s）" % dl if dl and dl not in r["action"] else ""
            lines.append("%d. %s%s → %s" % (n, r["title"], when, r["action"]))
    if watch:
        lines += ["", "有空再看："]
        for r in watch[:4]:
            lines.append("· %s → %s" % (r["title"], r["action"]))
    risk = [r for r in results if "风险" in (r.get("tags") or [])]
    if risk:
        lines += ["", "⚠️ 另有 %d 条疑似诈骗/诱导信息，已单独标红，别点链接、别转账。" % len(risk)]
    if skip:
        lines += ["", "已自动折叠 %d 条闲聊与营销，不再打扰你。" % len(skip)]
    return "\n".join(lines)


# ---------------------------------------------------------------- 自动模式（打开就筛好）
_LOCK = threading.Lock()
_TODAY = {"built": 0.0, "payload": None}


def build_today(force=False):
    """读 Windows 通知中心 → 分析 → 缓存。页面一打开直接拿这里的结果。"""
    with _LOCK:
        now_ts = time.time()
        if not force and _TODAY["payload"] and now_ts - _TODAY["built"] < AUTO_TTL_SEC:
            return _TODAY["payload"]

        scanned_at = datetime.now().strftime("%m-%d %H:%M")
        payload = {
            "auto": True,
            "ok": False,
            "scanned_at": scanned_at,
            "count": 0,
            "window_hours": AUTO_WINDOW_HOURS,
            "note": "",
            "source": "windows-notifications",
            "results": [],
            "brief": "",
            "llm_available": bool(os.getenv("DASHSCOPE_API_KEY")),
        }

        if collector is None:
            payload["note"] = "采集模块没加载成功，可以先用下面的手动粘贴。"
        else:
            try:
                got = collector.collect(hours=AUTO_WINDOW_HOURS)
            except Exception as exc:
                got = {"ok": False, "items": [], "note": "采集失败：%s" % exc}
            payload["scanned_at"] = got.get("scanned_at", scanned_at)
            payload["note"] = got.get("note", "")
            payload["ok"] = bool(got.get("ok"))
            payload["source_path"] = collector.DB_PATH if hasattr(collector, "DB_PATH") else ""
            if payload["ok"]:
                items = [{"source": it["source"], "text": it["text"],
                          "hidden": it.get("hidden", False)} for it in got["items"]]
                payload["im_found"] = got.get("im_found", {})
                payload["hidden_count"] = got.get("hidden_count", 0)
                results = [r for r in (analyze_one(it, i) for i, it in enumerate(items)) if r]
                payload["results"] = results
                payload["count"] = len(results)
                payload["brief"] = build_brief(results)
                payload["source_counts"] = got.get("source_counts", {})
                # 首次运行/每次刷新都做一次适配器自检（用户看到的"脚本跑了一下"）
                if ADAPTERS is not None:
                    counts = dict(got.get("source_counts", {}))
                    mirror = sum(v for k, v in counts.items() if k.startswith("手机镜像"))
                    if mirror:
                        counts["手机镜像"] = mirror
                    payload["adapters"] = ADAPTERS.scan(counts)
                    payload["adapter_ok"] = sum(1 for r in payload["adapters"]
                                                if r["status"] == "ok")

        _TODAY["payload"] = payload
        _TODAY["built"] = now_ts
        return payload


def _warm_loop():
    """后台每 60 秒悄悄刷新一次，用户打开页面时结果是热的。"""
    while True:
        try:
            build_today(force=True)
        except Exception:
            pass
        time.sleep(AUTO_TTL_SEC)


# ---------------------------------------------------------------- 首次运行引导
def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(state):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def onboarding_status():
    st = _load_state()
    return {
        "first_run": not st.get("completed"),
        "completed": bool(st.get("completed")),
        "completed_at": st.get("completed_at", ""),
        "skipped": bool(st.get("skipped")),
        "state_path": STATE_PATH,
    }


def onboarding_update(action):
    st = _load_state()
    if action == "reset":
        st = {}
        _save_state(st)
        return onboarding_status()
    st["completed"] = action in ("done", "skip")
    st["skipped"] = action == "skip"
    st["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save_state(st)
    return onboarding_status()


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/samples":
                with open(os.path.join(BASE_DIR, "samples.json"), "rb") as f:
                    self._send(200, f.read(), "application/json; charset=utf-8")
            elif path == "/api/health":
                self._send(200, {"ok": True, "llm": bool(os.getenv("DASHSCOPE_API_KEY"))})
            elif path == "/api/today":
                self._send(200, build_today(force=False))
            elif path == "/api/refresh":
                self._send(200, build_today(force=True))
            elif path == "/api/adapters":
                today = build_today(force=True)
                self._send(200, {
                    "scanned_at": today.get("scanned_at"),
                    "adapters": today.get("adapters", []),
                    "source_counts": today.get("source_counts", {}),
                    "ok_count": today.get("adapter_ok", 0),
                    "has_db": bool(collector and collector.available()),
                })
            elif path == "/api/onboarding":
                self._send(200, onboarding_status())
            elif path == "/api/fixes":
                self._send(200, {
                    "ok": fixes is not None,
                    "actions": fixes.preview() if fixes else [],
                    "can_undo": bool(fixes and os.path.exists(fixes.BACKUP_PATH)),
                })
            elif path == "/api/quit":
                self._send(200, {"ok": True})
                threading.Timer(0.4, lambda: os._exit(0)).start()
            else:
                self._send(404, {"error": "not found"})
        except BrokenPipeError:
            pass

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self._send(400, {"error": "bad request"})
            return

        if path == "/api/onboarding":
            action = payload.get("action", "done")
            if action not in ("done", "skip", "reset"):
                self._send(400, {"error": "action 只能是 done / skip / reset"})
                return
            self._send(200, onboarding_update(action))
            return

        # 一键设置：用户勾选并同意后才执行（可 dry_run 预览）
        if path == "/api/fix":
            if fixes is None:
                self._send(200, {"ok": False, "results": [{"ok": False, "msg": "fixes 模块不可用"}]})
                return
            ids = payload.get("actions") or []
            if not isinstance(ids, list) or not ids:
                self._send(400, {"error": "没有选择任何操作"})
                return
            allowed = {a["id"] for a in fixes.ACTIONS}
            ids = [i for i in ids if i in allowed]
            results = fixes.run(ids, dry=bool(payload.get("dry")))
            self._send(200, {"ok": all(r.get("ok") for r in results), "results": results})
            return

        if path == "/api/fix/undo":
            self._send(200, fixes.undo() if fixes else {"ok": False, "msg": "fixes 模块不可用"})
            return

        if path != "/api/analyze":
            self._send(404, {"error": "not found"})
            return
        items = payload.get("items") or []
        if not isinstance(items, list) or not items:
            self._send(400, {"error": "items 为空"})
            return
        results = None
        if payload.get("mode") == "llm":
            results = llm_analyze(items)
        if results is None:
            results = [r for r in (analyze_one(it, i) for i, it in enumerate(items)) if r]
        self._send(200, {"results": results, "brief": build_brief(results),
                         "engine": results[0]["engine"] if results else "rule",
                         "llm_available": bool(os.getenv("DASHSCOPE_API_KEY"))})

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print("信息筛选官已启动：http://127.0.0.1:%d" % PORT)
    if onboarding_status()["first_run"]:
        print("首次运行：页面会自动弹出「一键设置」引导（勾选同意后执行，可撤销）")
    print("大模型模式：%s" % ("可用" if os.getenv("DASHSCOPE_API_KEY") else "未配置（规则模式，可正常演示）"))
    if collector is not None and collector.available():
        print("自动采集：已开启（Windows 通知中心，每 %d 秒刷新一次）" % AUTO_TTL_SEC)
        if ADAPTERS is not None:
            ADAPTERS.bootstrap(verbose=True)
            print()
        threading.Thread(target=_warm_loop, daemon=True).start()
    else:
        print("自动采集：未检测到通知历史（页面仍可手动粘贴使用）")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:                      # 端口被占用（常见：已经开着一个了）
        print()
        print("端口 %d 已被占用（可能已经开着一个了）：%s" % (PORT, exc))
        print("直接打开 http://127.0.0.1:%d 用现成的那个即可，不用重复启动。" % PORT)
        try:
            import webbrowser
            webbrowser.open("http://127.0.0.1:%d" % PORT)
        except Exception:
            pass
        sys.exit(0)

    # 双击运行（exe / 无窗口启动器）时自动打开浏览器；命令行调试可设 NO_BROWSER=1
    if os.getenv("NO_BROWSER") != "1":
        def _open_browser():
            time.sleep(0.9)
            try:
                import webbrowser
                webbrowser.open("http://127.0.0.1:%d" % PORT)
            except Exception:
                pass
        threading.Thread(target=_open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")

