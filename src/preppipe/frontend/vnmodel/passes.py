# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0


from preppipe.irbase import Operation, typing
from .vnast import *
from ...pipeline import *
from ...irbase import *
from .vncodegen import VNCodeGen
from .vnutil import parse_pixel_resolution_str
from .vnparser import VNParser
from ...vnmodel import VNModel

@TransformArgumentGroup('vnparse', 'Options for VNModel source parsing')
@MiddleEndDecl('vnparse', input_decl=IMDocumentOp, output_decl=VNAST)
class VNParseTransform(TransformBase):
  _parser : VNParser
  name : typing.ClassVar[str] = '' # 如果没有名字的话就选用第一个文件的名字
  resolution : typing.ClassVar[tuple[int,int] | None] = None

  def __init__(self, ctx: Context) -> None:
    super().__init__(ctx)
    self._parser = VNParser.create(ctx, screen_resolution=VNParseTransform.resolution, name=VNParseTransform.name)

  @staticmethod
  def install_arguments(argument_group : argparse._ArgumentGroup):
    # 给命令行解析器（ArgumentParser）添加专属于该转换的参数
    # 只会在注册时提供了 arg_title 的情况下调用
    argument_group.add_argument('--vn-name', nargs='?', type=str, default='')
    argument_group.add_argument('--vn-resolution', nargs='?', type=str, default='')

  @staticmethod
  def handle_arguments(args : argparse.Namespace):
    # 当命令行解析完毕后，如果该转换被启用，则该函数负责读取该转换所使用的参数
    # 只会在注册时提供了 arg_title 的情况下调用
    if len(args.vn_name) > 0:
      VNParseTransform.name = args.vn_name
    if len(args.vn_resolution) > 0:
      if t := parse_pixel_resolution_str(args.vn_resolution):
        VNParseTransform.resolution = t
      else:
        raise ValueError('Not a valid resolution string: "' + args.vn_resolution + '"')

  def run(self) -> Operation | typing.List[Operation] | None:
    for doc in self.inputs:
      self._parser.add_document(doc)
    ast = self._parser.ast
    # print(ast.get_short_str())
    return ast

@MiddleEndDecl('vncodegen', input_decl=VNAST, output_decl=VNModel)
class VNCodeGenTransform(TransformBase):
  def run(self) -> Operation | list[Operation] | None:
    assert len(self.inputs) == 1
    ast = self.inputs[0]
    model = VNCodeGen.run(ast)
    return model
