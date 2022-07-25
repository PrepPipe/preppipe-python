# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *

class VNType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def is_int_type(self) -> bool:
    return isinstance(self, VNIntType)
  
  def is_bool_type(self) -> bool:
    return isinstance(self, VNBoolType)
  
  def is_string_type(self) -> bool:
    return isinstance(self, VNStringType)

  def is_text_type(self) -> bool:
    return isinstance(self, VNTextType)

class VNParameterizedType(VNType):
  # parameterized types are considered different if the parameters (can be types or literal values) are different
  _parameters : typing.List[VNType | int | str | bool | None] # None for separator

  def __init__(self, context: Context, parameters : typing.Iterable[VNType | int | str | bool | None]) -> None:
    super().__init__(context)
    self._parameters = list(parameters)
  
  @staticmethod
  def _get_parameter_repr(parameters : typing.List[VNType | int | str | bool | None]):
    result = ''
    isFirst = True
    for v in parameters:
      if isFirst:
        isFirst = False
      else:
        result += ', '
      if isinstance(v, VNType):
        result += repr(v)
      elif isinstance(v, str):
        result += '"' + v + '"'
      elif v is None:
        # this is a separator
        result += '---'
      else: # int or bool
        result += str(v)
    return result

  def __repr__(self) -> str:
    return  type(self).__name__ + '<' + VNParameterizedType._get_parameter_repr(self._parameters) + '>'

