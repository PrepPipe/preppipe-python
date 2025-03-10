import dataclasses
import tempfile
import sys
import enum
import platform
import subprocess
import threading
import time
from PySide6.QtCore import *
from preppipe.language import *
from .toolwidgets.setting import SettingWidget

@dataclasses.dataclass
class SpecifiedOutputInfo:
  # 有指定输出路径的输出项
  field_name: Translatable | str
  argindex: int = -1

@dataclasses.dataclass
class UnspecifiedPathInfo:
  # 未指定输出路径、需要在临时目录中的输出项
  default_name: Translatable | str
  is_dir: bool = False

@dataclasses.dataclass
class ExecutionInfo:
  args: list[str] = dataclasses.field(default_factory=list)
  envs: dict[str, str] = dataclasses.field(default_factory=dict)
  unspecified_paths: dict[int, UnspecifiedPathInfo] = dataclasses.field(default_factory=dict)
  specified_outputs: list[SpecifiedOutputInfo] = dataclasses.field(default_factory=list)

  def add_output_specified(self, field_name : Translatable | str, path : str):
    argindex = len(self.args)
    self.specified_outputs.append(SpecifiedOutputInfo(field_name, argindex))
    self.args.append(path)

  def add_output_unspecified(self, field_name : Translatable | str, default_name: Translatable | str, is_dir : bool = False):
    argindex = len(self.args)
    self.specified_outputs.append(SpecifiedOutputInfo(field_name, argindex))
    self.unspecified_paths[argindex] = UnspecifiedPathInfo(default_name, is_dir)
    self.args.append('')

  FRONTEND_FLAG_DICT : typing.ClassVar[dict[str, str]] = {
    "odt": "--odf",
    "docx": "--docx",
    "md": "--md",
    "txt": "--txt",
  }

  @staticmethod
  def init_common():
    lang = SettingWidget.get_current_language()
    return ExecutionInfo(envs={
      'PREPPIPE_LANGUAGE': lang,
    })

  @staticmethod
  def init_main_pipeline(inputs : list[str]):
    result = ExecutionInfo.init_common()
    result.envs["PREPPIPE_TOOL"] = "pipeline"
    result.args.append("-v")

    # 根据输入文件路径确定素材搜索路径
    searchpaths = []
    for i in inputs:
      # 对每个输入文件，把它们的父目录加入搜索路径
      parent = os.path.dirname(i)
      if parent not in searchpaths:
        searchpaths.append(parent)
    if len(searchpaths) > 0:
      result.args.append("--searchpath")
      result.args.extend(searchpaths)

    # 给输入文件选择合适的读取选项
    last_input_flag = ''
    for i in inputs:
      suffix = i.split('.')[-1]
      flag = ExecutionInfo.FRONTEND_FLAG_DICT.get(suffix)
      if flag is None:
        raise ValueError(f'Unsupported input file type: {suffix}')
      if flag != last_input_flag:
        result.args.append(flag)
        last_input_flag = flag
      result.args.append(i)

    # 添加前端命令
    result.args.extend([
      "--cmdsyntax",
      "--vnparse",
      "--vncodegen",
      "--vn-blocksorting",
      "--vn-entryinference",
    ])
    return result

class ExecutionState(enum.Enum):
  INIT = 0
  FAILED_TEMPDIR_CREATION = enum.auto()
  FAILED_LAUNCH = enum.auto()
  FAILED_EXECUTE = enum.auto()
  RUNNING = enum.auto()
  FINISHED = enum.auto()

@dataclasses.dataclass
class ExecutionResult:
  # 执行结果
  returncode: int
  output : str # 合并的 stdout 和 stderr

