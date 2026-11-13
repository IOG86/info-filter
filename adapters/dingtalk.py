# -*- coding: utf-8 -*-
"""钉钉适配器"""
from .base import Adapter


class DingTalkAdapter(Adapter):
    key = "dingtalk"
    name = "钉钉"
    kind = "im"
    patterns = (r"dingtalk",)
    attribution = ("钉钉", "dingtalk")
    install_paths = (
        r"C:\Program Files (x86)\DingDing\DingtalkLauncher.exe",
        r"C:\Program Files\DingDing\DingtalkLauncher.exe",
    )
    fix_tip = "钉钉 → 设置 → 消息通知 → 打开「桌面通知」，并检查群是否免打扰"
