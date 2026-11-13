# -*- coding: utf-8 -*-
"""适配器包：每个社交/办公 App 一个脚本，负责"认出它 + 解析它的通知 + 自检"。

新增一个 App 支持 = 在这个目录里加一个文件，然后登记到 registry.ADAPTERS。
"""
from . import registry  # noqa: F401
