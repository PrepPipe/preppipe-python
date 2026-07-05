# -*- coding: utf-8 -*-
"""
文字 ADV 脚本流程编辑器的数据模型与（后续）视图层入口。

当前仅实现数据模型层：
- 剧情段落（节点）
- 段落间连接条件
- 段落连接条件相关变量（flag）
"""

from ScriptFlowEditor.models import (
    FlagType,
    FlagVariable,
    StorySegment,
    SegmentPath,
    GameScriptFlow,
)

__all__ = [
    "FlagType",
    "FlagVariable",
    "StorySegment",
    "SegmentPath",
    "GameScriptFlow",
]
