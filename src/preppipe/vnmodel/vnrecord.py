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

class VNForwardOp(Symbol):
  # 【传递】用于把输入作为可以按名查找的值，只能出现在记录中
  # 此项不继承Value，根本上杜绝出现直接的环型依赖

  _op : OpOperand # 唯一参数，用于输出

  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._op = self._add_operand('')
  
  @property
  def value(self) -> Value:
    return self._op.get()
  
  @value.setter
  def value(self, v : Value):
    self._op.set_operand(0, v)
  
  @value.deleter
  def value(self):
    self._op.drop_all_uses()

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
    "语涵/ADV/侧边头像" : VNDisplayableType, # ADV模式下侧边头像的图案（一般在左侧）
    # NVL模式独有的设备
    "语涵/NVL/文本" : VNTextType,
    "语涵/NVL/发言者" : VNTextType,
    "语涵/NVL/侧边头像" : VNDisplayableType, # 一般没人用，但是万一
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
  def element_type(self) -> VNType:
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
  # 可显示项的转场效果记录，类型都是特效函数类型（VNEffectFunctionType）

  # 以下定义预设的转场效果，值为转场效果的输入类型
  # 所有时间单位默认是秒，距离单位是像素
  _predefined_input_transitions : typing.ClassVar[dict[str, list[type]]] = {
    "语涵/入场/渐变" : [VNFloatType], # 渐变(fade)，只有一个持续时间输入
    "语涵/入场/溶解" : [VNFloatType], # 溶解(dissolve)

  }
  # 还有出场的，TODO

  _input_types : list[type] # 该转场的输入

  pass

