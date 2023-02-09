# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
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
from .nameresolution import NamespaceNodeInterface, NameResolver

# ------------------------------------------------------------------------------
# 类型特质 (type traits)
# ------------------------------------------------------------------------------

class VNDisplayableTrait:
  # 可以用该 trait 来取内容的大小，或是生成内容
  pass

class VNDurationTrait:
  # 可以用该 trait 来取时长
  pass

class VNAudioTrait(VNDurationTrait):
  # 可以用该 trait 来取音频内容
  pass

# ------------------------------------------------------------------------------
# 类型
# ------------------------------------------------------------------------------

class VNTimeOrderType(ValueType):
  # 时间顺序类型，不是一个具体的值，由该型输入输出所形成的依赖关系链条决定了指令间的顺序
  def __init__(self, context: Context) -> None:
    super().__init__(context)

  def __str__(self) -> str:
    return "时间顺序类型"

  @staticmethod
  def get(ctx : Context) -> VNTimeOrderType:
    return ctx.get_stateless_type(VNTimeOrderType)

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



class VNDisplayableType(ValueType):
  # 可显示类型描述一个类似图片的内容，该内容的（像素）大小已知，但是不包含其他信息（比如是否透明，显示在哪，有无转场等）
  # 文字可以在套壳之后作为可显示类型输出到图形输出类型中
  # this type is for values representing a displayable stuff (like an image) on screen
  # the value should be able to describe two things:
  # 1. the pixel size of the displayable
  # 2. the pixel content
  # because when reading the inputs we do not attempt to read all assets,
  # the raw input should treat assets as byte arrays (i.e., use _AssetDataReferenceType instead)

  _s_traits : typing.ClassVar[tuple[type]] = (VNDisplayableTrait)

  def __init__(self, context: Context) -> None:
    super().__init__(context)

  @staticmethod
  def get(ctx : Context) -> VNDisplayableType:
    return ctx.get_stateless_type(VNDisplayableType)

class VNAudioType(ValueType):
  # this type is for audios that have at least the "duration" attribute
  # again, not for assets that are just read

  _s_traits : typing.ClassVar[tuple[type]] = (VNAudioTrait)

  def __init__(self, context: Context) -> None:
    super().__init__(context)

  @staticmethod
  def get(ctx : Context) -> VNAudioType:
    return ctx.get_stateless_type(VNAudioType)

class VNVideoType(ValueType):

  _s_traits : typing.ClassVar[tuple[type]] = (VNDisplayableTrait, VNAudioTrait)

  def __init__(self, context: Context) -> None:
    super().__init__(context)

  @staticmethod
  def get(ctx : Context) -> VNVideoType:
    return ctx.get_stateless_type(VNVideoType)

class VNCharacterDeclType(ValueType):
  # for character identity

  def __init__(self, context: Context) -> None:
    super().__init__(context)

  def __str__(self) -> str:
    return "人物声明类型"

  @staticmethod
  def get(ctx : Context) -> VNCharacterDeclType:
    return ctx.get_stateless_type(VNCharacterDeclType)

class VNSceneDeclType(ValueType):
  # for location identity

  def __init__(self, context: Context) -> None:
    super().__init__(context)

  def __str__(self) -> str:
    return "场景声明类型"

  @staticmethod
  def get(ctx : Context) -> VNSceneDeclType:
    return ctx.get_stateless_type(VNSceneDeclType)

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

class VNDataFunctionType(ParameterizedType):
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

  _s_traits : typing.ClassVar[tuple[type]] = (VNDurationTrait)

  def __init__(self, context: Context) -> None:
    super().__init__(context)

  def __str__(self) -> str:
    return "特效函数类型"

  @staticmethod
  def get(ctx : Context) -> VNEffectFunctionType:
    return ctx.get_stateless_type(VNEffectFunctionType)

# ------------------------------------------------------------------------------
# 记录
# ------------------------------------------------------------------------------

