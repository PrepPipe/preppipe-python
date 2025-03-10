import sys
import subprocess
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import QDesktopServices
from preppipe.language import *
from ..forms.generated.ui_outputentrywidget import Ui_OutputEntryWidget
from ..translatablewidgetinterface import *

class OutputEntryWidget(QWidget, TranslatableWidgetInterface):
  TR_gui_outputentrywidget = TranslationDomain("gui_outputentrywidget")
  _tr_open_containing_directory = TR_gui_outputentrywidget.tr("open_containing_directory",
    en="Open Containing Directory",
    zh_cn="打开所在目录",
    zh_hk="打開所在目錄",
  )
  _tr_open = TR_gui_outputentrywidget.tr("open",
    en="Open",
    zh_cn="打开",
    zh_hk="打開",
  )
  _tr_filestate_initial = TR_gui_outputentrywidget.tr("filestate_initial",
    en="Init",
    zh_cn="初始",
    zh_hk="初始",
  )
  _tr_filestate_generated = TR_gui_outputentrywidget.tr("filestate_generated",
    en="Generated",
    zh_cn="已生成",
    zh_hk="已生成",
  )
  _tr_filestate_not_updated = TR_gui_outputentrywidget.tr("filestate_not_updated",
    en="Not Updated",
    zh_cn="未更新",
    zh_hk="未更新",
  )
  _tr_filestate_not_generated_yet = TR_gui_outputentrywidget.tr("filestate_not_generated_yet",
    en="Not Generated Yet",
    zh_cn="尚未生成",
    zh_hk="尚未生成",
  )
  _tr_not_supported = TR_gui_outputentrywidget.tr("not_supported",
    en="Not Supported",
    zh_cn="暂不支持",
    zh_hk="暫不支持",
  )
  _tr_not_supporting_open_directory = TR_gui_outputentrywidget.tr("not_supporting_open_directory",
    en="Sorry, we do not support opening directories in the current system yet.",
    zh_cn="抱歉，我们暂不支持在当前系统下打开目录。",
    zh_hk="抱歉，我們暫不支持在當前系統下打開目錄。",
  )

  ui : Ui_OutputEntryWidget
  fieldName : Translatable | str
  path : str
  lastModified : QDateTime

  def __init__(self, parent=None):
    super().__init__(parent)
    self.ui = Ui_OutputEntryWidget()
    self.ui.setupUi(self)

    # Connect UI signals
    self.ui.openInExplorerPushButton.clicked.connect(self.requestOpenContainingDirectory)
    self.ui.openPushButton.clicked.connect(self.requestOpen)

    self.fieldName = ""
    self.path = ""
    self.lastModified = QDateTime()

    self.bind_text(self.ui.openPushButton.setText, self._tr_open)
    self.bind_text(self.ui.openInExplorerPushButton.setText, self._tr_open_containing_directory)

  @staticmethod
  def getLatestModificationInDir(dirpath: str) -> QDateTime:
    """Recursively iterates through the directory and returns the latest modification time."""
    result = QDateTime()
    iterator = QDirIterator(dirpath, QDir.Files | QDir.Dirs, QDirIterator.Subdirectories)
    while iterator.hasNext():
      file_info = QFileInfo(iterator.next())
      if not result.isValid() or result < file_info.lastModified():
        result = file_info.lastModified()
    return result

  def setData(self, fieldName: Translatable | str, path: str):
    """Set the field name and path, update labels and store the initial modification time."""
    self.fieldName = fieldName
    self.path = path
    if isinstance(fieldName, Translatable):
      self.bind_text(self.ui.fieldNameLabel.setText, fieldName)
    else:
      self.ui.fieldNameLabel.setText(fieldName)
    self.ui.pathLabel.setText(path)
    self.bind_text(self.ui.statusLabel.setText, self._tr_filestate_initial)

    info = QFileInfo(path)
    if info.exists():
      if info.isDir():
        # 如果是目录的话，我们使用当前时间
        # 其实应该遍历目录下所有文件、取最新的时间的，这里就先不这样做了
        self.lastModified = QDateTime.currentDateTime()
      else:
        self.lastModified = info.lastModified()
    else:
      self.lastModified = QDateTime()

  def updateStatus(self):
    """Updates the status label based on the modification time of the target file/directory."""
    info = QFileInfo(self.path)
    if info.exists():
      curtime = info.lastModified()
      if info.isDir():
        curtime = self.getLatestModificationInDir(self.path)
      if not self.lastModified.isValid() or self.lastModified < curtime:
        self.bind_text(self.ui.statusLabel.setText, self._tr_filestate_generated)
        return
      self.bind_text(self.ui.statusLabel.setText, self._tr_filestate_not_updated)
    else:
      self.bind_text(self.ui.statusLabel.setText, self._tr_filestate_not_generated_yet)

  def requestOpenContainingDirectory(self):
    if not os.path.exists(self.path):
      return

    if sys.platform.startswith('win'):
      # Windows
      explorer = 'explorer'
      path = os.path.normpath(self.path)
      subprocess.Popen([explorer, '/select,', path])
    elif sys.platform.startswith('darwin'):
      # macOS
      subprocess.Popen(['open', '-R', self.path])
    elif sys.platform.startswith('linux'):
      # Linux
      try:
        subprocess.Popen(['xdg-open', os.path.dirname(self.path)])
      except Exception:
        QMessageBox.warning(self, self._tr_not_supported.get(), self._tr_not_supporting_open_directory.get())
    else:
      QMessageBox.warning(self, self._tr_not_supported.get(), self._tr_not_supporting_open_directory.get())

  def requestOpen(self):
    """Opens the target file or directory using the default system handler."""
    info = QFileInfo(self.path)
    if info.exists():
      QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))
