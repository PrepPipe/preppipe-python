from __future__ import annotations
import typing
import weakref
from PySide6.QtCore import QObject
from preppipe.language import *

class TranslatableWidgetInterface:
  # 用于更新语言时自动更新文本
  _twi_binding_dict : weakref.WeakKeyDictionary[QObject, dict[str, Translatable | typing.Callable[[], str]]]
  _twi_general_list : list[tuple[typing.Callable[[str], None], Translatable | typing.Callable[[], str]]]
  _twi_child_set : weakref.WeakSet[TranslatableWidgetInterface]

  def __init__(self, *args, **kwargs) -> None:
    super().__init__(*args, **kwargs)
    self._twi_binding_dict = weakref.WeakKeyDictionary()
    self._twi_general_list = []
    self._twi_child_set = weakref.WeakSet()

  def bind_text(self, func : typing.Callable[[str], None], tr : Translatable | typing.Callable[[], str]):
    # 先检查 func 是否是 QObject 的方法
    if hasattr(func, "__self__") and isinstance(func.__self__, QObject):
      self.bind_text_qobject(func.__self__, func.__name__, tr)
      return
    # 否则直接加入列表
    self._twi_general_list.append((func, tr))
    func(tr.get() if isinstance(tr, Translatable) else tr())

  def add_translatable_widget_child(self, child : TranslatableWidgetInterface):
    self._twi_child_set.add(child)

  def update_text(self):
    for obj, tr_dict in self._twi_binding_dict.items():
      for key, tr in tr_dict.items():
        self._update_text_qobject(obj, key, tr)
    for func, tr in self._twi_general_list:
      func(tr.get() if isinstance(tr, Translatable) else tr())
    for child in self._twi_child_set:
      child.update_text()

  @staticmethod
  def _update_text_qobject(obj : QObject, key : str, tr : Translatable | typing.Callable[[], str]):
    newstr = tr.get() if isinstance(tr, Translatable) else tr()
    getattr(obj, key)(newstr)

  def bind_text_qobject(self, obj : QObject, key : str, tr : Translatable | typing.Callable[[], str]):
    if obj not in self._twi_binding_dict:
      self._twi_binding_dict[obj] = {}
    self._twi_binding_dict[obj][key] = tr
    self._update_text_qobject(obj, key, tr)

