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

    time_type = VNTimeType.get(loc.context)
    r = self._add_region()
    self._body = Block('', loc.context)
    r.push_back(self._body)
    self._body.add_argument(time_type)
  
  @property
  def body(self) -> Block:
    return self._body

class VNMenuStep(VNStep):
  # a step that pops up menu.
  # non-menu logic (everything after clicking a button) is not included in a menu step
  pass

class VNParallelStep(VNStep):
  pass