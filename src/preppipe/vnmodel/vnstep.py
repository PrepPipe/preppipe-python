# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNStep(Operation):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNRegularStep(VNStep):
  _body : Block

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

    time_type = VNTimeOrderType.get(loc.context)
    r = self._add_region()
    self._body = Block('', loc.context)
    r.push_back(self._body)
    self._body.add_argument(time_type)
  
  @property
  def body(self) -> Block:
    return self._body

class VNCallStep(VNStep):
  _callee : OpOperand
  def __init__(self, name: str, loc: Location, callee : Value = None, **kwargs) -> None:
    if callee is not None:
      assert isinstance(callee.valuetype, VNFunctionReferenceType)
    super().__init__(name, loc, **kwargs)
    self._callee = self._add_operand_with_value("调用目标", callee)
  
  @property
  def callee(self) -> Value:
    return self._callee.get()
  
  @callee.setter
  def callee(self, v : Value) -> None:
    assert isinstance(v.valuetype, VNFunctionReferenceType)
    self._callee.set_operand(0, v)

class VNReturnStep(VNStep):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._set_is_terminator()

class VNMenuStep(VNStep):
  # a step that pops up menu.
  # non-menu logic (everything after clicking a button) is not included in a menu step
  pass

class VNParallelStep(VNStep):
  pass