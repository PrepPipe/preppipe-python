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

  def __init__(self, name: str, loc: Location, parent : VNNamespace) -> None:
    ty = VNNamespaceReferenceType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty)
    self._add_operand_with_value('parent', parent)
    self._function_region = self._add_region('functions')
    self._record_region = self._add_region('records')
    self._asset_region = self._add_region('assets')

  def parent_namespace(self) -> VNNamespace:
    # the inherited parent attribute is the parent block for the operation
    # use this function to get the parent namespace
    return self.get_operand('parent')
  

