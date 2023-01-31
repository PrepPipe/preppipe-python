# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *
from .vnconstant import *
from .vnrecord import *

class VNInstruction(Operation):
  # 所有VNModel中的指令的基类
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNTimeChainedInstruction(VNInstruction):
  # 所有使用时间链的指令的基类
  _time_operand : OpOperand
  _time_result : OpResult

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._time_operand = self._add_operand('开始时间')
    time_type = VNTimeOrderType.get(loc.context)
    self._time_result = self._add_result('结束时间', time_type)

  @property
  def start_time(self) -> Value:
    # 取当前开始时间的值
    return self._time_operand.get()

  @start_time.setter
  def start_time(self, time : Value):
    # 设置当前开始时间的值
    assert isinstance(time.valuetype, VNTimeOrderType)
    self._time_operand.set_operand(0, time)

  @start_time.deleter
  def start_time(self):
    self._time_operand.drop_all_uses()

  @property
  def finish_time(self) -> OpResult:
    # 取当前结束时间的值
    return self._time_operand

class VNTerminatorInstruction(VNInstruction):
  # 结尾指令的基类
  # 结尾指令都带一个时间输入但是没有时间输出
  _time_operand : OpOperand

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._time_operand = self._add_operand('开始时间')
    self._set_is_terminator()

  @property
  def start_time(self) -> Value:
    # 取当前开始时间的值
    return self._time_operand.get()

  @start_time.setter
  def start_time(self, time : Value):
    # 设置当前开始时间的值
    assert isinstance(time.valuetype, VNTimeOrderType)
    self._time_operand.set_operand(0, time)

  @start_time.deleter
  def start_time(self):
    self._time_operand.drop_all_uses()

class VNInstructionGroup(VNTimeChainedInstruction):
  # 指令组都只有一个块，由时间输入、输出，其他则由各指令组子类决定
  _body : Block
  _body_start_time_arg : BlockArgument

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    time_type = VNTimeOrderType.get(loc.context)
    r = self._add_region()
    self._body = Block('', loc.context)
    r.push_back(self._body)
    self._body_start_time_arg = self._body.add_argument('开始时间', time_type)

  @property
  def body(self) -> Block:
    return self._body

  @property
  def body_start_time(self) -> BlockArgument:
    return self._body_start_time_arg

class VNBackendInstructionGroup(VNInstructionGroup):
  # 后端指令组，用于放置一些后端独有的指令
  # 执行顺序、时间参数等均由后端决定
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNSayInstructionGroup(VNInstructionGroup):
  # 发言指令组，用于将单次人物发言的所有有关内容（说话者，说话内容，侧边头像，等等）组合起来的指令组
  # 基本上一个发言指令组对应回溯记录（Backlog）里的一条记录
  _characters_operand : OpOperand

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._characters_operand = self._add_operand('发言者')

  @property
  def characters(self) -> Value:
    return self._characters_operand.get()

  @characters.setter
  def characters(self, c : VNCharacterRecord | list[VNCharacterRecord]):
    if isinstance(c, list):
      # list of characters
      self._characters_operand.drop_all_uses()
      for v in c:
        assert isinstance(v, VNCharacterRecord)
        self._characters_operand.add_operand(v)
    else:
      # single character
      assert isinstance(c, VNCharacterRecord)
      self._characters_operand.set_operand(0, c)

  @characters.deleter
  def characters(self):
    self._characters_operand.drop_all_uses()

