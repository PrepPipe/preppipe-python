# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from typing import Any
import math

from preppipe.frontend.vnmodel.vnast import VNASTCharacterSymbol, VNASTNodeBase, VNModifyInst, VNPlacementInstBase, VNRemoveInst, Value

from ..vnmodel import *
from .vnast import *
from ...imageexpr import *

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
  context : Context

  def __init__(self, context : Context) -> None:
    self.context = context

  def set_screen_size(self, width : int, height : int) -> None:
    # 设置屏幕大小
    # 应该只在初始化时调用一次
    pass

  def has_event_pending(self) -> bool:
    # 是否有事件等待处理，如果有的话，后续会调用 handle_pending_events()
    return False

  def handle_pending_events(self) -> list[tuple[typing.Any, Value, VNInstruction | None]] | None:
    # 处理等待处理的事件，职责包括：
    # 1. 给每个事件对应的指令添加位置信息
    # 2. 若有需要，调整其他内容的位置(既需要直接调用 scene 对象中改变当前位置的函数，也需要返回构建新指令的信息)
    # 返回值中每一项是一个三元组，分别是：
    # 1. 事件对应的 handle
    # 2. 内容的最终位置
    # 3. 新指令插入的位置（插入到该指令前），如果是 None 则表示插入到最后
    # 如果不需要任何新指令，返回 None
    pass

  def reset(self, scene : VNCodeGen_SceneContextPlacerInterface) -> None:
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

  # 以下是用于子类的辅助函数
  _image_bboxes : typing.ClassVar[dict[BaseImageLiteralExpr, tuple[int, int, int, int]]] = {}
  @staticmethod
  def get_opaque_boundingbox(image : BaseImageLiteralExpr) -> tuple[int, int, int, int]:
    """计算图片非透明部分的 <左, 上, 右, 下> 边界，同 BaseImageLiteralExpr.get_bbox()"""
    # 为了避免重复计算，我们会缓存结果
    if not isinstance(image, BaseImageLiteralExpr):
      raise PPInternalError("image is not BaseImageLiteralExpr")
    if bbox := VNCodeGen_PlacerBase._image_bboxes.get(image):
      return bbox
    bbox = image.get_bbox()
    VNCodeGen_PlacerBase._image_bboxes[image] = bbox
    return bbox

@dataclasses.dataclass
class VNCodeGen_PlacementInfo(VNCodeGen_PlacementInfoBase):
  # 以下是用于计算位置的信息，None 表示还没定
  # （上场时一定已知的）长宽，还有横向的非透明部分的边界
  w : int
  h : int
  bbox_x : tuple[int, int] # 非透明边界的 <左, 右> X 值。如果完全不透明，则为 <0, w>
  # 左上角坐标，有可能没有
  x : int | None = None
  y : int | None = None
  # 如果用户已经指定了位置，这里是位置的字面值
  manual_pos : VNScreen2DPositionLiteralExpr | None = None

  def get_position_value(self, context : Context) -> Value:
    if self.manual_pos is not None:
      return self.manual_pos
    if self.x is None or self.y is None:
      raise PPInternalError("Position not initialized")
    return VNScreen2DPositionLiteralExpr.get(context=context, x_abs=self.x, y_abs=self.y, width=self.w, height=self.h)

  def copy(self) -> VNCodeGen_PlacementInfo:
    return VNCodeGen_PlacementInfo(
      policy=self.policy,
      w=self.w,
      h=self.h,
      bbox_x=self.bbox_x,
      x=self.x,
      y=self.y,
      manual_pos=self.manual_pos,
    )

