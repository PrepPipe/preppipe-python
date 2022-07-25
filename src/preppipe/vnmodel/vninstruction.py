# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNInstruction(Operation):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNTimeChainedInstruction(VNInstruction):
  # base class for all instructions that use time chain values
  _time_operand : OpOperand
  _time_result : OpResult

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._time_operand = self._add_operand('start_time')
    time_type = VNTimeType.get(loc.context)
    self._time_result = self._add_result('finish_time', time_type)
  
  @property
  def start_time(self) -> Value:
    return self._time_operand.get()
  
  @start_time.setter
  def start_time(self, time : Value):
    assert isinstance(time.valuetype, VNTimeType)
    self._time_operand.set_operand(0, time)
  
  @property
  def finish_time(self) -> OpResult:
    return self._time_operand

class VNBackendInstructionGroup(VNTimeChainedInstruction):
  pass

class VNSayInstructionGroup(VNTimeChainedInstruction):
  _character_operand : OpOperand
  _body : Block

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._character_operand = self._add_operand('character')
    time_type = VNTimeType.get(loc.context)
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

class VNShowInst(VNTimeChainedInstruction):
  # show instruction is for stateful displayable content. Returns a handle corresponding to the displayable type
  _device_operand : OpOperand # Device<Displayable>
  _content : OpOperand # Displayable
  
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._device_operand = self._add_operand('device')
    self._content = self._add_operand('content')
  
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
  
  