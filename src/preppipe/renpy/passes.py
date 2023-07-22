# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from preppipe.irbase import Operation, typing
from .ast import *
from ..pipeline import *
from ..irbase import *
from .export import export_renpy
from .codegen import codegen_renpy
from ..vnmodel import VNModel
import shutil

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

@MiddleEndDecl('renpy-codegen', input_decl=VNModel, output_decl=RenPyModel)
class _RenPyCodeGen(TransformBase):
  def run(self) -> RenPyModel | None:
    if len(self._inputs) == 0:
      return None
    if len(self._inputs) > 1:
      raise RuntimeError("renpy-codegen: exporting multiple input IR is not supported")
    return codegen_renpy(self._inputs[0])
  pass