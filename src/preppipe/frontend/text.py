# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
import os
import chardet

from ..irbase import *
from ..inputmodel import *
from ..pipeline import *

def _parsetext(ctx : Context, path : str) -> IMDocumentOp:
  with open(path, "rb") as f:
    data = f.read()
    det = chardet.detect(data, should_rename_legacy=True)
    strcontent = data.decode(encoding=det["encoding"], errors="ignore")
    difile = ctx.get_DIFile(path)
    name = os.path.splitext(os.path.basename(path))[0]
    doc = IMDocumentOp.create(name, difile)
    lines = strcontent.splitlines(keepends=False)
    row = 0
    for line in lines:
      row += 1
      block = doc.body.create_block()
      if len(line) > 0:
        loc = ctx.get_DILocation(difile, 0, row, 1)
        e = IMElementOp.create(StringLiteral.get(line, ctx), '', loc)
        block.push_back(e)
    return doc

@FrontendDecl('txt', input_decl=IODecl('Text files', match_suffix=('txt',), nargs='+'), output_decl=IMDocumentOp)
class ReadText(TransformBase):
  _ctx : Context

  def __init__(self, _ctx: Context) -> None:
    super().__init__(_ctx)
    self._ctx = _ctx

  def run(self) -> IMDocumentOp | typing.List[IMDocumentOp]:
    if len(self.inputs) == 1:
      return _parsetext(self._ctx, self.inputs[0])
    results = []
    for f in self.inputs:
      results.append(_parsetext(self._ctx, f))
    return results
