# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *
from .vnfunction import *
from .vnasset import *
from .vnrecord import *

class VNNamespace(Operation, Value):
  _function_region : SymbolTableRegion
  _asset_region : SymbolTableRegion # region for VNAsset
  _device_region : SymbolTableRegion # region for VNDeviceRecord
  _variable_region : SymbolTableRegion # region for VNVariableRecord
  _character_region : SymbolTableRegion # region for VNCharacterRecord
  _record_region : SymbolTableRegion # region for misc records

  def __init__(self, name: str, loc: Location, parent : VNNamespace) -> None:
    ty = VNNamespaceReferenceType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty)
    self._add_operand_with_value('parent', parent)
    self._function_region = self._add_symbol_table('functions')
    self._asset_region = self._add_symbol_table('assets')
    self._device_region = self._add_symbol_table('devices')
    self._variable_region = self._add_symbol_table('variables')
    self._character_region = self._add_symbol_table('characters')
    self._record_region = self._add_symbol_table('records')
  
  def get_function(self, name: str) -> VNFunction:
    return self._function_region.get(name)
  
  def get_asset(self, name : str) -> VNAsset:
    return self._asset_region.get(name)
  
  def get_device(self, name : str) -> VNDeviceRecord:
    return self._device_region.get(name)
  
  def get_variable(self, name : str) -> VNVariableRecord:
    return self._variable_region.get(name)

  def get_character(self, name : str) -> VNCharacterRecord:
    return self._character_region.get(name)
  
  def get_record(self, name: str) -> VNRecord:
    return self._record_region.get(name)
  
  def get_or_create_predefined_device(self, name: str) -> VNDeviceRecord:
    result = self.get_device(name)
    if result is None:
      result = VNDeviceRecord.create_predefined_device(self, name)
      if result is not None:
        self._device_region.add(result)
    return result

  def parent_namespace(self) -> VNNamespace:
    # the inherited parent attribute is the parent block for the operation
    # use this function to get the parent namespace
    return self.get_operand('parent')
  
  #def _check_location_value(self, path : str | DIFile) -> DIFile:
  #  if isinstance(path, str):
  #    return self.context.get_DIFile(path)
  #  if isinstance(path, Location):
  
  def _asset_add_common(self, path : str, name : str, loc : Location) -> Location:
    if name in self._asset_region:
      raise RuntimeError("Asset with same name already exist:" + name)
    if loc is not None:
      assert loc.context is self.location.context
    else:
      # create loc from file path
      loc = self.context.get_DIFile(path)
    return loc
  
  def add_image_asset_from_file(self, path : str, name : str, loc : Location = None) -> VNImageAsset:
    loc = self._asset_add_common(self, path, name, loc)
    result = VNImageAsset.getFromFile(path, name, loc)
    self._asset_region.add(result)
    return result

  def add_audio_asset_from_file(self, path : str, name : str, loc : Location = None) -> VNAudioAsset:
    loc = self._asset_add_common(self, path, name, loc)
    result = VNAudioAsset.getFromFile(path, name, loc)
    self._asset_region.add(result)
    return result
  
  def add_character(self, name : str, loc : Location = None) -> VNCharacterRecord:
    assert name not in self._character_region
    if loc is not None:
      assert loc.context is self.context
    else:
      loc = Location.getNullLocation(self.context)
    result = VNCharacterRecord(name, loc)
    self._character_region.add(result)
    return result

  def add_function(self, name : str, loc : Location = None) -> VNFunction:
    assert name not in self._function_region
    if loc is not None:
      assert loc.context is self.context
    else:
      loc = Location.getNullLocation(self.context)
    result = VNFunction(name, loc)
    self._function_region.add(result)
    return result
    
