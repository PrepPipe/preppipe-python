import os
import typing
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from ..forms.generated.ui_fileselectionwidget import Ui_FileSelectionWidget
from preppipe.language import *
from ..translatablewidgetinterface import *
from ..util.fileopen import FileOpenHelper

class FileSelectionWidget(QWidget, TranslatableWidgetInterface):
  # Signal to indicate that the file path has been updated.
  filePathUpdated = Signal(str)

  TR_gui_fileselectionwidget = TranslationDomain("gui_fileselectionwidget")

  tr_pleaseselect = TR_gui_fileselectionwidget.tr("pleaseselect",
    en="Please select {fieldname}",
    zh_cn="请选择{fieldname}",
    zh_hk="請選擇{fieldname}",
  )
  tr_notselected = TR_gui_fileselectionwidget.tr("notselected",
    en="({fieldname}: Not selected)",
    zh_cn="({fieldname}: 未选择)",
    zh_hk="({fieldname}: 未選擇)",
  )
  tr_select = TR_gui_fileselectionwidget.tr("select",
    en="Select",
    zh_cn="选择",
    zh_hk="選擇",
  )
  tr_deselect = TR_gui_fileselectionwidget.tr("deselect",
    en="Deselect",
    zh_cn="取消选择",
    zh_hk="取消選擇",
  )

  @staticmethod
  def default_file_checker(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)

  @staticmethod
  def default_directory_checker(path: str) -> bool:
    return os.path.exists(path) and os.path.isdir(path)

  ui : Ui_FileSelectionWidget
  isDirectoryMode : bool
  isOutputInsteadofInput : bool
  isExistingOnly : bool
  verifyCB : typing.Callable[[str], bool] | None
  currentPath : str
  fieldName : Translatable | str
  filter : Translatable | str
  defaultName : Translatable | str

  def __init__(self, parent=None):
    super().__init__(parent)
    # Instantiate the UI from the compiled .ui file.
    self.ui = Ui_FileSelectionWidget()
    self.ui.setupUi(self)

    # Initial state
    self.isDirectoryMode = False
    self.isOutputInsteadofInput = False
    self.isExistingOnly = False
    self.verifyCB = None
    self.currentPath = ""
    self.fieldName = ""
    self.filter = ""
    self.defaultName = ""

    # 设置右键菜单策略
    self.ui.pathLabel.setContextMenuPolicy(Qt.CustomContextMenu)
    self.ui.pathLabel.customContextMenuRequested.connect(self.showContextMenu)

    # Connect the push button's clicked signal to open the dialog.
    self.ui.pushButton.clicked.connect(self.requestOpenDialog)
    self.bind_text(self.ui.pushButton.setText, self.tr_select)

    # Enable drag and drop.
    self.setAcceptDrops(True)
    # Initialize the verifier based on the directory mode.
    self.setDirectoryMode(self.isDirectoryMode)

  def setDirectoryMode(self, v: bool):
    self.isDirectoryMode = v
    self.verifyCB = FileSelectionWidget.getDefaultVerifier(self.isDirectoryMode)

  def getIsDirectoryMode(self) -> bool:
    return self.isDirectoryMode

  @staticmethod
  def getDefaultVerifier(isDirectoryMode: bool):
    if isDirectoryMode:
      return FileSelectionWidget.default_directory_checker
    else:
      return FileSelectionWidget.default_file_checker

  def setVerifyCallBack(self, cb):
    self.verifyCB = cb

  def setIsOutputInsteadofInput(self, v: bool):
    self.isOutputInsteadofInput = v

  def getIsOutputInsteadofInput(self) -> bool:
    return self.isOutputInsteadofInput

  def setExistingOnly(self, v: bool):
    self.isExistingOnly = v

  def setFieldName(self, name: Translatable | str):
    self.fieldName = name
    self.updateLabelText()

  def getFieldName(self) -> Translatable | str:
    return self.fieldName

  def setFilter(self, filter_str: Translatable | str):
    self.filter = filter_str

  def getFilter(self) -> Translatable | str:
    return self.filter

  def getCurrentPath(self) -> str:
    return self.currentPath

  def setDefaultName(self, name: Translatable | str):
    self.defaultName = name

  def getDefaultName(self) -> Translatable | str:
    return self.defaultName

  def setCurrentPath(self, newpath: str):
    """Slot to update the current path and refresh the label."""
    self.currentPath = newpath
    self.updateLabelText()
    self.filePathUpdated.emit(self.currentPath)

  def requestOpenDialog(self):
    dialogTitle = self.tr_pleaseselect.format(fieldname=str(self.fieldName))
    dialog = QFileDialog(self, dialogTitle, self.currentPath, str(self.filter))
    if self.isDirectoryMode:
      dialog.setFileMode(QFileDialog.Directory)
      dialog.setOption(QFileDialog.ShowDirsOnly, True)
    else:
      dialog.setFileMode(QFileDialog.ExistingFile if self.isExistingOnly else QFileDialog.AnyFile)
    if self.isOutputInsteadofInput:
      dialog.setAcceptMode(QFileDialog.AcceptSave)
    else:
      dialog.setAcceptMode(QFileDialog.AcceptOpen)
    dialog.fileSelected.connect(self.setCurrentPath)
    dialog.finished.connect(dialog.deleteLater)
    dialog.show()

  def updateLabelText(self):
    if not self.currentPath:
      self.ui.pathLabel.setText(self.tr_notselected.format(fieldname=str(self.fieldName)))
    else:
      self.ui.pathLabel.setText(self.currentPath)

  def update_text(self):
    super().update_text()
    self.updateLabelText()

  def dragEnterEvent(self, e: QDragEnterEvent):
    if e.mimeData().hasUrls():
      path = e.mimeData().urls()[0].toLocalFile()
      if not self.verifyCB or self.verifyCB(path):
        e.acceptProposedAction()
    else:
      super().dragEnterEvent(e)

  def dropEvent(self, event: QDropEvent):
    for url in event.mimeData().urls():
      path = url.toLocalFile()
      if not self.verifyCB or self.verifyCB(path):
        self.setCurrentPath(path)
        return

  def clearPath(self):
    """清除当前选择的路径"""
    self.setCurrentPath("")

  @Slot(QPoint)
  def showContextMenu(self, pos):
    """显示右键菜单"""
    menu = QMenu(self)

    selectAction = QAction(self.tr_select.get(), self)
    selectAction.triggered.connect(self.requestOpenDialog)
    menu.addAction(selectAction)

    if self.currentPath:
      deselectAction = QAction(self.tr_deselect.get(), self)
      openAction = QAction(FileOpenHelper.tr_open.get(), self)
      openDirAction = QAction(FileOpenHelper.tr_open_containing_directory.get(), self)
      deselectAction.triggered.connect(self.clearPath)
      openAction.triggered.connect(lambda: FileOpenHelper.open(self, self.currentPath))
      openDirAction.triggered.connect(lambda: FileOpenHelper.open_containing_directory(self, self.currentPath))
      menu.addAction(deselectAction)
      menu.addSeparator()
      menu.addAction(openAction)
      menu.addAction(openDirAction)

    menu.exec(self.ui.pathLabel.mapToGlobal(pos))