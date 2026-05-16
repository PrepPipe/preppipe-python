# -*- coding: utf-8 -*-
"""段落连接条件相关变量(flag)模型。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import enum


class FlagType(enum.Enum):

    """
    flag变量类型。
    
    bool: 布尔值
    int: 整数
    float: 浮点数
    """
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"


@dataclass
class FlagVariable:
    """
    控制分支走向相关变量(flag）。
    用于在段落间连接条件中引用，具备类型与初始值。
    """

    # 变量名称，全局范围内应唯一。
    name: str

    # 变量类型：bool / int / float。入参可为 str（如 "bool"）或 FlagType，字符串会转换为枚举。
    flag_type: str | FlagType

    # 初始值，类型需与 flag_type 一致。
    initial_value: bool | int | float

    # 注释。
    comment: str | None = None

    # 唯一标识，由 name 哈希生成 8 位；不传则自动生成。
    id: str | None = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = hashlib.sha256(self.name.encode()).hexdigest()[:8]
        self._normalize_flag_type()
        self._validate_initial_value()

    # 将入参转换为 FlagType，无效则抛错。
    def _normalize_flag_type(self) -> None:
        if isinstance(self.flag_type, str):
            try:
                self.flag_type = FlagType(self.flag_type)
            except ValueError:
                valid = [e.value for e in FlagType]
                raise ValueError(
                    f"FlagVariable {self.name!r}: flag_type value is invalid {self.flag_type!r}, "
                    f"it should be one of {valid}"
                ) from None
        elif not isinstance(self.flag_type, FlagType):
            raise TypeError(
                f"FlagVariable {self.name!r}: flag_type should be str or FlagType, "
                f"got {type(self.flag_type).__name__}"
            )

    # 校验初始值类型是否与 flag_type 一致。
    def _validate_initial_value(self) -> None:
        
        if self.flag_type == FlagType.BOOL and not isinstance(self.initial_value, bool):
            raise TypeError(
                f"FlagVariable {self.name!r}: flag_type is bool, "
                f"initial_value should be bool, got {type(self.initial_value).__name__}"
            )
        if self.flag_type == FlagType.INT and not isinstance(self.initial_value, int):
            raise TypeError(
                f"FlagVariable {self.name!r}: flag_type is int, "
                f"initial_value should be int, got {type(self.initial_value).__name__}"
            )
        if self.flag_type == FlagType.FLOAT and not isinstance(self.initial_value, (int, float)):
            raise TypeError(
                f"FlagVariable {self.name!r}: flag_type is float, "
                f"initial_value should be int or float, got {type(self.initial_value).__name__}"
            )
