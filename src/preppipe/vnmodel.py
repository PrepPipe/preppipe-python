# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import os
import io
import pathlib
import typing
import pydub
import pathlib
import enum
from enum import Enum

import PIL.Image

from preppipe.irbase import Value

from .commontypes import *
from .irbase import *
from .irdataop import *
from .nameresolution import NamespaceNodeInterface, NameResolver
from .language import TranslationDomain

TR_vnmodel = TranslationDomain("vnmodel")

# VNModel 只保留核心的、基于文本的IR信息，其他内容（如图片显示位置等）大部分都会放在抽象接口后
# 像图片位置（2D屏幕坐标）、设备外观（对话框贴图）等信息，在后端生成时会用到，所以需要在IR中记录
# 但是他们的具体内容、格式等可能每个引擎都不一样，强求统一的话一定会影响可拓展性
# 所以我们使用如下策略：
# 1. 当部分内容有比较统一的格式，后端可以只通过继承现有类而不改变现有类时（比如转场效果，都是实现+参数），我们把基类包含在此
# 2. 当内容没有比较统一的格式，后端可以支持的内容有较大差异时（比如屏幕坐标，可以基于"mid","left"这样的词或者是具体的2D屏幕坐标），
#    我们在需要此信息的操作项（Operation）中放一个 SymbolTable ，然后各种不同的格式以 Symbol 的形式接在该表中
# 最主要的分析主要基于控制流（哪些会被执行）和数据流（需要哪些素材），不需要有关具体的表现形式的信息，

# 对于操作项的名字：
# 1. 对于函数、基本块、场景、角色：
#     操作项的 name 是用户可读的名称（如“第一章”，“选项前”，“教室”，“苏语涵”）
#         （这样按名搜索更符合用户预期）
#     操作项带个 codename 参数，表示后端可用的名称（如"ch01", "ch01.beforechoice", "classroom", "yuhan"）
#         （codename 可以包含也可以不包含，在后端生成时再生成）
# 2. 对于指令：name 无意义，可以随意选择；一般用于调试信息（比如标记指令是由什么输入、什么转换生成的）

# ------------------------------------------------------------------------------
# 类型特质 (type traits)
# TODO 不使用特质
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

