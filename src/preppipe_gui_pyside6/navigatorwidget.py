from __future__ import annotations
import dataclasses
from PySide6.QtCore import *
from PySide6.QtCore import QObject
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from .forms.generated.ui_navigatorwidget import Ui_NavigatorWidget
from .guiassets import *
from .mainwindowinterface import *
from .toolwidgets.imagepack import *
from .toolwidgets.setting import *
from .toolwidgets.maininput import *

class ToolNode:
  info : ToolWidgetInfo | None
  parent : ToolNode | None
  children : list[ToolNode]
  ROOT : typing.ClassVar[ToolNode | None] = None
  PINNED : typing.ClassVar[list] = [

  ]
  NAVIGATION_LIST : typing.ClassVar[list] = [
    SettingWidget,
    MainInputWidget,
    (ImagePackWidget, {"category_kind": ImagePackDescriptor.ImagePackType.BACKGROUND}),
    (ImagePackWidget, {"category_kind": ImagePackDescriptor.ImagePackType.CHARACTER}),
  ]

  def __init__(self, /, info: ToolWidgetInfo | None, parent: ToolNode | None = None):
    self.info = info
    self.parent = parent
    self.children = []

  def addChild(self, child: ToolNode):
    self.children.append(child)
    child.parent = self

  def removeChild(self, child: ToolNode):
    self.children.remove(child)
    child.parent = None

  @staticmethod
  def build_tree():
    if ToolNode.ROOT is not None:
      return ToolNode.ROOT
    AssetManager.get_instance() # 触发资源载入
    def populate_entry(entry, parent : ToolNode | None) -> ToolNode:
      if isinstance(entry, ToolWidgetInfo):
        return ToolNode(entry, parent)
      if isinstance(entry, tuple) and len(entry) == 2:
        tool_cls = entry[0]
        kwargs = entry[1]
      elif isinstance(entry, type) and issubclass(entry, ToolWidgetInterface):
        tool_cls = entry
        kwargs = {}
      else:
        raise ValueError(f"Invalid entry type: {entry}")

      info = tool_cls.getToolInfo(**kwargs)
      node = ToolNode(info, parent)
      children = tool_cls.getChildTools(**kwargs)
      if children is not None:
        for child in children:
          node.addChild(populate_entry(child, node))
      return node
    root = ToolNode(None)
    for entry in ToolNode.NAVIGATION_LIST:
      root.addChild(populate_entry(entry, root))
    ToolNode.ROOT = root
    return root

class ToolModel(QAbstractItemModel):
  def __init__(self, /, parent: QObject | None) -> None:
    super().__init__(parent)

  def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
    if not index.isValid():
      return None
    info = index.internalPointer().info
    match role:
      case Qt.DisplayRole:
        if isinstance(info.name, Translatable):
          return info.name.get()
        return info.name
      case Qt.DecorationRole:
        if info.icon_path is not None:
          if icon_path := GUIAssetLoader.try_get_asset_path(info.icon_path):
            return QIcon(icon_path)
        return QIcon()
      case Qt.ToolTipRole:
        if isinstance(info.tooltip, Translatable):
          return info.tooltip.get()
        return None
      case _:
        return None

  def emitSignalsForLanguageChange(self):
    topleft = self.index(0, 0)
    bottomright = self.index(self.rowCount(topleft) - 1, 0)
    self.dataChanged.emit(topleft, bottomright, [Qt.DisplayRole, Qt.ToolTipRole])

  def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
    parent_node = parent.internalPointer() if parent.isValid() else ToolNode.ROOT
    return len(parent_node.children)

  def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
    return 1

  def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
    if column != 0:
      return QModelIndex()
    parent_node = parent.internalPointer() if parent.isValid() else ToolNode.ROOT
    if row >= len(parent_node.children):
      return QModelIndex()
    child_node = parent_node.children[row]
    return self.createIndex(row, 0, child_node)

  def parent(self, index: QModelIndex) -> QModelIndex:
    if not index.isValid():
      return QModelIndex()
    parent_node = index.internalPointer().parent
    if parent_node is None:
      return QModelIndex()
    grandparent_node = parent_node.parent
    if grandparent_node is None:
      return QModelIndex()
    rowindex = grandparent_node.children.index(parent_node)
    return self.createIndex(rowindex, 0, parent_node)

class NavigatorWidget(QWidget, ToolWidgetInterface):
  ui : Ui_NavigatorWidget
  model : ToolModel

  def __init__(self, parent : QWidget):
    super(NavigatorWidget, self).__init__(parent)
    self.ui = Ui_NavigatorWidget()
    self.ui.setupUi(self)
    ToolNode.build_tree()
    self.model = ToolModel(self)
    self.ui.treeView.setModel(self.model)
    self.ui.treeView.setHeaderHidden(True)
    self.ui.treeView.expandAll()
    self.ui.treeView.clicked.connect(self.on_treeView_clicked)

  def on_treeView_clicked(self, index: QModelIndex):
    if not index.isValid():
      return
    info = index.internalPointer().info
    if info is None:
      return
    MainWindowInterface.getHandle(self).requestOpen(info)

  _tr_toolname_navigator = TR_gui_mainwindow.tr("toolname_navigator",
    en="Navigator",
    zh_cn="导航",
    zh_hk="導航",
  )

  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="navigator",
      name=cls._tr_toolname_navigator,
      widget=cls,
      uniquelevel=ToolWidgetUniqueLevel.SINGLE_INSTANCE,
    )

  def update_text(self):
    super().update_text()
    self.model.emitSignalsForLanguageChange()

  def canClose(self) -> bool:
    return False
