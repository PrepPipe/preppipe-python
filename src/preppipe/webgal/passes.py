# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ..irbase import *
from ..pipeline import *
from .ast import *

from .export import export_webgal
from ..vnmodel import VNModel
import shutil

@TransformArgumentGroup('webgal-export', "Options for WebGal Export")
@BackendDecl('webgal-export', input_decl=WebGalModel, output_decl=IODecl(description='<output directory>', nargs=1))
class _WebGalExport(TransformBase):
  _template_dir : typing.ClassVar[str] = ""

  @staticmethod
  def install_arguments(argument_group : argparse._ArgumentGroup):
    argument_group.add_argument("--webgal-export-templatedir", nargs=1, type=str, default='')

  @staticmethod
  def handle_arguments(args : argparse.Namespace):
    _WebGalExport._template_dir = args.renpy_export_templatedir
    if isinstance(_WebGalExport._template_dir, list):
      assert len(_WebGalExport._template_dir) == 1
      _WebGalExport._template_dir = _WebGalExport._template_dir[0]
    assert isinstance(_WebGalExport._template_dir, str)
    if len(_WebGalExport._template_dir) > 0 and not os.path.isdir(_WebGalExport._template_dir):
      raise RuntimeError('--webgal-export-templatedir: input "' + _WebGalExport._template_dir + '" is not a valid path')

  def run(self) -> None:
    if len(self._inputs) == 0:
      return None
    if len(self._inputs) > 1:
      raise RuntimeError("webgal-export: exporting multiple input IR is not supported")
    out_path = self.output
    if os.path.exists(out_path):
      if not os.path.isdir(out_path):
        raise RuntimeError("webgal-export: exporting to non-directory path: " + out_path)
    return export_webgal(self.inputs[0], out_path, _WebGalExport._template_dir)
