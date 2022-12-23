# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *

class VNDisplayableType(ValueType):
  # 可显示类型不仅包含显示的内容（如图片、文字内容等），还包含显示内容的位置、大小、转场（入场出场）等所有确定该内容显示方式的信息
  # 同一个内容可以对应无数个可显示类型记录
  # 可显示类型的转场信息应该包含“转场需要多久”
  def __init__(self, context: Context) -> None:
    super().__init__(context)

  def __str__(self) -> str:
    return "可显示类型"
  
  @staticmethod
  def get(ctx : Context) -> VNDisplayableType:
    return ctx.get_stateless_type(VNDisplayableType)

class VNTimeOrderType(ValueType):
  # 时间顺序类型，不是一个具体的值，由该型输入输出所形成的依赖关系链条决定了指令间的顺序
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "时间顺序类型"
  
  @staticmethod
  def get(ctx : Context) -> VNTimeOrderType:
    return ctx.get_stateless_type(VNTimeOrderType)

class VNNamespaceReferenceType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "命名空间引用类型"
  
  @staticmethod
  def get(ctx : Context) -> VNNamespaceReferenceType:
    return ctx.get_stateless_type(VNNamespaceReferenceType)

class VNDeviceReferenceType(ParameterizedType):
  _data_type : ValueType # what kinds of data can be written to the device

  def __init__(self, data_type : ValueType) -> None:
    super().__init__(data_type.context, [data_type])
    self._data_type = data_type
  
  @property
  def element_type(self) -> ValueType:
    return self._data_type
  
  def __str__(self) -> str:
    return "设备<" + str(self._data_type) + ">"
  
  @staticmethod
  def get(data_type : ValueType) -> VNDeviceReferenceType:
    assert not isinstance(data_type, VNDeviceReferenceType)
    return data_type.context.get_parameterized_type_dict(VNDeviceReferenceType).get_or_create([data_type], lambda : VNDeviceReferenceType(data_type))
  
class VNHandleType(ParameterizedType):
  # handles for persistent instances (image/audio/video/text)
  # corresponding values are created when using show instructions
  _data_type : ValueType

  def __init__(self, data_type : ValueType) -> None:
    super().__init__(data_type.context, [data_type])
    self._data_type = data_type
  
  @property
  def element_type(self) -> ValueType:
    return self._data_type
  
  def __str__(self) -> str:
    return "句柄<" + str(self._data_type) + ">"
  
  @staticmethod
  def get(data_type : ValueType) -> VNHandleType:
    assert not isinstance(data_type, VNHandleType)
    return data_type.context.get_parameterized_type_dict(VNHandleType).get_or_create([data_type], lambda : VNHandleType(data_type))

class VNCharacterDeclType(ValueType):
  # for character identity

  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "人物声明类型"
  
  @staticmethod
  def get(ctx : Context) -> VNCharacterDeclType:
    return ctx.get_stateless_type(VNCharacterDeclType)

class VNLocationDeclType(ValueType):
  # for location identity
  
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "场景声明类型"
  
  @staticmethod
  def get(ctx : Context) -> VNLocationDeclType:
    return ctx.get_stateless_type(VNLocationDeclType)

class VNFunctionReferenceType(ValueType):
  # the value type for VNFunction
  # all VNFunctions take no arguments; all states passed through variables, so this is a stateless type
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "函数类型"
  
  @staticmethod
  def get(ctx : Context) -> VNFunctionReferenceType:
    return ctx.get_stateless_type(VNFunctionReferenceType)

class VNDataFunctionType(ValueType):
  # the function type for VNLambdaRecord data evaluation
  _return_type : tuple[ValueType] # tuple of zero or more types
  _argument_type : tuple[ValueType] # tuple of zero or more types
  
  def __init__(self, context: Context, args : tuple[ValueType], returns : tuple[ValueType]) -> None:
    super().__init__(context, [*returns, None, *args])
    self._argument_type = args
    self._return_type = returns
    for arg in self._argument_type:
      assert isinstance(arg, ValueType)
    for arg in self._return_type:
      assert isinstance(arg, ValueType)
  
  def __str__(self) -> str:
    return_type_str = '空'
    if len(self._return_type) > 0:
      if len(self._return_type) == 1:
        return_type_str = str(self._return_type[0])
      else:
        return_type_str = '<' + ', '.join([str(x) for x in self._return_type]) + '>'
    arg_type_str = '(' + ', '.join([str(x) for x in self._argument_type]) + ')'
    return return_type_str + arg_type_str
  
  @staticmethod
  def get(ctx: Context, args : typing.Iterable[ValueType], returns : typing.Iterable[ValueType]) -> VNDataFunctionType:
    argument_tuple = tuple(args)
    return_tuple = tuple(returns)
    return ctx.get_parameterized_type_dict(VNDataFunctionType).get_or_create([*return_tuple, None, *argument_tuple], lambda : VNDataFunctionType(ctx, args, returns))

class VNVariableReferenceType(ParameterizedType):
  _variable_type : ValueType

  def __init__(self, variable_type : ValueType) -> None:
    super().__init__(variable_type.context, [variable_type])
    self._variable_type = variable_type
  
  @property
  def variable_type(self) -> ValueType:
    return self._variable_type
  
  def __str__(self) -> str:
    return "变量引用<" + str(self._variable_type) + ">"
  
  @staticmethod
  def get(variable_type : ValueType) -> VNVariableReferenceType:
    assert not isinstance(variable_type, VNVariableReferenceType)
    return variable_type.context.get_parameterized_type_dict(VNVariableReferenceType).get_or_create([variable_type], lambda : VNVariableReferenceType(variable_type))

class VNScreenCoordinateType(ValueType):
  # 屏幕坐标类型，一对整数型值<x,y>，坐标原点是屏幕左上角，x沿右边增加，y向下方增加，单位都是像素值
  # 根据使用场景，坐标有可能被当做大小、偏移量，或是其他值来使用

  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "屏幕坐标类型"
  
  @staticmethod
  def get(ctx : Context) -> VNScreenCoordinateType:
    return ctx.get_stateless_type(VNScreenCoordinateType)

class VNEffectFunctionType(ValueType):
  # 特效函数类型，所有的转场（入场、出场等）函数记录都用这种类型
  # 特效函数可能带有额外的参数需要指定，我们不在该类型里包含这些信息

  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "特效函数类型"
  
  @staticmethod
  def get(ctx : Context) -> VNEffectFunctionType:
    return ctx.get_stateless_type(VNEffectFunctionType)