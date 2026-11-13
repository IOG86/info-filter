# -*- coding: utf-8 -*-
"""QQ / QQNT / TIM 适配器

注意：QQ 的 AppId 可能就是一个 "QQ"，也可能出现在长串里，
所以用边界匹配，避免把 qqmail、sqq 之类的误判成 QQ。
"""
from .base import Adapter


class QQAdapter(Adapter):
    key = "qq"
    name = "QQ"
    kind = "im"
    patterns = (
        r"(^|[^a-z])qq(nt)?([^a-z]|$)",
        r"tencent\.qq",
        r"(^|[^a-z])tim([^a-z]|$)",
    )
    attribution = ("qq", "qqnt", "tim", "腾讯qq")
    install_paths = (
        r"C:\Program Files\Tencent\QQNT\QQ.exe",
        r"C:\Program Files (x86)\Tencent\QQ\Bin\QQScLauncher.exe",
        r"C:\Program Files\Tencent\TIM\TIM.exe",
    )
    fix_tip = "QQ → 设置 → 消息通知 → 打开「允许系统通知 / 桌面通知」"

    def source_name(self, app_id, texts=()):
        low = str(app_id or "").lower()
        if "tim" in low and "qq" not in low.replace("tim", ""):
            return "TIM"
        return "QQ"
