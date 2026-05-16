# -*- coding: utf-8 -*-
"""段落间连接路径模型。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

@dataclass
class SegmentPath:
    """
    段落间分支路径。
    满足条件表达式时，可以通往目标段落。
    """

    # 前置剧情段落id。
    prev_segment_id: str

    # 后续剧情段落id。
    next_segment_id: str

    # 条件表达式或模式字符串，为空表示无条件。
    condition_expression: str|None = None

    # 路径名称，用于在编辑器中显示与引用。为空时按源与目标段落id拼接。
    name: str | None = None

    # 注释。
    comment: str | None = None

    # 唯一标识，由 name 哈希生成 8 位；不传则自动生成。
    id: str | None = None

    def __post_init__(self) -> None:
        if self.name is None or self.name == "":
            self.name = f"{self.prev_segment_id}_to_{self.next_segment_id}_path"
        if self.id is None or self.id == "":
            self.id = hashlib.sha256(self.name.encode()).hexdigest()[:8]