class VNRecord(Symbol, Value):
  # 记录是在输出脚本中 ODR 定义的、没有控制流的、可以赋予名称的、以自身所承载信息为主的实体
  # （输入输出）设备，变量，资源（图片、声音等），都算记录
  # 有些内容（比如缩放后的图片，纯色图片等）既可以作为常量表达式也可以作为记录，但是只要需要赋予名称，他们一定需要绑为记录(可用 VNConstExprAsRecord 解决)
  # 有些内容（比如预设的转场效果等）主要是代码，参数部分很少，我们可以为它们新定义字面值(Literal)，然后用常量表达式来表示对它们的引用

  def __init__(self, name: str, loc: Location, ty : ValueType, **kwargs) -> None:
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)

class VNConstExprAsRecord(VNRecord):
  def __init__(self, name: str, loc: Location, cexpr : ConstExpr, **kwargs) -> None:
    super().__init__(name, loc, cexpr.valuetype, **kwargs)
    self._add_operand_with_value('value', cexpr)

# ------------------------------------------------------------------------------
# 设备记录
# ------------------------------------------------------------------------------

# 标准设备的枚举类型
# 与用户自定义设备相比，使用标准设备意味着基础代码将使用后端特有的命令来单独实现对设备的操作以及外观设定
#（比如RenPy会用 scene 来切换背景，用 Character 来实现 side image，用 Config 来指定 UI 外观，等等）
# 对这些标准设备的操作是可移植的，所有后端都应当支持它们

class VNStandardDeviceKind(enum.Enum):
  # 输出设备
  O_BGM_AUDIO = enum.auto() # 背景音乐
  O_SE_AUDIO = enum.auto() # 音效
  O_VOICE_AUDIO = enum.auto() # 语音
  O_FOREGROUND_DISPLAY = enum.auto() # 前景（立绘，物件图等）
  O_BACKGROUND_DISPLAY = enum.auto() # 背景
  O_OVERLAY_DISPLAY = enum.auto() # （在消息层更上面的）遮罩
  O_SAY_TEXT_TEXT = enum.auto() # 说话内容
  O_SAY_NAME_TEXT = enum.auto() # 说话者名字
  O_SAY_SIDEIMAGE_DISPLAY = enum.auto() # 说话头像区

  # 无输入输出的设备
  N_SCREEN_GAME = enum.auto() # 游戏屏幕
  N_SCREEN_SAY_ADV = enum.auto() # ADV 模式的对话框区域
  N_SCREEN_SAY_NVL = enum.auto() # NVL 模式的对话框区域

  # 输入设备
  I_MENU = enum.auto() # 选项
  I_LINE_INPUT = enum.auto() # 文本输入

  @staticmethod
  def get_device_content_type(value : VNStandardDeviceKind, context : Context) -> ValueType:
    match value:
      # 输出设备
      case VNStandardDeviceKind.O_BGM_AUDIO | VNStandardDeviceKind.O_SE_AUDIO | VNStandardDeviceKind.O_VOICE_AUDIO:
        return VNAudioType.get(context)
      case VNStandardDeviceKind.O_FOREGROUND_DISPLAY | VNStandardDeviceKind.O_BACKGROUND_DISPLAY | VNStandardDeviceKind.O_OVERLAY_DISPLAY:
        return VNDisplayableType.get(context)
      case VNStandardDeviceKind.O_SAY_TEXT_TEXT | VNStandardDeviceKind.O_SAY_NAME_TEXT:
        return TextType.get(context)
      case VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY:
        return VNDisplayableType.get(context)
      # 无输入输出的设备
      case VNStandardDeviceKind.N_SCREEN_GAME | VNStandardDeviceKind.N_SCREEN_SAY_ADV | VNStandardDeviceKind.N_SCREEN_SAY_NVL:
        return VoidType.get(context)
      # 输入设备
      case VNStandardDeviceKind.I_MENU:
        # 对于选项输入来说我们一般使用其结果影响控制流
        # 硬要赋予类型的话还是作整型
        return IntType.get(context)
      case VNStandardDeviceKind.I_LINE_INPUT:
        return StringType.get(context)
      case _:
        raise NotImplementedError()

