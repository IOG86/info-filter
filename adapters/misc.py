# -*- coding: utf-8 -*-
"""其它来源适配器：系统类、工具类。

这些不是社交软件，但同样会往通知中心写东西（广告、系统提醒），
一并识别出来，避免它们被当成"重要消息"。
"""
from .base import Adapter


class SimpleAdapter(Adapter):
    """一行就能定义的适配器。"""

    def __init__(self, key, name, patterns, kind="system", install_paths=()):
        self.key = key
        self.name = name
        self.patterns = patterns
        self.kind = kind
        self.install_paths = install_paths


MISC_ADAPTERS = [
    SimpleAdapter("codex", "Codex", (r"codex",)),
    SimpleAdapter("defender", "系统安全", (r"defender",)),
    SimpleAdapter("widgets", "资讯", (r"widgets",)),
    SimpleAdapter("doubao", "豆包", (r"doubao",)),
    SimpleAdapter("onedrive", "OneDrive", (r"onedrive|skydrive",)),
    SimpleAdapter("browser", "浏览器", (r"chrome|msedge|edge|firefox",)),
    SimpleAdapter("store", "应用商店", (r"store",)),
    SimpleAdapter("update", "系统更新", (r"update",)),
]
