# -*- coding: utf-8 -*-
"""适配器基类：每个社交/办公 App 一个适配器。

适配器负责三件事：
  1. 认出通知是谁发的（AppId → 来源名）
  2. 知道这个 App 的 Toast 长什么样（归属文本、隐私模式文案）
  3. 首次运行时在这台电脑上自检：装了没 / 有没有注册系统通知 / 该怎么设置
"""
import os
import re


class Adapter(object):
    key = "base"
    name = "其他应用"
    kind = "other"          # im / mail / mirror / system / other
    patterns = ()            # 正则（对 AppId 小写后匹配）
    attribution = ()         # Toast 末尾可能出现的归属文本
    install_paths = ()       # 用文件存在性判断"装没装"
    fix_tip = ""             # 自检失败时给用户的操作建议
    note = ""                # 额外说明

    def match(self, app_id):
        low = str(app_id or "").lower()
        if not low:
            return False
        return any(re.search(p, low) for p in self.patterns)

    def source_name(self, app_id, texts=()):
        """默认返回适配器名；子类可覆写（比如 QQ/TIM 共用、手机镜像细化来源）。"""
        return self.name

    def installed(self):
        return any(os.path.exists(p) for p in self.install_paths)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.name)
