import dataclasses
from PySide6.QtWidgets import *
from ..toolwidgetinterface import *
from ..mainwindowinterface import *
from ..forms.generated.ui_maininputwidget import Ui_MainInputWidget
from preppipe.language import *
from ..componentwidgets.filelistinputwidget import *
from ..guiassets import *
from ..execution import *

class MainInputWidget(QWidget, ToolWidgetInterface):
  ui : Ui_MainInputWidget
  filelist : FileListInputWidget

  _tr_desc = TR_gui_mainwindow.tr("maininput_desc",
    en="Read story scripts and then export game projects or produce analysis reports.",
    zh_cn="读取剧本，导出游戏工程或是分析报告。",
    zh_hk="讀取劇本，導出遊戲工程或是分析報告。",
  )
  @classmethod
  def getToolInfo(cls) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="maininput",
      name=MainWindowInterface.tr_toolname_maininput,
      tooltip=cls._tr_desc,
      widget=cls,
    )

  _tr_maininput_group_input = TR_gui_mainwindow.tr("maininput_group_input",
    en="Input",
    zh_cn="输入",
    zh_hk="輸入",
  )
  _tr_maininput_group_analysis = TR_gui_mainwindow.tr("maininput_group_analysis",
    en="Analysis",
    zh_cn="分析",
    zh_hk="分析",
  )
  _tr_maininput_group_export = TR_gui_mainwindow.tr("maininput_group_export",
    en="Export",
    zh_cn="导出",
    zh_hk="導出",
  )
  _tr_fieldname_files = TR_gui_mainwindow.tr("fieldname_script_files",
    en="Script Files",
    zh_cn="剧本文件",
    zh_hk="劇本文件",
  )
  _tr_filter_scriptinput = TR_gui_mainwindow.tr("filter_scriptinput",
    en="Supported Files (*.odt *.docx *.md *.txt)",
    zh_cn="支持的文件类型 (*.odt *.docx *.md *.txt)",
    zh_hk="支持的文件類型 (*.odt *.docx *.md *.txt)",
  )
  _tr_unable_to_execute = TR_gui_mainwindow.tr("unable_to_execute",
    en="Unable to execute",
    zh_cn="无法执行",
    zh_hk="無法執行",
  )
  _tr_input_required = TR_gui_mainwindow.tr("input_required",
    en="Please specify input files first",
    zh_cn="请先指定输入文件",
    zh_hk="請先指定輸入文件",
  )
  _tr_export_path = TR_gui_mainwindow.tr("export_path",
    en="Export Path",
    zh_cn="导出路径",
    zh_hk="導出路徑",
  )

  def __init__(self, parent: QWidget):
    super(MainInputWidget, self).__init__(parent)
    self.ui = Ui_MainInputWidget()
    self.ui.setupUi(self)
    self.bind_text(self.ui.inputGroupBox.setTitle, self._tr_maininput_group_input)
    self.bind_text(self.ui.analysisGroupBox.setTitle, self._tr_maininput_group_analysis)
    self.bind_text(self.ui.exportGroupBox.setTitle, self._tr_maininput_group_export)
    self.filelist = FileListInputWidget(self)
    self.filelist.setFieldName(self._tr_fieldname_files)
    self.filelist.setDirectoryMode(False)
    self.filelist.setExistingOnly(True)
    self.filelist.setFilter(self._tr_filter_scriptinput)
    self.add_translatable_widget_child(self.filelist)
    input_layout = QVBoxLayout()
    input_layout.addWidget(self.filelist)
    #input_layout.setContentsMargins(0, 0, 0, 0)
    input_layout.setSpacing(0)
    self.ui.inputGroupBox.setLayout(input_layout)
    self.build_operation_groupbox(self.ui.analysisGroupBox, [
      (MainWindowInterface.tr_toolname_analysis, None, self.request_analysis),
    ])
    self.build_operation_groupbox(self.ui.exportGroupBox, [
      (MainWindowInterface.tr_toolname_export_renpy, "vnengines/renpy.png", self.request_export_renpy),
      (MainWindowInterface.tr_toolname_export_webgal, "vnengines/webgal.png", self.request_export_webgal),
    ])

  def build_operation_groupbox(self, group : QGroupBox, entry_list : list):
    # 在 group 中添加按钮，entry_list 中每一项会成为一个带有大图标的按钮，图片在文字上方
    layout = QVBoxLayout()
    #layout.setContentsMargins(0, 0, 0, 0)
    group.setLayout(layout)
    for i, (name, icon, slot) in enumerate(entry_list):
      button = QPushButton(name.get())
      if icon is not None:
        if iconpath := GUIAssetLoader.try_get_asset_path(icon):
          icon = QIcon(iconpath)
          button.setIcon(QIcon(icon))
          button.setIconSize(QSize(64, 64))
      button.clicked.connect(slot)
      layout.addWidget(button)
      self.bind_text(button.setText, name)

  @Slot()
  def request_analysis(self):
    self.showNotImplementedMessageBox()

  @Slot()
  def request_export_renpy(self):
    filelist = self.filelist.getCurrentList()
    if not filelist:
      QMessageBox.critical(self, self._tr_unable_to_execute.get(), self._tr_input_required.get())
      return
    info = ExecutionInfo.init_main_pipeline(filelist)
    info.args.append("--renpy-codegen")
    info.args.append("--renpy-export")
    info.add_output_unspecified(self._tr_export_path, "game", is_dir=True)
    MainWindowInterface.getHandle(self).requestExecution(info)

  @Slot()
  def request_export_webgal(self):
    filelist = self.filelist.getCurrentList()
    if not filelist:
      QMessageBox.critical(self, self._tr_unable_to_execute.get(), self._tr_input_required.get())
      return
    info = ExecutionInfo.init_main_pipeline(filelist)
    info.args.append("--webgal-codegen")
    info.args.append("--webgal-export")
    info.add_output_unspecified(self._tr_export_path, "game", is_dir=True)
    MainWindowInterface.getHandle(self).requestExecution(info)
