# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNFunction(Symbol, Value):
  _body: Region

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    ty = VNFunctionReferenceType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)
    self._body = self._add_region('body')
  
  @property
  def body(self) -> Region:
    return self._body
  
  
  
  

  
