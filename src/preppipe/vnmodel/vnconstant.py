# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNConstant(Value):
  _value : typing.Any
  def __init__(self, ty: ValueType, value : typing.Any, **kwargs) -> None:
    super().__init__(ty, **kwargs)
    self._value = value
  
  @property
  def value(self) -> typing.Any:
    return self._value
  
  def get_context(self) -> Context:
    return self.valuetype.context
  
  @staticmethod
  def _get_constant_impl(cls : type, value : typing.Any, context : Context) -> typing.Any:
    d = context.get_constant_uniquing_dict(cls)
    if value in d:
      return d[value]
    result = cls(context, value)
    d[value] = result
    return result
  
  @staticmethod
  def get(value: typing.Any, context : Context) -> typing.Any:
    if isinstance(value, int):
      return VNConstantInt.get(value, context)
    if isinstance(value, bool):
      return VNConstantBool.get(value, context)
    raise RuntimeError("Unknown value type for constant creation")
  
class VNConstantInt(VNConstant):
  def __init__(self, context : Context, value : int, **kwargs) -> None:
    # should not be called by user code
    assert isinstance(value, int)
    ty = VNIntType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> int:
    return super().value
  
  @staticmethod
  def get(value : int, context : Context) -> VNConstantInt:
    return VNConstant._get_constant_impl(VNConstantInt, value, context)

class VNConstantBool(VNConstant):
  def __init__(self, context : Context, value: bool, **kwargs) -> None:
    assert isinstance(value, bool)
    ty = VNBoolType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> bool:
    return super().value
  
  @staticmethod
  def get(value : bool, context : Context) -> VNConstantBool:
    return VNConstant._get_constant_impl(VNConstantBool, value, context)

class VNConstantString(VNConstant):
  def __init__(self, context : Context, value: str, **kwargs) -> None:
    assert isinstance(value, str)
    ty = VNStringType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> str:
    return super().value
  
  @staticmethod
  def get(value : str, context : Context) -> VNConstantString:
    return VNConstant._get_constant_impl(VNConstantString, value, context)

class VNDevicePath(VNConstantString):
  # all device paths are constant

  def __init__(self, context: Context, value: str, **kwargs) -> None:
    super().__init__(context, value, **kwargs)
  
  @staticmethod
  def get(value : str, context : Context) -> VNDevicePath:
    return VNConstant._get_constant_impl(VNDevicePath, value, context)
