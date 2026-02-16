# -*- coding: utf-8 -*-
"""脚本文档聚合模型：段落、连接、变量。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from dataclasses import asdict, dataclass, field
from ScriptFlowEditor.models.flag import FlagType, FlagVariable
from ScriptFlowEditor.models.segment import StorySegment
from ScriptFlowEditor.models.path import SegmentPath


@dataclass
class GameScriptFlow:
    """
    游戏脚本流程。

    聚合所有剧情段落、段落间分支路径、以及分支路径条件相关变量(flag)，
    构成一份完整的游戏脚本流程数据。
    """
    # 脚本名称，用于在编辑器中显示与引用。
    name: str = ""

    # 剧情段落（节点）列表。
    segments: list[StorySegment] = field(default_factory=list)

    # 段落间分支路径列表。
    paths: list[SegmentPath] = field(default_factory=list)

    # 分支路径条件相关变量列表。
    flags: list[FlagVariable] = field(default_factory=list)

    # 脚本流程标题（可选，用于显示）。
    title: str = ""

    # 注释。
    comment: str | None = None

    # 唯一标识，由 name 哈希生成 8 位；不传则自动生成。
    id: str | None = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = hashlib.sha256(self.name.encode()).hexdigest()[:8]

    # 按 id 查找剧情段落。
    def get_segment_by_id(self, segment_id: str) -> StorySegment | None:
        for s in self.segments:
            if s.id == segment_id:
                return s
        return None

    # 按 id 查找变量。
    def get_flag_by_id(self, flag_id: str) -> FlagVariable | None:
        for f in self.flags:
            if f.id == flag_id:
                return f
        return None

    # 按名称查找变量。
    def get_flag_by_name(self, name: str) -> FlagVariable | None:
        for f in self.flags:
            if f.name == name:
                return f
        return None

    # 按前置段落 id 查找分支路径。
    def get_path_prev(self, prev_segment_id: str) -> list[SegmentPath]:
        return [c for c in self.paths if c.prev_segment_id == prev_segment_id]

    # 按后续段落 id 查找分支路径。
    def get_path_next(self, next_segment_id: str) -> list[SegmentPath]:
        return [c for c in self.paths if c.next_segment_id == next_segment_id]

    # 序列化为可 JSON 序列化的字典（JSON 对象）。
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "id": self.id,
            "title": self.title,
            "comment": self.comment,
            "segments": [asdict(s) for s in self.segments],
            "paths": [asdict(p) for p in self.paths],
            "flags": [self._flag_to_dict(f) for f in self.flags],
        }

    # 将 FlagVariable 转为 dict，flag_type 枚举转为字符串。
    @staticmethod
    def _flag_to_dict(f: FlagVariable) -> dict:
        d = asdict(f)
        if hasattr(f.flag_type, "value"):
            d["flag_type"] = f.flag_type.value
        return d

    # 序列化为 JSON 字符串。
    def to_json(self, *, indent: int | None = None, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    def _get_generated_dir(self) -> Path:
        """返回 ScriptFlowEditor/generated 目录路径，不存在则创建。"""
        # 本文件位于 ScriptFlowEditor/models/gamescriptflow.py
        generated = Path(__file__).resolve().parent.parent / "generated"
        generated.mkdir(parents=True, exist_ok=True)
        return generated

    @classmethod
    def load_from_json(cls, path: str | Path) -> GameScriptFlow:
        """
        从 JSON 文件反序列化为 GameScriptFlow 对象。

        :param path: JSON 文件路径，例如 src/ScriptFlowEditor/generated/Demo Flow.json
        :return: 反序列化得到的 GameScriptFlow 实例
        """
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.load_from_dict(data)

    @classmethod
    def load_from_dict(cls, data: dict) -> GameScriptFlow:
        """
        从字典反序列化为 GameScriptFlow 对象（可含额外键如 node_positions，会被忽略）。

        :param data: 含 segments、paths、flags 等键的字典
        :return: 反序列化得到的 GameScriptFlow 实例
        """
        segments = [cls._segment_from_dict(d) for d in data.get("segments", [])]
        paths = [cls._path_from_dict(d) for d in data.get("paths", [])]
        flags = [cls._flag_from_dict(d) for d in data.get("flags", [])]
        return cls(
            name=data.get("name", ""),
            id=data.get("id"),
            title=data.get("title", ""),
            comment=data.get("comment"),
            segments=segments,
            paths=paths,
            flags=flags,
        )

    @staticmethod
    def _segment_from_dict(d: dict) -> StorySegment:
        return StorySegment(
            name=d["name"],
            content=d["content"],
            is_ending_segment=d.get("is_ending_segment", True),
            id=d.get("id"),
            comment=d.get("comment", ""),
            paths_segment_ids=d.get("paths_segment_ids", {}),
        )

    @staticmethod
    def _path_from_dict(d: dict) -> SegmentPath:
        return SegmentPath(
            prev_segment_id=d["prev_segment_id"],
            next_segment_id=d["next_segment_id"],
            condition_expression=d.get("condition_expression"),
            name=d.get("name"),
            comment=d.get("comment"),
            id=d.get("id"),
        )

    @staticmethod
    def _flag_from_dict(d: dict) -> FlagVariable:
        return FlagVariable(
            name=d["name"],
            flag_type=d["flag_type"],
            initial_value=d["initial_value"],
            comment=d.get("comment"),
            id=d.get("id"),
        )

    # 序列化为 JSON 并保存到 ScriptFlowEditor/generated 目录下的 .json 文件。
    def save_as_json(
        self,
        filename: str | None = None,
        *,
        indent: int | None = 2,
        ensure_ascii: bool = False,
    ) -> Path:
        """
        将当前对象序列化为 JSON 并保存到 src/ScriptFlowEditor/generated 目录。

        :param filename: 文件名（可含 .json 后缀）；为 None 时用 name 或 id，不含则自动加 .json。
        :param indent: 传给 json.dumps 的缩进，默认 2。
        :param ensure_ascii: 是否转义非 ASCII，默认 False 以保留中文。
        :return: 保存后的文件路径。
        """
        out_dir = self._get_generated_dir()
        if not filename:
            base = (self.name or self.id or "gamescriptflow").replace("/", "_").replace("\\", "_").strip(". ") or "flow"
            filename = f"{base}.json" if not base.lower().endswith(".json") else base
        elif not filename.lower().endswith(".json"):
            filename = f"{filename}.json"
        path = out_dir / filename
        path.write_text(self.to_json(indent=indent, ensure_ascii=ensure_ascii), encoding="utf-8")
        return path