class VNDisplayableTransitionDefinitionOp(Symbol):
  # 定义转场特效的、按名访问的符号
  # 基本上就是一个对转场特效函数的调用，放在可显示项记录的转场区以供引用
  # 我们只定义对转场特效函数的引用，其他所需参数由用户代码指定（可以在指令定义后添加输入）
  # 类型和 VNDisplayableTransitionEffectRecord 一样，都是特效函数类型（VNEffectFunctionType）

  _transition : OpOperand # 单个对转场特效函数的引用，该参数没有名字，必须存在

  def __init__(self, name: str, loc: Location, transition_function : VNDisplayableTransitionEffectRecord, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._transition = self._add_operand_with_value('', transition_function)
  
  @property
  def transition(self) -> VNDisplayableTransitionEffectRecord:
    return self._transition.get()

class VNContentRecordBase(VNRecord, Value):
  # 所有可用于输出的内容记录的基类
  # 所有的内容都有以下相同点：
  # 1. 内容绑定一个输出设备（我们以此区分背景图与立绘，音乐与音效，等等）
  # 2. 内容记录的值是一个对该内容的引用，可以用在创建、放置指令上
  # 3. 所有的内容都可以定义一些变体（如立绘有差分），代表了实际上的内容。部分内容可能只有一个变体，这不影响我们将其抽象出来
  # 4. 所有内容都可以定义一些过渡效果（如图片的溶解，声音的淡入淡出，等等），我们把该内容可能出现的过渡效果都在此类中记录下来
  # 5. 一些对所有变体都适用的设置（比如文本所用的字体、行间距等很少改的属性）。设置的名称应该对该内容有意义
  # 定义的变体以及过渡效果可以由 VNForwardOp 来直接存储引用
  # 由于内容可以有变体，“使用多个内容项、每项只有一个变体”与“使用单个内容项，该内容项内有众多变体”在其他项相同时没有实际意义上的区别。
  # 一般情况下，我们根据“该内容所关联的事物、人物”以及内容变种的“层级”决定变体与内容项的划分：
  # 1. 同一人物在不同姿势、衣着下的立绘属于不同的内容项，同一姿势、衣着下的不同表情差分属于相同的内容项。（三级：人物-形象-表情）
  # 2. 不同人物的发言属于不同的内容项，同一人物的所有发言文本属于相同的内容项。（两级：人物-内容）

  _device_operand : OpOperand
  _variants : SymbolTableRegion
  _transitions : SymbolTableRegion # 参数均为特效函数类型（VNEffectFunctionType）
  _settings : SymbolTableRegion # 参数类型根据具体的设定项决定，并不唯一
  
  def __init__(self, name: str, loc: Location, ty : VNType, device : Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, ty = ty, **kwargs)
    self._device_operand = self._add_operand_with_value('设备', device)
    self._variants = self._add_symbol_table('变体')
    self._transitions = self._add_symbol_table('过渡')
    self._settings = self._add_symbol_table('设置')
  
  @property
  def device(self) -> Value:
    return self._device_operand.get()
  
  @device.setter
  def device(self, d : VNDeviceRecord):
    assert isinstance(d.valuetype, VNDeviceReferenceType)
    self._device_operand.set_operand(0, d)
  
  @device.deleter
  def device(self):
    self._device_operand.drop_all_uses()

  # 子类可以加上更正的类型标注
  
  def add_variant(self, name : str, content : Value, loc : Location = None) -> VNForwardOp:
    if loc is None:
      loc = self.location
    op = VNForwardOp(name, loc)
    op.value = content
    self._variants.add(op)
    return op
  
  def add_transition(self, transition : Symbol):
    self._transitions.add(transition)
    return transition
  
  def get_or_create_setting(self, name : str, loc : Location = None) -> VNForwardOp:
    if name in self._settings:
      return self._settings[name]
    if loc is None:
      loc = self.location
    op = VNForwardOp(name, loc)
    self._settings.add(op)
    return op
  
  def set_setting(self, name : str, value : typing.Any, loc : Location = None) -> VNForwardOp:
    if name in self._settings:
      op = self._settings[name]
      op.value = value
      return op
    op = VNForwardOp(name, loc)
    self._settings.add(op)
    op.value = value
    return op

class VNDisplayableRecord(VNContentRecordBase):
  # 所有可显示项类型的基类
  # 可显示项记录包含了一个可显示项的所有信息，包括：
  # 1. 显示的内容（图片、文本、视频、帧动画等）、效果变体。所有改变了显示内容的效果（如高亮，滤镜，特别是缩放，等等）都包含在该部分。
  #    所有显示内容的大小都是编译时已知的常量，显示内容的坐标以左上角为原点
  #    创建、放置指令必须指定显示内容的值；修改指令不提供显示内容的值的话默认保持当前内容。
  # 2. 显示的位置（写这段注释的时候我们只使用屏幕坐标）。
  #    创建、放置指令必须包含有效的值。
  # 3. 其他（非过渡）效果（可以在不改变位置、内容时使用），如小跳（迅速向上移动然后下落）、冒泡（表达人物心情如愤怒、沉思、疑惑）等。任意时刻应该只有一个效果生效。
  #    若有关指令没有指定，则默认没有特殊效果。
  # 对于以上的每一项，如果他们需要带参数，则参数应该保留在该记录中（而不是在引起该改变的指令中），这样可以避免在创建、消除、更改指令中重复添加这些参数
  # 对于以上的每一项，同一个可显示项可以定义多个值（比如每个立绘表情都是独立的值，每个位置都是独立的值），创建、消除、更改指令会携带参数指明他们所需要的值
  # 对于以上的每一项，即使相同的值会被用在多个可显示项中（比如他们过渡效果是一样的），我们也要求该值必须出现在所有可显示项的各自记录中（而不是共享同一个值），
  # 这样便于我们检查、审查每个可显示项可能的显示方式及可能的显示效果，不必检查所有引用该可显示项的地方
  # 由以上对可显示项的定义，对于显示输出指令来说，基本上能“外包”的内容都外包给了可显示项记录这个“黑盒”，以后如果有更复杂的可显示项对以上部分有更强的约束条件的话也可以更好地进行支持
  # 如果该可显示项对应一个人物立绘，我们可以用元数据来标注。我们不把这个定义为必须项。

  # 在实现上，上述各项各有一个符号表用以存放相关信息
  # 坐标常量、图片引用等可以通过传递操作符（VNForwardOp）放到相应的区里
  # 所有内容都以左上顶点为位置的锚点（即坐标(0,0)将把图片的左上角对准屏幕左上角）
  # 纵向顺序（zorder）（一个整数值）将由各指令指定；如果该指令需要，则可以带这个输入。
  # 每个可显示项都绑定一个输出设备，由该记录的‘设备’参数指定。可显示项绑定设备的原因是（1）节省创建、放置指令的输入，只需指定可显示项即可；（2）可在检视时更方便地获取输出设备的信息（主要是分辨率）

  _positions : SymbolTableRegion # 参数值均为坐标类型，一般为坐标常量
  _effects : SymbolTableRegion # TODO 参数均为特效函数类型（VNEffectFunctionType）

  def __init__(self, name: str, loc: Location, device : Value, **kwargs) -> None:
    ty = VNDisplayableType.get(loc.context)
    super().__init__(name = name, loc = loc, ty = ty, device = device, **kwargs)
    self._positions = self._add_symbol_table('位置')
    self._effects = self._add_symbol_table('效果')
  
  @VNContentRecordBase.device.setter
  def device(self, d : VNDeviceRecord):
    assert isinstance(d.valuetype, VNDeviceReferenceType)
    assert isinstance(d.element_type, VNDisplayableType)
    self._device_operand.set_operand(0, d)
  
  def add_position(self, name : str, position : Value, loc : Location = None) -> VNForwardOp:
    if loc is None:
      loc = self.location
    op = VNForwardOp(name, loc)
    op.value = position
    self._positions.add(op)
    return op

  def add_effect(self, effect : VNForwardOp):
    self._effects.add(effect)
    return effect
  
  @staticmethod
  def create_simple_displayable_record(name : str, loc : Location, device : VNDeviceRecord, displayable : Value, position : Value) -> dict[str, typing.Any]:
    # 创建一个只有单个变体、单个位置、没有其他任何过渡效果及特效的可显示项
    # 返回的字典可以直接用于创建、放置指令
    d = VNDisplayableRecord(name, loc, device)
    variant = d.add_variant(displayable)
    pos = d.add_position('', position)
    return {'content' : d, 'variant' : variant, 'position' : pos}

class VNAudioRecord(VNContentRecordBase):
  # 音频类型记录的基类
  # 暂时没有额外的信息需要记录

  def __init__(self, name: str, loc: Location, device: Value, **kwargs) -> None:
    ty = VNAudioType.get(loc.context)
    super().__init__(name, loc, ty, device, **kwargs)

  @staticmethod
  def create_simple_audio_record(name : str, loc : Location, device : VNDeviceRecord, audio : Value) -> dict[str, typing.Any]:
    # 创建一个只有单个变体、没有任何其他过渡效果及特效的音频
    # 返回的字典可以直接用于创建、放置指令
    a = VNAudioRecord(name, loc, device)
    v = a.add_variant(audio)
    return {'content' : a, 'variant' : v}

class VNTextRecord(VNContentRecordBase):
  # 文本类型记录
  # 没有额外的信息需要记录
  def __init__(self, name: str, loc: Location, device: Value, **kwargs) -> None:
    ty = VNTextType.get(loc.context)
    super().__init__(name, loc, ty, device, **kwargs)
  
  @staticmethod
  def create_simple_text_record(name : str, loc : Location, device : VNDeviceRecord, text : Value) -> dict[str, typing.Any]:
    t = VNTextRecord(name, loc, device)
    v = t.add_variant(text)
    return {'content' : t, 'variant' : v}

class VNSelectorRecord(VNRecord):
  pass