@IRObjectJsonTypeName("vn_time_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNTimeOrderType(StatelessType):
  # 时间顺序类型，不是一个具体的值，由该型输入输出所形成的依赖关系链条决定了指令间的顺序
  def __str__(self) -> str:
    return "时间顺序类型"

@IRObjectJsonTypeName("vn_devref_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNDeviceReferenceType(ParameterizedType):
  #def __str__(self) -> str:
  #  return "设备<" + str(self.element_type) + ">"

  @staticmethod
  def get(element_types : typing.Iterable[ValueType], context : Context) -> VNDeviceReferenceType:
    return context.get_or_create_parameterized_type(
      VNDeviceReferenceType,
      list(element_types),
      lambda : VNDeviceReferenceType(init_mode = IRObjectInitMode.CONSTRUCT,
                   context = context,
                   parameters=tuple(element_types))
    )

@IRObjectJsonTypeName("vn_handle_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNHandleType(SingleElementParameterizedType):
  # handles for persistent instances (image/audio/video/text)
  # corresponding values are created when using show instructions

  def __str__(self) -> str:
    return "句柄<" + str(self.element_type) + ">"

  @classmethod
  def _get_typecheck(cls, element_type : ValueType) -> None:
    assert not isinstance(element_type, VNHandleType)

  @classmethod
  def get(cls, element_type : ValueType) -> VNHandleType:
    return super(VNHandleType, cls).get(element_type=element_type) # type: ignore

@IRObjectJsonTypeName("vn_displayable_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNDisplayableType(StatelessType):
  # 可显示类型描述一个类似图片的内容，该内容的（像素）大小已知，但是不包含其他信息（比如是否透明，显示在哪，有无转场等）
  # 文字可以在套壳之后作为可显示类型输出到图形输出类型中
  # this type is for values representing a displayable stuff (like an image) on screen
  # the value should be able to describe two things:
  # 1. the pixel size of the displayable
  # 2. the pixel content
  # because when reading the inputs we do not attempt to read all assets,
  # the raw input should treat assets as byte arrays (i.e., use _AssetDataReferenceType instead)

  _s_traits : typing.ClassVar[tuple[type,...]] = (VNDisplayableTrait,)

@IRObjectJsonTypeName("vn_audio_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNAudioType(StatelessType):
  # this type is for audios that have at least the "duration" attribute
  # again, not for assets that are just read

  _s_traits : typing.ClassVar[tuple[type,...]] = (VNAudioTrait,)

@IRObjectJsonTypeName("vn_video_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNVideoType(StatelessType):
  _s_traits : typing.ClassVar[tuple[type,...]] = (VNDisplayableTrait, VNAudioTrait)

@IRObjectJsonTypeName("vn_chardecl_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNCharacterDeclType(StatelessType):
  # for character identity
  def __str__(self) -> str:
    return "人物声明类型"

@IRObjectJsonTypeName("vn_scenedecl_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNSceneDeclType(StatelessType):
  # for location identity
  def __str__(self) -> str:
    return "场景声明类型"

@IRObjectJsonTypeName("vn_funcref_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNFunctionReferenceType(StatelessType):
  # the value type for VNFunction
  # all VNFunctions take no arguments; all states passed through variables, so this is a stateless type

  def __str__(self) -> str:
    return "函数类型"

@IRObjectJsonTypeName("vn_datafunc_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNDataFunctionType(ParameterizedType):
  # the function type for VNLambdaRecord data evaluation
  def construct_init(self, *, context: Context, args : tuple[ValueType], returns : tuple[ValueType], **kwargs) -> None:
    super().construct_init(context=context, parameters=[*returns, None, *args], **kwargs)

  def get_return_type_tuple(self) -> tuple[ValueType]:
    breakloc = self.parameters.index(None)
    return self.parameters[:breakloc] # type: ignore

  def get_argument_type_tuple(self) -> tuple[ValueType]:
    breakloc = self.parameters.index(None)
    return self.parameters[breakloc+1:] # type: ignore

  def __str__(self) -> str:
    return_type_str = '空'
    return_type_tuple = self.get_return_type_tuple()
    if len(return_type_tuple) > 0:
      if len(return_type_tuple) == 1:
        return_type_str = str(return_type_tuple[0])
      else:
        return_type_str = '<' + ', '.join([str(x) for x in return_type_tuple]) + '>'
    arg_type_str = '(' + ', '.join([str(x) for x in self.get_argument_type_tuple()]) + ')'
    return return_type_str + arg_type_str

  @staticmethod
  def get(ctx: Context, args : typing.Iterable[ValueType], returns : typing.Iterable[ValueType]) -> VNDataFunctionType:
    argument_tuple = tuple(args)
    return_tuple = tuple(returns)
    return ctx.get_or_create_parameterized_type(VNDataFunctionType, [*return_tuple, None, *argument_tuple], lambda : VNDataFunctionType(init_mode=IRObjectInitMode.CONSTRUCT, context = ctx, args=args, returns=returns))

@IRObjectJsonTypeName("vn_varref_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNVariableReferenceType(SingleElementParameterizedType):
  def __str__(self) -> str:
    return "变量引用<" + str(self.element_type) + ">"

  @classmethod
  def _get_typecheck(cls, element_type : ValueType) -> None:
    assert not isinstance(element_type, VNVariableReferenceType)

@IRObjectJsonTypeName("vn_coord2d_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNScreenCoordinate2DType(StatelessType):
  # 屏幕坐标类型，一对整数型值<x,y>，坐标原点是屏幕左上角，x沿右边增加，y向下方增加，单位都是像素值
  # 根据使用场景，坐标有可能被当做大小、偏移量，或是其他值来使用
  def __str__(self) -> str:
    return "屏幕坐标类型"

@IRObjectJsonTypeName("vn_sefunc_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNEffectFunctionType(StatelessType):
  # 特效函数类型，所有的转场（入场、出场等）函数记录都用这种类型
  _s_traits : typing.ClassVar[tuple[type]] = (VNDurationTrait)

  def __str__(self) -> str:
    return "特效函数类型"

# ------------------------------------------------------------------------------
# 记录
# ------------------------------------------------------------------------------

@IROperationDataclassWithValue(VoidType)
@IRObjectJsonTypeName("vn_record_op")
class VNSymbol(Symbol, Value):
  # 所有能够按名查找的（全局、顶层）内容的基类
  # 有些内容（比如缩放后的图片，纯色图片等）既可以作为常量表达式也可以作为符号，但是只要需要赋予名称，他们一定需要绑为符号(可用 VNConstExprAsSymbol 解决)
  # 有些内容（比如预设的转场效果等）主要是代码，参数部分很少，我们可以为它们新定义字面值(Literal)，然后用常量表达式来表示对它们的引用
  codename : OpOperand[StringLiteral]


@IRObjectJsonTypeName("vn_cexpr_record_op")
class VNConstExprAsSymbol(VNSymbol):
  def construct_init(self, *, name: str, loc: Location, value : ConstExpr | LiteralExpr | AssetData, **kwargs) -> None:
    assert isinstance(value, (ConstExpr, LiteralExpr, AssetData))
    super().construct_init(name=name, loc=loc, ty=value.valuetype, **kwargs)
    self._add_operand_with_value('value', value)

  def get_value(self) -> ConstExpr | LiteralExpr | AssetData:
    return self.get_operand('value') # type: ignore

  @staticmethod
  def create(context : Context, value : ConstExpr | LiteralExpr | AssetData, name : str, loc : Location | None = None):
    return VNConstExprAsSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, value=value, name=name, loc=loc)


# ------------------------------------------------------------------------------
# 设备记录
# ------------------------------------------------------------------------------

# 标准设备的枚举类型
# 与用户自定义设备相比，使用标准设备意味着基础代码将使用后端特有的命令来单独实现对设备的操作以及外观设定
#（比如RenPy会用 scene 来切换背景，用 Character 来实现 side image，用 Config 来指定 UI 外观，等等）
# 对这些标准设备的操作是可移植的，所有后端都应当支持它们

@IRWrappedStatelessClassJsonName("vn_stddev_kind_e")
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
  N_AUDIONODE = enum.auto() # 音频结点（为了表述音量控制）

  # 输入设备
  I_MENU = enum.auto() # 选项
  I_LINE_INPUT = enum.auto() # 文本输入

  # 默认名称 (原名+"_DNAME")
  O_BGM_AUDIO_DNAME   = "dev_audio_bgm"
  O_SE_AUDIO_DNAME    = "dev_audio_se"
  O_VOICE_AUDIO_DNAME = "dev_audio_voice"
  O_FOREGROUND_DISPLAY_DNAME  = "dev_display_foreground"
  O_BACKGROUND_DISPLAY_DNAME  = "dev_display_background"
  O_OVERLAY_DISPLAY_DNAME     = "dev_display_overlay"
  O_SAY_TEXT_TEXT_DNAME       = "dev_text_say"
  O_SAY_NAME_TEXT_DNAME       = "dev_text_sayer_name"
  O_SAY_SIDEIMAGE_DISPLAY_DNAME = "dev_display_sayer_image"
  N_SCREEN_GAME_DNAME           = "dev_screen_game"
  N_SCREEN_SAY_ADV_DNAME        = "dev_screen_say_adv"
  N_SCREEN_SAY_NVL_DNAME        = "dev_screen_say_nvl"
  N_AUDIONODE_DNAME             = "dev_audio_node"
  I_MENU_DNAME =        "dev_input_menu"
  I_LINE_INPUT_DNAME =  "dev_input_line"

  @staticmethod
  def get_device_content_type(kind : VNStandardDeviceKind, context : Context) -> ValueType:
    match kind:
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
      case VNStandardDeviceKind.N_SCREEN_GAME | VNStandardDeviceKind.N_SCREEN_SAY_ADV | VNStandardDeviceKind.N_SCREEN_SAY_NVL | VNStandardDeviceKind.N_AUDIONODE:
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

  @staticmethod
  def get_standard_device_name(kind: VNStandardDeviceKind) -> str:
    return getattr(VNStandardDeviceKind, kind.name + '_DNAME').value

  @staticmethod
  def get_pretty_device_name(devname : str):
    # 当我们在资源统计时，如果设备名是默认值，我们希望有个更好理解的输出名
    # 目前只加了大概会需要的设备
    match devname:
      case VNStandardDeviceKind.O_BGM_AUDIO_DNAME.value:
        return _VNDeviceNamePrettyPrintScope._tr_devname_bgm.get()
      case VNStandardDeviceKind.O_SE_AUDIO_DNAME.value:
        return _VNDeviceNamePrettyPrintScope._tr_devname_se.get()
      case VNStandardDeviceKind.O_VOICE_AUDIO_DNAME.value:
        return _VNDeviceNamePrettyPrintScope._tr_devname_voice.get()
      case VNStandardDeviceKind.O_BACKGROUND_DISPLAY_DNAME.value:
        return _VNDeviceNamePrettyPrintScope._tr_devname_background.get()
      case VNStandardDeviceKind.O_FOREGROUND_DISPLAY_DNAME.value:
        return _VNDeviceNamePrettyPrintScope._tr_devname_foreground.get()
      case VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY_DNAME.value:
        return _VNDeviceNamePrettyPrintScope._tr_devname_sideimage.get()
      case _:
        return devname

class _VNDeviceNamePrettyPrintScope:
  _tr_devname_bgm = TR_vnmodel.tr("devname_bgm",
    en="Used as background music",
    zh_cn="用作背景音乐",
    zh_hk="用作背景音樂",
  )
  _tr_devname_se = TR_vnmodel.tr("devname_se",
    en="Used as sound effect",
    zh_cn="用作音效",
    zh_hk="用作音效",
  )
  _tr_devname_voice = TR_vnmodel.tr("devname_voice",
    en="Used as voice",
    zh_cn="用作语音",
    zh_hk="用作語音",
  )
  _tr_devname_background = TR_vnmodel.tr("devname_background",
    en="Used as background image",
    zh_cn="用作背景图片",
    zh_hk="用作背景圖片",
  )
  _tr_devname_foreground = TR_vnmodel.tr("devname_foreground",
    en="Used as foreground image",
    zh_cn="用作前景图片（包含角色立绘和其他物件图）",
    zh_hk="用作前景圖片（包含角色立繪和其他物件圖）",
  )
  _tr_devname_sideimage = TR_vnmodel.tr("devname_sideimage",
    en="Used as side image",
    zh_cn="用作头像",
    zh_hk="用作頭像",
  )

@IROperationDataclass
@IRObjectJsonTypeName("vn_device_record_op")
class VNDeviceSymbol(VNSymbol):
  # 所有输入输出设备记录的基类
  # 实例一般记录运行时的外观等设置，比如对话框背景图片和对话框位置
  # 现在还没开始做外观所以留白
  # 对于显示设备来说，所有的坐标都是相对于父设备的
  # 所有的显示设备都构成一棵树，最顶层是屏幕，屏幕包含一系列子设备（背景、前景、发言、遮罩）
  # 为了便于在命名空间层级查找设备名称，我们使用 def-use chain 来记录子设备，所有的设备记录实例都在同一个（命名空间的）表内
  std_device_kind : OpOperand[EnumLiteral[VNStandardDeviceKind]] # 如果设备是某个标准设备的话，这是标准设备的类型
  parent_device : OpOperand # OpOperand[VNDeviceSymbol] # 如果该设备是含在另一个设备中的子设备，这里保留对父设备的引用

  def get_parent_device(self) -> VNDeviceSymbol | None:
    return self.parent_device.try_get_value()

  def set_parent_device(self, parent : VNDeviceSymbol):
    self.parent_device.set_operand(0, parent)

  def get_std_device_kind(self) -> VNStandardDeviceKind | None:
    if kind_value := self.std_device_kind.try_get_value():
      return kind_value.value
    return None

  @staticmethod
  def create_standard_device(context : Context, std_device_kind : VNStandardDeviceKind, name : str | None = None, parent_device : VNDeviceSymbol | None = None) -> VNDeviceSymbol:
    # 目前定义的标准设备都只有一种内容类型，所以下面这里只用单个 content_ty
    content_ty = VNStandardDeviceKind.get_device_content_type(std_device_kind, context)
    ty = VNDeviceReferenceType.get((content_ty,), context)
    if name is None:
      name = VNStandardDeviceKind.get_standard_device_name(std_device_kind)
    std_device_kind_value = EnumLiteral.get(context, std_device_kind)
    return VNDeviceSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=context.null_location, ty=ty, std_device_kind=std_device_kind_value, parent_device=parent_device)

  @staticmethod
  def create(context : Context, name: str, loc: Location, content_types: typing.Iterable[ValueType] | ValueType, std_device_kind : VNStandardDeviceKind | None = None, parent_device : VNDeviceSymbol | None = None) -> VNDeviceSymbol:
    if isinstance(content_types, ValueType):
      ty = VNDeviceReferenceType.get((content_types,), context)
    else:
      for t in content_types:
        assert isinstance(t, ValueType)
      ty = VNDeviceReferenceType.get(content_types, context)
    return VNDeviceSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc, ty=ty, std_device_kind = std_device_kind, parent_device=parent_device)

  DEFAULT_AUDIO_ROOT_NAME : typing.ClassVar[str] = "dev_audio_root"
  STANDARD_DEVICE_TREE : typing.ClassVar[dict] = {
    VNStandardDeviceKind.N_SCREEN_GAME_DNAME.value : (VNStandardDeviceKind.N_SCREEN_GAME, {
      VNStandardDeviceKind.O_BACKGROUND_DISPLAY_DNAME.value : VNStandardDeviceKind.O_BACKGROUND_DISPLAY,
      VNStandardDeviceKind.O_FOREGROUND_DISPLAY_DNAME.value : VNStandardDeviceKind.O_FOREGROUND_DISPLAY,
      VNStandardDeviceKind.N_SCREEN_SAY_NVL_DNAME.value : (VNStandardDeviceKind.N_SCREEN_SAY_NVL, {
        VNStandardDeviceKind.O_SAY_TEXT_TEXT_DNAME.value + '_nvl' : VNStandardDeviceKind.O_SAY_TEXT_TEXT,
        VNStandardDeviceKind.O_SAY_NAME_TEXT_DNAME.value + '_nvl' : VNStandardDeviceKind.O_SAY_NAME_TEXT,
        VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY_DNAME.value + '_nvl' : VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY
      }),
      VNStandardDeviceKind.N_SCREEN_SAY_ADV_DNAME.value : (VNStandardDeviceKind.N_SCREEN_SAY_ADV, {
        VNStandardDeviceKind.O_SAY_TEXT_TEXT_DNAME.value + '_adv' : VNStandardDeviceKind.O_SAY_TEXT_TEXT,
        VNStandardDeviceKind.O_SAY_NAME_TEXT_DNAME.value + '_adv' : VNStandardDeviceKind.O_SAY_NAME_TEXT,
        VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY_DNAME.value + '_adv' : VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY
      }),
      VNStandardDeviceKind.I_MENU_DNAME.value: VNStandardDeviceKind.I_MENU,
      VNStandardDeviceKind.I_LINE_INPUT_DNAME.value: VNStandardDeviceKind.I_LINE_INPUT,
      VNStandardDeviceKind.O_OVERLAY_DISPLAY_DNAME.value : VNStandardDeviceKind.O_OVERLAY_DISPLAY
    }),
    "dev_audio_root" : (VNStandardDeviceKind.N_AUDIONODE, {
      VNStandardDeviceKind.O_BGM_AUDIO_DNAME.value : VNStandardDeviceKind.O_BGM_AUDIO,
      VNStandardDeviceKind.O_SE_AUDIO_DNAME.value : VNStandardDeviceKind.O_SE_AUDIO,
      VNStandardDeviceKind.O_VOICE_AUDIO_DNAME.value : VNStandardDeviceKind.O_VOICE_AUDIO
    }),
  }

  @staticmethod
  def create_standard_device_tree(ns : VNNamespace, tree: dict | None = None, loc : Location | None = None) -> None:
    def handle_entry(parent : VNDeviceSymbol | None, name : str, entry : tuple[VNStandardDeviceKind, dict] | VNStandardDeviceKind):
      nonlocal ns
      if isinstance(entry, tuple):
        kind, child = entry
      else:
        kind = entry
        child = None
      cur_entry = VNDeviceSymbol.create_standard_device(ns.context, kind, name)
      ns.add_device(cur_entry)
      if parent is not None:
        cur_entry.set_parent_device(parent)
      if child is not None:
        for name, entry in child.items():
          handle_entry(cur_entry, name, entry)
    if tree is None:
      tree = VNDeviceSymbol.STANDARD_DEVICE_TREE
    for toplevel_name, toplevel_entry in tree.items():
      handle_entry(None, toplevel_name, toplevel_entry)

# 我们在这里尽量简化继承关系，没有确定的设备类型继承数之前先把东西全放在 VNDeviceRecord 里面
#class VNDisplayDeviceCommon:
  # 把关于显示设备外观的部分放这
#  def __init__(self, **kwargs) -> None:
#    super().__init__(**kwargs)

#class VNScreenDeviceRecord(VNRecord, VNDisplayDeviceCommon):
  # 屏幕设备不接受输入输出，只作为其他设备的父或子设备出现
  # 屏幕设备
#  def __init__(self, name: str, context : Context, **kwargs) -> None:
#    content_type = VoidType.get(context)
#    super().__init__(name, context.null_location, content_type, **kwargs)

#class VNDisplayableOutputDeviceRecord(VNDeviceRecord, VNDisplayDeviceCommon):
#  def __init__(self, name: str, context : Context, std_device_kind: VNStandardDeviceKind = None, **kwargs) -> None:
#    super().__init__(name, context.null_location, VNDisplayableType.get(context), std_device_kind, **kwargs)


# (有了 ConstExpr 之后，对 VNRecord 的需求就下降了，VNContentRecordBase 什么的就不用再移过来了)

@IRObjectJsonTypeName("vn_value_record_op")
class VNValueSymbol(VNSymbol):
  # 任何类型的编译时未知的量，包括用户定义的变量，设置（游戏名、版本号等），系统参数（引擎名称或版本，是否支持Live2D），有无子命名空间(有无DLC), 等等
  # 部分值只在特定命名空间有效，值的含义（如版本号）可能会由命名空间的不同而改变（比如是主游戏的版本还是DLC的版本，等等）
  pass


@IRObjectJsonTypeName("vn_env_value_record_op")
class VNEnvironmentValueSymbol(VNValueSymbol):
  # 所有用户无法写入的值，主要是版本号、是否有子命名空间，等等
  pass

@IRWrappedStatelessClassJsonName("vn_var_storage_e")
class VNVariableStorageModel(enum.Enum):
  # 决定某个变量的存储方式
  PERSISTENT  = enum.auto() # 可与其他程序、游戏共享的变量，游戏重装不清除。对应 RenPy 中的 MultiPersistent
  GLOBAL      = enum.auto() # 全局变量，不随存档改变，游戏删除后重装可清除。对应 RenPy 中的 Persistent
  SAVE_LOCAL  = enum.auto() # 存档变量，不同存档中的值可不同，删除存档后即可清除
  CONFIG      = enum.auto() # 设置变量，取决于引擎的具体实现。只能用于由引擎定义的值（版本号，游戏名，成就系统的值，等等）


@IRObjectJsonTypeName("vn_var_value_symbol_op")
class VNVariableSymbol(VNValueSymbol):
  # 所有用户可以写入的值，包括用户定义的值和系统设置等引擎定义的值
  _storage_model_operand : OpOperand
  _initializer_operand : OpOperand

  def construct_init(self, *, ty: ValueType, storage_model : VNVariableStorageModel, initializer : Value, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(ty=ty, name=name, loc=loc, **kwargs)
    self._storage_model_operand = self._add_operand_with_value('storage_model', EnumLiteral.get(ty.context, storage_model))
    self._initializer_operand = self._add_operand_with_value('initializer', initializer)

  def post_init(self) -> None:
    self._storage_model_operand = self.get_operand_inst('storage_model')
    self._initializer_operand = self.get_operand_inst('initializer')

  @property
  def storage_model(self) -> VNVariableStorageModel:
    return self._storage_model_operand.get().value

  @property
  def initializer(self) -> Value:
    return self._initializer_operand.get()

@IRWrappedStatelessClassJsonName("vn_char_kind_e")
class VNCharacterKind(enum.Enum):
  # 代表角色类型的枚举值，基于角色的分析可能会用到该值
  NORMAL = enum.auto() # 寻常的用户定义的角色
  CROWD = enum.auto() # 用户定义的、代表一类人群的角色（路人甲）
  NARRATOR = enum.auto() # 旁白角色
  SYSTEM = enum.auto() # 用来代表一些游戏系统的消息（错误信息等）

@IROperationDataclassWithValue(VNCharacterDeclType)
@IRObjectJsonTypeName("vn_char_record_op")
class VNCharacterSymbol(VNSymbol):
  NARRATOR_DEFAULT_NAME : typing.ClassVar[str] = "narrator"
  NARRATOR_ALL_NAMES : typing.ClassVar[list[str]] = [
    "narrator",
    "旁白",
  ]

  kind : OpOperand[EnumLiteral[VNCharacterKind]]

  # 如果后端支持给所有文本上格式（比如 RenPy, 可以指定发言名和内容颜色等），
  # 我们在这里记录些对发言内容的基础设置，这样可以更好地利用后端的功能
  # 注意，这里的设置内容都是已经施加在内容上的，生成时对于这些特性不支持的后端不需要再对内容进行调整
  # （即可以忽略剩下所有的设置项）
  sayname_style : OpOperand[TextStyleLiteral] # 可以为空
  saytext_style : OpOperand[TextStyleLiteral] # 可以为空

  # 后端可能可以根据以下内容更好地给导出的资源起名
  # 如果使用一个声明的资源，我们这里也直接引用其值而不引用资源声明的 VNConstExprAsSymbol
  # （需要的话之后可以找到值相同的 VNConstExprAsSymbol 进行去重）
  # 这里只是声明一些可能会用到的，不用的话可以忽略，改变角色状态时肯定会带完整的值，不需要这里的信息
  sprites : SymbolTableRegion[VNConstExprAsSymbol]
  sideimages : SymbolTableRegion[VNConstExprAsSymbol]

  @staticmethod
  def create(context : Context, kind : EnumLiteral[VNCharacterKind] | VNCharacterKind, name : str, codename : StringLiteral | str | None = None, loc : Location | None = None) -> VNCharacterSymbol:
    if isinstance(kind, VNCharacterKind):
      kind = EnumLiteral.get(context, kind)
    assert isinstance(kind, EnumLiteral)
    return VNCharacterSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind = kind, codename=codename, name=name, loc=loc)

  @staticmethod
  def create_narrator(context : Context) -> VNCharacterSymbol:
    return VNCharacterSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind = EnumLiteral.get(context,VNCharacterKind.NARRATOR), name=VNCharacterSymbol.NARRATOR_DEFAULT_NAME, loc=context.null_location)

  @staticmethod
  def create_normal_sayer(context : Context, name : str, codename : StringLiteral | str | None = None, loc : Location | None = None) -> VNCharacterSymbol:
    return VNCharacterSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind=EnumLiteral.get(context,VNCharacterKind.NORMAL), codename=codename, name=name, loc=loc)


@IROperationDataclassWithValue(VNSceneDeclType)
@IRObjectJsonTypeName("vn_scene_symbol_op")
class VNSceneSymbol(VNSymbol):

  # 后端可能可以根据以下内容更好地给导出的资源起名
  backgrounds : SymbolTableRegion[VNConstExprAsSymbol]

  @staticmethod
  def create(context : Context, name : str, codename : StringLiteral | str | None = None, loc : Location | None = None):
    return VNSceneSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, codename=codename, name=name, loc=loc)

@IROperationDataclassWithValue(VoidType)
@IRObjectJsonTypeName("vn_alias_symbol_op")
class VNAliasSymbol(VNSymbol):
  target_name : OpOperand[StringLiteral]
  target_namespace : OpOperand[StringLiteral] # 单个字符串，字符串形式的命名空间路径

  def get_entry_dataclass(self) -> NamespaceNodeInterface.AliasEntry:
    return NamespaceNodeInterface.AliasEntry(ns_path=VNNamespace.expand_namespace_str(self.target_namespace.get().get_string()), name=self.target_name.get().get_string())

  @staticmethod
  def create(context : Context, name : str, target_name : StringLiteral | str, target_namespace : StringLiteral | str, loc : Location | None = None):
    return VNAliasSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, target_name=target_name, target_namespace=target_namespace, name=name, loc=loc)

# ------------------------------------------------------------------------------
# (对于显示内容、非音频的)转场效果
# ------------------------------------------------------------------------------

# 基本上后端支持的转场效果都不同，对相同的转场效果也有不同的参数和微调方式
# 在这里我们定义一些(1)能满足自动演出需要的，(2)比较常见、足以在大多数作品中表述所有用到的转场效果的
# 我们对所有的转场效果(不管是这里定义的还是后端或者用户定义的)都有如下要求：
# 1.  对转场效果的含义和参数有明确的定义；后端可以定义在语义上有些许不同的同一转场效果
# 2.  所有定义在此的(通用)转场效果必须在所有后端都有实现(可以转化为其他效果)
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
  # 对该转场的引用中需要包含实际转场的名称
  pass


#class VNTransitionEffectRecord(VNRecord):
#  _backing_impl_operand : OpOperand # ClassLiteral 参数，指向该效果的实现
#  _duration_operand : OpOperand # 浮点参数，以秒为单位，代表默认的持续时间。所有转场都必须有这个。（后端实现不了的话可忽略该值）

#  def __init__(self, name: str, loc: Location, **kwargs) -> None:
#    ty = VNEffectFunctionType.get(loc.context)
#    super().__init__(name, loc, ty, **kwargs)
#    self._duration_operand = self._add_operand_with_value('duration', FloatLiteral.get(0.35, loc.context))


@IRObjectJsonTypeName("vn_transition_ce")
class VNTransitionEffectConstExpr(ConstExpr):
  # 我们使用此类型来给转场效果赋予参数
  # 如果需要给该调用赋予名称，可以使用 VNConstExprAsRecord

  def construct_init(self, *, context: Context, values: typing.Iterable[Value], **kwargs) -> None:
    ty = VNEffectFunctionType.get(context)
    super().construct_init(context=context, ty=ty, values=values, **kwargs)

  def post_init(self) -> None:
    # 检查输入，第一项一定是一个转场效果的实现，第二个是一个浮点数的时长
    impl = self.get_operand(0)
    assert isinstance(impl, ClassLiteral) and issubclass(impl.value, VNTransitionEffectImplementationBase)
    duration = self.get_operand(1)
    assert isinstance(duration.valuetype, FloatType)

  def get_implementation(self) -> type:
    return self.get_operand(0).value

  def get_duration(self) -> Value: # may be a variable or a FloatLiteral
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
    return VNTransitionEffectConstExpr._get_impl(ty, params) # type: ignore

# TODO 定义作用于设备的特效（既有持续性的（比如下雪）也有暂态的（比如屏幕闪光））
# 基于类似转场效果的逻辑，我们把特效定义为一种值而不是指令
# 特效有两种，一种作用于有句柄的内容（比如角色小跳），一种作用于设备（基本就是多一个内容项）
# 我们使用 put/create 来表示作用于设备的特效，使用 modify 来表示作用于句柄的特效

class VNDefaultTransitionType(enum.Enum):
  # 默认的转场，包括图片、音视频
  # 使用默认转场时，这个值应该在 EnumLiteral 中
  DT_NO_TRANSITION  = enum.auto()
  DT_SPRITE_SHOW  = enum.auto()
  DT_SPRITE_MOVE  = enum.auto()
  # 没有修改的情形；立绘改变内容时（主要是切换表情时）默认没有渐变
  DT_SPRITE_HIDE  = enum.auto()
  DT_IMAGE_SHOW   = enum.auto()
  DT_IMAGE_MOVE   = enum.auto()
  DT_IMAGE_MODIFY = enum.auto()
  DT_IMAGE_HIDE   = enum.auto()
  DT_BACKGROUND_SHOW    = enum.auto()
  DT_BACKGROUND_CHANGE  = enum.auto()
  DT_BACKGROUND_HIDE    = enum.auto()
  #DT_BGM_START    = enum.auto()
  DT_BGM_CHANGE   = enum.auto()
  #DT_BGM_STOP     = enum.auto()

  @staticmethod
  def get_default_transition_type(v : Value) -> VNDefaultTransitionType | None:
    if isinstance(v, EnumLiteral):
      e = v.value
      if isinstance(e, VNDefaultTransitionType):
        return e
    return None

  def get_enum_literal(self, context : Context) -> EnumLiteral:
    return EnumLiteral.get(context, self)

class VNBackendDisplayableTransitionExpr(LiteralExpr):
  # 后端特有的
  def construct_init(self, *, context : Context, value_tuple : tuple[StringLiteral, StringLiteral, EnumLiteral[VNDefaultTransitionType]], **kwargs) -> None:
    assert len(value_tuple) == 3
    assert isinstance(value_tuple[0], StringLiteral)
    assert isinstance(value_tuple[1], StringLiteral)
    assert isinstance(value_tuple[2], EnumLiteral)
    assert isinstance(value_tuple[2].value, VNDefaultTransitionType)
    ty = VNEffectFunctionType.get(context)
    super().construct_init(ty=ty, value_tuple=value_tuple, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return VNEffectFunctionType

  @property
  def value(self) -> tuple[StringLiteral, StringLiteral, EnumLiteral[VNDefaultTransitionType]]:
    return super().value

  @property
  def backend(self) -> StringLiteral:
    return self.get_operand(0)

  @property
  def expression(self) -> StringLiteral:
    return self.get_operand(1)

  @property
  def fallback(self) -> EnumLiteral[VNDefaultTransitionType]:
    return self.get_operand(2)

  def __str__(self) -> str:
    return 'Transition<' + self.backend.get_string() + ">(\"" + self.expression.get_string() + "\", fallback=" + self.fallback.value.name +")"

  @staticmethod
  def get(context : Context, backend : StringLiteral, expression : StringLiteral, fallback : EnumLiteral[VNDefaultTransitionType]) -> VNBackendDisplayableTransitionExpr:
    if not isinstance(backend, StringLiteral):
      raise RuntimeError("Expecting StringLiteral for backend: " + type(backend).__name__)
    if not isinstance(expression, StringLiteral):
      raise RuntimeError("Expecting StringLiteral for expression: " + type(expression).__name__)
    if not isinstance(fallback, EnumLiteral):
      raise RuntimeError("Expecting EnumLiteral for fallback: " + type(fallback).__name__)
    elif not isinstance(fallback.value, VNDefaultTransitionType):
      raise RuntimeError("Expecting VNDefaultTransitionType for fallback element: " + type(fallback.value).__name__)
    return VNBackendDisplayableTransitionExpr._get_literalexpr_impl((backend, expression, fallback), context)

# 目前音频仅支持淡入淡出渐变
# TODO 加入前端支持
class VNAudioFadeTransitionExpr(LiteralExpr):
  DEFAULT_FADEIN : typing.ClassVar[decimal.Decimal] = decimal.Decimal(0.5)
  DEFAULT_FADEOUT : typing.ClassVar[decimal.Decimal] = decimal.Decimal(0.5)

  def construct_init(self, *, context : Context, value_tuple : tuple[FloatLiteral, FloatLiteral], **kwargs) -> None:
    assert len(value_tuple) == 2
    assert isinstance(value_tuple[0], FloatLiteral) and isinstance(value_tuple[1], FloatLiteral)
    ty = VNEffectFunctionType.get(context)
    super().construct_init(ty=ty, value_tuple=value_tuple, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return VNEffectFunctionType

  @property
  def value(self) -> tuple[FloatLiteral, FloatLiteral]:
    return super().value

  @property
  def fadein(self) -> FloatLiteral:
    return self.get_operand(0)

  @property
  def fadeout(self) -> FloatLiteral:
    return self.get_operand(1)

  def __str__(self) -> str:
    return "AudioFade(fadein=" + str(self.fadein.value) + ", fadeout=" + str(self.fadeout.value) + ")"

  @staticmethod
  def get(context : Context, fadein: FloatLiteral | None, fadeout : FloatLiteral | None):
    if fadein:
      assert isinstance(fadein, FloatLiteral)
    else:
      fadein = FloatLiteral.get(VNAudioFadeTransitionExpr.DEFAULT_FADEIN, context)
    if fadeout:
      assert isinstance(fadeout, FloatLiteral)
    else:
      fadeout = FloatLiteral.get(VNAudioFadeTransitionExpr.DEFAULT_FADEOUT, context)
    return VNAudioFadeTransitionExpr._get_literalexpr_impl((fadein, fadeout), context)

# ------------------------------------------------------------------------------
# 函数、指令等
# ------------------------------------------------------------------------------

@IROperationDataclassWithValue(VNFunctionReferenceType)
@IRObjectJsonTypeName("vn_function_op")
class VNFunction(VNSymbol):
  # 为了保证用户能够理解“为什么有一部分内容没有在函数中出现”，
  # 我们需要保留没有被转为有效输出的内容
  # 现在他们都被放在 lost 区中，都以 MetadataOp 的形式保存
  # 如果一个函数的函数体(body)是空的，那么这是一个函数声明，否则这是一个定义

  # 函数属性标记
  ATTR_ENTRYPOINT : typing.ClassVar[str] = "EntryPoint" # 表示该函数应当作为引擎的某个入口。带一个字符串参数，表示是什么入口。
  ATTRVAL_ENTRYPOINT_MAIN : typing.ClassVar[str] = "main"

  NAME_PREBODY  : typing.ClassVar[str] = "prebody"
  NAME_POSTBODY : typing.ClassVar[str] = "postbody"

  lost : Region # 编译中碰到的不属于任何其他函数或命令的内容
  body: Region # 内容主体

  def set_lost_block_prebody(self, block : Block):
    assert self.lost.blocks.empty
    block.name = self.NAME_PREBODY
    self.lost.blocks.push_back(block)

  def set_lost_block_postbody(self, block : Block):
    assert self._lost.blocks.size < 2
    block.name = self.NAME_POSTBODY
    self.lost.blocks.push_back(block)

  def create_block(self, name : str) -> Block:
    b = self.body.create_block(name)
    b.add_argument('start', VNTimeOrderType.get(self.context))
    return b

  def has_body(self) -> bool:
    return not self.body.blocks.empty

  def get_entry_block(self) -> Block:
    return self.body.entry_block

  def get_entry_point(self) -> str | None:
    # 如果该函数有 EntryPoint 属性，则返回所指的入口名
    return self.get_attr(VNFunction.ATTR_ENTRYPOINT)

  def set_as_entry_point(self, entryname : str | None = None):
    if entryname is None:
      self.remove_attr(VNFunction.ATTR_ENTRYPOINT)
    else:
      assert isinstance(entryname, str)
      self.set_attr(VNFunction.ATTR_ENTRYPOINT, entryname)

  @staticmethod
  def create(context : Context, name : str, loc : Location | None = None):
    return VNFunction(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IRObjectJsonTypeName("vn_instr_op")
class VNInstruction(Operation):
  # 所有指令的基类
  _start_time_operand : OpOperand # 1-N个开始时间
  _finish_time_result : OpResult # 1个结束时间

  def construct_init(self, *, context : Context, start_time : typing.Iterable[Value] | Value | None = None, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(context=context, name=name, loc=loc, **kwargs)
    self._start_time_operand = self._add_operand_with_value('start', start_time)
    self._finish_time_result = self._add_result('finish', VNTimeOrderType.get(context))

  def post_init(self) -> None:
    super().post_init()
    self._start_time_operand = self.get_operand_inst('start')
    self._finish_time_result = self.get_result('finish')

  def get_start_time(self, index : int | None = None) -> Value:
    return self._start_time_operand.get(index)

  def get_finish_time(self) -> OpResult:
    return self._finish_time_result

  def set_start_time(self, value : Value, index : int | None = None):
    self._start_time_operand.set_operand(index if index is not None else 0, value)

  def try_get_parent_group(self) -> VNInstructionGroup | None:
    if isinstance(self.parent_op, VNInstructionGroup):
      return self.parent_op
    return None

@IROperationDataclass
@IRObjectJsonTypeName("vn_instrgroup_op")
class VNInstructionGroup(VNInstruction):
  # 指令组都只有一个块，指令组内的指令使用的时间直接取上层的（来自指令组外的）值
  # 为了方便计算指令组本身所用的时间，我们把：
  # 1.  指令组内“最先”的指令的时间输入作为指令组的时间输入
  # 2.  指令组的“时间输出”是个输入参数，引用指令组内的时间输出结果
  #     如果指令组内的指令输出多个时间，则一般把“最后”的时间输出作为指令组的时间输出结果
  # 指令组本身的 finish_time 即为 finish_time_operand 的取值

  body : Block
  group_finish_time : OpOperand[Value]

  def get_finish_time_src(self) -> Value | None:
    return self.group_finish_time.try_get_value()

@IROperationDataclass
@IRObjectJsonTypeName("vn_backend_instrgroup_op")
class VNBackendInstructionGroup(VNInstructionGroup):
  # 后端指令组，用于放置一些后端独有的指令
  # 执行顺序、时间参数等均由后端决定
  # 其中的指令不一定是（或者说大概率不是）VNInstruction 的子类

  @staticmethod
  def create(context : Context, start_time : Value | None = None, name: str = '', loc: Location | None = None):
    return VNBackendInstructionGroup(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, name=name, loc=loc)

@IROperationDataclass
@IRObjectJsonTypeName("vn_say_instrgroup_op")
class VNSayInstructionGroup(VNInstructionGroup):
  # 发言指令组，用于将单次人物发言的所有有关内容（说话者，说话内容，侧边头像，等等）组合起来的指令组
  # 一个发言指令组对应回溯记录（Backlog）里的一条记录
  # 发言人可以不止一个，语音、文本也可以不止一条，但是后端有可能会不支持
  # 我们可以给每条发言设置一个 ID，方便之后搞翻译和配音
  sayer : OpOperand[VNCharacterSymbol] # 发言者（可以不止一个不过一般是一个）
  sayid : OpOperand[StringLiteral]

  def get_single_sayer(self) -> VNCharacterSymbol:
    return self.sayer.get()

  @staticmethod
  def create(context : Context, start_time : Value, sayer : typing.Iterable[VNCharacterSymbol] | VNCharacterSymbol | None, name: str = '', loc: Location | None = None):
    return VNSayInstructionGroup(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, sayer=sayer, name=name, loc=loc)

@IROperationDataclass
@IRObjectJsonTypeName("vn_scene_switch_instrgroup_op")
class VNSceneSwitchInstructionGroup(VNInstructionGroup):
  # 场景切换指令组，用于将场景切换有关的内容组合起来
  # 部分后端有单个指令完成多个操作（如 RenPy 中的 scene 命令可以实现清屏+切换背景），该指令组用于引导该类指令生成
  # 该指令组应当包含所有由于“场景切换”所需的指令，这样如果后端有指令能够完成多个操作，则可以用这些特殊指令
  # 如果指令组中的指令无法全部由单个指令实现，则剩余指令可像其他情况那样视为单独的指令进行生成
  # 每个函数开始时，默认当前场景的内容都未定义（或者说就是一片黑）
  # 每个函数即将结束时也可有一个场景切换指令组，将当前的所有内容清除（目标场景可以为 None）；否则下一个函数（或者返回到调用者后）无法将场上的内容清除
  dest_scene : OpOperand[VNSceneSymbol]

  @staticmethod
  def create(context : Context, start_time : Value, dest_scene : VNSceneSymbol | None = None, name: str = '', loc: Location | None = None):
    return VNSceneSwitchInstructionGroup(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, dest_scene=dest_scene, name=name, loc=loc)

@IRObjectJsonTypeName("vn_wait_instr_op")
class VNWaitInstruction(VNInstruction):
  @staticmethod
  def create(context : Context, start_time : Value, name: str = '', loc: Location | None = None):
    return VNWaitInstruction(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, name=name, loc=loc)

@IROperationDataclass
class VNPlacementInstBase(VNInstruction):
  content : OpOperand[Value]
  device : OpOperand[VNDeviceSymbol]
  placeat : SymbolTableRegion
  transition : OpOperand[Value]

@IROperationDataclass
class VNPutInst(VNPlacementInstBase):
  # 放置指令会在目标设备上创建一个内容，但是与创建指令不同，该指令不返回句柄
  # 放置指令创建的内容的有效期由设备、环境等决定，而不是由程序显式地去移除
  # 常用的场景如在发言指令组内设置头像、发言内容等，有效期到下一条发言为止
  # 放置指令所创建的内容一般不会在非正常跳转时保留（比如用户指定跳转到某位置）
  # 如需要播放音频，放置指令将在设备上当前播放的内容结束后播放

  @staticmethod
  def create(context : Context, start_time: Value, content : typing.Iterable[Value] | Value | None = None, device : VNDeviceSymbol | None = None, name: str = '', loc: Location | None = None) -> VNPutInst:
    return VNPutInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, content=content, device=device, name=name, loc=loc)

@IROperationDataclass
class VNCreateInst(VNPlacementInstBase, Value):
  # 创建指令基本同放置指令，唯一区别是会有一个句柄值

  @staticmethod
  def create(context : Context, start_time: Value, content : Value | None = None, ty : VNHandleType | None = None, device : VNDeviceSymbol | None = None, name: str = '', loc: Location | None = None) -> VNCreateInst:
    if ty is not None:
      assert isinstance(ty, VNHandleType)
    elif content is not None:
      vty = content.valuetype
      ty = VNHandleType.get(vty)
    else:
      raise RuntimeError("Need to know content type")
    return VNCreateInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, content=content, device=device, ty=ty, name=name, loc=loc)

@IROperationDataclass
class VNModifyInst(VNInstruction, Value):
  # 对某对象做任何改变的指令，包括呈现方式更改（如位置）和内容更改（包括切换到另一个内容，不包括删除）
  # 强调一遍，可以使用该指令改变句柄代表的内容，这样可以指定比如 crossfade 这样涉及前后两个内容的渐变效果，或是使用前一个内容留下的位置等信息
  # 如果我们对场景进行切换，我们也使用基于该指令的子类
  # 更改指令不能更改所在的设备，不能更改内容的类型（比如不能用视频替换文本）
  # content 和 placeat 不为空，不改变对应项就重复之前的内容
  handlein : OpOperand
  content : OpOperand[Value]
  device : OpOperand[VNDeviceSymbol]
  placeat : SymbolTableRegion
  transition : OpOperand[Value]

  @staticmethod
  def create(context : Context, start_time: Value, handlein : Value, content : Value, device : VNDeviceSymbol, name: str = '', loc: Location | None = None) -> VNModifyInst:
    return VNModifyInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, handlein=handlein, content=content, ty=handlein.valuetype, device=device, name=name, loc=loc)

@IROperationDataclass
class VNRemoveInst(VNInstruction):
  # 去除某对象句柄所用的指令，只能指定渐变效果
  handlein : OpOperand
  transition : OpOperand[Value]

  @staticmethod
  def create(context : Context, start_time: Value, handlein : Value, name: str = '', loc: Location | None = None) -> VNRemoveInst:
    return VNRemoveInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, handlein=handlein, name=name, loc=loc)

@IROperationDataclass
class VNTerminatorInstBase(VNInstruction):
  # 该指令可以结束当前基本块
  pass

@IROperationDataclass
class VNExitInstBase(VNTerminatorInstBase):
  # 该指令可以结束当前函数（同时结束当前基本块）
  pass

@IROperationDataclass
class VNCallInst(VNInstruction):
  target : OpOperand[VNFunction]
  destroyed_handle_list : OpOperand[Value]
  # 跳转到目标函数，但仍返回；当前所有句柄不保留
  @staticmethod
  def create(context : Context, start_time: Value, target : VNFunction, destroyed_handle_list : typing.Iterable[Value] | None = None, name : str = '', loc : Location | None = None):
    return VNCallInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, target=target, destroyed_handle_list=destroyed_handle_list, name=name, loc=loc)

@IROperationDataclass
class VNReturnInst(VNExitInstBase):
  # 返回调用者，当前所有句柄不保留
  @staticmethod
  def create(context : Context, start_time: Value, name : str = '', loc : Location | None = None):
    return VNReturnInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, name=name, loc=loc)

@IROperationDataclass
class VNUnreachableInst(VNExitInstBase):
  # 该指令不该被执行
  # 目前如果有跳转到一个没被定义的标签的话，该标签会包含一条该指令
  @staticmethod
  def create(context : Context, start_time: Value, name : str = '', loc : Location | None = None):
    return VNUnreachableInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, name=name, loc=loc)

@IROperationDataclass
class VNTailCallInst(VNExitInstBase, VNCallInst):
  # 跳转到目标函数，不返回；当前所有句柄不保留
  @staticmethod
  def create(context : Context, start_time: Value, target : VNFunction, destroyed_handle_list : typing.Iterable[Value] | None = None, name : str = '', loc : Location | None = None):
    return VNTailCallInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, target=target, destroyed_handle_list=destroyed_handle_list, name=name, loc=loc)

@IROperationDataclass
class VNEndingInst(VNExitInstBase):
  # 结束故事所用的指令，显式地表示到达某个结局
  ending : OpOperand[StringLiteral] # 结局的名称

  @staticmethod
  def create(context : Context, start_time: Value, ending: StringLiteral | str , name : str = '', loc : Location | None = None):
    return VNEndingInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, ending=ending, name=name, loc=loc)

@IROperationDataclass
class VNLocalTransferInstBase(VNTerminatorInstBase):
  # 该指令只结束当前基本块；控制流会转移到同函数的另一基本块
  # 由于我们使用 BlockArgument 来取代句柄的 PHI 结点，当目的基本块不同时，我们需要传递的句柄也可能不同
  # 所以这里我们统一给每个可能的目的基本块单独保存需传递的句柄
  # （如果句柄被传递到这，那么后续的代码不能再用原来的句柄值，必须使用目标基本块的 BlockArgument）
  # target_list 可以包含同一个基本块不止一次（比如不同选项对应同一个结局）

  target_list : OpOperand[Block] # 所有的跳转目标

  def _get_blockarg_operand_name(self, index : int) -> str:
    return 'blockarg_' + str(index)

  def get_blockarg_operandinst(self, index : int) -> OpOperand:
    return self.get_operand_inst(self._get_blockarg_operand_name(index))

  def _add_branch_impl(self, target : Block) -> OpOperand:
    index = self.target_list.get_num_operands()
    self.target_list.add_operand(target)
    return self._add_operand(self._get_blockarg_operand_name(index))

  def get_local_cfg_dest(self) -> tuple[Block]:
    return tuple([v.value for v in self.target_list.operanduses()])

@IROperationDataclass
class VNBranchInst(VNLocalTransferInstBase):
  # 所有的函数内跳转（不管有无条件）都用这个
  # condition_list 一定比 target_list 少一个值，target_list里第一项为无条件跳转的目标点
  condition_list : OpOperand[Value] # 所有的条件（各个 if 的条件，应该都是 BoolType）（无条件跳转的话可以为空）

  def get_default_branch_target(self) -> Block:
    return self.target_list.get_operand(0)

  def add_branch(self, condition : Value, target : Block) -> OpOperand:
    assert isinstance(condition.valuetype, BoolType) and isinstance(target, Block)
    self.condition_list.add_operand(condition)
    return super()._add_branch_impl(target)

  def get_num_conditional_branch(self) -> int:
    return self.condition_list.get_num_operands()

  def get_conditional_branch_tuple(self, index : int) -> tuple[Block, Value]: # conditional branch index --> <Block, condition>
    target = self.target_list.get_operand(index + 1)
    cond = self.condition_list.get_operand(index)
    return (target, cond)

  @staticmethod
  def create(context : Context, start_time: Value, defaultbranch : Block, name : str = '', loc : Location | None = None):
    result = VNBranchInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, name=name, loc=loc)
    result._add_branch_impl(defaultbranch)
    return result

