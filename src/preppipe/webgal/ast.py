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

  def set_flag_next(self, v : bool = True):
    self.flag_next.set_operand(0, BoolLiteral.get(v, context=self.context))

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

  @staticmethod
  def create(context : Context, content : StringLiteral | str, loc : Location | None = None):
    if isinstance(content, str):
      content = StringLiteral.get(content, context=context)
    return WebGalASMNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, content=content, loc=loc)

@irdataop.IROperationDataclass
class WebGalSayNode(WebGalNode):
  sayer : OpOperand[StringLiteral] # 必须有值，旁白的话就是空字符串
  content : OpOperand[StringListLiteral]
  voice : OpOperand[StringLiteral]
  voice_volume : OpOperand[IntLiteral]
  # 不管下面哪一个 flag 被设置，历史记录中都会把之前的所有内容重复一遍
  # （相当于一个独立的 VNSayInstructionGroup）
  flag_notend : OpOperand[BoolLiteral] # 等效于 next 外加输出 \r
  flag_concat : OpOperand[BoolLiteral] # 等效于前一句没加 \n

  @staticmethod
  def create(context : Context, sayer : StringLiteral | str, content : StringListLiteral, loc : Location | None = None):
    if isinstance(sayer, str):
      sayer = StringLiteral.get(sayer, context=context)
    return WebGalSayNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, sayer=sayer, content=content, loc=loc)

@irdataop.IROperationDataclass
class WebGalIntroNode(WebGalNode):
  content : OpOperand[StringListLiteral]
  flag_hold : OpOperand[BoolLiteral]

@irdataop.IROperationDataclass
class WebGalSetTextboxNode(WebGalNode):
  on : OpOperand[BoolLiteral]

@irdataop.IROperationDataclass
class WebGalEndNode(WebGalNode):

  @staticmethod
  def create(context : Context, loc : Location | None = None):
    return WebGalEndNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, loc=loc)

@irdataop.IROperationDataclass
class WebGalChangeBGNode(WebGalNode):
  bg : OpOperand[StringLiteral] # 相对路径或者 "none"

  @staticmethod
  def create(context : Context, bg : StringLiteral | str = "none", loc : Location | None = None):
    if isinstance(bg, str):
      bg = StringLiteral.get(bg, context=context)
    return WebGalChangeBGNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, bg=bg, loc=loc)

@irdataop.IROperationDataclass
class WebGalChangeFigureNode(WebGalNode):
  id_str : OpOperand[StringLiteral] # -id=<ID>
  figure : OpOperand[StringLiteral] # 相对路径或者 "none"
  position : OpOperand[StringLiteral] # "", "left", "right"
  transform : OpOperand[StringLiteral] # 应该是一个 json dict 转换为字符串后的结果

  @staticmethod
  def create(context : Context, figure : StringLiteral | str = "none", loc : Location | None = None):
    if isinstance(figure, str):
      figure = StringLiteral.get(figure, context=context)
    return WebGalChangeFigureNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, figure=figure, loc=loc)

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

  @staticmethod
  def create(context : Context, bgm : StringLiteral | str = "none", loc : Location | None = None):
    if isinstance(bgm, str):
      bgm = StringLiteral.get(bgm, context=context)
    return WebGalBGMNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, bgm=bgm, loc=loc)

@irdataop.IROperationDataclass
class WebGalPlayEffectNode(WebGalNode):
  id_str : OpOperand[StringLiteral]
  effect : OpOperand[StringLiteral]
  volume : OpOperand[IntLiteral]

  @staticmethod
  def create(context : Context, effect : StringLiteral | str = "none", loc : Location | None = None):
    if isinstance(effect, str):
      effect = StringLiteral.get(effect, context=context)
    return WebGalPlayEffectNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, effect=effect, loc=loc)

@irdataop.IROperationDataclass
class WebGalUnlockBGMNode(WebGalNode):
  bgm : OpOperand[StringLiteral]
  namestr : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, bgm : StringLiteral | str, loc : Location | None = None):
    if isinstance(bgm, str):
      bgm = StringLiteral.get(bgm, context=context)
    return WebGalUnlockBGMNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, bgm=bgm, loc=loc)

@irdataop.IROperationDataclass
class WebGalPlayVideoNode(WebGalNode):
  video : OpOperand[StringLiteral]
  flag_skipoff : OpOperand[BoolLiteral]

@irdataop.IROperationDataclass
class WebGalChangeSceneNode(WebGalNode):
  scene : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, scene : StringLiteral | str, loc : Location | None = None):
    if isinstance(scene, str):
      scene = StringLiteral.get(scene, context=context)
    return WebGalChangeSceneNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, scene=scene, loc=loc)

@irdataop.IROperationDataclass
class WebGalCallSceneNode(WebGalNode):
  scene : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, scene : StringLiteral | str, loc : Location | None = None):
    if isinstance(scene, str):
      scene = StringLiteral.get(scene, context=context)
    return WebGalCallSceneNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, scene=scene, loc=loc)

@irdataop.IROperationDataclass
class WebGalChooseBranchNode(WebGalNode):
  condition_show : OpOperand[StringLiteral]
  condition_clickable : OpOperand[StringLiteral]
  text : OpOperand[StringLiteral]
  destination : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, text : StringLiteral | str, destination : StringLiteral | str, loc : Location | None = None):
    if isinstance(text, str):
      text = StringLiteral.get(text, context=context)
    if isinstance(destination, str):
      destination = StringLiteral.get(destination, context=context)
    return WebGalChooseBranchNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, text=text, destination=destination, loc=loc)

@irdataop.IROperationDataclass
class WebGalChooseNode(WebGalNode):
  choices : Block # WebGalChooseBranchNode

  @staticmethod
  def create(context : Context, loc : Location | None = None):
    return WebGalChooseNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, loc=loc)

@irdataop.IROperationDataclass
class WebGalLabelNode(WebGalNode):
  label : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, label : StringLiteral | str, loc : Location | None = None):
    if isinstance(label, str):
      label = StringLiteral.get(label, context=context)
    return WebGalLabelNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, label=label, loc=loc)

@irdataop.IROperationDataclass
class WebGalJumpLabelNode(WebGalNode):
  label : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, label : StringLiteral | str, loc : Location | None = None):
    if isinstance(label, str):
      label = StringLiteral.get(label, context=context)
    return WebGalJumpLabelNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, label=label, loc=loc)

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