class VNCodeGen_Placer(VNCodeGen_PlacerBase):
  # 实现放置算法的类
  # 对于新添加的对象（角色立绘或图片），我们会尝试根据对象声明时的约束条件来决定位置
  # 对于角色立绘，如果没有约束条件，使用立绘默认方案的默认值
  # 对于其他图片，默认放在屏幕中心稍高的位置（基本上把对话框的位置扣掉后上下居中）。如果图片高度不足以基本撑满剩下的屏幕则大小不变，否则缩放到撑满剩下的屏幕
  # 对于已经在场上的对象，我们只考虑对其进行横向移动，纵坐标不变
  # 我们默认将已在场的对象向右移动，新上场的对象放在左侧
  # 算法实现：
  # 1.  对每个新上场的对象，我们根据以上设定决定一个初始位置；初始位置的 Y 轴不变，X 轴可以选择是否是不可变的（即用户有输入）。
  #     每个已在场的对象的当前位置作为此对象的初始位置，X 轴可变与否与用户输入有关。
  # 2. 将退场的对象去除后，我们通过(1)现有的顺序，(2)不可变的X轴值，给所有剩下的对象定义一个从左到右的顺序
  # 3. 我们给每个 X 轴可变的对象决定一个最终的目标位置。

  class HandleType(enum.Enum):
    CHARACTER = enum.auto()
    IMAGE = enum.auto()

  @dataclasses.dataclass
  class ObjectInfo:
    # 描述一个当前在场上或者即将上场的对象
    handle : typing.Any
    ty : VNCodeGen_Placer.HandleType
    pos : VNCodeGen_PlacementInfo
    # 如果该对象有新的事件，就放在这里
    event : 'VNCodeGen_Placer.EventInfo | None' = None

    def __hash__(self) -> int:
      return hash(id(self))

    def __eq__(self, __value: object) -> bool:
      return __value is self

  @dataclasses.dataclass
  class EventInfo:
    # 描述一个事件
    handle : typing.Any
    ty : VNCodeGen_Placer.HandleType
    instr : VNPlacementInstBase | VNModifyInst | VNRemoveInst
    destexpr : VNASTNodeBase
    initpos : VNCodeGen_PlacementInfo | None # 初始推荐出场位置(只有退场事件会是 None)

  _scene_objects : list[ObjectInfo]
  _pending_events : list[EventInfo]
  _cur_scene : VNCodeGen_SceneContextPlacerInterface | None
  _screen_width : int
  _screen_height : int

  # 以下是算法的参数
  OPTION_OVERLAPPING_NEW_OBJECT_AT_LEFT : typing.ClassVar[bool] = True # 如果新上场的对象与已有对象重叠，是否放在左侧，False 则放在右侧

  def __init__(self, context : Context) -> None:
    super().__init__(context)
    self._scene_objects = []
    self._pending_events = []
    self._cur_scene = None
    self._screen_width = 0
    self._screen_height = 0

  def set_screen_size(self, width: int, height: int) -> None:
    self._screen_width = width
    self._screen_height = height

  def has_event_pending(self) -> bool:
    return len(self._pending_events) > 0

  def reset(self, scene: VNCodeGen_SceneContextPlacerInterface) -> None:
    self._scene_objects.clear()
    self._pending_events.clear()
    self._cur_scene = scene

  def _query_current_scene(self) -> None:
    if self._cur_scene is None:
      raise PPInternalError("Current scene is not set")
    characters = []
    assets = []
    self._cur_scene.populate_active_scene_contents(characters, assets)
    for ch in characters:
      pos = self._cur_scene.get_character_position(ch)
      if pos is None:
        raise PPInternalError("Character is not in current scene")
      if not isinstance(pos, VNCodeGen_PlacementInfo):
        raise PPInternalError("Character position is not VNCodeGen_PlacementInfo")
      self._scene_objects.append(self.ObjectInfo(handle=ch, ty=VNCodeGen_Placer.HandleType.CHARACTER, pos=pos))
    for asset in assets:
      pos = self._cur_scene.get_asset_position(asset)
      if pos is None:
        raise PPInternalError("Asset is not in current scene")
      if not isinstance(pos, VNCodeGen_PlacementInfo):
        raise PPInternalError("Asset position is not VNCodeGen_PlacementInfo")
      self._scene_objects.append(self.ObjectInfo(handle=asset, ty=VNCodeGen_Placer.HandleType.IMAGE, pos=pos))

  def compute_initial_position_for_character(self, character: VNASTCharacterSymbol, sprite: Value, destexpr : VNASTNodeBase) -> VNCodeGen_PlacementInfo:
    if not isinstance(sprite, BaseImageLiteralExpr):
      raise PPInternalError("Unhandled sprite type")
    width, height = sprite.size.value
    left, top, right, bot = self.get_opaque_boundingbox(sprite)
    # 如果用户已经指定了位置，我们直接使用该位置
    # 不过目前暂不支持从用户输入中读取位置，所以跳过这里
    # 如果用户没有指定位置，我们根据角色声明时的约束条件来决定位置
    def handle_sprite_default_pos(baseheight : decimal.Decimal, topheight : decimal.Decimal, xoffset : decimal.Decimal, xpos : decimal.Decimal) -> VNCodeGen_PlacementInfo:
      if not isinstance(baseheight, decimal.Decimal) or not isinstance(topheight, decimal.Decimal) or not isinstance(xoffset, decimal.Decimal) or not isinstance(xpos, decimal.Decimal):
        raise PPInternalError("Sprite parameters are not decimal")
      y = int(self._screen_height*(1-topheight))
      scaledheight = (self._screen_height - y) * (1-baseheight)
      scale = scaledheight / height
      scaledwidth = width * scale
      scaledwidth_i = int(scaledwidth)
      scaledheight_i = int(scaledheight)
      scaledleft = int(left * scale)
      scaledright = int(right * scale)
      solidwidth = scaledright - scaledleft
      xadjust = xoffset * solidwidth
      x = int(self._screen_width*(xpos+1)/2 - decimal.Decimal(solidwidth/2) - scaledleft + xadjust)
      return VNCodeGen_PlacementInfo(policy=VNCodeGen_PlacementPolicy.AUTO, w=scaledwidth_i, h=scaledheight_i, bbox_x=(scaledleft, scaledright), x=x, y=y)
    if spritedefault := character.placers.get(VNASTImagePlacerKind.SPRITE.name):
      baseheight = spritedefault.parameters.get_operand(0).value
      topheight = spritedefault.parameters.get_operand(1).value
      xoffset = spritedefault.parameters.get_operand(2).value
      xpos = decimal.Decimal(0)
      if spritedefault.parameters.get_num_operands() > 3:
        xpos = spritedefault.parameters.get_operand(3).value
      return handle_sprite_default_pos(baseheight=baseheight, topheight=topheight, xoffset=xoffset, xpos=xpos)
    if absolute := character.placers.get(VNASTImagePlacerKind.ABSOLUTE.name):
      x, y = absolute.parameters.get_operand(0).value
      scale = absolute.parameters.get_operand(1).value
      if not isinstance(x, int) or not isinstance(y, int) or not isinstance(scale, decimal.Decimal):
        raise PPInternalError("Absolute parameters type mismatch")
      scaledleft = int(left * scale)
      scaledright = int(right * scale)
      scaledwidth = int(width * scale)
      scaledheight = int(height * scale)
      return VNCodeGen_PlacementInfo(policy=VNCodeGen_PlacementPolicy.MANUAL, w=scaledwidth, h=scaledheight, bbox_x=(scaledleft, scaledright), x=int(x), y=int(y))
    # 没有约束条件，使用默认值
    baseheight, topheight, xoffset = VNASTImagePlacerKind.get_fixed_default_params(VNASTImagePlacerKind.SPRITE) # pylint: disable=unbalanced-tuple-unpacking
    xpos = VNASTImagePlacerKind.get_additional_default_params(VNASTImagePlacerKind.SPRITE)
    if not isinstance(xpos, decimal.Decimal):
      raise PPInternalError("Sprite xpos is not decimal")
    return handle_sprite_default_pos(baseheight=baseheight, topheight=topheight, xoffset=xoffset, xpos=xpos)

  def add_character_event(self, handle: Any, character: VNASTCharacterSymbol, sprite: Value | None, instr: VNPlacementInstBase | VNModifyInst | VNRemoveInst, destexpr: VNASTNodeBase) -> None:
    if len(self._pending_events) == 0:
      self._query_current_scene()
    # 添加事件并决定初始位置
    event = self.EventInfo(handle=handle, ty=self.HandleType.CHARACTER, instr=instr, destexpr=destexpr, initpos=None)
    if isinstance(instr, (VNPlacementInstBase, VNModifyInst)):
      if sprite is None:
        raise PPInternalError("Sprite missing for character enter/move event")
      initpos = self.compute_initial_position_for_character(character=character, sprite=sprite, destexpr=destexpr)
      event.initpos = initpos
    self._pending_events.append(event)

  def add_image_event(self, handle: Any, content: Value, instr: VNPlacementInstBase | VNModifyInst | VNRemoveInst, destexpr: VNASTNodeBase) -> None:
    if len(self._pending_events) == 0:
      self._query_current_scene()
    # 添加事件并决定初始位置
    event = self.EventInfo(handle=handle, ty=self.HandleType.IMAGE, instr=instr, destexpr=destexpr, initpos=None)
    if isinstance(instr, (VNPlacementInstBase, VNModifyInst)):
      # 该事件是入场或移动事件，我们需要给其添加位置信息
      # 目前暂时不支持读取手动输入的位置，我们固定把对象放在屏幕正中偏上的位置
      ratio_reserved_bot = 0.3 # 保留给屏幕下方对话框的比例
      bbox_xmin = 0
      bbox_xmax = 0
      bbox_ymin = 0
      bbox_ymax = 0
      total_width = 0
      total_height = 0
      if isinstance(content, BaseImageLiteralExpr):
        l, t, r, b = self.get_opaque_boundingbox(content)
        bbox_xmin = l
        bbox_xmax = r
        bbox_ymin = t
        bbox_ymax = b
        total_width, total_height = content.size.value
      else:
        raise PPInternalError("Unsupported content type")
      target_x = int((self._screen_width-(bbox_xmax - bbox_xmin))/2 - bbox_xmin)
      target_y = int((self._screen_height*(1-ratio_reserved_bot)-(bbox_ymax - bbox_ymin))/2 - bbox_ymin)
      pos = VNCodeGen_PlacementInfo(
        policy=VNCodeGen_PlacementPolicy.AUTO,
        w=total_width,
        h=total_height,
        bbox_x=(bbox_xmin, bbox_xmax),
        x=target_x,
        y=target_y,
      )
      event.initpos = pos
    self._pending_events.append(event)

  def handle_pending_events(self) -> list[tuple[typing.Any, Value, VNInstruction | None]] | None:
    # 在开始前，整理已在场上的对象的（从左到右）的相对顺序，以此指导事件发生后的相对顺序
    # 我们以对象的中轴线的 X 坐标作为排序依据
    self._scene_objects.sort(key=lambda obj: (obj.pos.bbox_x[0]+obj.pos.bbox_x[1]/2) + (obj.pos.x if obj.pos.x is not None else 0)) # obj.pos.x 应该不会是 None，只是让语法检查通过
    existing_obj_orders : dict[VNCodeGen_Placer.ObjectInfo, int] = {}
    for i in range(len(self._scene_objects)):
      existing_obj_orders[self._scene_objects[i]] = i
    # 第一步：整理所有事件，找出现在场上到底有哪些对象
    handle_to_obj : dict[int, VNCodeGen_Placer.ObjectInfo] = {}
    for obj in self._scene_objects:
      handle_to_obj[id(obj.handle)] = obj
    # 遍历已储存的事件，更新场上对象信息
    # event_to_obj_ordered : collections.OrderedDict[VNCodeGen_Placer.EventInfo, VNCodeGen_Placer.ObjectInfo] = collections.OrderedDict()
    scene_objects_new : list[VNCodeGen_Placer.ObjectInfo] = []
    for event in self._pending_events:
      if obj := handle_to_obj.get(id(event.handle)):
        # 该对象已经在场上了
        obj.event = event
        if event.initpos is not None:
          obj.pos = event.initpos
      else:
        # 该对象是新上场的
        if event.initpos is None:
          raise PPInternalError("New object has no initpos")
        obj = VNCodeGen_Placer.ObjectInfo(handle=event.handle, ty=event.ty, pos=event.initpos, event=event)
        handle_to_obj[id(obj.handle)] = obj
        scene_objects_new.append(obj)
      # event_to_obj_ordered[event] = obj
    # 把退场的对象去除
    cur_scene_objects : list[VNCodeGen_Placer.ObjectInfo] = [obj for obj in self._scene_objects if obj.event is None or not isinstance(obj.event.instr, VNRemoveInst)]
    # 第二步：给对象安排一个从左到右的顺序
    scene_objects_sorted : list[VNCodeGen_Placer.ObjectInfo] = []
    scene_objects_existing : list[VNCodeGen_Placer.ObjectInfo] = []

    # 先把位置固定的对象放进去
    for obj in cur_scene_objects:
      if obj.pos.manual_pos is not None:
        scene_objects_sorted.append(obj)
      else:
        scene_objects_existing.append(obj)
    # 根据当前对象的位置，给对象排序
    # manual_pos 在这里不应该为 None，只是让语法检查通过
    scene_objects_sorted.sort(key=lambda obj: (obj.pos.bbox_x[0]+obj.pos.bbox_x[1]/2) + (obj.pos.manual_pos.x_abs.value if obj.pos.manual_pos is not None else 0))

    # 使用辅助函数来把对象放入（排好序的）场景
    def add_obj_to_scene(obj : VNCodeGen_Placer.ObjectInfo, prev_order : int) -> None:
      # obj 是当前要放进去的对象，prev_order 是该对象在该系列事件前的顺序号
      # 使用该函数放进去的对象一定没有 manual_pos，不过既可能是已在场的，也可能是新上场的
      # 如果 obj 原来就在场上，那么 prev_order 在 [0, len(self._scene_objects)] 之间
      # 如果 obj 是新上场的对象，则 prev_order 是 -1 (OPTION_OVERLAPPING_NEW_OBJECT_AT_LEFT 为 True)
      #              或者 len(self._scene_objects) (OPTION_OVERLAPPING_NEW_OBJECT_AT_LEFT 为 False)
      # 我们根据现在的坐标来尝试找一个合适的位置
      # 如果该坐标所处的位置未被占用，那么就放在那里
      # 如果该坐标所处的位置被占用，那么我们参考事件发生前两对象的相对位置来决定现在的位置
      # 如果占用该坐标的对象也是新上场的对象，那么我们就根据 OPTION_OVERLAPPING_NEW_OBJECT_AT_LEFT 来决定
      insert_index = 0
      if obj.pos.x is None:
        raise PPInternalError("Position not initialized")
      # 先计算本对象的边界
      obj_xmin = obj.pos.bbox_x[0] + obj.pos.x
      obj_xmax = obj.pos.bbox_x[1] + obj.pos.x
      while (insert_index < len(scene_objects_sorted)):
        cur_obj = scene_objects_sorted[insert_index]
        if cur_obj.pos.x is None:
          raise PPInternalError("Position not initialized")
        cur_obj_xmin = cur_obj.pos.bbox_x[0] + cur_obj.pos.x
        cur_obj_xmax = cur_obj.pos.bbox_x[1] + cur_obj.pos.x
        # 先检查不重叠的情况
        if obj_xmax <= cur_obj_xmin:
          # 本对象在当前对象的左边
          break
        if obj_xmin >= cur_obj_xmax:
          # 本对象在当前对象的右边（还不确定，需要继续循环）
          insert_index += 1
          continue

        # 本对象与当前对象重叠
        if cur_obj_order := existing_obj_orders.get(cur_obj):
          # 当前对象是已在场上的对象
          if prev_order < cur_obj_order:
            # 本对象在当前对象的左边
            break
          # 本对象在当前对象的右边
          insert_index += 1
          break

        # 当前对象是新上场的对象
        if self.OPTION_OVERLAPPING_NEW_OBJECT_AT_LEFT:
          # 本对象在当前对象的左边
          break
        # 本对象在当前对象的右边
        insert_index += 1
        break
      scene_objects_sorted.insert(insert_index, obj)

    # 先把已在场上的对象放进去
    for obj in scene_objects_existing:
      if obj.pos.manual_pos is not None:
        raise PPInternalError("Position is manual but is not already in scene")
      prev_order = existing_obj_orders.get(obj)
      if prev_order is None:
        raise PPInternalError("Object is not in scene???")
      add_obj_to_scene(obj, prev_order)
    # 再把新上场的对象放进去
    for obj in scene_objects_new:
      if obj.pos.manual_pos is not None:
        raise PPInternalError("Position is manual but is not already in scene")
      prev_order = -1 if self.OPTION_OVERLAPPING_NEW_OBJECT_AT_LEFT else len(scene_objects_sorted)
      add_obj_to_scene(obj, prev_order)

    # 第三步：给每个 X 轴可变的对象决定一个最终的目标位置
    # 我们把固定位置的对象作为锚点，把屏幕的 X 轴分成若干个区间，每个区间单独计算
    # 每个区间内，我们根据区间内对象的宽度来分配空余空间
    objs_with_position_changed : list[VNCodeGen_Placer.ObjectInfo] = []
    def handle_interval(startx : int, starthw : int, endx : int, endhw : int, interval_start : int, interval_end : int):
      # startx, endx 是区间的左右边界，starthw, endhw 是区间内对象的宽度（基本上就是整个对象宽度的一半）
      # interval 是该区间内的对象在 scene_objects_sorted 中的下标
      widths = [scene_objects_sorted[i].pos.bbox_x[1] - scene_objects_sorted[i].pos.bbox_x[0] for i in range(interval_start, interval_end)]
      total_obj_width = sum(widths)
      # 如果区间内的对象宽度之和大于区间长度，我们需要将对象挤在一起，按照宽度比例来分配空间
      # 如果区间内的对象宽度之和小于区间长度，我们将剩余空间平均分配给每个对象
      ratio = (endx - startx) / (total_obj_width + starthw + endhw)
      extraspace = 0
      is_qually_distribute_space = ratio >= 1
      if ratio > 1:
        extraspace = (endx - startx) - (total_obj_width + starthw + endhw)
        extraspace = int(extraspace / (interval_end - interval_start + 1))
      cumulative_x_offset = starthw
      for index in range(0, len(widths)): # pylint: disable=consider-using-enumerate
        obj = scene_objects_sorted[index + interval_start]
        cur_width = widths[index]
        if is_qually_distribute_space:
          cur_offset = cumulative_x_offset + extraspace + cur_width / 2
          obj_center_x = cur_offset + startx
          cumulative_x_offset += cur_width + extraspace
        else:
          cur_offset = cumulative_x_offset + cur_width / 2
          obj_center_x = cur_offset * ratio + startx
          cumulative_x_offset += cur_width
        new_x = int(obj_center_x - cur_width / 2 - obj.pos.bbox_x[0])
        if obj.pos.x != new_x:
          objs_with_position_changed.append(scene_objects_sorted[index + interval_start])
        obj.pos.x = new_x
    startx = 0
    starthw = 0
    interval_start = 0
    boundary_ratio = ((3 - math.sqrt(5)) / 2) / 4 # (1-0.618)/4
    assert boundary_ratio >= 0 and boundary_ratio < 0.5
    for i in range(0, len(scene_objects_sorted)): # pylint: disable=consider-using-enumerate
      obj = scene_objects_sorted[i]
      if obj.pos.manual_pos is not None:
        # 我们将该对象视为锚点，计算前面的区间
        obj_center_x = int(obj.pos.manual_pos.x_abs.value + (obj.pos.bbox_x[0] + obj.pos.bbox_x[1]) / 2)
        obj_hw = int((obj.pos.bbox_x[1] - obj.pos.bbox_x[0]) / 2)
        if interval_start < i:
          # 如果左边缘不是由另一个对象决定的而是屏幕边缘，我们在这里更新 starthw 使其为总长的一个比例
          if startx == 0 and starthw == 0:
            starthw = int((obj_center_x - startx) * boundary_ratio)
          handle_interval(startx, starthw, obj_center_x, obj_hw, interval_start, i)
        interval_start = i + 1
        startx = obj_center_x
        starthw = obj_hw
    if interval_start < len(scene_objects_sorted):
      # 还剩下最后一个区间
      endhw = int((self._screen_width - startx) * boundary_ratio)
      if startx == 0 and starthw == 0:
        starthw = endhw
      handle_interval(startx, starthw, self._screen_width, endhw, interval_start, len(scene_objects_sorted))
    # 开始写回位置信息
    # 对于新指令，如果现在的事件中有对象上场，则插入到该对象的指令之前，否则插入到最后
    insertpos : VNInstruction | None = None
    for event in self._pending_events:
      if isinstance(event.instr, VNPlacementInstBase):
        insertpos = event.instr
        break
    new_instr_info : list[tuple[typing.Any, Value, VNInstruction | None]] = []
    # 只有(1)没有涉及事件，(2)自动计算的位置也与原来不同，才不需要新指令或设置新的位置
    # 其他情况都需要新指令或设置新的位置
    if self._cur_scene is None:
      raise PPInternalError("Current scene is not set")
    for obj in scene_objects_sorted:
      match obj.ty:
        case VNCodeGen_Placer.HandleType.CHARACTER:
          self._cur_scene.set_character_position(obj.handle, obj.pos)
        case VNCodeGen_Placer.HandleType.IMAGE:
          self._cur_scene.set_asset_position(obj.handle, obj.pos)
        case _:
          raise PPInternalError("Unhandled object type")
      if obj.event is not None:
        # 该对象有事件，我们需要给事件添加位置信息
        if isinstance(obj.event.instr, (VNPlacementInstBase, VNModifyInst)):
          # 该事件是入场或移动事件，我们需要给其添加位置信息
          position = obj.pos.get_position_value(context=self.context)
          symb = VNPositionSymbol.create(context=self.context, name=VNPositionSymbol.NAME_SCREEN2D, position=position, loc=obj.event.instr.location)
          obj.event.instr.placeat.add(symb)
        # 如果是退场事件，我们不需要额外处理
        # 该对象处理完毕
        continue
      # 该对象没有事件
      if obj in objs_with_position_changed:
        # 该对象的位置发生了变化，我们需要添加新指令
        new_instr_info.append((obj.handle, obj.pos.get_position_value(context=self.context), insertpos))
    # 重置状态
    self._scene_objects.clear()
    self._pending_events.clear()
    return new_instr_info if len(new_instr_info) > 0 else None
