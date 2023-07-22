# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 如果根命名空间下没有任何函数带入口标记，我们在此尝试找个函数加入口
# 我们选第一个没有调用者的函数

from ...vnmodel import *
from ...pipeline import TransformBase, MiddleEndDecl

def vn_entry_inference(m : VNModel):
  rootns = m.get_namespace('/')
  if rootns is None:
    return
  first_func_without_caller = None
  for func in rootns.functions:
    if entry := func.get_entry_point():
      # 已经有函数是入口了，不用再加
      return
    is_caller_found = False
    for u in func.uses:
      user = u.user_op
      if isinstance(user, VNCallInst):
        is_caller_found = True
        break
    if not is_caller_found and first_func_without_caller is None:
      first_func_without_caller = func
  if first_func_without_caller is not None:
    first_func_without_caller.set_as_entry_point(VNFunction.ATTRVAL_ENTRYPOINT_MAIN)

@MiddleEndDecl('vn-entryinference', input_decl=VNModel, output_decl=VNModel)
class VNEntryInferencePass(TransformBase):
  def run(self) -> VNModel:
    assert len(self.inputs) == 1
    vn_entry_inference(self.inputs[0])
    return self.inputs[0]
