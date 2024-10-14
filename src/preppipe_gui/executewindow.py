# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import threading
import sys
import os
import platform
import dataclasses
import tempfile
import tkinter as tk
import tkinter.ttk
import tkinter.scrolledtext
import preppipe
from preppipe.language import *
from .languageupdate import get_string_var


TR_gui_executewindow = TranslationDomain("gui_executewindow")

@dataclasses.dataclass
class SpecifiedOutputInfo:
  # Information about an output item
  field_name: Translatable
  argindex: int = -1

@dataclasses.dataclass
class UnspecifiedPathInfo:
  default_name: Translatable
  is_dir: bool = False
  filter: str = ''

@dataclasses.dataclass
class ExecutionInfo:
  args: list[str] = dataclasses.field(default_factory=list)
  envs: dict[str, str] = dataclasses.field(default_factory=dict)
  unspecified_paths: dict[int, UnspecifiedPathInfo] = dataclasses.field(default_factory=dict)
  specified_outputs: list[SpecifiedOutputInfo] = dataclasses.field(default_factory=list)


class OutputWidget(tk.Frame):
  _tr_open_containing_directory = TR_gui_executewindow.tr("open_containing_directory",
    en="Open Containing Directory",
    zh_cn="打开所在目录",
    zh_hk="打開所在目錄",
  )
  _tr_open = TR_gui_executewindow.tr("open",
    en="Open",
    zh_cn="打开",
    zh_hk="打開",
  )
  _tr_filestate_initial = TR_gui_executewindow.tr("filestate_initial",
    en="Init",
    zh_cn="初始",
    zh_hk="初始",
  )
  _tr_filestate_generated = TR_gui_executewindow.tr("filestate_generated",
    en="Generated",
    zh_cn="已生成",
    zh_hk="已生成",
  )
  _tr_filestate_not_updated = TR_gui_executewindow.tr("filestate_not_updated",
    en="Not Updated",
    zh_cn="未更新",
    zh_hk="未更新",
  )
  _tr_filestate_not_generated_yet = TR_gui_executewindow.tr("filestate_not_generated_yet",
    en="Not Generated Yet",
    zh_cn="尚未生成",
    zh_hk="尚未生成",
  )
  _tr_not_supported = TR_gui_executewindow.tr("not_supported",
    en="Not Supported",
    zh_cn="暂不支持",
    zh_hk="暫不支持",
  )
  _tr_not_supporting_open_directory = TR_gui_executewindow.tr("not_supporting_open_directory",
    en="Sorry, we do not support opening directories in the current system yet.",
    zh_cn="抱歉，我们暂不支持在当前系统下打开目录。",
    zh_hk="抱歉，我們暫不支持在當前系統下打開目錄。",
  )

  def __init__(self, parent, fieldName, path):
    super().__init__(parent)
    self.fieldName = fieldName
    self.path = path
    self.lastModified = None  # Stores the last modified time

    # Create GUI elements
    self.create_widgets()
    # Set data
    self.setData(fieldName, path)

  def create_widgets(self):
    # Vertical layout
    # First horizontal layout
    h_frame1 = tk.Frame(self)
    h_frame1.pack(fill=tk.X)

    # fieldNameLabel
    self.fieldNameLabel = tk.Label(h_frame1, text='')
    self.fieldNameLabel.pack(side=tk.LEFT)

    # Spacer (we can use empty label)
    spacer1 = tk.Label(h_frame1, width=2)
    spacer1.pack(side=tk.LEFT)

    # statusLabel
    self.statusLabel = tk.Label(h_frame1, text='状态标签') # 这个应该不会被用户看到，不需要单独做多语言处理
    self.statusLabel.pack(side=tk.LEFT)

    # Spacer
    spacer2 = tk.Label(h_frame1, width=4)
    spacer2.pack(side=tk.LEFT, expand=True)

    # openInExplorerPushButton
    self.openInExplorerPushButton = tk.Button(h_frame1, command=self.requestOpenContainingDirectory)
    self.openInExplorerPushButton.config(textvariable=get_string_var(self._tr_open_containing_directory, self.openInExplorerPushButton))
    self.openInExplorerPushButton.pack(side=tk.LEFT)

    # openPushButton
    self.openPushButton = tk.Button(h_frame1, command=self.requestOpen)
    self.openPushButton.config(textvariable=get_string_var(self._tr_open, self.openPushButton))
    self.openPushButton.pack(side=tk.LEFT)

    # Second horizontal layout
    h_frame2 = tk.Frame(self)
    h_frame2.pack(fill=tk.X)

    # pathLabel
    self.pathLabel = tk.Label(h_frame2, text='')
    self.pathLabel.pack(side=tk.LEFT)

  def setData(self, fieldName, path):
    self.fieldName = fieldName
    self.path = path
    self.fieldNameLabel.config(text=fieldName)
    self.pathLabel.config(text=path)
    self.statusLabel.config(textvariable=get_string_var(self._tr_filestate_initial, self.statusLabel))

    if os.path.exists(path):
      if os.path.isdir(path):
        self.lastModified = self.getLatestModificationInDir(path)
      else:
        self.lastModified = os.path.getmtime(path)
    else:
      self.lastModified = None

  def getLatestModificationInDir(self, dirpath):
    latest_time = None
    for root, dirs, files in os.walk(dirpath):
      for name in files + dirs:
        full_path = os.path.join(root, name)
        try:
          mtime = os.path.getmtime(full_path)
          if latest_time is None or mtime > latest_time:
            latest_time = mtime
        except FileNotFoundError:
          continue
    if latest_time is None:
      return 0.0
    return latest_time

  def updateStatus(self):
    if os.path.exists(self.path):
      if os.path.isdir(self.path):
        current_time = self.getLatestModificationInDir(self.path)
      else:
        current_time = os.path.getmtime(self.path)
      if self.lastModified is None or self.lastModified < current_time:
        self.statusLabel.config(textvariable=get_string_var(self._tr_filestate_generated, self.statusLabel))
      else:
        self.statusLabel.config(textvariable=get_string_var(self._tr_filestate_not_updated, self.statusLabel))
    else:
      self.statusLabel.config(textvariable=get_string_var(self._tr_filestate_not_generated_yet, self.statusLabel))

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
        tk.messagebox.showwarning(self._tr_not_supported.get(), self._tr_not_supporting_open_directory.get())
    else:
      tk.messagebox.showwarning(self._tr_not_supported.get(), self._tr_not_supporting_open_directory.get())

  def requestOpen(self):
    if os.path.exists(self.path):
      if sys.platform.startswith('win'):
        os.startfile(self.path) # type: ignore
      elif sys.platform.startswith('darwin'):
        subprocess.Popen(['open', self.path])
      else:
        subprocess.Popen(['xdg-open', self.path])

