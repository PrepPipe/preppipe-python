import os
import sys
import subprocess
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import QDesktopServices
from .utilcommon import *

class FileOpenHelper:
  tr_open = TR_gui_utilcommon.tr("open",
    en="Open",
    zh_cn="打开",
    zh_hk="打開",
  )
  tr_open_containing_directory = TR_gui_utilcommon.tr("open_containing_directory",
    en="Open Containing Directory",
    zh_cn="打开所在目录",
    zh_hk="打開所在目錄",
  )
  _tr_not_supported = TR_gui_utilcommon.tr("not_supported",
    en="Not Supported",
    zh_cn="暂不支持",
    zh_hk="暫不支持",
  )
  _tr_not_supporting_open_directory = TR_gui_utilcommon.tr("not_supporting_open_directory",
    en="Sorry, we do not support opening directories in the current system yet.",
    zh_cn="抱歉，我们暂不支持在当前系统下打开目录。",
    zh_hk="抱歉，我們暫不支持在當前系統下打開目錄。",
  )
  @staticmethod
  def open(parent : QWidget, path : str):
    info = QFileInfo(path)
    if info.exists():
      QDesktopServices.openUrl(QUrl.fromLocalFile(path))

  @staticmethod
  def open_containing_directory(parent : QWidget, path : str):
    if not os.path.exists(path):
      return

    if sys.platform.startswith('win'):
      # Windows
      explorer = 'explorer'
      path = os.path.normpath(path)
      subprocess.Popen([explorer, '/select,', path])
    elif sys.platform.startswith('darwin'):
      # macOS
      subprocess.Popen(['open', '-R', path])
    elif sys.platform.startswith('linux'):
      # Linux
      try:
        subprocess.Popen(['xdg-open', os.path.dirname(path)])
      except Exception:
        QMessageBox.warning(parent, FileOpenHelper._tr_not_supported.get(), FileOpenHelper._tr_not_supporting_open_directory.get())
    else:
      QMessageBox.warning(parent, FileOpenHelper._tr_not_supported.get(), FileOpenHelper._tr_not_supporting_open_directory.get())