class VNIntType(VNType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "int"
  
  @staticmethod
  def get(ctx : Context) -> VNIntType:
    return ctx.get_stateless_type(VNIntType)

class VNBoolType(VNType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "bool"
  
  @staticmethod
  def get(ctx : Context) -> VNBoolType:
    return ctx.get_stateless_type(VNBoolType)
  
class VNStringType(VNType):
  # any string
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "string"
  
  @staticmethod
  def get(ctx : Context) -> VNStringType:
    return ctx.get_stateless_type(VNStringType)

class VNDisplayableType(VNType):
  # image, text, or anything that has a visual display
  def __init__(self, context: Context) -> None:
    super().__init__(context)

  def __str__(self) -> str:
    return "Displayable"
  
  # no other members

class VNTextType(VNDisplayableType):
  # string + style (style can be empty)
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "Text"
  
  @staticmethod
  def get(ctx : Context) -> VNTextType:
    return ctx.get_stateless_type(VNTextType)

class VNImageType(VNDisplayableType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "Image"
  
  @staticmethod
  def get(ctx : Context) -> VNImageType:
    return ctx.get_stateless_type(VNImageType)

class VNAudioType(VNType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "Audio"
  
  @staticmethod
  def get(ctx : Context) -> VNAudioType:
    return ctx.get_stateless_type(VNAudioType)

class VNTimeType(VNType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "Time"
  
  @staticmethod
  def get(ctx : Context) -> VNTimeType:
    return ctx.get_stateless_type(VNTimeType)

class VNNamespaceReferenceType(VNType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "NamespaceRef"
  
  @staticmethod
  def get(ctx : Context) -> VNNamespaceReferenceType:
    return ctx.get_stateless_type(VNNamespaceReferenceType)

class VNDevicePathType(VNType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "DevicePath"
  
  @staticmethod
  def get(ctx : Context) -> VNDevicePathType:
    return ctx.get_stateless_type(VNDevicePathType)

class VNDeviceReferenceType(VNParameterizedType):
  _data_type : VNType # what kinds of data can be written to the device

  def __init__(self, data_type : VNType) -> None:
    super().__init__(data_type.context, [data_type])
    self._data_type = data_type
  
  @property
  def element_type(self) -> VNType:
    return self._data_type
  
  def __str__(self) -> str:
    return "Device<" + str(self._data_type) + ">"
  
  @staticmethod
  def get(data_type : VNType) -> VNDeviceReferenceType:
    assert not isinstance(data_type, VNDeviceReferenceType)
    reprstr = VNParameterizedType._get_parameter_repr([data_type])
    d = data_type.context.get_parameterized_type_dict(VNDeviceReferenceType)
    if reprstr in d:
      return d[reprstr]
    result = VNDeviceReferenceType(data_type)
    d[reprstr] = result
    return result
  
class VNHandleType(VNParameterizedType):
  # handles for persistent instances (image/audio/video/text)
  # corresponding values are created when using show instructions
  _data_type : VNType

  def __init__(self, data_type : VNType) -> None:
    super().__init__(data_type.context, [data_type])
    self._data_type = data_type
  
  @property
  def element_type(self) -> VNType:
    return self._data_type
  
  def __str__(self) -> str:
    return "Handle<" + str(self._data_type) + ">"
  
  @staticmethod
  def get(data_type : VNType) -> VNHandleType:
    assert not isinstance(data_type, VNHandleType)
    reprstr = VNParameterizedType._get_parameter_repr([data_type])
    d = data_type.context.get_parameterized_type_dict(VNHandleType)
    if reprstr in d:
      return d[reprstr]
    result = VNHandleType(data_type)
    d[reprstr] = result
    return result

class VNOptionalType(VNParameterizedType):
  # dependent type that is optional of the specified type
  # likely used for a PHI for handles
  _depend_type : VNType

  def __init__(self, ty : VNType) -> None:
    super().__init__(ty.context, [ty])
    self._depend_type = ty
  
  def __str__(self) -> str:
    return "Optional<" + str(self._depend_type) + ">"
  
  @property
  def element_type(self) -> VNType:
    return self._depend_type

  @staticmethod
  def get(ty : VNType) -> VNOptionalType:
    # skip degenerate case
    if isinstance(ty, VNOptionalType):
      return ty
    ctx = ty.context
    reprstr = VNParameterizedType._get_parameter_repr([ty])
    d = ctx.get_parameterized_type_dict(VNOptionalType)
    if reprstr in d:
      return d[reprstr]
    result = VNOptionalType(ty)
    d[reprstr] = result
    return result

class VNCharacterDeclType(VNType):
  # for character identity

  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "CharacterDecl"
  
  @staticmethod
  def get(ctx : Context) -> VNCharacterDeclType:
    return ctx.get_stateless_type(VNCharacterDeclType)

class VNDataFunctionType(VNType):
  # the function type for data evaluation
  _return_type : tuple[VNType] # tuple of zero or more types
  _argument_type : tuple[VNType] # tuple of zero or more types
  
  def __init__(self, context: Context, args : tuple[VNType], returns : tuple[VNType]) -> None:
    super().__init__(context, [*returns, None, *args])
    self._argument_type = args
    self._return_type = returns
    for arg in self._argument_type:
      assert isinstance(arg, VNType)
    for arg in self._return_type:
      assert isinstance(arg, VNType)
  
  def __str__(self) -> str:
    return_type_str = 'void'
    if len(self._return_type) > 0:
      if len(self._return_type) == 1:
        return_type_str = str(self._return_type[0])
      else:
        return_type_str = '<' + ', '.join([str(x) for x in self._return_type]) + '>'
    arg_type_str = '(' + ', '.join([str(x) for x in self._argument_type]) + ')'
    return return_type_str + arg_type_str
  
  @staticmethod
  def get(ctx: Context, args : typing.Iterable[VNType], returns : typing.Iterable[VNType]) -> VNDataFunctionType:
    argument_tuple = tuple(args)
    return_tuple = tuple(returns)
    d = ctx.get_parameterized_type_dict(VNDataFunctionType)
    key = VNParameterizedType._get_parameter_repr([*return_tuple, None, *argument_tuple])
    if key in d:
      return d[key]
    result = VNDataFunctionType(ctx, args, returns)
    d[key] = result
    return result

class VNVariableReferenceType(VNParameterizedType):
  _variable_type : VNType

  def __init__(self, variable_type : VNType) -> None:
    super().__init__(variable_type.context, [variable_type])
    self._variable_type = variable_type
  
  @property
  def variable_type(self) -> VNType:
    return self._variable_type
  
  @staticmethod
  def get(variable_type : VNType) -> VNVariableReferenceType:
    assert not isinstance(variable_type, VNVariableReferenceType)
    ctx = variable_type.context
    reprstr = VNParameterizedType._get_parameter_repr([variable_type])
    d = ctx.get_parameterized_type_dict(VNVariableReferenceType)
    if reprstr in d:
      return d[reprstr]
    result = VNVariableReferenceType(variable_type)
    d[reprstr] = result
    return result


