from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from ..forms.generated.ui_fguiconverterwidget import Ui_FguiConverterWidget
from ..toolwidgetinterface import *
from ..mainwindowinterface import *
from ..settingsdict import *
from ..translatablewidgetinterface import *
from ..util.fileopen import FileOpenHelper

from fgui_converter.utils.renpy.Fgui2RenpyConverter import *

TR_gui_fguiconverter = TranslationDomain("gui_fguiconverter")

class FguiConverterWidget(QWidget, ToolWidgetInterface):
  listChanged = Signal()
  isDirectoryMode : bool
  isExistingOnly : bool
  verifyCB : typing.Callable[[str], bool] | None
  fieldName : Translatable | str
  filter : Translatable | str
  lastInputPath : str
  lastOutputPath : str
  ui : Ui_FguiConverterWidget


  TR_gui_fguiassetsdictwidget = TranslationDomain("gui_fguiassetsdictwidget")
  _tr_fgui_assets_dict_label = TR_gui_fguiassetsdictwidget.tr("fgui_assets_dict_label",
      en="FairyGUI Assets Dictionary",
      zh_cn="FairyGUI资源目录",
      zh_hk="FairyGUI資源目錄",
  )
  _tr_add = TR_gui_fguiassetsdictwidget.tr("add",
      en="Add",
      zh_cn="添加",
      zh_hk="添加",
  )
  _tr_remove = TR_gui_fguiassetsdictwidget.tr("remove",
      en="Remove",
      zh_cn="删除",
      zh_hk="刪除",
  )
  _tr_open_directory = TR_gui_fguiassetsdictwidget.tr("open_directory",
      en="Open Directory",
      zh_cn="打开目录",
      zh_hk="打開目錄",
  )
  _tr_output_dict_label = TR_gui_fguiassetsdictwidget.tr("output_dict_label",
      en="Ren'Py Project Base Directory",
      zh_cn="Ren'Py项目基目录",
      zh_hk="Ren'Py項目基目錄",
  )
  _tr_output_dict_button = TR_gui_fguiassetsdictwidget.tr("output_dict_button",
      en="Select",
      zh_cn="选择",
      zh_hk="選擇",
  )
  _tr_output_dict_line = TR_gui_fguiassetsdictwidget.tr("output_dict_line_edit",
      en="(None)",
      zh_cn="(未指定)",
      zh_hk="(未指定)",
  )
  _tr_convert_button = TR_gui_fguiassetsdictwidget.tr("convert_button",
      en="Convert",
      zh_cn="转换",
      zh_hk="轉換",
  )

  def __init__(self, parent : QWidget):
    super(FguiConverterWidget, self).__init__(parent)
    self.ui = Ui_FguiConverterWidget()
    self.ui.setupUi(self)
    self.isDirectoryMode = True
    self.isExistingOnly = False
    self.verifyCB = None
    self.fieldName = ""
    self.filter = ""
    self.lastInputPath = ""
    self.lastOutputPath = ""

    self.bind_text(self.ui.fguiAssetDictLabel.setText, self._tr_fgui_assets_dict_label)
    self.bind_text(self.ui.addDictButton.setText, self._tr_add)
    self.bind_text(self.ui.removeDictButton.setText, self._tr_remove)
    self.bind_text(self.ui.openDictButton.setText, self._tr_open_directory)
    self.bind_text(self.ui.outputDictLabel.setText, self._tr_output_dict_label)
    self.bind_text(self.ui.outputDictButton.setText, self._tr_output_dict_button)
    self.bind_text(self.ui.outputDictLine.setText, self._tr_output_dict_line)
    self.bind_text(self.ui.convertButton.setText, self._tr_convert_button)

    self.ui.listWidget.itemChanged.connect(lambda: self.listChanged.emit())
    self.ui.addDictButton.clicked.connect(self.itemAdd)
    self.ui.removeDictButton.clicked.connect(self.itemRemove)
    self.ui.openDictButton.clicked.connect(self.itemOpenContainingDirectory)
    self.setAcceptDrops(True)
    self.ui.outputDictButton.clicked.connect(self.itemOpenOutputDirectory)
    self.ui.outputDictLine.textChanged.connect(self.setOutputDict)
    self.ui.convertButton.clicked.connect(self.generateRenpyUi)

  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="fguiconverter",
      name="UI资源转换",
      widget=cls,
      is_wip_feature=True,
    )


  def setDirectoryMode(self, v: bool):
    self.isDirectoryMode = v
    if self.verifyCB is None:
      self.verifyCB = (lambda path: os.path.isdir(path)) if v else (lambda path: os.path.isfile(path))

  def setVerifyCallBack(self, cb):
    """Set a callback function that verifies a path. The function should accept a string and return a boolean."""
    self.verifyCB = cb

  def setExistingOnly(self, v: bool):
    self.isExistingOnly = v

  def setFieldName(self, name: Translatable | str):
    self.fieldName = name
    if isinstance(name, Translatable):
      self.bind_text(self.ui.label.setText, name)
    else:
      self.ui.label.setText(name)

  def setFilter(self, filter_str: Translatable | str):
    self.filter = filter_str

  def getCurrentList(self):
    results = []
    for i in range(self.ui.listWidget.count()):
      item = self.ui.listWidget.item(i)
      results.append(item.text())
    return results

  def dragEnterEvent(self, e: QDragEnterEvent):
    if e.mimeData().hasUrls():
      path = e.mimeData().urls()[0].toLocalFile()
      if not self.verifyCB or self.verifyCB(path):
        e.acceptProposedAction()
        return
    super().dragEnterEvent(e)

  def dropEvent(self, event: QDropEvent):
    for url in event.mimeData().urls():
      path = url.toLocalFile()
      if not self.verifyCB or self.verifyCB(path):
        self.addPath(path)
    event.acceptProposedAction()

  @Slot(str)
  def addPath(self, path: str):
    # Prevent duplicates
    for i in range(self.ui.listWidget.count()):
      if self.ui.listWidget.item(i).text() == path:
        return
    newItem = QListWidgetItem(path)
    #newItem.setToolTip(path)
    self.ui.listWidget.addItem(newItem)
    self.lastInputPath = path
    self.listChanged.emit()

  @Slot()
  def itemMoveUp(self):
    curRow = self.ui.listWidget.currentRow()
    if curRow > 0:
      item = self.ui.listWidget.takeItem(curRow)
      self.ui.listWidget.insertItem(curRow - 1, item)
      self.ui.listWidget.setCurrentRow(curRow - 1)
      self.listChanged.emit()

  @Slot()
  def itemMoveDown(self):
    curRow = self.ui.listWidget.currentRow()
    if curRow >= 0 and curRow + 1 < self.ui.listWidget.count():
      item = self.ui.listWidget.takeItem(curRow)
      self.ui.listWidget.insertItem(curRow + 1, item)
      self.ui.listWidget.setCurrentRow(curRow + 1)
      self.listChanged.emit()

  @Slot()
  def itemOpenContainingDirectory(self):
    curRow = self.ui.listWidget.currentRow()
    if curRow >= 0:
      path = self.ui.listWidget.item(curRow).text()
      FileOpenHelper.open_containing_directory(self, path)

  _tr_select_dialog_title = TR_gui_fguiassetsdictwidget.tr("select_dialog_title",
    en="Please select FairyGUI Assets Dictionary{field}",
    zh_cn="请选择FairyGUI资源目录{field}",
    zh_hk="請選擇FairyGUI資源目錄{field}",
  )

  @Slot()
  def itemAdd(self):
    dialogTitle = self._tr_select_dialog_title.format(field=str(self.fieldName))
    initialDir = self.lastInputPath if self.lastInputPath else ""
    dialog = QFileDialog(self, dialogTitle, initialDir, str(self.filter))
    if self.isDirectoryMode:
      dialog.setFileMode(QFileDialog.Directory)
      dialog.setOption(QFileDialog.ShowDirsOnly, True)
    else:
      dialog.setFileMode(QFileDialog.ExistingFile if self.isExistingOnly else QFileDialog.AnyFile)
    dialog.fileSelected.connect(self.addPath)
    dialog.show()

  @Slot()
  def itemRemove(self):
    curRow = self.ui.listWidget.currentRow()
    if curRow >= 0:
      item = self.ui.listWidget.takeItem(curRow)
      del item
      self.listChanged.emit()

  _tr_select_dialog_title_2 = TR_gui_fguiassetsdictwidget.tr("select_dialog_title_2",
    en="Please select Ren'Py Project Base Directory{field}",
    zh_cn="请选择Ren'Py项目基目录{field}",
    zh_hk="請選擇Ren'Py項目基目錄{field}",
  )

  @Slot()
  def itemOpenOutputDirectory(self):
    dialogTitle = self._tr_select_dialog_title_2.format(field=str(self.fieldName))
    initialDir = self.lastOutputPath if self.lastOutputPath else ""
    dialog = QFileDialog(self, dialogTitle, initialDir, str(self.filter))
    if self.isDirectoryMode:
      dialog.setFileMode(QFileDialog.Directory)
      dialog.setOption(QFileDialog.ShowDirsOnly, True)
    else:
      dialog.setFileMode(QFileDialog.ExistingFile if self.isExistingOnly else QFileDialog.AnyFile)
    dialog.fileSelected.connect(self.setOutputDict)
    dialog.show()

  @Slot(str)
  def setOutputDict(self, path: str):
    self.ui.outputDictLine.setText(path)
    self.lastOutputPath = path

  _tr_unable_to_transform = TR_gui_fguiassetsdictwidget.tr("unable_to_transform",
    en="Unable to transform",
    zh_cn="无法转换",
    zh_hk="無法轉換",
  )

  _tr_input_required = TR_gui_fguiassetsdictwidget.tr("input_required",
    en="Please specify input directory first",
    zh_cn="请先指定输入文件夹",
    zh_hk="請先指定輸入文件夾",
  )

  _tr_output_required = TR_gui_fguiassetsdictwidget.tr("output_required",
    en="Please specify output directory first",
    zh_cn="请先指定输出文件夹",
    zh_hk="請先指定輸出文件夾",
  )

  @Slot()
  def generateRenpyUi(self):
    # 检查当前输入输出设置。
    # 报错暂时只在Python命令行打印，后续改为弹窗信息。
    if self.ui.listWidget.count() > 0:
      inputPathList = self.getCurrentList()
    else:
      print("Input Path List is Empty.")
      QMessageBox.critical(self, self._tr_unable_to_transform.get(), self._tr_input_required.get())
      return
    outputPathStr = self.ui.outputDictLine.text()
    if os.path.isdir(outputPathStr):
      print(outputPathStr)
    else:
      print("Ren'Py Project base dictionary does not exsit.")
      QMessageBox.critical(self, self._tr_unable_to_transform.get(), self._tr_output_required.get())
      return

    curRow = self.ui.listWidget.currentRow()
    if curRow >= 0:
      #item = self.ui.listWidget.takeItem(curRow)
      # 创建FguiToRenpyConverter对象
      convert(["Test", "-i", inputPathList[curRow], "-o", outputPathStr])