class ExecutionObject(QObject):
  # 用于管理一次执行操作，支持多次使用相同的命令执行操作（即支持重试）
  executionFinished = Signal()
  outputAvailable = Signal(str)

  info : ExecutionInfo
  result : ExecutionResult | None
  state : ExecutionState
  custom_error_message : str
  isCanDestroy : bool
  tmpdir : tempfile.TemporaryDirectory | None
  composed_args : list[str]
  composed_envs : dict[str, str]
  proc : subprocess.Popen[bytes] | None
  outputs : list[str] # 只在不等待执行完成时使用
  watcher_thread : threading.Thread | None

  def __init__(self, parent: QObject, info : ExecutionInfo) -> None:
    super().__init__(parent)
    self.info = info
    self.result = None
    self.state = ExecutionState.INIT
    self.custom_error_message = ''
    self.isCanDestroy = True
    self.tmpdir = None
    self.outputs = []
    self.proc = None
    self.watcher_thread = None
    # 准备执行环境
    self.composed_envs = os.environ.copy()
    self.composed_envs.update(self.info.envs)
    # 总是使用 UTF-8 编码
    self.composed_envs.update({
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONLEGACYWINDOWSSTDIO': 'utf-8',
      'PYTHONUTF8': '1'
    })
    self.composed_args = self.info.args.copy()
    if self.info.unspecified_paths:
      self.tmpdir = tempfile.TemporaryDirectory()
      if not self.tmpdir:
        self.state = ExecutionState.FAILED_TEMPDIR_CREATION
        return
      tmppath = self.tmpdir.name
      for argindex, pathinfo in self.info.unspecified_paths.items():
        fullpath = os.path.join(tmppath, str(pathinfo.default_name))
        self.composed_args[argindex] = fullpath

  @Slot()
  def report_execution_finish(self):
    self.executionFinished.emit()
    if self.watcher_thread:
      self.watcher_thread.join()
    self.watcher_thread = None
    self.isCanDestroy = True

  @Slot()
  def kill(self):
    if self.state == ExecutionState.FINISHED:
      return
    if self.proc is not None:
      self.proc.kill()

  def destroy(self):
    if not self.isCanDestroy:
      raise ValueError('Cannot destroy')
    if self.tmpdir is not None:
      self.tmpdir.cleanup()
      self.tmpdir = None

  def get_final_commands(self):
    # 这里有两种情况：
    # 1. 执行的是脚本， sys.executable 指向 Python 解释器， sys.argv[0] 指向脚本路径
    # 2. 执行的是打包好的可执行文件， sys.executable 和 sys.argv[0] 都指向可执行文件路径
    # 如果执行的是打包好的可执行文件， 我们优先选择相同目录下的 preppipe_cli[.exe]，避免闪过窗口
    executable_basename = os.path.basename(sys.executable)
    argv0_basename = os.path.basename(sys.argv[0])
    if executable_basename != argv0_basename:
      # 情况1
      return [sys.executable, sys.argv[0]] + self.composed_args
    # 情况2，尝试寻找 preppipe_cli[.exe]
    executable_base, executable_ext = os.path.splitext(executable_basename)
    cli_executable_path = os.path.join(os.path.dirname(sys.executable), executable_base + '_cli' + executable_ext)
    if os.path.isfile(cli_executable_path):
      return [cli_executable_path] + self.composed_args
    return [sys.executable] + self.composed_args

  def launch(self, wait : bool = False):
    if self.state == ExecutionState.FAILED_TEMPDIR_CREATION:
      return
    if self.watcher_thread is not None:
      raise ValueError('Already running')
    self.isCanDestroy = False
    self.outputs = []
    commands = self.get_final_commands()
    self.state = ExecutionState.RUNNING
    try:
      self.proc = subprocess.Popen(
        commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=self.composed_envs,
        universal_newlines=False
      )
    except Exception as e:
      self.state = ExecutionState.FAILED_LAUNCH
      self.custom_error_message = str(e)
      self.isCanDestroy = True
      return
    if wait:
      try:
        stdout, stderr = self.proc.communicate()
        self.result = ExecutionResult(self.proc.returncode, stdout.decode('utf-8'))
        self.state = ExecutionState.FINISHED
      except Exception as e:
        self.result = ExecutionResult(-1, str(e))
        self.state = ExecutionState.FAILED_EXECUTE
      finally:
        self.report_execution_finish()
    else:
      self.watcher_thread = threading.Thread(target=self.read_process_output)
      self.watcher_thread.start()

  def read_process_output(self):
    if not self.proc:
      raise ValueError('No process to read')
    while True:
      if self.proc.stdout:
        line = self.proc.stdout.readline()
        if line:
          try:
            decoded = line.decode('utf-8', errors='replace')
          except Exception as e:
            decoded = str(e)
          self.outputs.append(decoded)
          self.outputAvailable.emit(decoded.rstrip())
          # 及时重新循环，避免输出堆积
          continue

      exitcode = self.proc.poll()
      if exitcode is None:
        time.sleep(0.1)
      else:
        self.result = ExecutionResult(exitcode, '\n'.join(self.outputs))
        self.state = ExecutionState.FINISHED
        QMetaObject.invokeMethod(self, 'report_execution_finish', Qt.QueuedConnection)
        return

  @staticmethod
  def get_os_info() -> str:
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