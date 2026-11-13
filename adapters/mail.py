# -*- coding: utf-8 -*-
"""邮件客户端 + Teams 适配器（不是 IM，但同属"会打断你"的信息源）"""
from .base import Adapter


class MailAdapter(Adapter):
    key = "mail"
    name = "邮箱"
    kind = "mail"
    patterns = (r"outlook|hxoutlook|windows\.mail|thunderbird",)
    attribution = ("outlook", "邮件", "mail")
    fix_tip = "邮件客户端一般默认走系统通知，不需要额外设置"


class TeamsAdapter(Adapter):
    key = "teams"
    name = "Teams"
    kind = "im"
    patterns = (r"msteams|(^|[^a-z])teams([^a-z]|$)",)
    attribution = ("teams", "microsoft teams")