class VNFinishStepInst(VNTerminatorInstruction):
  # 结束指令结束该单步
  # 我们要求该指令的时间输入“汇聚”该块内其他时间输入
  # 如果有异步执行的内容，他们应该在独立的并行单步内

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNBranchInst(VNTerminatorInstruction):
  # 分支指令结束该块并跳转到相同单步的另一个块内
  # 若是要跳转出该单步，请使用远跳转指令
  # 分支指令可以有 N 个条件输入和 N+1 个目标块，先判断到哪个条件成立就跳转到对应目标块，最后一个目标块是当前面所有条件都不成立时采用的目标
  # 条件判断输入是逻辑值，一般由求值指令计算
  _default_destination_operand : OpOperand # 1个对目标块的引用
  _conditions_operand : OpOperand # 0-N 个逻辑型值
  _candidate_destinations_operand : OpOperand # 0-N 个对目标块的引用

  def __init__(self, name: str, loc: Location, default_target : Block, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._default_destination_operand = self._add_operand_with_value('默认目标块', default_target)
    self._conditions_operand = self._add_operand('条件列表')
    self._candidate_destinations_operand = self._add_operand('目标块列表')

  @property
  def default_destination(self) -> Block:
    return self._default_destination_operand.get()

  @default_destination.setter
  def default_destination(self, b : Block):
    assert isinstance(b, Block)
    self._default_destination_operand.set_operand(0, b)

  @default_destination.deleter
  def default_destination(self):
    self._default_destination_operand.drop_all_uses()

  @property
  def num_candidates(self) -> int:
    return self._conditions_operand.get_num_operands()

  def add_candidate_destination(self, condition : Value, target : Block):
    assert isinstance(condition.valuetype, VNBoolType)
    assert isinstance(target, Block)
    self._conditions_operand.add_operand(condition)
    self._candidate_destinations_operand.add_operand(target)

  def get_candidate(self, index : int) -> tuple[Value, Block]:
    condition = self._conditions_operand.get_operand(index)
    target = self._candidate_destinations_operand.get_operand(index)
    return (condition, target)

  def set_candidate(self, index : int, condition : Value, target : Block):
    assert isinstance(condition.valuetype, VNBoolType)
    assert isinstance(target, Block)
    self._conditions_operand.set_operand(index, condition)
    self._candidate_destinations_operand.set_operand(index, target)


class VNFarJumpInst(VNTerminatorInstruction):
  # 远跳转指令结束当前单步并跳转到另一个（函数层级的）块内
  # 远跳转指令没有有条件跳转的类型，若是要根据情况跳转到不同的上层块内，请在单步内创建多个块，并在这些块内使用远跳转。

  _destination_operand : OpOperand # 1个对目标块的引用

  def __init__(self, name: str, loc: Location, target : Block, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._destination_operand = self._add_operand_with_value('目标块', target)

  @property
  def destination(self) -> Block:
    return self._destination_operand.get()

  @destination.setter
  def destination(self, b : Block):
    assert isinstance(b, Block)
    self._destination_operand.set_operand(0, b)

  @destination.deleter
  def destination(self):
    self._destination_operand.drop_all_uses()

class VNWaitUserInst(VNTimeChainedInstruction):
  # 等待用户指令一般接在发言指令组之后，表述等待用户阅读完毕、通过点击等方式进入下一步的动作
  # 我们默认所有的发言指令组都没有等待用户的语义，只有在等待用户指令存在时才会有该语义
  # 若用于发言指令组，一般我们把等待用户指令放在发言指令组**内**，方便后端生成后端指令
  # 该指令也可以放在发言指令组外，比如可以通过该指令给动画加入间隔

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)


class VNContentManipulationInst(VNTimeChainedInstruction):
  # 任何创建、修改输出内容的指令都继承该类
  # 共用的参数：变体、过渡
  _variant_operand : OpOperand
  _transition_operand : OpOperand

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._variant_operand = self._add_operand('变体')
    self._transition_operand = self._add_operand('过渡')

  @property
  def variant(self) -> Value:
    return self._variant_operand.get()

  @variant.setter
  def variant(self, v : Value):
    self._variant_operand.set_operand(0, v)

  @variant.deleter
  def variant(self):
    self._variant_operand.drop_all_uses()

  @property
  def transition(self) -> Value:
    return self._transition_operand.get()

  @transition.setter
  def transition(self, v : Value):
    if not isinstance(v.valuetype, VNEffectFunctionType):
      raise RuntimeError('无效的值类型')
    self._transition_operand.set_operand(0, v)

  @transition.deleter
  def transition(self):
    self._transition_operand.drop_all_uses()

class VNContentRemovalInst(VNTimeChainedInstruction):
  # 任何移除特定内容的指令都继承该类
  # 共用的参数：过渡

  _transition_operand : OpOperand

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._transition_operand = self._add_operand('过渡')

  @property
  def transition(self) -> Value:
    return self._transition_operand.get()

  @transition.setter
  def transition(self, v : Value):
    if not isinstance(v.valuetype, VNEffectFunctionType):
      raise RuntimeError('无效的值类型')
    self._transition_operand.set_operand(0, v)

  @transition.deleter
  def transition(self):
    self._transition_operand.drop_all_uses()

class VNCreateInst(VNTimeChainedInstruction):
  # 设定一个可显示、播放的内容（音视频都含）并创建一个对该内容的句柄
  # 该内容直到使用消除指令前一直存在
  # 这是创建指令的基类，子类应该根据不同的内容类型（图片、音乐等）添加相应的输入与类型检查
  _content_operand : OpOperand # Displayable | AudioType | ...
  _handle : OpResult

  def __init__(self, name: str, loc: Location, content_type : VNType, content : Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    handle_type = VNHandleType.get(content_type)
    self._content_operand = self._add_operand_with_value('内容', content)
    self._handle = self._add_result('句柄', handle_type)

  @property
  def device(self) -> VNDeviceRecord:
    content = self.content
    if content is not None:
      return content.device
    return None

  # 子类应该覆盖以下属性来添加正确的类型检查

  @property
  def content(self) -> Value:
    return self._content_operand

  @content.setter
  def content(self, v : Value):
    self._content_operand.set_operand(0, v)

  @content.deleter
  def content(self):
    self._content_operand.drop_all_uses()

  @property
  def handle(self) -> OpResult:
    return self._handle

class VNModifyInst(VNTimeChainedInstruction):
  # 修改指令取一个句柄，并对内容或其他属性作出修改
  # 句柄属于SSA值，但是修改指令对句柄所指内容的修改不算为值的定义、不作为SSA中的定义
  _handle_operand : OpOperand # 句柄类型

  def __init__(self, name: str, loc: Location, handle : Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._handle_operand = self._add_operand_with_value('句柄', handle)

  @property
  def handle(self) -> Value:
    return self._handle_operand.get()

  @handle.setter
  def handle(self, h : Value):
    self._handle_operand.set_operand(0, h)

  @handle.deleter
  def handle(self):
    self._handle_operand.drop_all_uses()

class VNPutInst(VNTimeChainedInstruction):
  # 放置指令会在目标设备上创建一个内容，但是与创建指令不同，该指令不返回句柄
  # 放置指令创建的内容的有效期由设备、环境等决定，而不是由程序显式地去移除
  # 常用的场景如在发言指令组内设置头像、发言内容等，有效期到下一条发言为止
  # 如需要播放音频，放置指令将在设备上当前播放的内容结束后播放
  _content_operand : OpOperand

  def __init__(self, name: str, loc: Location, content : Value, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._content_operand = self._add_operand_with_value('内容', content)

  @property
  def device(self) -> VNDeviceRecord:
    content = self.content
    if content is not None:
      return content.device
    return None

  @property
  def content(self) -> Value:
    return self._content_operand

  @content.setter
  def content(self, v : Value):
    self._content_operand.set_operand(0, v)

  @content.deleter
  def content(self, v : Value):
    self._content_operand.drop_all_uses()

class VNDisplayableManipulationInst(VNContentManipulationInst):
  # 所有修改可显示项的指令都继承该类
  # 这个类不应该被独立使用，任何子类都应该同时继承创建、修改、放置指令中的一种
  # 除了继承的变体、过渡之外，该类定义了如下可用于可显示项的输入：
  # 1. 位置：一个描述内容所处位置的引用，屏幕坐标类型（VNScreenCoordinateType）
  # 2. 纵向顺序（zorder）：整数
  # 3. 特效：特效函数类型
  _position_operand : OpOperand
  _zorder_operand : OpOperand
  _effect_operand : OpOperand

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._position_operand = self._add_operand('位置')
    self._zorder_operand = self._add_operand('纵向顺序')
    self._effect_operand = self._add_operand('特效')

  @property
  def position(self) -> Value:
    return self._position_operand.get()

  @position.setter
  def position(self, v : Value):
    if not isinstance(v.valuetype, VNScreenCoordinateType):
      raise RuntimeError('类型错误')
    self._position_operand.set_operand(0, v)

  @position.deleter
  def position(self):
    self._position_operand.drop_all_uses()

  @property
  def zorder(self) -> int | None:
    zorder = self._zorder_operand.get()
    if zorder is None:
      return None
    if isinstance(zorder, VNConstantInt):
      return zorder.value
    raise RuntimeError('无效的值类型')

  @zorder.setter
  def zorder(self, v : int | VNConstantInt):
    value : VNConstantInt = None
    if isinstance(v, int):
      value = VNConstantInt.get(v, self.context)
    elif isinstance(v, VNConstantInt):
      value = v
    else:
      raise RuntimeError('无效的值类型')
    self._zorder_operand.set_operand(0, value)

  @zorder.deleter
  def zorder(self):
    self._zorder_operand.drop_all_uses()

  @property
  def effect(self):
    return self._effect_operand.get()

  @effect.setter
  def effect(self, v : Value):
    if not isinstance(v.valuetype, VNEffectFunctionType):
      raise RuntimeError('无效的值类型')
    self._effect_operand.set_operand(0, v)

  @effect.deleter
  def effect(self):
    self._effect_operand.drop_all_uses()

class VNAudioManipulationInst(VNContentManipulationInst):
  # 与 VNDisplayableManipulationInst 对应的、创建或修改音频内容的指令的基类
  # 1. 相对音量（浮点数）（基准值为音源给定的音量）
  # 2. 播放速度（浮点数，1：正常速度；0：暂停；2：两倍速）（一般我们只使用 0 和 1（暂停/正常播放）两个值）
  # 部分播放特性（即不播放音频的全部内容，而是指定时间区间内的内容）将由音源（或者说音频内容）实现
  # 音频循环与否也由音源决定，我们不在该指令中包含这个信息
  # 音源也可以设置音量，若要平衡多个声音的音量，最好的方式是在音源设置音量系数。该指令内的相对音量仅用于控制播放时的音量改变。将由音源设定，我们不将其包含在该指令内
  _volume_operand : OpOperand
  _playback_speed_operand : OpOperand

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._volume_operand = self._add_operand('音量')
    self._playback_speed_operand = self._add_operand('播放速度')

  @property
  def volume(self) -> float | None:
    v = self._volume_operand.get()
    if v is None:
      return None
    if isinstance(v, VNConstantFloat):
      return v.value
    raise RuntimeError('无效类型')

  @volume.setter
  def volume(self, v : float | VNConstantFloat):
    value : VNConstantFloat = None
    if isinstance(v, float):
      value = VNConstantFloat.get(v, self.context)
    elif isinstance(v, VNConstantFloat):
      value = v
    else:
      raise RuntimeError('无效类型')
    self._volume_operand.set_operand(0, value)

  @volume.deleter
  def volume(self):
    self._volume_operand.drop_all_uses()

  @property
  def playback_speed(self) -> float | None:
    v = self._playback_speed_operand.get()
    if v is None:
      return None
    if isinstance(v, VNConstantFloat):
      return v.value
    raise RuntimeError('无效类型')

  @playback_speed.setter
  def playback_speed(self, v : float | VNConstantFloat):
    value : VNConstantFloat = None
    if isinstance(v, float):
      value = VNConstantFloat.get(v, self.context)
    elif isinstance(v, VNConstantFloat):
      value = v
    else:
      raise RuntimeError('无效类型')
    self._playback_speed_operand.set_operand(0, value)

  @playback_speed.deleter
  def playback_speed(self):
    self._playback_speed_operand.drop_all_uses()

class VNTextManipulationInst(VNContentManipulationInst):
  # 创建或修改文本内容的指令的基类
  # 呃目前对文本内容没有任何额外的参数需要设置

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)

class VNRemoveInst(VNContentRemovalInst):
  # 移除指令取一个句柄，从设备上移除所标注的内容
  # 移除指令执行后，该句柄值不应再被使用
  # 不管内容是什么类型，移除指令都只接受一过渡效果输入
  # 区别于创建、修改、放置指令，移除指令不应被当做根据内容而特化的指令的基类；直接使用该指令即可

  _handle_operand : OpOperand # 句柄类型

  def __init__(self, name: str, loc: Location, handle : Value, transition : Value = None, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._handle_operand = self._add_operand_with_value('句柄', handle)

  @property
  def handle(self) -> Value:
    return self._handle_operand.get()

  @handle.setter
  def handle(self, h : Value):
    self._handle_operand.set_operand(0, h)

  @handle.deleter
  def handle(self):
    self._handle_operand.drop_all_uses()

class VNClearInst(VNContentRemovalInst):
  # 清空指令将清空所选设备上的所有内容，创建指令和放置指令创建的内容都将被该指令清除。
  _device_operand : OpOperand

  def __init__(self, name: str, loc: Location, device : Value, transition: Value = None, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._device_operand = self._add_operand_with_value('设备', device)

  @property
  def device(self) -> Value:
    return self._device_operand.get()

  @device.setter
  def device(self, d : Value):
    assert isinstance(d.valuetype, VNDeviceReferenceType)
    self._device_operand.set_operand(0, d)

  @device.deleter
  def device(self):
    self._device_operand.drop_all_uses()

class VNCreateDisplayableInst(VNCreateInst, VNDisplayableManipulationInst):
  # 创建可显示项指令

  def __init__(self, name: str, loc: Location, content: Value, **kwargs) -> None:
    content_type = VNDisplayableType.get(loc.context)
    super().__init__(name = name, loc = loc, content_type = content_type, content = content, **kwargs)

  @VNCreateInst.content.setter
  def content(self, v : Value):
    if not isinstance(v.valuetype, VNDisplayableType):
      raise RuntimeError("类型错误")
    self._content_operand.set_operand(0, v)

class VNPutDisplayableInst(VNPutInst, VNDisplayableManipulationInst):
  # 放置可显示项指令

  def __init__(self, name: str, loc: Location, content: Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, content = content, **kwargs)

  @VNPutInst.content.setter
  def content(self, v : Value):
    if not isinstance(v.valuetype, VNDisplayableType):
      raise RuntimeError("类型错误")
    self._content_operand.set_operand(0, v)

class VNModifyDisplayableInst(VNModifyInst, VNDisplayableManipulationInst):
  # 修改可显示项指令

  def __init__(self, name: str, loc: Location, handle: Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, handle = handle, **kwargs)


class VNCreateAudioInst(VNCreateInst, VNAudioManipulationInst):
  # 创建音频项指令

  def __init__(self, name: str, loc: Location, content: Value, **kwargs) -> None:
    content_type = VNAudioType.get(loc.context)
    super().__init__(name = name, loc = loc, content_type = content_type, content = content, **kwargs)

  @VNCreateInst.content.setter
  def content(self, v : Value):
    if not isinstance(v.valuetype, VNAudioType):
      raise RuntimeError("类型错误")
    self._content_operand.set_operand(0, v)

class VNPutAudioInst(VNPutInst, VNAudioManipulationInst):

  def __init__(self, name: str, loc: Location, content: Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, content = content, **kwargs)

  @VNPutInst.content.setter
  def content(self, v : Value):
    if not isinstance(v.valuetype, VNAudioType):
      raise RuntimeError("类型错误")
    self._content_operand.set_operand(0, v)

class VNModifyAudioInst(VNModifyInst, VNAudioManipulationInst):
  def __init__(self, name: str, loc: Location, handle: Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, handle = handle, **kwargs)

class VNPutTextInst(VNPutInst, VNTextManipulationInst):
  # 放置文本指令
  # 写这则注释时我们尚不需要创建、修改文本指令

  def __init__(self, name: str, loc: Location, content: Value, **kwargs) -> None:
    super().__init__(name, loc, content, **kwargs)

  @VNPutInst.content.setter
  def content(self, v : Value):
    if not isinstance(v.valuetype, VNTextType):
      raise RuntimeError("类型错误")
    self._content_operand.set_operand(0, v)
