# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import enum

from ..irbase import *
from .vntype import *
from .vnconstant import *

class VNRecord(Operation):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNDeviceRecord(VNRecord, Value):
  _path : VNDevicePath
  _element_type : VNType
  def __init__(self, name: str, loc: Location, path: VNDevicePath, element_type : VNType, **kwargs) -> None:
    ty = VNDeviceReferenceType.get(element_type)
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)
    self._path = path
    self._element_type = element_type
    assert isinstance(self._path.valuetype, VNDevicePathType)
    assert isinstance(element_type, VNType)
  
  @property
  def path(self) -> VNDevicePath:
    return self._path
  
  @property
  def element_Type(self) -> VNType:
    return self._element_type


class VNVariableRecord(VNRecord, Value):
  class StorageModel(enum.Enum):
    Global = 0, # per-player/account/.. state; all savings share the same copy
    ThreadLocal = enum.auto() # per-saving state; each saving has its own copy
  
  _storage_model : StorageModel
  _data_type : VNType
  
  def __init__(self, name: str, loc: Location, ty : VNType, storage : StorageModel, **kwargs) -> None:
    reftype = VNVariableReferenceType.get(ty)
    super().__init__(name = name, loc = loc, ty = reftype, **kwargs)
    self._storage_model = storage
    self._data_type = ty
  
  @property
  def storage_model(self) -> StorageModel:
    return self._storage_model
  
  @property
  def variable_type(self) -> VNType:
    return self._data_type

class VNSelectorRecord(VNRecord):
  pass