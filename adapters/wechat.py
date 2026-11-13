# -*- coding: utf-8 -*-
"""微信适配器（WeChat 3.x / Weixin 4.x / 小程序容器 WeChatAppEx）"""
from .base import Adapter


class WeChatAdapter(Adapter):
    key = "wechat"
    name = "微信"
    kind = "im"
    # 3.x 的 WeChat、4.x 的 Weixin、小程序容器 WeChatAppEx 都归到这里
    patterns = (r"wechatappex|wechat|weixin",)
    attribution = ("微信", "wechat", "weixin")
    install_paths = (
        r"C:\Program Files\Tencent\Weixin\Weixin.exe",
        r"C:\Program Files (x86)\Tencent\Weixin\Weixin.exe",
        r"C:\Program Files\Tencent\WeChat\WeChat.exe",
        r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
    )
    fix_tip = "微信 4.x 是自绘弹窗，不写系统通知；用「手机连接」镜像手机微信，或安装旧版 3.x"
    note = "3.x 可以自动读取；4.x 需要手机镜像或手动补录"
