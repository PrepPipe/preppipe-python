# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNInstruction(Operation):
  # 所有VNModel中的指令的基类
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNTimeChainedInstruction(VNInstruction):
  # 所有使用时间链的指令的基类
  _time_operand : OpOperand
  _time_result : OpResult

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
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
  
  @property
  def finish_time(self) -> OpResult:
    # 取当前结束时间的值
    return self._time_operand

class VNBackendInstructionGroup(VNTimeChainedInstruction):
  pass

class VNSayInstructionGroup(VNTimeChainedInstruction):
  # 发言指令组，用于将单次人物发言的所有有关内容（说话者，说话内容，侧边头像，等等）组合起来的指令组
  # 基本上一个发言指令组对应回溯记录（Backlog）里的一条记录
  _character_operand : OpOperand
  _body : Block

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._character_operand = self._add_operand('character')
    time_type = VNTimeOrderType.get(loc.context)
    r = self._add_region()
    self._body = Block('', loc.context)
    r.push_back(self._body)
    self._body.add_argument(time_type)
  
  @property
  def character(self) -> Value:
    return self._character_operand.get()
  
  @character.setter
  def character(self, c : Value):
    assert c.valuetype is VNCharacterDeclType
    self._character_operand.set_operand(0, c)
  
  @property
  def body(self) -> Block:
    return self._body

class VNCreateInst(VNTimeChainedInstruction):
  # 设定一个可显示、播放的内容（音视频都含）并创建一个对该内容的句柄
  # 该内容直到使用消除指令前一直存在
  _device_operand : OpOperand # Device<Displayable>
  _content : OpOperand # Displayable
  
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._device_operand = self._add_operand('设备')
    self._content = self._add_operand('内容')
  
  @property
  def device(self) -> Value:
    return self._device_operand.get()
  
  @device.setter
  def device(self, d : Value):
    assert isinstance(d.valuetype, VNDeviceReferenceType)
    self._device_operand.set_operand(0, d)
  
  @property
  def content(self) -> Value:
    return self._content
  
  @content.setter
  def content(self, v : Value):
    assert isinstance(v.valuetype, VNDisplayableType)
    self._content.set_operand(0, v)
  
  