class ExecuteWindow(tk.Toplevel):
  windowindex : typing.ClassVar[int] = 0
  _tr_window_title = TR_gui_executewindow.tr("window_title",
    en="Execution window #{index}",
    zh_cn="执行窗口 #{index}",
    zh_hk="執行窗口 #{index}",
  )
  _tr_outputs = TR_gui_executewindow.tr("outputs",
    en="Output files and directories",
    zh_cn="输出的文件、目录",
    zh_hk="輸出的文件、目錄",
  )
  _tr_kill_process = TR_gui_executewindow.tr("kill_process",
    en="Kill process",
    zh_cn="强制结束进程",
    zh_hk="強制結束進程",
  )
  _tr_process_killed = TR_gui_executewindow.tr("process_killed",
    en="Process killed",
    zh_cn="进程已被强制结束",
    zh_hk="進程已被強制結束",
  )
  _tr_tempdir_creation_failed = TR_gui_executewindow.tr("tempdir_creation_failed",
    en="Failed to create temporary directory (required for unspecified outputs), cannot execute",
    zh_cn="无法创建临时目录(用于未指定的输出)，无法执行",
    zh_hk="無法創建臨時目錄(用於未指定的輸出)，無法執行",
  )
  _tr_cannot_start_process = TR_gui_executewindow.tr("cannot_start_process",
    en="Cannot start process: {error}",
    zh_cn="无法启动程序: {error}",
    zh_hk="無法啟動程序: {error}",
  )
  _tr_execution_completed = TR_gui_executewindow.tr("execution_completed",
    en="Execution completed (exit code: {exitcode})",
    zh_cn="执行完成 (返回值：{exitcode})",
    zh_hk="執行完成 (返回值：{exitcode})",
  )
  _tr_execution_failed = TR_gui_executewindow.tr("execution_failed",
    en="Execution failed (exit code: {exitcode}). Please contact developers if you have questions.",
    zh_cn="执行出错 (返回值：{exitcode})，如有疑问请联系开发者。",
    zh_hk="執行出錯 (返回值：{exitcode})，如有疑問請聯繫開發者。",
  )
  _tr_finish_prompt = TR_gui_executewindow.tr("finish_prompt",
    en="You may now close this window.",
    zh_cn="您现在可以关闭这个窗口了。",
    zh_hk="您現在可以關閉這個窗口了。",
  )
  _tr_tempdir_clear_warning = TR_gui_executewindow.tr("tempdir_clear_warning",
    en="The temporary directory (including everything inside) will be deleted when closing the window: {path}",
    zh_cn="临时目录（及其下所有文件）会在本窗口关闭时删除： {path}",
    zh_hk="臨時目錄（及其下所有文件）會在本窗口關閉時刪除： {path}",
  )

  def __init__(self, parent=None):
    super().__init__(parent)
    ExecuteWindow.windowindex += 1
    self.title(self._tr_window_title.format(index=str(ExecuteWindow.windowindex)))

    # Initialize variables
    self.isCanClose = False
    self.progOutput = ''
    self.proc = None

    # Set up the GUI
    self.setupUI()

    # Handle window close event
    self.protocol("WM_DELETE_WINDOW", self.on_close)

    # For temporary directory
    self.tmpdir = None  # We can use tempfile.TemporaryDirectory

  def setupUI(self):
    # Create main frames
    main_frame = tk.Frame(self)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Create horizontal layout
    left_frame = tk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right_frame = tk.Frame(main_frame)
    right_frame.pack(side=tk.LEFT, fill=tk.Y)

    # Left side: Text widget for output log
    self.plainTextEdit = tk.scrolledtext.ScrolledText(left_frame, wrap='word', state='normal')
    self.plainTextEdit.pack(fill=tk.BOTH, expand=True)
    self.plainTextEdit.config(state='disabled')  # Make it read-only

    # Right side: Vertical layout
    # Output group box
    groupbox_label = tk.Label(self, textvariable=get_string_var(self._tr_outputs, self))
    self.outputGroupBox = tk.ttk.LabelFrame(right_frame, labelwidget=groupbox_label)
    self.outputGroupBox.pack(fill=tk.BOTH, expand=True)
    self.outputLayout = tk.Frame(self.outputGroupBox)
    self.outputLayout.pack(fill=tk.BOTH, expand=True)
    self.outputWidgets = []

    # Spacer: We can use a frame with height
    spacer = tk.Frame(right_frame, height=40)
    spacer.pack()

    # Kill Process button
    self.killButton = tk.Button(right_frame, command=self.kill_process)
    self.killButton.config(textvariable=get_string_var(self._tr_kill_process, self.killButton))
    self.killButton.pack()
    self.killButton.config(state='disabled')  # Initially disabled

    # OS info
    self.appendPlainText(self.get_os_info())

  def appendPlainText(self, text):
    self.plainTextEdit.config(state='normal')
    self.plainTextEdit.insert(tk.END, text + '\n')
    self.plainTextEdit.config(state='disabled')
    self.plainTextEdit.see(tk.END)

  def get_os_info(self):
    osinfo = platform.system() + ' ' + platform.release()
    if platform.system() == 'Windows':
      version = platform.version()
      try:
        major, minor, build = map(int, version.split('.'))
        if major == 10 and minor == 0 and build >= 22000:
          osinfo += ' (Windows 11)'
      except ValueError:
        pass
    return osinfo

  def on_close(self):
    if not self.isCanClose:
      return
    else:
      if self.tmpdir:
        self.tmpdir.cleanup()
        self.tmpdir = None
      self.destroy()

  def init(self, info: ExecutionInfo):
    self.isCanClose = False
    SEPARATOR = '=' * 20
    args = info.args.copy()
    # Handle unspecifiedPaths and tmpdir
    if info.unspecified_paths:
      self.tmpdir = tempfile.TemporaryDirectory()
      if not self.tmpdir:
        self.appendPlainText(self._tr_tempdir_creation_failed.get())
        self.isCanClose = True
        return
      tmppath = self.tmpdir.name
      for argindex, pathinfo in info.unspecified_paths.items():
        fullpath = os.path.join(tmppath, pathinfo.default_name.get())
        args[argindex] = fullpath

    # Handle specifiedOutputs
    for out in info.specified_outputs:
      value = args[out.argindex]
      w = OutputWidget(self.outputLayout, out.field_name, value)
      w.pack(fill=tk.X, pady=2)
      self.outputWidgets.append(w)

    # Build the command
    self.command = [sys.executable, sys.argv[0]] + args

    # Handle environment variables
    env = os.environ.copy()
    actualEnvs = info.envs.copy()
    actualEnvs['PYTHONIOENCODING'] = 'utf-8'
    actualEnvs['PYTHONLEGACYWINDOWSSTDIO'] = 'utf-8'
    actualEnvs['PYTHONUTF8'] = '1'
    env.update(actualEnvs)
    for key, value in actualEnvs.items():
      self.appendPlainText(f"{key}={value}")

    # Start the process
    try:
      self.proc = subprocess.Popen(
        self.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        universal_newlines=False
      )
    except Exception as e:
      self.appendPlainText(self._tr_cannot_start_process.format(error=str(e)))
      self.isCanClose = True
      return

    self.appendPlainText(self.get_merged_command(self.command) + '\n' + SEPARATOR)
    self.killButton.config(state='normal')

    # Start reading process output
    self.read_process_output()

  def get_merged_command(self, args : list[str]) -> str:
    mergedstr = ''
    for a in args:
      if len(mergedstr) > 0:
        mergedstr += ' '
      if ' ' in a:
        copy = a.replace('"', '\\"')
        mergedstr += f'"{copy}"'
      else:
        mergedstr += a
    return mergedstr

  def read_process_output(self):
    if self.proc and self.proc.stdout:
      line = self.proc.stdout.readline()
      if line:
        try:
          decoded = line.decode('utf-8', errors='replace')
        except Exception as e:
          decoded = str(e)
        self.appendPlainText(decoded.rstrip())
        self.progOutput += decoded
      if self.proc.poll() is None:
        self.after(100, self.read_process_output)
      else:
        self.handle_process_finished()
    else:
      if self.proc.poll() is None:
        self.after(100, self.read_process_output)
      else:
        self.handle_process_finished()

  def handle_process_finished(self):
    SEPARATOR = '=' * 20
    exitCode = self.proc.returncode
    self.appendPlainText(SEPARATOR)
    if exitCode == 0:
      self.appendPlainText(self._tr_execution_completed.format(exitcode=str(exitCode)))
    else:
      self.appendPlainText(self._tr_execution_failed.format(exitcode=str(exitCode)))
    self.appendPlainText(self._tr_finish_prompt.get())
    if self.tmpdir:
      self.appendPlainText(self._tr_tempdir_clear_warning.format(path=self.tmpdir.name))
    self.killButton.config(state='disabled')
    self.isCanClose = True
    for w in self.outputWidgets:
      w.updateStatus()

  def kill_process(self):
    if self.proc and self.proc.poll() is None:
      self.proc.kill()
      self.appendPlainText(self._tr_process_killed.get())
      self.handle_process_finished()
