# -*- coding: utf-8 -*-
"""飞书 / Lark 适配器（两个包名都覆盖）"""
from .base import Adapter


class FeishuAdapter(Adapter):
    key = "feishu"
    name = "飞书"
    kind = "im"
    patterns = (r"feishu", r"(^|[^a-z])lark([^a-z]|$)")
    attribution = ("飞书", "feishu", "lark")
    install_paths = (
        r"C:\Program Files\LarkShell\Lark.exe",
        r"C:\Program Files (x86)\LarkShell\Lark.exe",
        r"C:\Program Files\Feishu\Feishu.exe",
    )
    fix_tip = "飞书 → 设置 → 通知 → 打开「桌面通知」，并检查会话是否免打扰"
