from __future__ import annotations
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import *
from .forms.generated.ui_mainwindow import Ui_MainWindow
from .navigatorwidget import *
from .toolwidgets.home import *
from .toolwidgets.setting import *
from .mainwindowinterface import *

class MainWindow(QMainWindow, MainWindowInterface):
  def __init__(self):
    super(MainWindow, self).__init__()
    self.ui = Ui_MainWindow()
    self.ui.setupUi(self)
    self.setWindowTitle(Translatable.tr_program_name.get())
    self.requestOpenWithType(NavigatorWidget)
    self.requestOpenWithType(HomeWidget)

  def requestOpen(self, info : ToolWidgetInfo) -> None:
    if info.widget is None:
      return
    numtabs = self.ui.tabWidget.count()
    for i in range(numtabs):
      curtab = self.ui.tabWidget.widget(i)
      if not isinstance(curtab, ToolWidgetInterface):
        raise PPInternalError(f"Tab {i} is not a ToolWidgetInterface")
      cur_info = curtab.getWidgetIdentificationInfo()
      if cur_info.idstr != info.idstr:
        continue
      if cur_info.uniquelevel == ToolWidgetUniqueLevel.SINGLE_INSTANCE:
        self.ui.tabWidget.setCurrentIndex(i)
        return
      if cur_info.data != info.data or cur_info.uniquelevel == ToolWidgetUniqueLevel.UNLIMITED:
        continue
      if cur_info.uniquelevel == ToolWidgetUniqueLevel.SINGLE_INSTANCE_WITH_DIFFERENT_DATA:
        self.ui.tabWidget.setCurrentIndex(i)
        return
      raise PPInternalError(f"Unhandled unique level {cur_info.uniquelevel.name}")

    widget = info.widget(self)
    if not isinstance(widget, ToolWidgetInterface):
      raise PPInternalError(f"Widget {widget} is not a ToolWidgetInterface")
    widget.setWidgetIdentificationInfo(info)
    if info.data is not None:
      widget.setData(**info.data)
    else:
      widget.setData()
    self.ui.tabWidget.addTab(widget, info.name.get() if isinstance(info.name, Translatable) else info.name)
    self.ui.tabWidget.setCurrentWidget(widget)
    return

  def handleLanguageChange(self) -> None:
    for i in range(self.ui.tabWidget.count()):
      curtab = self.ui.tabWidget.widget(i)
      if not isinstance(curtab, ToolWidgetInterface):
        raise PPInternalError(f"Tab {i} is not a ToolWidgetInterface")
      curtab.update_text()
      self.ui.tabWidget.setTabText(i, curtab.windowTitle())
      self.ui.tabWidget.setTabToolTip(i, curtab.toolTip())
    self.setWindowTitle(Translatable.tr_program_name.get())
    return

  @staticmethod
  def initialize():
    # 读取已保存的设置
    SettingWidget.initialize()
