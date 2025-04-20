# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import threading
import sys
import os
import platform
import dataclasses
import tempfile
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from ..forms.generated.ui_executewidget import Ui_ExecuteWidget
from ..execution import *
import preppipe
from preppipe.language import *
from ..toolwidgetinterface import *
from ..componentwidgets.outputentrywidget import OutputEntryWidget

TR_gui_executewidget = TranslationDomain("gui_executewidget")

class ExecuteWidget(QWidget, ToolWidgetInterface):
  _tr_window_title = TR_gui_executewidget.tr("window_title",
    en="Execution window",
    zh_cn="执行窗口",
    zh_hk="執行窗口",
  )
  _tr_outputs = TR_gui_executewidget.tr("outputs",
    en="Output files and directories",
    zh_cn="输出的文件、目录",
    zh_hk="輸出的文件、目錄",
  )
  _tr_kill_process = TR_gui_executewidget.tr("kill_process",
    en="Kill process",
    zh_cn="强制结束进程",
    zh_hk="強制結束進程",
  )
  _tr_process_killed = TR_gui_executewidget.tr("process_killed",
    en="Process killed",
    zh_cn="进程已被强制结束",
    zh_hk="進程已被強制結束",
  )
  _tr_tempdir_creation_failed = TR_gui_executewidget.tr("tempdir_creation_failed",
    en="Failed to create temporary directory (required for unspecified outputs), cannot execute",
    zh_cn="无法创建临时目录(用于未指定的输出)，无法执行",
    zh_hk="無法創建臨時目錄(用於未指定的輸出)，無法執行",
  )
  _tr_cannot_start_process = TR_gui_executewidget.tr("cannot_start_process",
    en="Cannot start process: {error}",
    zh_cn="无法启动程序: {error}",
    zh_hk="無法啟動程序: {error}",
  )
  _tr_execution_completed = TR_gui_executewidget.tr("execution_completed",
    en="Execution completed (exit code: {exitcode})",
    zh_cn="执行完成 (返回值：{exitcode})",
    zh_hk="執行完成 (返回值：{exitcode})",
  )
  _tr_execution_failed = TR_gui_executewidget.tr("execution_failed",
    en="Execution failed (exit code: {exitcode}). Please contact developers if you have questions.",
    zh_cn="执行出错 (返回值：{exitcode})，如有疑问请联系开发者。",
    zh_hk="執行出錯 (返回值：{exitcode})，如有疑問請聯繫開發者。",
  )
  _tr_finish_prompt = TR_gui_executewidget.tr("finish_prompt",
    en="You may now close this tab.",
    zh_cn="您现在可以关闭这个标签页了。",
    zh_hk="您現在可以關閉這個標籤頁了。",
  )
  _tr_tempdir_clear_warning = TR_gui_executewidget.tr("tempdir_clear_warning",
    en="The temporary directory (including everything inside) will be deleted when closing the window: {path}",
    zh_cn="临时目录（及其下所有文件）会在本页关闭时删除： {path}",
    zh_hk="臨時目錄（及其下所有文件）會在本頁關閉時刪除： {path}",
  )

  @classmethod
  def getToolInfo(cls) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="execute",
      name=ExecuteWidget._tr_window_title,
      widget=cls,
      uniquelevel=ToolWidgetUniqueLevel.UNLIMITED,
    )

  ui : Ui_ExecuteWidget
  exec : ExecutionObject | None

  def __init__(self, parent: QWidget):
    super(ExecuteWidget, self).__init__(parent)
    self.ui = Ui_ExecuteWidget()
    self.ui.setupUi(self)
    self.ui.outputGroupBox.setLayout(QVBoxLayout())
    self.bind_text(self.ui.killButton.setText, self._tr_kill_process)
    self.bind_text(self.ui.outputGroupBox.setTitle, self._tr_outputs)
    self.ui.killButton.clicked.connect(self.kill_process)
    self.exec = None

  def setData(self, execinfo : ExecutionInfo):
    self.exec = ExecutionObject(self, execinfo)
    self.appendPlainText(self.exec.get_os_info() + '\n')
    for key, value in execinfo.envs.items():
      self.appendPlainText(f"{key}={value}\n")
    self.appendPlainText(' '.join(self.exec.get_final_commands()) + '\n')
    self.appendPlainText('='*20 + '\n')
    self.exec.outputAvailable.connect(self.handleOutput)

    for out in execinfo.specified_outputs:
      value = self.exec.composed_args[out.argindex]
      w = OutputEntryWidget(self)#, out.field_name, value)
      w.setData(out.field_name, value)
      self.ui.outputGroupBox.layout().addWidget(w)

    self.exec.executionFinished.connect(self.handle_process_finished)
    self.exec.launch()

  @Slot(str)
  def handleOutput(self, output : str):
    self.appendPlainText(output + '\n')

  def canClose(self) -> bool:
    if self.exec is None:
      raise RuntimeError("ExecuteWidget canClose() called before setData()")
    return self.exec.isCanDestroy

  def closeHandler(self):
    if self.exec is None:
      raise RuntimeError("ExecuteWidget closeHandler() called before setData()")
    self.exec.destroy()

  def appendPlainText(self, text : str):
    cursor = self.ui.plainTextEdit.textCursor()
    isAtEnd = cursor.atEnd()
    self.ui.plainTextEdit.moveCursor(QTextCursor.End)
    self.ui.plainTextEdit.insertPlainText(text)
    if not isAtEnd:
      self.ui.plainTextEdit.setTextCursor(cursor)
    else:
      self.ui.plainTextEdit.moveCursor(QTextCursor.End)

  @Slot()
  def handle_process_finished(self):
    if self.exec is None:
      raise RuntimeError("ExecuteWidget handle_process_finished() called before setData()")
    self.appendPlainText('='*20 + '\n')
    if result := self.exec.result:
      exitcode = result.returncode
      if exitcode == 0:
        self.appendPlainText(self._tr_execution_completed.format(exitcode=str(exitcode)) + '\n')
      else:
        self.appendPlainText(self._tr_execution_failed.format(exitcode=str(exitcode)) + '\n')
    self.appendPlainText(self._tr_finish_prompt.get() + '\n')
    if self.exec.tmpdir:
      self.appendPlainText(self._tr_tempdir_clear_warning.format(path=self.exec.tmpdir.name) + '\n')
    self.ui.killButton.setEnabled(False)
    for i in range(self.ui.outputGroupBox.layout().count()):
      w = self.ui.outputGroupBox.layout().itemAt(i).widget()
      if isinstance(w, OutputEntryWidget):
        w.updateStatus()

  def kill_process(self):
    if self.exec:
      self.exec.kill()
      self.appendPlainText(self._tr_process_killed.get())
