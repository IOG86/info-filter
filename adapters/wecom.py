# -*- coding: utf-8 -*-
"""企业微信适配器"""
from .base import Adapter


class WeComAdapter(Adapter):
    key = "wecom"
    name = "企业微信"
    kind = "im"
    patterns = (r"wxwork|wecom",)
    attribution = ("企业微信", "wxwork", "wecom")
    install_paths = (
        r"C:\Program Files (x86)\WXWork\WXWork.exe",
        r"C:\Program Files\WXWork\WXWork.exe",
    )
    fix_tip = "企业微信 → 设置 → 通知 → 打开「新消息通知」"