class VNDeviceRecord(VNRecord):
  # 所有输入输出设备记录的基类
  # 实例一般记录运行时的外观等设置，比如对话框背景图片和对话框位置
  # 现在还没开始做外观所以留白
  # 对于显示设备来说，所有的坐标都是相对于父设备的
  # 所有的显示设备都构成一棵树，最顶层是屏幕，屏幕包含一系列子设备（背景、前景、发言、遮罩）
  _std_device_kind_op : OpOperand # 如果设备是某个标准设备的话，这是标准设备的类型
  _subdevice_table : SymbolTableRegion # 如果设备有子设备的话（比如发言，除了内容之外还要有说话者和侧边头像），它们都应该在这里

  def __init__(self, name: str, loc: Location, content_type: ValueType, std_device_kind : VNStandardDeviceKind = None, **kwargs) -> None:
    self_type = VNDeviceReferenceType.get(content_type)
    super().__init__(name, loc, self_type, **kwargs)
    std_device_kind_value = None
    if std_device_kind is not None and isinstance(std_device_kind, VNStandardDeviceKind):
      std_device_kind_value = EnumLiteral.get(self_type.context, std_device_kind)
    self._std_device_kind_op = self._add_operand_with_value('std_device', std_device_kind_value)
    self._subdevice_table = self._add_symbol_table('subdevice')

  def get_std_device_kind(self) -> VNStandardDeviceKind | None:
    kind_value = self._std_device_kind_op.get()
    if isinstance(kind_value, EnumLiteral):
      return kind_value.value
    return None

class VNDisplayDeviceCommon:
  # 把关于显示设备外观的部分放这
  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)

class VNScreenDeviceRecord(VNRecord, VNDisplayDeviceCommon):
  # 屏幕设备不接受输入输出，只作为其他设备的父或子设备出现
  # 屏幕设备
  def __init__(self, name: str, context : Context, **kwargs) -> None:
    content_type = VoidType.get(context)
    super().__init__(name, context.null_location, content_type, **kwargs)

class VNDisplayableOutputDeviceRecord(VNDeviceRecord, VNDisplayDeviceCommon):
  def __init__(self, name: str, context : Context, std_device_kind: VNStandardDeviceKind = None, **kwargs) -> None:
    super().__init__(name, context.null_location, VNDisplayableType.get(context), std_device_kind, **kwargs)

# TODO 添加创建标准设备（比如游戏屏幕、对话框区域等）的函数

# (有了 ConstExpr 之后，对 VNRecord 的需求就下降了，VNContentRecordBase 什么的就不用再移过来了)

class VNValueRecord(VNRecord):
  # 任何类型的编译时未知的量，包括用户定义的变量，设置（游戏名、版本号等），系统参数（引擎名称或版本，是否支持Live2D），有无子命名空间(有无DLC), 等等
  # 部分值只在特定命名空间有效，值的含义（如版本号）可能会由命名空间的不同而改变（比如是主游戏的版本还是DLC的版本，等等）
  def __init__(self, name: str, loc: Location, ty: ValueType, **kwargs) -> None:
    super().__init__(name, loc, ty, **kwargs)

class VNConfigValueRecord(VNValueRecord):
  # 所有不是用户定义的、用户可以写入的值（不管是初值还是在运行时写入）
  # 包括版本号，游戏名，以及成就系统的值
  pass

class VNEnvironmentValueRecord(VNValueRecord):
  # 所有用户无法写入的值，主要是版本号、是否有子命名空间，等等
  pass

class VNVariableStorageModel(enum.Enum):
  # 决定某个变量的存储方式
  PERSISTENT  = enum.auto() # 可与其他程序、游戏共享的变量，游戏重装不清除。对应 RenPy 中的 MultiPersistent
  GLOBAL      = enum.auto() # 全局变量，不随存档改变，游戏删除后重装可清除。对应 RenPy 中的 Persistent
  SAVE_LOCAL  = enum.auto() # 存档变量，不同存档中的值可不同，删除存档后即可清除

class VNVariableRecord(VNValueRecord):
  # 用户定义的值
  _storage_model_operand : OpOperand
  _initializer_operand : OpOperand

  def __init__(self, name: str, loc: Location, ty: ValueType, storage_model : VNVariableStorageModel, initializer : Value, **kwargs) -> None:
    super().__init__(name, loc, ty, **kwargs)
    self._storage_model_operand = self._add_operand_with_value('storage_model', EnumLiteral.get(ty.context, storage_model))
    self._initializer_operand = self._add_operand_with_value('initializer', initializer)

  @property
  def storage_model(self) -> VNVariableStorageModel:
    return self._storage_model_operand.get().value

  @property
  def initializer(self) -> Value:
    return self._initializer_operand.get()

