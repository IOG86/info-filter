# -*- coding: utf-8 -*-
"""手机连接（Phone Link）适配器

安卓手机连上 Windows「手机连接」后，手机通知会镜像成系统通知。
这个适配器负责把"手机镜像"进一步细化成「手机镜像·微信」「手机镜像·QQ」等，
依据是 Toast 末尾的归属文本（比如微信通知会带一条「微信」）。
"""
from .base import Adapter

MIRROR_HINTS = [
    (("微信", "wechat", "weixin"), "微信"),
    (("企业微信", "wxwork", "wecom"), "企业微信"),
    (("钉钉", "dingtalk"), "钉钉"),
    (("飞书", "feishu", "lark"), "飞书"),
    (("qq", "tim"), "QQ"),
    (("telegram",), "Telegram"),
]


class PhoneLinkAdapter(Adapter):
    key = "phonelink"
    name = "手机镜像"
    kind = "mirror"
    patterns = (r"yourphone|phoneexperiencehost|crossdevice",)
    fix_tip = ("设置 → 蓝牙和其他设备 → 手机连接 → 连上安卓手机并允许「访问手机通知」；"
               "之后手机微信/QQ 的消息会以系统通知形式出现")
    note = "把手机通知镜像到电脑，绕过微信 4.x 不写系统通知的限制"

    def source_name(self, app_id, texts=()):
        joined = " ".join(texts).lower()
        for keys, app in MIRROR_HINTS:
            for k in keys:
                if k in joined:
                    return "手机镜像·" + app
        return "手机镜像"
