# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from preppipe.irbase import Operation, typing
from .ast import *
from ..pipeline import *
from ..irbase import *
from .export import export_renpy
import shutil

@FrontendDecl('test-renpy-build', input_decl=IODecl(description='<No Input>', nargs=0), output_decl=RenPyModel)
class _TestVNModelBuild(TransformBase):
  def run(self) -> RenPyModel:
    model = RenPyModel.create(self.context)
    file1 = RenPyScriptFileOp.create(self.context, 'script')
    model.add_script(file1)
    chdef, chexpr = RenPyDefineNode.create_character(self.context, 'sayer', "发言者")
    file1.body.push_back(chdef)
    startlabel = RenPyLabelNode.create(self.context, 'start')
    file1.body.push_back(startlabel)
    say1 = RenPySayNode.create(self.context, chdef, 'Test message')
    startlabel.body.push_back(say1)
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
      raise RuntimeError('--renpy-export-templatedir: input "' + _RenPyExport._template_dir + '" is not a valid path')

  def run(self) -> None:
    if len(self._inputs) == 0:
      return None
    if len(self._inputs) > 1:
      raise RuntimeError("renpy-export: exporting multiple input IR is not supported")
    out_path = self.output
    if os.path.exists(out_path):
      if not os.path.isdir(out_path):
        raise RuntimeError("renpy-export: exporting to non-directory path: " + out_path)
    return export_renpy(self.inputs[0], out_path, _RenPyExport._template_dir)
