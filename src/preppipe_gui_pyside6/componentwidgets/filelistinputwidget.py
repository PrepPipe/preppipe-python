import os
import typing
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from ..forms.generated.ui_filelistinputwidget import Ui_FileListInputWidget
from preppipe.language import *
from ..translatablewidgetinterface import *

class FileListInputWidget(QWidget, TranslatableWidgetInterface):
  listChanged = Signal()

  ui : Ui_FileListInputWidget
  isDirectoryMode : bool
  isExistingOnly : bool
  verifyCB : typing.Callable[[str], bool] | None
  fieldName : Translatable | str
  filter : Translatable | str
  lastAddedPath : str

  TR_gui_filelistinputwidget = TranslationDomain("gui_filelistinputwidget")
  _tr_add = TR_gui_filelistinputwidget.tr("add",
      en="Add",
      zh_cn="添加",
      zh_hk="添加",
  )
  _tr_remove = TR_gui_filelistinputwidget.tr("remove",
      en="Remove",
      zh_cn="删除",
      zh_hk="刪除",
  )
  _tr_move_up = TR_gui_filelistinputwidget.tr("move_up",
      en="Move Up",
      zh_cn="上移",
      zh_hk="上移",
  )
  _tr_move_down = TR_gui_filelistinputwidget.tr("move_down",
      en="Move Down",
      zh_cn="下移",
      zh_hk="下移",
  )

  def __init__(self, parent : QWidget | None = None):
    super(FileListInputWidget, self).__init__(parent)
    self.ui = Ui_FileListInputWidget()
    self.ui.setupUi(self)
    self.isDirectoryMode = False
    self.isExistingOnly = False
    self.verifyCB = None
    self.fieldName = ""
    self.filter = ""
    self.lastAddedPath = ""

    self.bind_text(self.ui.addButton.setText, self._tr_add)
    self.bind_text(self.ui.removeButton.setText, self._tr_remove)
    self.bind_text(self.ui.moveUpButton.setText, self._tr_move_up)
    self.bind_text(self.ui.moveDownButton.setText, self._tr_move_down)

    self.ui.listWidget.itemChanged.connect(lambda: self.listChanged.emit())
    self.ui.addButton.clicked.connect(self.itemAdd)
    self.ui.removeButton.clicked.connect(self.itemRemove)
    self.ui.moveUpButton.clicked.connect(self.itemMoveUp)
    self.ui.moveDownButton.clicked.connect(self.itemMoveDown)
    self.setAcceptDrops(True)

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
    newItem.setToolTip(path)
    self.ui.listWidget.addItem(newItem)
    self.lastAddedPath = path
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

  _tr_select_dialog_title = TR_gui_filelistinputwidget.tr("select_dialog_title",
    en="Please select {field}",
    zh_cn="请选择{field}",
    zh_hk="請選擇{field}",
  )

  @Slot()
  def itemAdd(self):
    dialogTitle = self._tr_select_dialog_title.format(field=str(self.fieldName))
    initialDir = self.lastAddedPath if self.lastAddedPath else ""
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
