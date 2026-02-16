from __future__ import annotations
import webbrowser
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from .forms.generated.ui_mainwindow import Ui_MainWindow
from .navigatorwidget import *
from .toolwidgets.home import *
from .toolwidgets.setting import *
from .toolwidgets.execute import *
from .mainwindowinterface import *
from .guiassets import *

class MainWindow(QMainWindow, MainWindowInterface):
  wip_feature_warned : set[type[QWidget]]
  def __init__(self):
    super(MainWindow, self).__init__()
    self.ui = Ui_MainWindow()
    self.ui.setupUi(self)
    self.wip_feature_warned = set()
    if ico_path := GUIAssetLoader.try_get_asset_path("preppipe.ico"):
      self.setWindowIcon(QIcon(ico_path))
    self.updateTextForLanguage()
    self.requestOpenWithType(NavigatorWidget)
    self.requestOpenWithType(HomeWidget)
    self.ui.actionOpenDocumentation.triggered.connect(self.openDocumentHomePage)
    self.ui.actionOpenDocumentation.setShortcut(QKeySequence(QKeySequence.HelpContents))
    self.ui.actionSettings.triggered.connect(lambda: self.requestOpenWithType(SettingWidget))
    self.ui.actionMainPipeline.triggered.connect(lambda: self.requestOpenWithType(MainInputWidget))
    self.ui.actionNavigator.triggered.connect(lambda: self.requestOpenWithType(NavigatorWidget))
    self.ui.tabWidget.tabCloseRequested.connect(self.handleTabCloseRequest)

  _tr_functionality = TR_gui_mainwindow.tr("functionality",
    en="Functionality",
    zh_cn="功能",
    zh_hk="功能",
  )
  _tr_help = TR_gui_mainwindow.tr("help",
    en="Help",
    zh_cn="帮助",
    zh_hk="幫助",
  )
  _tr_open_documentation = TR_gui_mainwindow.tr("open_documentation",
    en="Open Documentation",
    zh_cn="打开文档",
    zh_hk="打開文檔",
  )
  _tr_wip_feature_title = TR_gui_mainwindow.tr("wip_feature_title",
    en="WIP Feature",
    zh_cn="特性未完成",
    zh_hk="特性未完成",
  )
  _tr_wip_feature_details = TR_gui_mainwindow.tr("wip_feature_details",
    en="This feature is still under development. The current appearance and functionality is subject to change.",
    zh_cn="此功能仍在开发中。目前的外观和功能随时可能被修改。",
    zh_hk="此功能仍在開發中。目前的外觀和功能隨時可能被修改。",
  )
  def updateTextForLanguage(self):
    self.setWindowTitle(Translatable.tr_program_name.get())
    self.ui.menuFunctionality.setTitle(self._tr_functionality.get())
    self.ui.actionSettings.setText(self.tr_toolname_settings.get())
    self.ui.actionMainPipeline.setText(self.tr_toolname_maininput.get())
    self.ui.actionNavigator.setText(self.tr_toolname_navigator.get())
    self.ui.menuHelp.setTitle(self._tr_help.get())
    self.ui.actionOpenDocumentation.setText(self._tr_open_documentation.get())

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
    setattr(widget, 'mainWindowHandle', self)
    if info.data is not None:
      widget.setData(**info.data)
    else:
      widget.setData()
    self.ui.tabWidget.addTab(widget, info.name.get() if isinstance(info.name, Translatable) else info.name)
    self.ui.tabWidget.setCurrentWidget(widget)
    if info.is_wip_feature and info.widget not in self.wip_feature_warned:
      self.wip_feature_warned.add(info.widget)
      QMessageBox.warning(self, self._tr_wip_feature_title.get(), self._tr_wip_feature_details.get())
    return

  def handleLanguageChange(self) -> None:
    for i in range(self.ui.tabWidget.count()):
      curtab = self.ui.tabWidget.widget(i)
      if not isinstance(curtab, ToolWidgetInterface):
        raise PPInternalError(f"Tab {i} is not a ToolWidgetInterface")
      curtab.update_text()
      self.ui.tabWidget.setTabText(i, curtab.windowTitle())
      self.ui.tabWidget.setTabToolTip(i, curtab.toolTip())
    self.updateTextForLanguage()
    return

  @Slot(int)
  def handleTabCloseRequest(self, tabindex : int):
    tab = self.ui.tabWidget.widget(tabindex)
    if not isinstance(tab, ToolWidgetInterface):
      raise PPInternalError(f"Tab {tabindex} is not a ToolWidgetInterface")
    if tab.canClose():
      tab.closeHandler()
      self.ui.tabWidget.removeTab(tabindex)
      if self.ui.tabWidget.count() == 0:
        self.requestOpenWithType(HomeWidget)
    return


  _tr_documentation_not_found_title = TR_gui_mainwindow.tr("documentation_not_found_title",
    en="Documentation not found",
    zh_cn="文档未找到",
    zh_hk="文檔未找到",
  )
  _tr_documentation_not_found_details_dir = TR_gui_mainwindow.tr("documentation_not_found_details_dir",
    en="Document directory {dir} not found. Please check the integrity of the installation.",
    zh_cn="文档目录 {dir} 未找到，请检查安装是否完整。",
    zh_hk="文檔目錄 {dir} 未找到，請檢查安裝是否完整。",
  )
  _tr_documentation_not_found_details_file = TR_gui_mainwindow.tr("documentation_not_found_details_file",
    en="Document page {page} not found. Please check the integrity of the installation.",
    zh_cn="文档页面 {page} 未找到，请检查安装是否完整。",
    zh_hk="文檔頁面 {page} 未找到，請檢查安裝是否完整。",
  )
  def requestOpenDocument(self, relpath : str | None = None) -> None:
    docs_root = ''
    if docs := os.environ.get("PREPPIPE_DOCS"):
      docs_root = os.path.abspath(docs)
    if len(docs_root) == 0:
      docs_root = os.path.join(SettingsDict.get_executable_base_dir(), 'docs')
    if not os.path.isdir(docs_root):
      QMessageBox.critical(self, self._tr_documentation_not_found_title.get(), self._tr_documentation_not_found_details_dir.format(dir=docs_root))
      return
    language_subdir = ""
    for lang_tag in Translatable.PREFERRED_LANG:
      match lang_tag:
        case "zh_cn":
          language_subdir = ""
          break
        case "en":
          language_subdir = "en"
          break
        case "zh_hk":
          language_subdir = "zh-Hant"
          break
        case _:
          continue
    if len(language_subdir) > 0:
      docs_root = os.path.join(docs_root, language_subdir)
    requested_page_relpath = relpath if relpath is not None else 'index.html'
    requested_page_path = os.path.join(docs_root, requested_page_relpath)
    if not os.path.isfile(requested_page_path):
      QMessageBox.critical(self, self._tr_documentation_not_found_title.get(), self._tr_documentation_not_found_details_file.format(page=requested_page_path))
      return
    webbrowser.open_new_tab('file:///' + requested_page_path)

  @Slot()
  def openDocumentHomePage(self):
    self.requestOpenDocument(None)

  def requestExecution(self, info : ExecutionInfo) -> None:
    toolinfo = ExecuteWidget.getToolInfo()
    toolinfo.data = {
      "execinfo" : info,
    }
    self.requestOpen(toolinfo)
    return

  @staticmethod
  def initialize():
    # 读取已保存的设置
    SettingWidget.initialize()
