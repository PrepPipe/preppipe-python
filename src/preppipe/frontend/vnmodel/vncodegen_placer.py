# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from typing import Any

from preppipe.frontend.vnmodel.vnast import VNASTCharacterSymbol, VNASTNodeBase, VNModifyInst, VNPlacementInstBase, VNRemoveInst, Value

from ..vnmodel import *
from .vnast import *
import copy

# 在我们解析入场、退场、移动等事件时，我们使用“事件驱动”的逻辑，但这对于决定每个对象的最佳位置比较困难
# 所以在处理时我们会先把这些事件记录下来，等到当前事件处理完毕后再处理这些事件，对位置进行统筹
# 本文件包含对这些事件的处理逻辑
# 只有切换场景时发生的退场不会在这里处理，相关代码会清除所有状态

class VNCodeGen_PlacementPolicy(enum.Enum):
  MANUAL = enum.auto() # 该位置由用户手动指定，位置不可自动变动，在用户明确表示解除锁定时才会更改
  AUTO = enum.auto() # 该位置可由算法决定。

@dataclasses.dataclass
class VNCodeGen_PlacementInfoBase:
  # 保存在 VNCodeGen 中每个场景内对象上的信息
  # 子类应当添加更多项来实现自己的功能

  policy : VNCodeGen_PlacementPolicy

  def copy(self) -> VNCodeGen_PlacementInfoBase:
    raise PPInternalError("Should be implemented in subclass")

class VNCodeGen_SceneContextPlacerInterface:
  # 该类定义 SceneContext 中给这里的代码使用的接口

  def get_character_position(self, handle : typing.Any) -> VNCodeGen_PlacementInfoBase | None:
    # handle 为 VNCodeGen_PlacerBase.add_character_event() 中的 handle
    raise PPInternalError("Should be implemented in subclass")

  def set_character_position(self, handle : typing.Any, pos : VNCodeGen_PlacementInfoBase) -> None:
    raise PPInternalError("Should be implemented in subclass")

  def get_asset_position(self, handle : typing.Any) -> VNCodeGen_PlacementInfoBase | None:
    # handle 为 VNCodeGen_PlacerBase.add_image_event() 中的 handle
    raise PPInternalError("Should be implemented in subclass")

  def set_asset_position(self, handle : typing.Any, pos : VNCodeGen_PlacementInfoBase) -> None:
    raise PPInternalError("Should be implemented in subclass")

  def populate_active_scene_contents(self, characters : list[typing.Any], assets : list[typing.Any]) -> None:
    # 将当前场上的所有角色和内容图片的 handle 添加到 characters 和 assets 中
    raise PPInternalError("Should be implemented in subclass")

class VNCodeGen_PlacerBase:
  # 用来辅助 VNCodeGen 在屏幕上放置角色立绘、内容图片等对象的类
  # 该类只是基类，实现请见下面的子类

  def has_event_pending(self) -> bool:
    # 是否有事件等待处理，如果有的话，后续会调用 handle_pending_events()
    return False

  def handle_pending_events(self) -> None:
    # 处理等待处理的事件，职责包括：
    # 1. 给每个事件对应的指令添加位置信息
    # 2. 若有需要，调整其他内容的位置
    # 我们既需要直接调用 scene 对象中改变当前位置的函数，也需要生成指令来改变位置
    # TODO 定义与 FunctionCodeGenHelper 的接口，把指令生成的职责交给它，这里只负责位置计算
    pass

  def reset(self, scene : typing.Any) -> None:
    # 丢弃所有状态，重新开始
    # 一般在切换场景或者在调用函数后被调用
    # （一般改变基本块时都可以沿用当前的场景信息，有分支时会有新的 _FunctionCodeGenHelper 和此 Placer 实例对其负责）
    pass

  # 以下是用于添加事件的函数
  # 待处理的事件应当以 IR 顺序排列
  # 如果有需要在事件前调整其他内容位置的话，第一个事件的指令位置将被作为插入点
  # 如果有需要在事件后调整其他内容位置的话，最后一个事件的指令位置之后将被作为插入点

  def add_character_event(self, handle : typing.Any, character : VNASTCharacterSymbol, sprite : Value | None, instr : VNPlacementInstBase | VNModifyInst | VNRemoveInst, destexpr : VNASTNodeBase) -> None:
    # 添加角色的入场、退场、移动事件
    # handle 只用于在 SceneContext 中引用角色，本类不会对其进行任何操作
    # sprite 仅在退场时可为 None，其他情况下必须有值
    # destexpr 用于读取用户输入的目标位置
    # 默认实现仅把事件记录下来
    s = StringLiteral.get('PlacerEvent: character=' + character.name, context=instr.context)
    op = CommentOp.create(comment=s, loc=instr.location)
    op.insert_before(instr)

  def add_image_event(self, handle : typing.Any, content : Value, instr : VNPlacementInstBase | VNModifyInst | VNRemoveInst, destexpr : VNASTNodeBase) -> None:
    # 添加其他图片的入场、退场、移动事件（不过目前只有入场退场）
    # handle 只用于在 SceneContext 中引用图片，本类不会对其进行任何操作
    # content 在退场时是出场指令的句柄，其余情况下是图片内容
    # 默认实现仅把事件记录下来
    s = StringLiteral.get('PlacerEvent: image=' + str(content), context=instr.context)
    op = CommentOp.create(comment=s, loc=instr.location)
    op.insert_before(instr)

class VNCodeGen_Placer(VNCodeGen_PlacerBase):
  def __init__(self) -> None:
    super().__init__()

  def add_character_event(self, handle: Any, character: VNASTCharacterSymbol, sprite: Value | None, instr: VNPlacementInstBase | VNModifyInst | VNRemoveInst, destexpr: VNASTNodeBase) -> None:
    pass # TODO

  def add_image_event(self, handle: Any, content: Value, instr: VNPlacementInstBase | VNModifyInst | VNRemoveInst, destexpr: VNASTNodeBase) -> None:
    pass # TODO
