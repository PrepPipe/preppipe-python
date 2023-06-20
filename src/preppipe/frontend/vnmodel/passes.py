# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0


from preppipe.irbase import Operation, typing
from .vnast import *
from ...pipeline import *
from ...irbase import *
from .vncodegen import VNCodeGen
from .vnparser_v2 import VNParser
from ...vnmodel_v4 import VNModel

@MiddleEndDecl('vnparse', input_decl=IMDocumentOp, output_decl=VNAST)
class VNParseTransform(TransformBase):
  _parser : VNParser
  def __init__(self, ctx: Context) -> None:
    super().__init__(ctx)
    self._parser = VNParser.create(ctx)

  def run(self) -> Operation | typing.List[Operation] | None:
    for doc in self.inputs:
      self._parser.add_document(doc)
    ast = self._parser.ast
    print(ast.get_short_str())
    return ast

@MiddleEndDecl('vncodegen', input_decl=VNAST, output_decl=VNModel)
class VNCodeGenTransform(TransformBase):
  def run(self) -> Operation | list[Operation] | None:
    assert len(self.inputs) == 1
    ast = self.inputs[0]
    model = VNCodeGen.run(ast)
    return model