@IROperationDataclass
class VNMenuInst(VNLocalTransferInstBase):
  # 想跳出选项时就用该指令
  # 如果想在选项时有发言(VNSayInstGroup)，那么该指令组后面不应该跟随 VNWaitInst 而是直接跟这个
  # (即该 VNMenuInst 的起始时间应该取 VNSayInstGroup 的结束时间)
  # 目前暂不支持在选单文本中使用字符串表达式，每个选项必须是字符串常量
  text_list : OpOperand[StringLiteral] # 所有的选项文本
  condition_list : OpOperand[Value] # 所有的让选项出现的条件（各个 if 的条件，应该都是 BoolType）（没有的话用 BoolLiteral 来填）

  def add_option(self, text : StringLiteral | str, target : Block, condition : Value | None = None) -> OpOperand:
    assert isinstance(target, Block)
    if condition is not None:
      assert isinstance(condition.valuetype, BoolType)
    else:
      condition = BoolLiteral.get(True, self.context)
    if isinstance(text, str):
      text = StringLiteral.get(text, self.context)
    else:
      assert isinstance(text, StringLiteral)
    self.text_list.add_operand(text)
    self.condition_list.add_operand(condition)
    return self._add_branch_impl(target)

  @staticmethod
  def create(context : Context, start_time: Value, name : str = '', loc : Location | None = None):
    return VNMenuInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, name=name, loc=loc)

