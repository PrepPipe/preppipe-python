# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
import sys
import shutil
from preppipe.irbase import Operation, typing
from preppipe.appdir import get_executable_base_dir
from .ast import *
from ..pipeline import *
from ..irbase import *
from ..exceptions import PPInternalError
from .export import export_renpy
from .codegen import codegen_renpy
from ..vnmodel import VNModel


def _find_renpy_sdk() -> str | None:
  """查找内嵌的 Ren'Py SDK 目录（含 renpy.py 的 renpy-sdk 目录）。"""
  env_path = os.environ.get('PREPPIPE_RENPY_SDK')
  if env_path and os.path.isdir(env_path) and os.path.isfile(os.path.join(env_path, 'renpy.py')):
    return os.path.abspath(env_path)
  base = get_executable_base_dir()
  for dir_ in (base, os.path.dirname(base), os.path.dirname(os.path.dirname(base)), '.'):
    candidate = os.path.join(dir_, 'renpy-sdk') if dir_ != '.' else os.path.abspath('renpy-sdk')
    if dir_ != '.':
      candidate = os.path.abspath(candidate)
    if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, 'renpy.py')):
      return candidate
  return None


def _get_renpy_python_exe(sdk_dir: str) -> str:
  """返回 Ren'Py SDK 内嵌的 Python 解释器路径。"""
  system = sys.platform
  if system == 'win32':
    lib_python = os.path.join(sdk_dir, 'lib', 'py3-windows-x86_64', 'python.exe')
  elif system == 'darwin':
    lib_python = os.path.join(sdk_dir, 'lib', 'py3-darwin-x86_64', 'python')
    if not os.path.isfile(lib_python):
      lib_python = os.path.join(sdk_dir, 'lib', 'py3-darwin-arm64', 'python')
  else:
    lib_python = os.path.join(sdk_dir, 'lib', 'py3-linux-x86_64', 'python')
  if not os.path.isfile(lib_python):
    raise PPInternalError('Ren\'Py SDK 中未找到对应平台的 Python: ' + lib_python)
  return lib_python


def _renpy_launcher_language_from_env() -> str | None:
  """根据 PREPPIPE_LANGUAGE 返回 Ren'Py launcher 的 --language 值。仅处理简中/繁中，其他不传（默认英语）。"""
  lang = (os.environ.get('PREPPIPE_LANGUAGE') or '').strip().lower()
  if lang in ('zh_cn', 'schinese'):
    return 'schinese'
  if lang in ('zh_hk', 'tchinese', 'zh-tw'):
    return 'tchinese'
  return None


def _ensure_renpy_project_generated(game_dir: str, language: str | None = None) -> None:
  """
  若 game_dir 下尚无完整 Ren'Py 工程（无 gui.rpy），则使用内嵌 SDK 生成空工程并生成 GUI 图片。
  game_dir 为工程下的 game 目录（即输出目录）；其父目录为工程根。
  language 为 None 时不传 --language，由 Ren'Py 使用默认（英语）。
  """
  gui_rpy = os.path.join(game_dir, 'gui.rpy')
  if os.path.isfile(gui_rpy):
    return
  sdk_dir = _find_renpy_sdk()
  if not sdk_dir:
    # 如果没有找到内置 SDK （比如是在测试环境里）则不补完工程
    return
  project_root = os.path.dirname(game_dir)
  os.makedirs(game_dir, exist_ok=True)
  python_exe = _get_renpy_python_exe(sdk_dir)
  renpy_py = os.path.join(sdk_dir, 'renpy.py')
  cmd_generate = [
    python_exe, renpy_py, 'launcher', 'generate_gui',
    os.path.abspath(project_root), '--start',
  ]
  if language is not None:
    cmd_generate.extend(('--language', language))
  subprocess.run(cmd_generate, cwd=sdk_dir, check=True)
  cmd_gui_images = [python_exe, renpy_py, os.path.abspath(project_root), 'gui_images']
  subprocess.run(cmd_gui_images, cwd=sdk_dir, check=True)


def run_renpy_project(project_root: str, sdk_dir: str | None = None) -> None:
  """
  使用内嵌 Ren'Py SDK 运行指定工程（不等待进程结束）。
  project_root 为工程根目录，其下应包含 game 目录。
  sdk_dir 若提供则优先使用（如 GUI 设置中的默认路径），否则按环境变量与默认目录查找。
  供 GUI「运行项目」等调用。
  """
  if sdk_dir and os.path.isdir(sdk_dir) and os.path.isfile(os.path.join(sdk_dir, 'renpy.py')):
    pass
  else:
    sdk_dir = _find_renpy_sdk()
  if not sdk_dir:
    raise PPInternalError(
      '未找到 Ren\'Py SDK，无法运行项目。'
      '请设置环境变量 PREPPIPE_RENPY_SDK 或将 SDK 解压到 renpy-sdk 目录。'
    )
  python_exe = _get_renpy_python_exe(sdk_dir)
  renpy_py = os.path.join(sdk_dir, 'renpy.py')
  abs_root = os.path.abspath(project_root)
  subprocess.Popen(
    [python_exe, renpy_py, abs_root],
    cwd=sdk_dir,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
  )

