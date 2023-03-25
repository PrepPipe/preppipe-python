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
class VNDeviceReferenceType(SingleElementParameterizedType):
  def __str__(self) -> str:
    return "设备<" + str(self.element_type) + ">"

  @classmethod
  def _get_typecheck(cls, element_type : ValueType) -> None:
    assert not isinstance(element_type, VNDeviceReferenceType)

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

  _s_traits : typing.ClassVar[tuple[type]] = (VNDisplayableTrait)

@IRObjectJsonTypeName("vn_audio_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNAudioType(StatelessType):
  # this type is for audios that have at least the "duration" attribute
  # again, not for assets that are just read

  _s_traits : typing.ClassVar[tuple[type]] = (VNAudioTrait)

@IRObjectJsonTypeName("vn_video_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNVideoType(StatelessType):
  _s_traits : typing.ClassVar[tuple[type]] = (VNDisplayableTrait, VNAudioTrait)

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
    breakloc = self.parameters.indexof(None)
    return self.parameters[:breakloc]

  def get_argument_type_tuple(self) -> tuple[ValueType]:
    breakloc = self.parameters.indexof(None)
    return self.parameters[breakloc+1:]

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
class VNVariableReferenceType(ParameterizedType):
  def __str__(self) -> str:
    return "变量引用<" + str(self.element_type) + ">"

  @classmethod
  def _get_typecheck(cls, element_type : ValueType) -> None:
    assert not isinstance(element_type, VNVariableReferenceType)

@IRObjectJsonTypeName("vn_coord_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VNScreenCoordinateType(StatelessType):
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

@IRObjectJsonTypeName("vn_record_op")
class VNRecord(Symbol, Value):
  # 记录是在输出脚本中 ODR 定义的、没有控制流的、可以赋予名称的、以自身所承载信息为主的实体
  # （输入输出）设备，变量，资源（图片、声音等），都算记录
  # 有些内容（比如缩放后的图片，纯色图片等）既可以作为常量表达式也可以作为记录，但是只要需要赋予名称，他们一定需要绑为记录(可用 VNConstExprAsRecord 解决)
  # 有些内容（比如预设的转场效果等）主要是代码，参数部分很少，我们可以为它们新定义字面值(Literal)，然后用常量表达式来表示对它们的引用
  def construct_init(self, *, ty : ValueType, name: str = '', loc: Location | None = None, **kwargs) -> None:
    return super().construct_init(name=name, loc=loc, ty=ty, **kwargs)

@IRObjectJsonTypeName("vn_cexpr_record_op")
class VNConstExprAsRecord(VNRecord):
  def construct_init(self, *, name: str, loc: Location, cexpr : ConstExpr, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, ty=cexpr.valuetype, **kwargs)
    self._add_operand_with_value('value', cexpr)


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


@IRObjectJsonTypeName("vn_device_record_op")
class VNDeviceRecord(VNRecord):
  # 所有输入输出设备记录的基类
  # 实例一般记录运行时的外观等设置，比如对话框背景图片和对话框位置
  # 现在还没开始做外观所以留白
  # 对于显示设备来说，所有的坐标都是相对于父设备的
  # 所有的显示设备都构成一棵树，最顶层是屏幕，屏幕包含一系列子设备（背景、前景、发言、遮罩）
  # 为了便于在命名空间层级查找设备名称，我们使用 def-use chain 来记录子设备，所有的设备记录实例都在同一个（命名空间的）表内
  _std_device_kind_op : OpOperand # 如果设备是某个标准设备的话，这是标准设备的类型
  _parent_operand : OpOperand # 如果该设备是含在另一个设备中的子设备，这里记录父设备的 _devnode_ref
  _devnode_ref : OpResult # 如果该设备包含子设备（比如发言，除了内容之外还要有说话者和侧边头像），则子设备的所有 _parent_operand 将引用该值

  def construct_init(self, name: str, loc: Location, content_type: ValueType, std_device_kind : VNStandardDeviceKind | None = None, **kwargs) -> None:
    ty = VNDeviceReferenceType.get(content_type)
    super().construct_init(name=name, loc=loc, ty=ty, **kwargs)
    std_device_kind_value = None
    if std_device_kind is not None and isinstance(std_device_kind, VNStandardDeviceKind):
      std_device_kind_value = EnumLiteral.get(ty.context, std_device_kind)
    self._std_device_kind_op = self._add_operand_with_value('std_device', std_device_kind_value)
    self._parent_operand = self._add_operand('parent')
    self._devnode_ref = self._add_result('devnode_ref', ty)

  def post_init(self) -> None:
    super().post_init()
    self._std_device_kind_op = self.get_operand_inst('std_device')
    self._parent_operand = self.get_operand_inst('parent')
    self._devnode_ref = self.get_result('devnode_ref')

  def get_parent_device(self) -> VNDeviceRecord | None:
    return self._parent_operand.get()

  def set_parent_device(self, parent : VNDeviceRecord):
    self._parent_operand.set_operand(0, parent.get_devnode_reference())

  def get_devnode_reference(self) -> OpResult:
    return self._devnode_ref

  def get_std_device_kind(self) -> VNStandardDeviceKind | None:
    kind_value = self._std_device_kind_op.get()
    if isinstance(kind_value, EnumLiteral):
      return kind_value.value
    return None

  @staticmethod
  def create_standard_device(context : Context, std_device_kind : VNStandardDeviceKind, name : str | None = None) -> VNDeviceRecord:
    content_ty = VNStandardDeviceKind.get_device_content_type(std_device_kind, context)
    if name is None:
      name = VNStandardDeviceKind.get_standard_device_name(std_device_kind)
    return VNDeviceRecord(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=context.null_location, content_type=content_ty, std_device_kind=std_device_kind)

  @staticmethod
  def create(context : Context, name: str, loc: Location, content_type: ValueType, std_device_kind : VNStandardDeviceKind | None = None) -> VNDeviceRecord:
    return VNDeviceRecord(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc, content_type=content_type, std_device_kind = std_device_kind)

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
    def handle_entry(parent : VNDeviceRecord | None, name : str, entry : tuple[VNStandardDeviceKind, dict] | VNStandardDeviceKind):
      nonlocal ns
      if isinstance(entry, tuple):
        kind, child = entry
      else:
        kind = entry
        child = None
      cur_entry = VNDeviceRecord.create_standard_device(ns.context, kind, name)
      ns.add_record(cur_entry)
      if parent is not None:
        cur_entry.set_parent_device(parent)
      if child is not None:
        for name, entry in child.items():
          handle_entry(cur_entry, name, entry)
    if tree is None:
      tree = VNDeviceRecord.STANDARD_DEVICE_TREE
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
class VNValueRecord(VNRecord):
  # 任何类型的编译时未知的量，包括用户定义的变量，设置（游戏名、版本号等），系统参数（引擎名称或版本，是否支持Live2D），有无子命名空间(有无DLC), 等等
  # 部分值只在特定命名空间有效，值的含义（如版本号）可能会由命名空间的不同而改变（比如是主游戏的版本还是DLC的版本，等等）
  pass


@IRObjectJsonTypeName("vn_env_value_record_op")
class VNEnvironmentValueRecord(VNValueRecord):
  # 所有用户无法写入的值，主要是版本号、是否有子命名空间，等等
  pass

@IRWrappedStatelessClassJsonName("vn_var_storage_e")
class VNVariableStorageModel(enum.Enum):
  # 决定某个变量的存储方式
  PERSISTENT  = enum.auto() # 可与其他程序、游戏共享的变量，游戏重装不清除。对应 RenPy 中的 MultiPersistent
  GLOBAL      = enum.auto() # 全局变量，不随存档改变，游戏删除后重装可清除。对应 RenPy 中的 Persistent
  SAVE_LOCAL  = enum.auto() # 存档变量，不同存档中的值可不同，删除存档后即可清除
  CONFIG      = enum.auto() # 设置变量，取决于引擎的具体实现。只能用于由引擎定义的值（版本号，游戏名，成就系统的值，等等）


@IRObjectJsonTypeName("vn_var_value_record_op")
class VNVariableRecord(VNValueRecord):
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

@IRObjectJsonTypeName("vn_char_record_op")
class VNCharacterRecord(VNRecord):
  _kind_operand : OpOperand

  NARRATOR_DEFAULT_NAME : typing.ClassVar[str] = "narrator"

  def construct_init(self, *, context : Context, kind : VNCharacterKind, name: str, loc: Location | None = None, **kwargs) -> None:
    ty = VNCharacterDeclType.get(context)
    super().construct_init(context=context, ty=ty, name=name, loc=loc, **kwargs)
    kind_value = EnumLiteral.get(context, kind)
    self._kind_operand = self._add_operand_with_value('kind', kind_value)

  def post_init(self) -> None:
    super().post_init()
    self._kind_operand = self.get_operand_inst('kind')

  @staticmethod
  def get_fixed_value_type() -> type:
    return VNCharacterDeclType

  @staticmethod
  def create(context : Context, kind : VNCharacterKind, name : str, loc : Location | None = None) -> VNCharacterRecord:
    return VNCharacterRecord(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind = kind, name=name, loc=loc)

  @staticmethod
  def create_narrator(context : Context) -> VNCharacterRecord:
    return VNCharacterRecord(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind = VNCharacterKind.NARRATOR, name=VNCharacterRecord.NARRATOR_DEFAULT_NAME, loc=context.null_location)

@IRObjectJsonTypeName("vn_scene_record_op")
class VNSceneRecord(VNRecord):
  def construct_init(self, *, context : Context, name: str = '', loc: Location | None = None, **kwargs) -> None:
    ty = VNSceneDeclType.get(context)
    super().construct_init(context=context, ty=ty, name=name, loc=loc, **kwargs)

  @staticmethod
  def get_fixed_value_type() -> type:
    return VNSceneDeclType

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

# ------------------------------------------------------------------------------
# 函数、指令等
# ------------------------------------------------------------------------------

@IRObjectJsonTypeName("vn_function_op")
class VNFunction(Symbol, Value):
  # 为了保证用户能够理解“为什么有一部分内容没有在函数中出现”，
  # 我们需要保留没有被转为有效输出的内容
  # 现在他们都被放在 lost 区中，都以 MetadataOp 的形式保存
  _lost : Region # 编译中碰到的不属于任何其他函数或命令的内容
  _body: Region # 内容主体

  def construct_init(self, *, context : Context, name: str = '', loc: Location | None = None, **kwargs) -> None:
    ty = VNFunctionReferenceType.get(context)
    super().construct_init(context=context, ty=ty, name=name, loc=loc, **kwargs)
    self._body = self._add_region('body')
    self._lost = self._add_region('lost')

  def post_init(self) -> None:
    super().post_init()
    self._body = self.get_region('body')
    self._lost = self.get_region('lost')

  def set_lost_block_prebody(self, block : Block):
    assert self._lost.blocks.empty
    block.name = 'prebody'
    self._lost.blocks.push_back(block)

  def set_lost_block_postbody(self, block : Block):
    assert self._lost.blocks.size < 2
    block.name = 'postbody'
    self._lost.blocks.push_back(block)

  def create_block(self, name : str) -> Block:
    b = self._body.create_block(name)
    b.add_argument('start', VNTimeOrderType.get(self.context))
    return b

  @property
  def body(self) -> Region:
    return self._body

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
    if isinstance(start_time, Value):
      start_time = (start_time,)
    self._start_time_operand = self._add_operand_with_value_list('start', start_time)
    self._finish_time_result = self._add_result('finish', VNTimeOrderType.get(context))

  def post_init(self) -> None:
    super().post_init()
    self._start_time_operand = self.get_operand_inst('start')
    self._finish_time_result = self.get_result('finish')

  def get_start_time(self, index : int | None = None) -> Value:
    return self._start_time_operand.get(index)

  def get_finish_time(self) -> OpResult:
    return self._finish_time_result

@IRObjectJsonTypeName("vn_instrgroup_op")
class VNInstructionGroup(VNInstruction):
  # 指令组都只有一个块，有时间输入、输出，其他则由各指令组子类决定
  _body : Block
  _body_start_time_arg : BlockArgument

  def construct_init(self, *, context: Context, start_time: typing.Iterable[Value] | Value | None = None, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(context=context, start_time=start_time, name=name, loc=loc, **kwargs)
    self._body = Block.create('body', context)
    self._add_region('').push_back(self._body)
    self._body_start_time_arg = self._body.add_argument('start', VNTimeOrderType.get(context))

  def post_init(self) -> None:
    self._body = self.get_region('').entry_block
    self._body_start_time_arg = self._body.get_argument('start')

  @property
  def body(self) -> Block:
    return self._body

  @property
  def body_start_time(self) -> BlockArgument:
    return self._body_start_time_arg

@IRObjectJsonTypeName("vn_backend_instrgroup_op")
class VNBackendInstructionGroup(VNInstructionGroup):
  # 后端指令组，用于放置一些后端独有的指令
  # 执行顺序、时间参数等均由后端决定
  # 其中的指令不一定是（或者说大概率不是）VNInstruction 的子类，开始时间参数完全可以不用
  pass

@IRObjectJsonTypeName("vn_say_instrgroup_op")
class VNSayInstructionGroup(VNInstructionGroup):
  # 发言指令组，用于将单次人物发言的所有有关内容（说话者，说话内容，侧边头像，等等）组合起来的指令组
  # 一个发言指令组对应回溯记录（Backlog）里的一条记录
  # 发言人可以不止一个，语音、文本也可以不止一条，但是后端有可能会不支持
  _sayer_operand : OpOperand

  def construct_init(self, *, context: Context, start_time: Value, sayer : VNCharacterRecord, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(context=context, name=name, loc=loc, start_time=start_time, **kwargs)
    self._sayer_operand = self._add_operand_with_value('sayer', sayer)

  def post_init(self) -> None:
    super().post_init()
    self._sayer_operand = self.get_operand_inst('sayer')

  def get_single_sayer(self) -> VNCharacterRecord:
    return self._sayer_operand.get()

  def get_sayer_operand(self) -> OpOperand:
    return self._sayer_operand

  @staticmethod
  def create(context : Context, start_time : Value, sayer : VNCharacterRecord, name: str = '', loc: Location | None = None):
    return VNSayInstructionGroup(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, sayer=sayer, name=name, loc=loc)

@IRObjectJsonTypeName("vn_wait_instr_op")
class VNWaitInstruction(VNInstruction):
  @staticmethod
  def create(context : Context, start_time : Value, name: str = '', loc: Location | None = None):
    return VNWaitInstruction(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, name=name, loc=loc)

class VNPutInst(VNInstruction):
  # 放置指令会在目标设备上创建一个内容，但是与创建指令不同，该指令不返回句柄
  # 放置指令创建的内容的有效期由设备、环境等决定，而不是由程序显式地去移除
  # 常用的场景如在发言指令组内设置头像、发言内容等，有效期到下一条发言为止
  # 放置指令所创建的内容一般不会在非正常跳转时保留（比如用户指定跳转到某位置）
  # 如需要播放音频，放置指令将在设备上当前播放的内容结束后播放
  _content_operand : OpOperand
  _device_operand : OpOperand

  def construct_init(self, *, context: Context, start_time: Value, content : Value | None = None, device : VNDeviceRecord | None = None, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(context=context, name=name, loc=loc, start_time=start_time, **kwargs)
    self._content_operand = self._add_operand_with_value('content', content)
    self._device_operand = self._add_operand_with_value('device', device)

  def post_init(self) -> None:
    super().post_init()
    self._content_operand = self.get_operand_inst('content')
    self._device_operand = self.get_operand_inst('device')

  @property
  def device(self) -> VNDeviceRecord | None:
    return self._device_operand.get()

  @device.setter
  def device(self, dev : VNDeviceRecord) -> None:
    self._device_operand.set_operand(0, dev)

  @property
  def content(self) -> Value:
    return self._content_operand.get()

  @content.setter
  def content(self, v : Value):
    self._content_operand.set_operand(0, v)

  @content.deleter
  def content(self, v : Value):
    self._content_operand.drop_all_uses()

  @staticmethod
  def create(context : Context, start_time: Value, content : Value | None = None, device : VNDeviceRecord | None = None, name: str = '', loc: Location | None = None) -> VNPutInst:
    return VNPutInst(init_mode=IRObjectInitMode.CONSTRUCT, context=context, start_time=start_time, content=content, device=device, name=name, loc=loc)

@IRObjectJsonTypeName("vn_namespace_op")
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

  def construct_init(self, *, name: str, loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    # 命名空间应该组成一个树结构，都以'/'开始，以'/'为分隔符
    assert name.startswith('/')
    self._namespace_path_tuple = VNNamespace.expand_namespace_str(name)
    self._function_region = self._add_symbol_table('functions')
    self._record_region = self._add_symbol_table('records')
    self._asset_region = self._add_symbol_table('assets')

  def post_init(self) -> None:
    super().post_init()
    self._namespace_path_tuple = VNNamespace.expand_namespace_str(self.name)
    self._function_region = self.get_symbol_table('functions')
    self._record_region = self.get_symbol_table('records')
    self._asset_region = self.get_symbol_table('assets')

  def add_function(self, func : VNFunction) -> VNFunction:
    assert isinstance(func, VNFunction)
    self._function_region.add(func)
    return func

  def get_function(self, name : str) -> VNFunction:
    return self._function_region.get(name)

  def add_record(self, record : VNRecord) -> VNRecord:
    assert isinstance(record, VNRecord)
    self._record_region.add(record)
    return record

  def get_record(self, name : str) -> VNRecord:
    return self._record_region.get(name)

  def get_device_record(self, name : str) -> VNDeviceRecord:
    record = self._record_region.get(name)
    assert isinstance(record, VNDeviceRecord)
    return record

  def get_namespace_path(self) -> tuple[str]:
    return self._namespace_path_tuple

  def get_namespace_parent_node(self) -> VNNamespace | None:
    if len(self._namespace_path_tuple) == 0:
      return None
    toplevel = self.parent_op
    assert isinstance(toplevel, VNModel)
    return toplevel.get_namespace(VNNamespace.stringize_namespace_path(self._namespace_path_tuple[:-1]))

  def lookup_name(self, name: str) -> VNNamespace | VNFunction | VNRecord | NamespaceNodeInterface.AliasEntry | None:
    if func := self._function_region.get(name):
      return func
    if record := self._record_region.get(name):
      return record
    if asset := self._asset_region.get(name):
      return asset
    return None

  @staticmethod
  def create(name : str, loc : Location):
    return VNNamespace(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

@IRObjectJsonTypeName("vn_model_op")
class VNModel(Operation):
  _namespace_region : SymbolTableRegion
  # 为了复用符号表的有关代码，我们把命名空间的不同部分用'/'分隔开，和目录一样，全局命名空间也有'/'
  # 根据命名空间查找内容应该使用额外的手段（比如前段可以用 nameresolution 有关的实现）

  def construct_init(self, name: str = '', loc: Location = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_symbol_table('namespaces')

  def post_init(self) -> None:
    super().post_init()
    self._namespace_region = self.get_symbol_table('namespaces')

  def get_namespace(self, namespace : str) -> VNNamespace | None:
    return self._namespace_region.get(namespace)

  def add_namespace(self, namespace : VNNamespace) -> VNNamespace:
    self._namespace_region.add(namespace)
    return namespace

  @staticmethod
  def create(context : Context, name : str = '', loc : Location = None) -> VNModel:
    return VNModel(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

class VNModelNameResolver(NameResolver[VNFunction | VNRecord]):
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
  _insert_before_op : VNInstruction | None # if none, insert at the end of block

  def __init__(self, loc : Location, block : Block, insert_before : VNInstruction | None = None, time : Value | None = None) -> None:
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
    assert self._time is not None
    if isinstance(self._time, OpResult):
      assert self._time.parent.parent_block is self._block

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
    return instr

  def createSayInstructionGroup(self, sayer : VNCharacterRecord, name : str = '', loc : Location | None = None, update_time : bool = True) -> tuple[VNSayInstructionGroup, VNInstructionBuilder]:
    group = VNSayInstructionGroup.create(self._loc.context, self._time, sayer=sayer, name=name, loc=loc)
    self.place_instr(update_time, group)
    builder = VNInstructionBuilder(group.location, group.body)
    return (group, builder)

  def createPut(self, content : Value, device : VNDeviceRecord, name : str = '', loc : Location | None = None):
    # put instructions default NOT to update the start time
    return self.place_instr(False, VNPutInst.create(context=self._loc.context, start_time=self._time, content=content, device=device, name=name, loc=loc))

  def createWait(self, name : str = '', loc : Location | None = None):
    return self.place_instr(True, VNWaitInstruction.create(self._loc.context, self._time, name, loc))

