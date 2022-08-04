# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import enum

from ..irbase import *
from .vntype import *
from .vnconstant import *

class VNRecord(Symbol):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNDeviceRecord(VNRecord, Value):
  class DeviceFlag(enum.Enum):
    NoFlag = 0,
    Input = 1,  # can read from this device
    Output = 2  # can write to the device

  # map for all predefined, cross-platform I/O endpoints
  # all predefined devices are under preppipe/ prefix
  # all the values are for the output types (which data can be written to this device)
  # we typically only use standard instructions (show, hide, post, etc) on them
  _predefined_output_device_map : typing.ClassVar[dict[str, type]] = {
    # 音频设备
    "语涵/音频/语音" : VNAudioType,
    "语涵/音频/声效" : VNAudioType,
    "语涵/音频/音乐" : VNAudioType,
    # 图形（displayable）设备
    # 虽然一般都只用一个屏幕，但是为了避免在任何时候都要用到纵向顺序（zorder），我们预设以下多个设备来保证图形间的顺序
    # 若同设备下还需分层（比如不同层需要用不同的指令），则可以在设备记录里记录【纵向顺序区间】到【图层组】的对应关系
    "语涵/图形/背景" : VNDisplayableType, # 背景图片
    "语涵/图形/前景" : VNDisplayableType, # 立绘和前景等
    "语涵/图形/覆盖" : VNDisplayableType, # 在UI等元素之上的层(Overlay)；全屏的视频等可以放这里
    # ADV模式独有的设备
    "语涵/ADV/文本" : VNTextType, # ADV模式下对话内容输出
    "语涵/ADV/发言者" : VNTextType, # ADV模式下说话者名称的输出
    "语涵/ADV/侧边头像" : VNImageType, # ADV模式下侧边头像的图案（一般在左侧）
    # NVL模式独有的设备
    "语涵/NVL/文本" : VNTextType,
    "语涵/NVL/发言者" : VNTextType,
    "语涵/NVL/侧边头像" : VNImageType, # 一般没人用，但是万一
    # 调试输出设备
    "语涵/调试/日志" : VNTextType # 调试日志输出
  }
  # the map for input devices; the value of each entry is the result type
  # we typically use special instructions to tune the exact appearance (e.g., the prompt for a text input)
  _predefined_input_device_map : typing.ClassVar[dict[str, type]] = {
    "preppipe/textbox/string" : VNStringType, # string input
    "preppipe/menu/singlechoice": None, # menu steps use control flow to use the selection value instead of dataflow
    "preppipe/rand/randint" : VNIntType # random integer input
  }
  _element_type : VNType
  _flags : set[DeviceFlag]
  def __init__(self, name: str, loc: Location, element_type : VNType, flags : set[DeviceFlag], **kwargs) -> None:
    ty = VNDeviceReferenceType.get(element_type)
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)
    self._element_type = element_type
    self._flags = flags.copy()
    assert isinstance(element_type, VNType)
  
  @property
  def element_Type(self) -> VNType:
    return self._element_type
  
  @property
  def flags(self) -> set[DeviceFlag]:
    return self._flags
  
  @staticmethod
  def create_predefined_device(ctx : Context, name : str) -> VNDeviceRecord:
    name = name.lower()
    if name in VNDeviceRecord._predefined_output_device_map:
      ty = VNDeviceRecord._predefined_output_device_map[name]
      flags = set([VNDeviceRecord.DeviceFlag.Output])
      return VNDeviceRecord(name, Location.getNullLocation(ctx), ty, flags)
    elif name in VNDeviceRecord._predefined_input_device_map:
      ty = VNDeviceRecord._predefined_input_device_map[name]
      flags = set([VNDeviceRecord.DeviceFlag.Input])
      return VNDeviceRecord(name, Location.getNullLocation(ctx), ty, flags)
    return None

class VNVariableRecord(VNRecord, Value):
  class StorageModel(enum.Enum):
    Global = 0, # per-player/account/.. state; all savings share the same copy
    ThreadLocal = enum.auto() # per-saving state; each saving has its own copy
  
  _storage_model : StorageModel
  _data_type : VNType
  
  def __init__(self, name: str, loc: Location, variable_type : VNType, storage : StorageModel, **kwargs) -> None:
    reftype = VNVariableReferenceType.get(variable_type)
    super().__init__(name = name, loc = loc, ty = reftype, **kwargs)
    self._storage_model = storage
    self._data_type = variable_type
  
  @property
  def storage_model(self) -> StorageModel:
    return self._storage_model
  
  @property
  def variable_type(self) -> VNType:
    return self._data_type

class VNCharacterRecord(VNRecord, Value):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    ty = VNCharacterDeclType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)

class VNDisplayableTransitionEffectRecord(VNRecord):
  # 可显示项的转场效果记录
  # 由于这部分我们一般直接检查对象类型，没有需要引用该类型的其他场景（没有二阶类型会引用这个），所以这些记录不继承Value
  # 对转场效果的引用都直接引用该对象

  # 以下定义预设的转场效果，值为转场效果的输入类型
  # 所有时间单位默认是秒，距离单位是像素
  _predefined_input_transitions : typing.ClassVar[dict[str, list[type]]] = {
    "语涵/入场/渐变" : [VNFloatType], # 渐变(fade)，只有一个持续时间输入
    "语涵/入场/溶解" : [VNFloatType], # 溶解(dissolve)

  }
  # 还有出场的，TODO

  _input_types : list[type] # 该转场的输入

  pass

class VNDisplayableRecord(VNRecord, Value):
  # 可显示项记录包含了一个可显示项的所有信息，包括：
  # 1. 显示的内容（图片、文本、视频、帧动画等）或是效果
  # 2. 显示的位置（写这段注释的时候我们只使用屏幕坐标）
  # 3. 入场、出场效果（直接出现，飞入，等等）
  # 对于以上的每一项，如果他们需要带参数，则参数应该保留在该记录中（而不是在引起该改变的指令中），这样可以避免在创建、消除、更改指令中重复添加这些参数
  # 对于以上的每一项，同一个可显示项可以定义多个值（比如每个立绘表情都是独立的值，每个位置都是独立的值），创建、消除、更改指令会携带参数指明他们所需要的值
  # 由以上对可显示项的定义，对于显示输出指令来说，基本上能“外包”的内容都外包给了可显示项记录这个“黑盒”，以后如果有更复杂的可显示项对以上部分有更强的约束条件的话也可以更好地进行支持

  # 如果该可显示项对应一个人物立绘，我们可以用元数据来标注。我们不把这个定义为必须项。
  
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    ty = VNDisplayableType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)

class VNSelectorRecord(VNRecord):
  pass