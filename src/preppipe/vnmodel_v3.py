# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import os
import io
import pathlib
import typing
import PIL.Image
import pydub
import pathlib
import enum
from enum import Enum

from .commontypes import *
from .irbase import *
from vnmodel.vntype import *
  
class VNNamespace(Operation, Value):
  _function_region : Region
  _record_region : Region
  _asset_region : Region

  def __init__(self, name: str, loc: Location) -> None:
    ty = VNNamespaceReferenceType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty)
    self._function_region = self._add_region('functions')
    self._record_region = self._add_region('records')
    self._asset_region = self._add_region('assets')

class VNModel(Operation):
  _namespace_region : SymbolTableRegion
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._namespace_region = self._add_symbol_table('namespaces')
  