class VNCharacterRecord(VNRecord):
  pass

class VNSceneRecord(VNRecord):
  pass

# ------------------------------------------------------------------------------
# (对于显示内容、非音频的)转场效果
# ------------------------------------------------------------------------------

# 基本上后端支持的转场效果都不同，对相同的转场效果也有不同的参数和微调方式
# 在这里我们定义一些(1)能满足自动演出需要的，(2)比较常见、足以在大多数作品中表述所有用到的转场效果的
# 我们对所有的转场效果(不管是这里定义的还是后端或者用户定义的)都有如下要求：
# 1.  对转场效果的含义和参数有明确的定义；后端可以定义在语义上有些许不同的同一转场效果
# 2.  所有定义在此的(通用)转场效果必须在所有后端都有实现
# 3.  所有其他来源定义的转场效果必须指定如何使用通用转场效果来替换该效果
#     (定义中也可以指定在某个后端如何进行特化的实现)
# 由于转场效果的生成比较复杂，每种独特的转场效果都由两部分实现:
# 1.  一个 VNTransitionEffectImplementationBase 的子类，用于描述某种转场如何实现
# 2.  一个 VNTransitionEffectConstExpr 来描述转场的参数以及其他细节
# 打个比方，如果我们生成代码时使用 callable ，那么第一项提供 callable 本身，第二项提供 callable 所需的参数

class VNTransitionEffectImplementationBase:
  # 定义转场效果的含义以及各种参数，同时也确定如何实现该效果
  # 在 Python 代码（包括编译器本体以及用户脚本）中定义的转场效果应该继承自该类
  # 在用户剧本中内嵌的转场效果应该使用下方的 VNCustomTransitionImplementation

  @classmethod
  def get_class_value(cls, context : Context) -> ClassLiteral:
    assert cls is not VNTransitionEffectImplementationBase
    return ClassLiteral.get(VNTransitionEffectImplementationBase, cls, context)

class VNSequenceTransitionImplementation(VNTransitionEffectImplementationBase):
  # 多个转场的串联组合
  pass

class VNCustomTransitionImplementation(VNTransitionEffectImplementationBase):
  # 用户剧本中指定的转场
  pass


class VNTransitionEffectRecord(VNRecord):
  _backing_impl_operand : OpOperand # ClassLiteral 参数，指向该效果的实现
  _duration_operand : OpOperand # 浮点参数，以秒为单位，代表默认的持续时间。所有转场都必须有这个。（后端实现不了的话可忽略该值）

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    ty = VNEffectFunctionType.get(loc.context)
    super().__init__(name, loc, ty, **kwargs)
    self._duration_operand = self._add_operand_with_value('duration', FloatLiteral.get(0.35, loc.context))


class VNTransitionEffectConstExpr(ConstExpr):
  # 我们使用此类型来给转场效果赋予参数
  # 如果需要给该调用赋予名称，可以使用 VNConstExprAsRecord
  def __init__(self, context: Context, values: typing.Iterable[Value], **kwargs) -> None:
    ty = VNEffectFunctionType.get(context)
    super().__init__(ty, values, **kwargs)
    # 检查输入，第一项一定是一个转场效果的实现，第二个是一个浮点数的时长
    impl = self.get_operand(0)
    assert isinstance(impl, ClassLiteral) and issubclass(impl.value, VNTransitionEffectImplementationBase)
    duration = self.get_operand(1)
    assert isinstance(duration.valuetype, FloatType)

  def get_implementation(self) -> type:
    return self.get_operand(0).value

  def get_duration(self) -> Value:
    return self.get_operand(1)

  @classmethod
  def get(cls, context : Context, transition_effect : type, duration : Value, parameters : typing.Iterable[Value] = None) -> VNTransitionEffectConstExpr:
    assert issubclass(transition_effect, VNTransitionEffectImplementationBase)
    assert isinstance(duration.valuetype, FloatType)
    transition_literal = ClassLiteral.get(VNTransitionEffectImplementationBase, transition_effect, context)
    ty = VNEffectFunctionType.get(context)
    params = [transition_literal, duration]
    if parameters is not None:
      params.extend(parameters)
    return VNTransitionEffectConstExpr._get_impl(ty, params)

