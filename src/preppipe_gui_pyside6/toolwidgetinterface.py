from __future__ import annotations
import dataclasses
import typing
import enum
import weakref
from PySide6.QtCore import *
from PySide6.QtWidgets import QWidget
from preppipe.language import *

class ToolWidgetUniqueLevel(enum.Enum):
  UNLIMITED = 0
  SINGLE_INSTANCE = 1
  SINGLE_INSTANCE_WITH_DIFFERENT_DATA = 2

@dataclasses.dataclass
class ToolWidgetInfo:
  idstr : str # 用于避免重复打开同一个工具的标识符
  name : Translatable | str
  widget : type[QWidget] | None = None
  data : dict[str, typing.Any] | None = None
  icon_path : str | None = None
  tooltip : Translatable | None = None
  uniquelevel : ToolWidgetUniqueLevel = ToolWidgetUniqueLevel.SINGLE_INSTANCE_WITH_DIFFERENT_DATA

class ToolWidgetInterface:
  # 在主界面的树状结构中展示的工具的基类
  # 因为可能需要一些“假节点”所以该类不继承自 QWidget
  # 为了使同一个工具能提供多个不同的入口，我们使用如下准则：
  # 1. 一个入口 = 工具类 + 任意参数，当能作为入口时， getToolInfo() 返回有效值，否则返回 None
  # 2. getToolInfo() 返回值不是 None 的话， idstr 一定是相同的值
  # 3. 同一内容的所有 kwargs (包括 getToolInfo(), getChildTools(), setData() 的参数)都会保持一致，这也意味着 kwargs 相同时不同函数返回的内容应该是对同一个入口的
  #
  # 举例：图片包工具的可以用 kwargs 指定打开哪个图片包，这样就可以在树状结构中展示多个图片包工具；同时 kwargs 不包含图片包 ID 的话则作为父节点将所有图片包内容整合在一起

  # 用于去重、标签管理的信息
  _toolinfo : ToolWidgetInfo

  # 用于更新语言时自动更新文本
  _tr_binding_dict : weakref.WeakKeyDictionary[QObject, dict[str, Translatable | typing.Callable[[], str]]]
  _tr_general_list : list[tuple[typing.Callable[[str], None], Translatable | typing.Callable[[], str]]]

  def __init__(self, *args, **kwargs) -> None:
    super().__init__(*args, **kwargs)
    self._tr_binding_dict = weakref.WeakKeyDictionary()
    self._tr_general_list = []

  def setData(self, **kwargs):
    pass

  def getData(self) -> dict:
    return {}

  def setWidgetIdentificationInfo(self, info : ToolWidgetInfo):
    self._toolinfo = info

  def getWidgetIdentificationInfo(self) -> ToolWidgetInfo:
    return self._toolinfo

  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    raise NotImplementedError("Subclasses must implement the getToolInfo() method.")

  @classmethod
  def getChildTools(cls, **kwargs) -> list[type[ToolWidgetInterface] | tuple[type[ToolWidgetInterface], dict] | ToolWidgetInfo] | None:
    # 如果返回列表的话，有三种可选项：
    # 1. 直接返回 ToolWidgetInterface 子类、不带参数，程序会再调用 getToolInfo()、getChildTools() 来获取信息
    # 2. 带参数的版本：返回一个元组，第一个元素是 ToolWidgetInterface 子类，第二个元素是一个 dict
    # 3. 直接返回 ToolWidgetInfo，这样没有子节点了
    return None

  def canClose(self) -> bool:
    # 返回 True 表示可以关闭
    return True

  def closeHandler(self) -> None:
    # 如果关闭时有待完成的操作，可以在这里完成
    pass

  # 用于应对语言切换

  @staticmethod
  def _update_text_qobject(obj : QObject, key : str, tr : Translatable | typing.Callable[[], str]):
    newstr = tr.get() if isinstance(tr, Translatable) else tr()
    getattr(obj, key)(newstr)

  def bind_text_qobject(self, obj : QObject, key : str, tr : Translatable | typing.Callable[[], str]):
    if obj not in self._tr_binding_dict:
      self._tr_binding_dict[obj] = {}
    self._tr_binding_dict[obj][key] = tr
    self._update_text_qobject(obj, key, tr)

  def bind_text(self, func : typing.Callable[[str], None], tr : Translatable | typing.Callable[[], str]):
    # 先检查 func 是否是 QObject 的方法
    if hasattr(func, "__self__") and isinstance(func.__self__, QObject):
      self.bind_text_qobject(func.__self__, func.__name__, tr)
      return
    # 否则直接加入列表
    self._tr_general_list.append((func, tr))
    func(tr.get() if isinstance(tr, Translatable) else tr())

  def update_text(self):
    if not isinstance(self, QWidget):
      raise RuntimeError("ToolWidgetInterface instance must be a QWidget")
    for obj, tr_dict in self._tr_binding_dict.items():
      for key, tr in tr_dict.items():
        self._update_text_qobject(obj, key, tr)
    for func, tr in self._tr_general_list:
      func(tr.get() if isinstance(tr, Translatable) else tr())
    # 先按照默认信息改标题，子类可以按需要在之后再更改
    # (如果值不是 Translatable 的话也不需要更改)
    if isinstance(self._toolinfo.name, Translatable):
      self.setWindowTitle(self._toolinfo.name.get())
    if isinstance(self._toolinfo.tooltip, Translatable):
      self.setToolTip(self._toolinfo.tooltip.get())

