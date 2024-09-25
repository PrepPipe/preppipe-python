# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ..irbase import *
from .. import irdataop
from ..language import TranslationDomain, Translatable
from ..enginecommon.ast import *

TR_webgal = TranslationDomain("webgal")

@irdataop.IROperationDataclass
class WebGalNode(BackendASTNodeBase):
  flag_next : OpOperand[BoolLiteral] # 是否立即执行下一句
  when : OpOperand[StringLiteral] # 执行该命令的条件

  @classmethod
  def is_controlflow_instruction(cls) -> bool:
    # 是否是控制流指令
    # 一般而言这些指令之后的场景状态会被清空
    return False

  def get_flag_next(self) -> bool:
    if v := self.flag_next.try_get_value():
      return v.value
    return False

@irdataop.IROperationDataclass
class WebGalCommentNode(WebGalNode):
  content : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, content : StringLiteral | str, loc : Location | None = None):
    if isinstance(content, str):
      content = StringLiteral.get(content, context=context)
    return WebGalCommentNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, content=content, loc=loc)

@irdataop.IROperationDataclass
class WebGalASMNode(WebGalNode):
  content : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalSayNode(WebGalNode):
  sayer : OpOperand[StringLiteral]
  content : OpOperand[StringListLiteral]
  voice : OpOperand[StringLiteral]
  voice_volume : OpOperand[IntLiteral]
  flag_hold : OpOperand[BoolLiteral]
  # 不管下面哪一个 flag 被设置，历史记录中都会把之前的所有内容重复一遍
  flag_notend : OpOperand[BoolLiteral] # 等效于 next 外加输出 \r
  flag_concat : OpOperand[BoolLiteral] # 等效于前一句没加 \n

@irdataop.IROperationDataclass
class WebGalSetTextboxNode(WebGalNode):
  on : OpOperand[BoolLiteral]

@irdataop.IROperationDataclass
class WebGalEndNode(WebGalNode):
  pass

@irdataop.IROperationDataclass
class WebGalChangeBGNode(WebGalNode):
  bg : OpOperand[StringLiteral] # 相对路径或者 "none"

@irdataop.IROperationDataclass
class WebGalChangeFigureNode(WebGalNode):
  id_str : OpOperand[StringLiteral] # -id=<ID>
  figure : OpOperand[StringLiteral] # 相对路径或者 "none"
  position : OpOperand[StringLiteral] # "", "left", "right"
  transform : OpOperand[StringLiteral] # 应该是一个 json dict 转换为字符串后的结果

@irdataop.IROperationDataclass
class WebGalMiniAvatarNode(WebGalNode):
  avatar : OpOperand[StringLiteral] # 相对路径或者 "none"

@irdataop.IROperationDataclass
class WebGalUnlockCGNode(WebGalNode):
  cg : OpOperand[StringLiteral]
  namestr : OpOperand[StringLiteral]
  series : OpOperand[IntLiteral]

@irdataop.IROperationDataclass
class WebGalBGMNode(WebGalNode):
  bgm : OpOperand[StringLiteral]
  volume : OpOperand[IntLiteral]
  enter : OpOperand[IntLiteral]

@irdataop.IROperationDataclass
class WebGalPlayEffectNode(WebGalNode):
  id_str : OpOperand[StringLiteral]
  effect : OpOperand[StringLiteral]
  volume : OpOperand[IntLiteral]

@irdataop.IROperationDataclass
class WebGalUnlockBGMNode(WebGalNode):
  bgm : OpOperand[StringLiteral]
  namestr : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalPlayVideoNode(WebGalNode):
  video : OpOperand[StringLiteral]
  flag_skipoff : OpOperand[BoolLiteral]

@irdataop.IROperationDataclass
class WebGalChangeSceneNode(WebGalNode):
  scene : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalCallSceneNode(WebGalNode):
  scene : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalChooseBranchNode(WebGalNode):
  condition_show : OpOperand[StringLiteral]
  condition_clickable : OpOperand[StringLiteral]
  text : OpOperand[StringLiteral]
  destination : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalChooseNode(WebGalNode):
  choices : Block # WebGalChooseBranchNode

@irdataop.IROperationDataclass
class WebGalLabelNode(WebGalNode):
  label : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalJumpLabelNode(WebGalNode):
  label : OpOperand[StringLiteral]

irdataop.IROperationDataclass
class WebGalSetVarNode(WebGalNode):
  varname : OpOperand[StringLiteral]
  expr : OpOperand[StringLiteral]
  flag_global : OpOperand[BoolLiteral]

@irdataop.IROperationDataclass
class WebGalGetUserInputNode(WebGalNode):
  varname : OpOperand[StringLiteral]
  title : OpOperand[StringLiteral]
  buttontext : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalSetAnimationNode(WebGalNode):
  animation : OpOperand[StringLiteral]
  target : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalSetTransitionNode(WebGalNode):
  target : OpOperand[StringLiteral]
  enter : OpOperand[StringLiteral]
  exit : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalPixiInitNode(WebGalNode):
  pass

@irdataop.IROperationDataclass
class WebGalPixiPerformNode(WebGalNode):
  effect : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class WebGalScriptFileOp(Symbol):
  relpath : OpOperand[StringLiteral]
  body : Block

  @staticmethod
  def create(context : Context, name : str, loc : Location | None = None):
    return WebGalScriptFileOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

class WebGalASTVisitor(BackendASTVisitorBase):
  def start_visit(self, v : WebGalScriptFileOp):
    assert isinstance(v, WebGalScriptFileOp)
    return self.visitChildren(v)

@irdataop.IROperationDataclass
class WebGalModel(BackendProjectModelBase[WebGalScriptFileOp]):

  @staticmethod
  def create(context : Context):
    return WebGalModel(init_mode=IRObjectInitMode.CONSTRUCT, context=context)