# TODO 定义作用于设备的特效（既有持续性的（比如下雪）也有暂态的（比如屏幕闪光））
# 基于类似转场效果的逻辑，我们把特效定义为一种值而不是指令
# 特效有两种，一种作用于有句柄的内容（比如角色小跳），一种作用于设备（基本就是多一个内容项）
# 我们使用 put/create 来表示作用于设备的特效，使用 modify 来表示作用于句柄的特效

# ------------------------------------------------------------------------------
# 函数、指令等
# ------------------------------------------------------------------------------

class VNFunction(Symbol, Value):
  # 为了保证用户能够理解“为什么有一部分内容没有在函数中出现”，
  # 我们需要保留没有被转为有效输出的内容
  # 现在他们都被放在 lost 区中，都以 MetadataOp 的形式保存
  _lost : Region # 编译中碰到的不属于任何其他函数或命令的内容
  _body: Region # 内容主体

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    ty = VNFunctionReferenceType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)
    self._body = self._add_region('body')
    self._lost = self._add_region('lost')

  def set_lost_block_prebody(self, block : Block):
    assert self._lost.blocks.empty()
    block.name = 'prebody'
    self._lost.blocks.push_back(block)

  def set_lost_block_postbody(self, block : Block):
    assert self._lost.blocks.size() < 2
    block.name = 'postbody'
    self._lost.blocks.push_back(block)

  @property
  def body(self) -> Region:
    return self._body

class VNNamespace(Symbol, NamespaceNodeInterface[VNFunction | VNRecord]):
  _function_region : SymbolTableRegion
  _record_region : SymbolTableRegion
  _asset_region : SymbolTableRegion
  _namespace_path_tuple : tuple[str]

  @staticmethod
  def stringize_namespace_path(path : tuple[str]) -> str:
    return '/' + '/'.join(path)

  @staticmethod
  def expand_namespace_str(path : str) -> tuple[str]:
    return tuple(path.split('/')[1:])

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    # 命名空间应该组成一个树结构，都以'/'开始，以'/'为分隔符
    assert name.startswith('/')
    super().__init__(name, loc, **kwargs)
    self._namespace_path_tuple = VNNamespace.expand_namespace_str(name)
    self._function_region = self._add_symbol_table('functions')
    self._record_region = self._add_symbol_table('records')
    self._asset_region = self._add_symbol_table('assets')

  def get_namespace_path(self) -> tuple[str]:
    return self._namespace_path_tuple

  def get_namespace_parent_node(self) -> VNNamespace | None:
    if len(self._namespace_path_tuple) == 0:
      return None
    toplevel = self.parent_op
    assert isinstance(toplevel, VNModel)
    return toplevel.get_namespace(VNNamespace.stringize_namespace_path(self._namespace_path_tuple))

  def lookup_name(self, name: str) -> VNNamespace | VNFunction | VNRecord | NamespaceNodeInterface.AliasEntry | None:
    if func := self._function_region.get(name):
      return func
    if record := self._record_region.get(name):
      return record
    if asset := self._asset_region.get(name):
      return asset
    return None

class VNModel(Operation):
  _namespace_region : SymbolTableRegion
  # 为了复用符号表的有关代码，我们把命名空间的不同部分用'/'分隔开，和目录一样，全局命名空间也有'/'
  # 根据命名空间查找内容应该使用额外的手段（比如前段可以用 nameresolution 有关的实现）
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._namespace_region = self._add_symbol_table('namespaces')

  def get_namespace(self, namespace : str) -> VNNamespace | None:
    return self._namespace_region.get(namespace)

class VNModelNameResolver(NameResolver[VNFunction | VNRecord]):
  _model : VNModel

  def __init__(self, model : VNModel) -> None:
    super().__init__()
    self._model = model

  def get_namespace_node(self, path: typing.Tuple[str]) -> NamespaceNodeInterface[T] | None:
    return self._model.get_namespace(VNNamespace.stringize_namespace_path(path))

  def get_root_node(self) -> NamespaceNodeInterface[T]:
    return self._model.get_namespace('/')
