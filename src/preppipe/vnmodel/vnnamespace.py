# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNNamespace(Operation, Value):
  _function_region : Region
  _asset_region : Region # region for VNAsset
  _device_region : Region # region for VNDeviceRecord
  _variable_region : Region # region for VNVariableRecord
  _record_region : Region # region for misc records

  def __init__(self, name: str, loc: Location, parent : VNNamespace) -> None:
    ty = VNNamespaceReferenceType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty)
    self._add_operand_with_value('parent', parent)
    self._function_region = self._add_region('functions')
    self._asset_region = self._add_region('assets')
    self._device_region = self._add_region('devices')
    self._variable_region = self._add_region('variables')
    self._record_region = self._add_region('records')
    

  def parent_namespace(self) -> VNNamespace:
    # the inherited parent attribute is the parent block for the operation
    # use this function to get the parent namespace
    return self.get_operand('parent')