@IROperationDataclass
@IRObjectJsonTypeName("vn_namespace_op")
class VNNamespace(Symbol, NamespaceNodeInterface[VNSymbol]):
  functions : SymbolTableRegion[VNFunction]
  assets : SymbolTableRegion[VNConstExprAsSymbol]
  characters : SymbolTableRegion[VNCharacterSymbol]
  scenes : SymbolTableRegion[VNSceneSymbol]
  devices : SymbolTableRegion[VNDeviceSymbol]
  values : SymbolTableRegion[VNValueSymbol]
  aliases : SymbolTableRegion[VNAliasSymbol]
  _namespace_path_tuple : tuple[str] = temp_field(default_factory=tuple)

  @staticmethod
  def stringize_namespace_path(path : tuple[str]) -> str:
    return '/' + '/'.join(path)

  @staticmethod
  def expand_namespace_str(path : str) -> tuple[str]:
    assert len(path) > 0 and path[0] == '/'
    return tuple([v for v in path.split('/') if len(v) > 0])

  def _custom_postinit_(self):
    # 命名空间应该组成一个树结构，都以'/'开始，以'/'为分隔符
    assert self.name.startswith('/')
    self._namespace_path_tuple = VNNamespace.expand_namespace_str(self.name)

  def add_function(self, func : VNFunction) -> VNFunction:
    assert isinstance(func, VNFunction)
    self.functions.add(func)
    return func

  def get_function(self, name : str) -> VNFunction:
    return self.functions.get(name)

  def add_scene(self, scene : VNSceneSymbol) -> VNSceneSymbol:
    assert isinstance(scene, VNSceneSymbol)
    self.scenes.add(scene)
    return scene

  def add_character(self, character : VNCharacterSymbol) -> VNCharacterSymbol:
    assert isinstance(character, VNCharacterSymbol)
    self.characters.add(character)
    return character

  def add_device(self, device : VNDeviceSymbol) -> VNDeviceSymbol:
    assert isinstance(device, VNSymbol)
    self.devices.add(device)
    return device

  def add_asset(self, asset : VNConstExprAsSymbol) -> VNConstExprAsSymbol:
    assert isinstance(asset, VNConstExprAsSymbol)
    self.assets.add(asset)
    return asset

  def add_alias(self, alias : VNAliasSymbol) -> VNAliasSymbol:
    assert isinstance(alias, VNAliasSymbol)
    self.aliases.add(alias)
    return alias

  def get_device(self, name : str) -> VNDeviceSymbol:
    record = self.devices.get(name)
    assert isinstance(record, VNDeviceSymbol)
    return record

  def get_namespace_path(self) -> tuple[str]:
    return self._namespace_path_tuple

  def get_namespace_string(self) -> str:
    return self.name

  def get_namespace_parent_node(self) -> VNNamespace | None:
    if len(self._namespace_path_tuple) == 0:
      return None
    toplevel = self.parent_op
    assert isinstance(toplevel, VNModel)
    return toplevel.get_namespace(VNNamespace.stringize_namespace_path(self._namespace_path_tuple[:-1]))

  def lookup_name(self, name: str) -> VNNamespace | VNSymbol | NamespaceNodeInterface.AliasEntry | None:
    if alias := self.aliases.get(name):
      return alias.get_entry_dataclass()
    for table in (self.functions, self.assets, self.characters, self.scenes, self.devices):
      if symb := table.get(name):
        return symb
    return None

  @staticmethod
  def create(name : str, loc : Location):
    return VNNamespace(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

@IROperationDataclass
@IRObjectJsonTypeName("vn_model_op")
class VNModel(Operation):
  namespace : SymbolTableRegion[VNNamespace]
  # 为了复用符号表的有关代码，我们把命名空间的不同部分用'/'分隔开，和目录一样，全局命名空间也有'/'
  # 根据命名空间查找内容应该使用额外的手段（比如前段可以用 nameresolution 有关的实现）

  def get_namespace(self, namespace : str) -> VNNamespace | None:
    return self.namespace.get(namespace)

  def add_namespace(self, namespace : VNNamespace) -> VNNamespace:
    self.namespace.add(namespace)
    return namespace

  @staticmethod
  def create(context : Context, name : str = '', loc : Location = None) -> VNModel:
    return VNModel(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

class VNModelNameResolver(NameResolver[VNFunction | VNSymbol]):
  _model : VNModel

  def __init__(self, model : VNModel) -> None:
    super().__init__()
    self._model = model

  def get_namespace_node(self, path: typing.Tuple[str]) -> NamespaceNodeInterface[T] | None:
    return self._model.get_namespace(VNNamespace.stringize_namespace_path(path))

  def get_root_node(self) -> NamespaceNodeInterface[T]:
    return self._model.get_namespace('/')

class VNInstructionBuilder:
  _block : Block
  _loc : Location
  _time : Value
  _time_writeback : OpOperand[Value] | None
  _insert_before_op : VNInstruction | None # if none, insert at the end of block

  def __init__(self, loc : Location, block : Block, insert_before : VNInstruction | None = None, time : Value | None = None, time_writeback : OpOperand[Value] | None = None) -> None:
    assert block is not None or insert_before is not None
    self._block = block
    self._insert_before_op = insert_before
    self._loc = loc
    if self._insert_before_op:
      if block is not None:
        assert self._insert_before_op.parent_block is block
      else:
        self._block = self._insert_before_op.parent_block
    if time is not None:
      self._time = time
    else:
      # if we insert before inst, we use the start time value for the instruction being inserted
      # otherwise, find the end time of the last instruction in the block
      # if the block is empty, use the block start time
      if self._insert_before_op is not None:
        self._time = self._insert_before_op.get_start_time()
      else:
        self._time = self._block.get_argument('start')
        if not self._block.body.empty:
          if last_inst := self.get_last_vninst_before_pos(self._block.body.back):
            self._time = last_inst.get_finish_time()
    assert self._time is not None and isinstance(self._time.valuetype, VNTimeOrderType)
    self._time_writeback = time_writeback
    if time_writeback is not None:
      assert isinstance(time_writeback, OpOperand)
      time_writeback.set_operand(0, self._time)

  @staticmethod
  def get_last_vninst_before_pos(op : Operation) -> VNInstruction | None:
    while not isinstance(op, VNInstruction):
      prev = op.get_prev_node()
      if prev is None:
        return None
      op = prev
    return op

  @property
  def block(self):
    return self._block

  @property
  def insert_before(self):
    return self._insert_before_op

  @property
  def location(self):
    return self._loc

  @location.setter
  def location(self, loc : Location):
    self._loc = loc

  @property
  def time(self):
    return self._time

  @time.setter
  def time(self, t : Value):
    self._time = t

  def place_instr(self, update_time : bool, instr : VNInstruction) -> VNInstruction:
    if self._insert_before_op is None:
      self._block.body.push_back(instr)
    else:
      instr.insert_before(self._insert_before_op)
    if update_time:
      self._time = instr.get_finish_time()
      if self._time_writeback is not None:
        self._time_writeback.set_operand(0, self._time)
    return instr

  def move_ip_to_end_of_block(self, target : Block):
    self._block = target
    self._time = self._block.get_argument('start')
    self._insert_before_op = None
    if not self._block.body.empty:
      if last_inst := self.get_last_vninst_before_pos(self._block.body.back):
        self._time = last_inst.get_finish_time()

  def createSayInstructionGroup(self, sayer : typing.Iterable[VNCharacterSymbol] | VNCharacterSymbol | None, name : str = '', loc : Location | None = None, update_time : bool = True) -> tuple[VNSayInstructionGroup, VNInstructionBuilder]:
    group = VNSayInstructionGroup.create(self._loc.context, self._time, sayer=sayer, name=name, loc=loc)
    builder = VNInstructionBuilder(group.location, group.body, time=self._time, time_writeback=group.group_finish_time)
    self.place_instr(update_time, group)
    return (group, builder)

  def createSceneSwitchInstructionGroup(self, scene : VNSceneSymbol, name : str = '', loc : Location | None = None, update_time : bool = True) -> tuple[VNSceneSwitchInstructionGroup, VNInstructionBuilder]:
    group = VNSceneSwitchInstructionGroup.create(self._loc.context, self._time, dest_scene=scene, name=name, loc=loc)
    builder = VNInstructionBuilder(group.location, group.body, time=self._time, time_writeback=group.group_finish_time)
    self.place_instr(update_time, group)
    return (group, builder)

  def createPut(self, content : Value, device : VNDeviceSymbol, update_time : bool = False, name : str = '', loc : Location | None = None) -> VNPutInst:
    # put instructions default NOT to update the start time
    return self.place_instr(update_time, VNPutInst.create(context=self._loc.context, start_time=self._time, content=content, device=device, name=name, loc=loc))

  def createCreate(self, content : Value, device : VNDeviceSymbol, update_time : bool = True, name : str = '', loc : Location | None = None) -> VNCreateInst:
    return self.place_instr(update_time, VNCreateInst.create(context=self._loc.context, start_time=self._time, content=content, device=device, name=name, loc=loc))

  def createWait(self, update_time : bool = True, name : str = '', loc : Location | None = None) -> VNWaitInstruction:
    return self.place_instr(update_time, VNWaitInstruction.create(self._loc.context, self._time, name, loc))

  def createBranch(self, defaultbranch : Block, move_ip : bool = True,  name : str = '', loc : Location | None = None) -> VNBranchInst:
    result = self.place_instr(False, VNBranchInst.create(context=self._loc.context, start_time=self._time, defaultbranch=defaultbranch, name=name, loc=loc))
    if move_ip:
      self.move_ip_to_end_of_block(defaultbranch)
    return result

  def createCall(self, target : VNFunction, destroyed_handle_list : typing.Iterable[Value] | None = None, update_time : bool = True, name : str = '', loc : Location | None = None) -> VNCallInst:
    return self.place_instr(update_time, VNCallInst.create(context=self._loc.context, start_time=self._time, target=target, destroyed_handle_list=destroyed_handle_list, name=name, loc=loc))

  def createReturn(self, name : str = '', loc : Location | None = None) -> VNReturnInst:
    return self.place_instr(False, VNReturnInst.create(context=self._loc.context, start_time=self._time, name=name, loc=loc))