@FrontendDecl('test-renpy-build', input_decl=IODecl(description='<No Input>', nargs=0), output_decl=RenPyModel)
class _TestVNModelBuild(TransformBase):
  def run(self) -> RenPyModel:
    model = RenPyModel.create(self.context)
    file1 = RenPyScriptFileOp.create(self.context, 'script')
    model.add_script(file1)
    bg = RenPyImageNode.create(self.context, 'bg', 'Placeholder(base="bg")')
    sayer_normal = RenPyImageNode.create(self.context, 'sayer', 'Placeholder(base="girl", text="normal")')
    sayer_smile = RenPyImageNode.create(self.context, ('sayer', 'smile'), 'Placeholder(base="girl", text="smile")')
    file1.body.push_back(bg)
    file1.body.push_back(sayer_normal)
    file1.body.push_back(sayer_smile)
    chdef, chexpr = RenPyDefineNode.create_character(self.context, 's', "发言者")
    file1.body.push_back(chdef)
    chexpr.image.set_operand(0, StringLiteral.get('sayer', self.context))
    dummyvar = RenPyDefaultNode.create(self.context, 'dummyint', expr=RenPyASMExpr.create(self.context, asm='0'))
    file1.body.push_back(dummyvar)

    startlabel = RenPyLabelNode.create(self.context, 'start')
    file1.body.push_back(startlabel)
    dummylabel = RenPyLabelNode.create(self.context, 'dummy')
    file1.body.push_back(dummylabel)
    dummylabel.body.push_back(RenPyReturnNode.create(self.context))
    startlabel.body.push_back(RenPySayNode.create(self.context, None, 'Test1'))
    startlabel.body.push_back(RenPyCallNode.create(self.context, 'dummy'))
    testmenu = RenPyMenuNode.create(self.context, varname='testmenu')
    testmenu.items.push_back(RenPySayNode.create(self.context, None, "what's your choice?"))
    item1 = RenPyMenuItemNode.create(self.context, label='continue')
    item1.body.push_back(RenPyPassNode.create(self.context))
    item2 = RenPyMenuItemNode.create(self.context, label='return')
    item2.body.push_back(RenPyReturnNode.create(self.context))
    testmenu.items.push_back(item1)
    testmenu.items.push_back(item2)
    startlabel.body.push_back(testmenu)
    testwhile = RenPyWhileNode.create(self.context, condition=RenPyASMExpr.create(self.context, asm='dummyint < 10'))
    startlabel.body.push_back(testwhile)
    testif = RenPyIfNode.create(self.context)
    testwhile.body.push_back(testif)
    b1 = testif.add_branch(RenPyASMExpr.create(self.context, asm='dummyint < 3'))
    b1.push_back(RenPyASMNode.create(self.context, asm=StringLiteral.get('$ dummyint += 2', self.context)))
    b2 = testif.add_branch(None)
    b2.push_back(RenPyASMNode.create(self.context, asm=StringLiteral.get('$ dummyint += 1', self.context)))
    startlabel.body.push_back(RenPySceneNode.create(self.context, 'bg'))
    startlabel.body.push_back(RenPyShowNode.create(self.context, ('sayer', 'happy'), showat=RenPyASMExpr.create(self.context, asm='mid'), with_=RenPyWithNode.create(self.context, expr='None')))
    startlabel.body.push_back(RenPySayNode.create(self.context, chdef, 'Test2'))
    startlabel.body.push_back(RenPyHideNode.create(self.context, 'sayer', with_=RenPyWithNode.create(self.context, 'dissolve')))
    startlabel.body.push_back(RenPySayNode.create(self.context, chdef, 'Test3'))
    return model

@TransformArgumentGroup('renpy-export', "Options for RenPy Export")
@BackendDecl('renpy-export', input_decl=RenPyModel, output_decl=IODecl(description='<output directory>', nargs=1))
class _RenPyExport(TransformBase):
  _template_dir : typing.ClassVar[str] = ""

  @staticmethod
  def install_arguments(argument_group : argparse._ArgumentGroup):
    argument_group.add_argument("--renpy-export-templatedir", nargs=1, type=str, default='')

  @staticmethod
  def handle_arguments(args : argparse.Namespace):
    _RenPyExport._template_dir = args.renpy_export_templatedir
    if isinstance(_RenPyExport._template_dir, list):
      assert len(_RenPyExport._template_dir) == 1
      _RenPyExport._template_dir = _RenPyExport._template_dir[0]
    assert isinstance(_RenPyExport._template_dir, str)
    if len(_RenPyExport._template_dir) > 0 and not os.path.isdir(_RenPyExport._template_dir):
      raise PPInternalError('--renpy-export-templatedir: input "' + _RenPyExport._template_dir + '" is not a valid path')

  def run(self) -> None:
    if len(self._inputs) == 0:
      return None
    if len(self._inputs) > 1:
      raise PPInternalError("renpy-export: exporting multiple input IR is not supported")
    out_path = self.output
    if os.path.exists(out_path):
      if not os.path.isdir(out_path):
        raise PPInternalError("renpy-export: exporting to non-directory path: " + out_path)
    # 若输出目录尚无完整 Ren'Py 工程（无 gui.rpy），则用内嵌 SDK 先生成空工程与 GUI 图片
    _ensure_renpy_project_generated(out_path, _renpy_launcher_language_from_env())
    return export_renpy(self.inputs[0], out_path, _RenPyExport._template_dir)

@MiddleEndDecl('renpy-codegen', input_decl=VNModel, output_decl=RenPyModel)
class _RenPyCodeGen(TransformBase):
  def run(self) -> RenPyModel | None:
    if len(self._inputs) == 0:
      return None
    if len(self._inputs) > 1:
      raise PPInternalError("renpy-codegen: exporting multiple input IR is not supported")
    return codegen_renpy(self._inputs[0])
  pass