# -*- coding: utf-8 -*-
"""剧情段落(节点)模型。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class StorySegment:
    """
    剧情段落(节点)。
    表示一段可播放的剧情内容，具备名称、正文以及是否为终点段落的属性。
    """

    # 段落名称，用于在编辑器中显示。
    name: str

    # 段落正文内容(脚本文本)。
    content: str

    # 是否为终点段落；默认为 True。如果为 False，则有后继连接。 如果为 True，则没有后继连接。
    is_ending_segment: bool = True

    # 唯一标识，由 name 哈希生成 8 位；不传则自动生成。
    id: str | None = None

    # 注释。
    comment: str = ""

    # 分支路径id与后续段落id字典。
    paths_segment_ids: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = hashlib.sha256(self.name.encode()).hexdigest()[:8]

    def add_path_segment_id(self, path_id: str, segment_id: str) -> None:
        self.paths_segment_ids[path_id] = segment_id
