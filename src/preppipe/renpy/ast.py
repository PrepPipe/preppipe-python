# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ..irbase import *
from .. import irdataop
from ..language import TranslationDomain, Translatable

# 在此我们定义 RenPy 语法的一个子集，以供我们对 Renpy 进行生成
# （有朝一日应该也能把读取 Renpy 的功能做进来吧。。）
# 我们使用 IR 形式组成 AST 的结构，这样便于我们使用 IR 提供的一系列功能

TR_renpy = TranslationDomain("renpy")

#-----------------------------------------------------------
# 抽象基类
#-----------------------------------------------------------

@irdataop.IROperationDataclass
class RenPyNode(Operation):
  # 代表一个 AST 节点的基类，对应 renpy 的 renpy/ast.py
  def accept(self, visitor):
    return getattr(visitor, "visit" + self.__class__.__name__)(self)

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyASMNode(RenPyNode, Value):
  # 可以多行的 ASM
  asm : OpOperand[StringListLiteral] # 带一个 StringListLiteral，每行一个字符串，行首空格保留（只会有空格，RenPy不支持Tab缩进），行末尾没有\r\n这种EOL

  def get_singleline_str(self) -> str:
    if sl := self.asm.try_get_value():
      return ','.join(sl.value)
    return ''

  @staticmethod
  def create(context : Context, asm : StringLiteral | StringListLiteral, name : str = '', loc : Location | None = None) -> RenPyASMNode:
    if isinstance(asm, StringLiteral):
      asm = StringListLiteral.get(context, (asm,))
    return RenPyASMNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, asm=asm, name=name, loc=loc)

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyASMExpr(RenPyNode, Value):
  # 单行或内嵌的 ASM
  asm : OpOperand[StringLiteral]

  def get_string(self) -> str:
    return self.asm.get().get_string()

  @staticmethod
  def create(context : Context, asm : StringLiteral | str, name : str = '', loc : Location | None = None) -> RenPyASMExpr:
    return RenPyASMExpr(init_mode=IRObjectInitMode.CONSTRUCT, context=context, asm=asm, name=name, loc=loc)

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyCharacterExpr(RenPyNode, Value):
  displayname : OpOperand[StringLiteral]
  kind        : OpOperand[StringLiteral] # str （可以指定另一个 Character 并获取默认值，或者指定 adv / nvl）
  image       : OpOperand[StringLiteral] # str (头像图片)
  voicetag    : OpOperand[StringLiteral] # str (voice_tag)
  what_color  : OpOperand[StringLiteral]
  what_prefix : OpOperand[StringLiteral]
  what_suffix : OpOperand[StringLiteral]
  who_color   : OpOperand[StringLiteral]
  who_prefix  : OpOperand[StringLiteral]
  who_suffix  : OpOperand[StringLiteral]
  dynamic   : OpOperand[RenPyASMExpr]
  condition : OpOperand[RenPyASMExpr]
  interact  : OpOperand[BoolLiteral] # bool，是否等待用户点击
  advance   : OpOperand[BoolLiteral] # bool, 用户是否可以通过点击来继续。（不行的话可能必须要点一个链接或是执行其他操作来继续）
  mode      : OpOperand[StringLiteral] # str: https://www.renpy.org/doc/html/modes.html#modes
  callback  : OpOperand[StringLiteral] # str, 一个函数名
  ctc             : OpOperand[RenPyASMExpr] # displayable expr
  ctc_pause       : OpOperand[RenPyASMExpr]
  ctc_timedpause  : OpOperand[RenPyASMExpr]
  ctc_position    : OpOperand[StringLiteral] # str : enum {"nestled", "nestled-close", "fixed"}
  screen      : OpOperand[StringLiteral] # str : 用来显示对话的 Screen 的名称
  show_params : OpOperand[RenPyASMExpr] # 应该是一串 "show_param1=xxx" "show_param2=yyy" 这样的参数
  body        : Block # 放需要的 RenPyASMExpr

  @staticmethod
  def create(context : Context, displayname : StringLiteral | str | None) -> RenPyCharacterExpr:
    return RenPyCharacterExpr(init_mode=IRObjectInitMode.CONSTRUCT, context=context, displayname=displayname)

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyDefineNode(RenPyNode, Value):
  # 用来定义像角色、图片等信息
  # https://www.renpy.org/doc/html/python.html#define-statement
  # store : str = 'store'
  # varname : str
  # operator : enum: '=', '+=', '|='
  # expr : RenPyCharacterExpr / RenPyImageExpr / RenPyASMExpr
  store : OpOperand[StringLiteral]
  varname : OpOperand[StringLiteral]
  assign_operator : OpOperand[StringLiteral] # enum: '=', '+=', '|='
  expr : OpOperand[Value] # RenPyCharacterExpr / RenPyImageExpr / RenPyASMExpr
  body : Block

  @staticmethod
  def create(context : Context, varname : StringLiteral | str, expr : Value, store : StringLiteral | str | None = None, assign_operator : StringLiteral | str | None = None) -> RenPyDefineNode:
    return RenPyDefineNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, varname=varname, expr=expr, store=store, assign_operator=assign_operator)

  @staticmethod
  def create_character(context : Context, varname : StringLiteral | str, displayname : StringLiteral | str | None) -> tuple[RenPyDefineNode, RenPyCharacterExpr]:
    charexpr = RenPyCharacterExpr.create(context, displayname)
    defnode = RenPyDefineNode.create(context, varname=varname, expr=charexpr)
    defnode.body.push_back(charexpr)
    return (defnode, charexpr)

  def get_varname_str(self) -> str:
    vname = self.varname.get().get_string()
    if s := self.store.try_get_value():
      return s.get_string() + '.' + vname
    return vname

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyDefaultNode(RenPyNode, Value):
  # 用来给变量做声明、赋初值
  # store : str = 'store'
  # varname : str
  # expr
  store : OpOperand[StringLiteral]
  varname : OpOperand[StringLiteral]
  expr : OpOperand[RenPyASMExpr]
  body : Block

  def get_varname_str(self) -> str:
    vname = self.varname.get().get_string()
    if s := self.store.try_get_value():
      return s.get_string() + '.' + vname
    return vname

  @staticmethod
  def create(context : Context, varname : StringLiteral | str, expr : RenPyASMExpr, store : StringLiteral | str | None = None) -> RenPyDefaultNode:
    result = RenPyDefaultNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, varname=varname, expr=expr, store=store)
    result.body.push_back(expr)
    return result


@irdataop.IROperationDataclass
class RenPySayNode(RenPyNode):
  #'who' 发言者；旁白的话为空
  #'what' 发言内容
  # 'with_' with 从句
  # 'interact', bool, 是否等待玩家点击
  # 'attributes' --> 'persistent_attributes', 执行后持久施加给角色的属性
  # 'temporary_attributes', 只在该发言时施加给角色的属性
  # 'identifier',发言的ID，用于与语音绑定等
  # 'arguments' 忽略
  # 'rollback', 忽略
  # <who> [<attribute>] [@ <temporary attribute>] <what> [id <identifier>] [with <with_>]
  who : OpOperand[RenPyDefineNode]
  what : OpOperand[Value] # StringLiteral, TextFragmentLiteral, string-type variables
  with_ : OpOperand[StringLiteral] = irdataop.operand_field(lookup_name="with")
  interact : OpOperand[BoolLiteral]
  persistent_attributes : OpOperand[StringLiteral]
  temporary_attributes : OpOperand[StringLiteral]
  identifier : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, who : RenPyDefineNode | None, what : typing.Iterable[Value] | Value | str) -> RenPySayNode:
    return RenPySayNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, who=who, what=what)

@irdataop.IROperationDataclass
class RenPyInitNode(RenPyNode):
  # RenPy 的 init 块
  # 除了优先级外基本上只有个 body
  # 如果是单纯的 init, 则 pythoncode 为空，所有 RenPy AST结点都在 body 内
  # 如果是 init pyton 块，则 pythoncode 包含所有 python 代码，该 RenPyASMNode 储存在 body 中
  # priority : int
  # body : region
  priority : OpOperand[IntLiteral]
  pythoncode : OpOperand[RenPyASMNode]
  body : Block

  @staticmethod
  def create(context : Context, priority : IntLiteral | int, pythoncode : RenPyASMNode | None = None):
    result = RenPyInitNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, priority=priority, pythoncode=pythoncode)
    if pythoncode is not None:
      result.body.push_back(pythoncode)
    return result

@irdataop.IROperationDataclass
class RenPyLabelNode(RenPyNode):
  # 主文章：RenPy Labels & Control Flow
  # https://www.renpy.org/doc/html/label.html#labels-control-flow
  # hide: 忽略
  #name : str
  #parameters: RenPyNode
  codename : OpOperand[StringLiteral]
  parameters : OpOperand[StringLiteral]
  body : Block

  @staticmethod
  def create(context : Context, codename : StringLiteral | str) -> RenPyLabelNode:
    return RenPyLabelNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, codename=codename)

@irdataop.IROperationDataclass
class RenPyPythonNode(RenPyNode):
  # 普通的内嵌 Python 代码块
  # code : RenPyPyCodeObject
  # hide : bool # 是否使用局部词典、避免污染上层环境的变量词典
  # store : str = 'store' # 使用哪个 store 对象来存值，暂不支持
  code : OpOperand[RenPyASMNode]
  hide : OpOperand[BoolLiteral]
  store : OpOperand[StringLiteral] # in xxx
  body : Block

  @staticmethod
  def create(context : Context, code : RenPyASMNode, hide : BoolLiteral | bool | None = None, store : StringLiteral | str | None = None):
    result = RenPyPythonNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, code=code, hide=hide, store=store)
    result.body.push_back(code)
    return result

@irdataop.IROperationDataclass
class RenPyEarlyPythonNode(RenPyPythonNode):

  @staticmethod
  def create(context : Context, code : RenPyASMNode):
    result = RenPyEarlyPythonNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, code=code)
    result.body.push_back(code)
    return result

@irdataop.IROperationDataclass
class RenPyImageNode(RenPyNode):
  #name : str
  #displayable : str # atl or PyCode
  codename : OpOperand[StringLiteral]
  displayable : OpOperand[RenPyASMExpr]
  body : Block

  @staticmethod
  def create(context : Context, codename : typing.Iterable[str] | StringLiteral | str, displayable : RenPyASMExpr | StringLiteral | str):
    if isinstance(displayable, str):
      displayable = StringLiteral.get(displayable, context)
    if isinstance(displayable, StringLiteral):
      displayable = RenPyASMExpr.create(context, displayable)
    assert isinstance(displayable, RenPyASMExpr)
    result = RenPyImageNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, codename=codename, displayable=displayable)
    result.body.push_back(displayable)
    return result

#@irdataop.IROperationDataclass
#class RenPyTransformNode(RenPyNode):
  # store : str = 'store'
  # name : str
  # atl : ATL code block
  # parameters : 应该表述为类似 inspect.signature 的对象
#  codename : OpOperand[StringLiteral]
#  store : OpOperand[StringLiteral]
#  parameters : OpOperand[StringLiteral]
#  atl : OpOperand[RenPyASMNode]
#  body : Block

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyWithNode(RenPyNode, Value):
  # expr : str
  # paired: 暂时不管
  expr : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, expr : typing.Iterable[StringLiteral | str] | StringLiteral | str):
    return RenPyWithNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, expr=expr)

@irdataop.IROperationDataclass
class RenPyShowNode(RenPyNode):
  # imspec: list[str]
  # atl
  imspec : OpOperand[StringLiteral]
  showas : OpOperand[StringLiteral]
  atl : OpOperand[RenPyASMExpr] # at block
  behind : OpOperand[StringLiteral] # 0-N 个图片名
  onlayer : OpOperand[StringLiteral]
  zorder : OpOperand[IntLiteral]
  with_ : OpOperand[RenPyWithNode]
  body : Block # only for ATL

  @staticmethod
  def create(context : Context, imspec : typing.Iterable[StringLiteral | str] | StringLiteral | str,
             showas : StringLiteral | str | None = None, showat : RenPyASMExpr | None = None,
             behind : typing.Iterable[StringLiteral | str] | StringLiteral | str | None = None,
             onlayer : StringLiteral | str | None = None,
             zorder : IntLiteral | int | None = None,
             with_ : RenPyWithNode | None = None):
    result = RenPyShowNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, imspec=imspec, showas=showas, atl=showat, behind=behind, onlayer=onlayer, zorder=zorder, with_=with_)
    if showat is not None:
      result.body.push_back(showat)
    if with_ is not None:
      result.body.push_back(with_)
    return result

#class RenPyShowLayerNode(RenPyNode):
  # 可以暂时不做
  # layer : str
  # at_list : list[str]
  # atl
#  pass

#class RenPyCameraNode(RenPyNode):
  # 语义和 ShowLayer 有细微差别，其他完全一样
  # 可以暂时不做
  # layer : str
  # at_list : list[str]
  # atl
#  pass

@irdataop.IROperationDataclass
class RenPySceneNode(RenPyNode):
  # 'imspec' : list[str]
  # 'layer' : str
  # 'atl',
  imspec : OpOperand[StringLiteral]
  #layer : OpOperand[StringLiteral]
  #atl : OpOperand[RenPyASMExpr]
  with_ : OpOperand[RenPyWithNode]
  body : Block # only for ATL

  @staticmethod
  def create(context : Context, imspec : typing.Iterable[StringLiteral | str] | StringLiteral | str, with_ : RenPyWithNode | None = None):
    result = RenPySceneNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, imspec=imspec, with_=with_)
    if with_ is not None:
      result.body.push_back(with_)
    return result

@irdataop.IROperationDataclass
class RenPyHideNode(RenPyNode):
  # 'imspec' : list[str]
  imspec : OpOperand[StringLiteral]
  onlayer : OpOperand[StringLiteral]
  with_ : OpOperand[RenPyWithNode]
  body : Block

  @staticmethod
  def create(context : Context, imspec : typing.Iterable[StringLiteral | str] | StringLiteral | str, onlayer : StringLiteral | str | None = None, with_ : RenPyWithNode | None = None):
    result = RenPyHideNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, imspec=imspec, onlayer=onlayer, with_=with_)
    if with_ is not None:
      result.body.push_back(with_)
    return result


@irdataop.IROperationDataclass
class RenPyPlayNode(RenPyNode):
  channel : OpOperand[StringLiteral] # 大概是 music 或 sound, 也可能是别的
  audiospec : OpOperand[StringLiteral]
  fadein : OpOperand[FloatLiteral] # 秒数时长，可能没有值
  fadeout : OpOperand[FloatLiteral] # 秒数时长，可能没有值

  CHANNEL_MUSIC : typing.ClassVar[str] = 'music'
  CHANNEL_SOUND : typing.ClassVar[str] = 'sound'

  @staticmethod
  def create(context : Context, channel : StringLiteral | str, audiospec : StringLiteral | str, fadein : FloatLiteral | None = None, fadeout : FloatLiteral | None = None):
    return RenPyPlayNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, channel=channel, audiospec=audiospec, fadein=fadein, fadeout=fadeout)

@irdataop.IROperationDataclass
class RenPyStopNode(RenPyNode):
  channel : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, channel : StringLiteral | str):
    return RenPyStopNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, channel=channel)

@irdataop.IROperationDataclass
class RenPyVoiceNode(RenPyNode):
  audiospec : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, audiospec : StringLiteral | str):
    return RenPyVoiceNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, audiospec=audiospec)

@irdataop.IROperationDataclass
class RenPyCallNode(RenPyNode):
  # label : str
  # arguments: 暂时不管
  # expression : bool, 决定 label 是否是一个表达式
  label : OpOperand[StringLiteral]
  is_expr : OpOperand[BoolLiteral] # label 是否是表达式
  arguments : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, label : StringLiteral | str, is_expr : BoolLiteral | bool | None = None, arguments : typing.Iterable[StringLiteral] | StringLiteral | str | None = None):
    return RenPyCallNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, label=label, is_expr=is_expr, arguments=arguments)

@irdataop.IROperationDataclass
class RenPyReturnNode(RenPyNode):
  # expr : str
  expr : OpOperand[RenPyASMExpr]
  body : Block

  @staticmethod
  def create(context: Context, expr : RenPyASMExpr | None = None):
    result = RenPyReturnNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, expr=expr)
    if expr is not None:
      result.body.push_back(expr)
    return result

@irdataop.IROperationDataclass
class RenPyMenuItemNode(RenPyNode):
  # 用于 menu 命令
  # "<label>" (<arguments>) if <condition>:
  #    <body>
  label : OpOperand[Value]
  condition : OpOperand[RenPyASMExpr]
  arguments : OpOperand[RenPyASMExpr]
  optionblock : Block
  body : Block

  @staticmethod
  def create(context: Context, label : typing.Iterable[TextFragmentLiteral | StringLiteral | str] | TextFragmentLiteral | StringLiteral | str, condition : RenPyASMExpr | None = None, arguments : RenPyASMExpr | None = None):
    result = RenPyMenuItemNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, label=label, condition=condition, arguments=arguments)
    if condition is not None:
      result.optionblock.push_back(condition)
    if arguments is not None:
      result.optionblock.push_back(arguments)
    return result

@irdataop.IROperationDataclass
class RenPyMenuNode(RenPyNode):
  # https://www.renpy.org/doc/html/menus.html
  # items : list[tuple[label : str, condition : expr, block]]
  # set : str (执行选单时如果某项的标题已在 set 中存在，则该选项不会出现。用这个来实现“排除选项”的功能)
  # with_: with 从句, 暂时不管
  # has_caption: bool, 暂时不管
  varname : OpOperand[StringLiteral]
  menuset : OpOperand[StringLiteral]
  arguments : OpOperand[RenPyASMExpr]
  optionblock : Block
  items : Block # 里面有 0-1个 RenPySayNode ，其余应该都是 RenPyMenuItemNode

  @staticmethod
  def create(context : Context, varname : StringLiteral | str | None = None, menuset : StringLiteral | str | None = None, arguments : RenPyASMExpr | None = None):
    result = RenPyMenuNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, varname=varname, menuset=menuset, arguments=arguments)
    if arguments is not None:
      result.optionblock.push_back(arguments)
    return result

@irdataop.IROperationDataclass
class RenPyJumpNode(RenPyNode):
  # target : str
  # expression : bool, target是否是表达式
  target : OpOperand[StringLiteral]
  is_expr : OpOperand[BoolLiteral] # target是否是表达式

  @staticmethod
  def create(context : Context, target : StringLiteral | str, is_expr : BoolLiteral | bool | None = None):
    return RenPyJumpNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, target=target, is_expr=is_expr)

@irdataop.IROperationDataclass
class RenPyPassNode(RenPyNode):

  @staticmethod
  def create(context : Context):
    return RenPyPassNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context)

@irdataop.IROperationDataclass
class RenPyCondBodyPair(RenPyNode):
  # 用于 if 和 while
  condition : OpOperand[RenPyASMExpr]
  body : Block

  # 不应直接创建，没有 create()

@irdataop.IROperationDataclass
class RenPyWhileNode(RenPyCondBodyPair):
  # condition : bool expr
  # block
  optionblock : Block # 存放 RenPyASMExpr

  @staticmethod
  def create(context : Context, condition : RenPyASMExpr):
    result = RenPyWhileNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, condition=condition)
    result.optionblock.push_back(condition)
    return result

@irdataop.IROperationDataclass
class RenPyIfNode(RenPyNode):
  # entries : list[tuple[condition : bool expr, block]]
  entries : Block # 里面应该是一串 RenPyCondBodyPair, 按照判断顺序排列
  optionblock : Block # 存放 RenPyASMExpr

  def add_branch(self, condition : RenPyASMExpr | None) -> Block:
    if condition is not None:
      self.optionblock.push_back(condition)
    branch = RenPyCondBodyPair(init_mode=IRObjectInitMode.CONSTRUCT, context=self.context, condition=condition)
    self.entries.push_back(branch)
    return branch.body

  @staticmethod
  def create(context : Context):
    return RenPyIfNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context)

@irdataop.IROperationDataclass
class RenPyFileAssetOp(Symbol):
  ref : OpOperand
  export_format : OpOperand[StringLiteral] # 如果非空，我们在导出时需要进行另存为

  def get_asset_value(self) -> Value:
    return self.ref.get()

  @staticmethod
  def create(context : Context, assetref : Value, path : str, export_format : StringLiteral | str | None = None, loc : Location | None = None):
    return RenPyFileAssetOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, ref=assetref, export_format=export_format, name=path, loc=loc)

@irdataop.IROperationDataclass
class RenPyScriptFileOp(Symbol):
  body : Block # "body"区下的单块，每个内容都是顶层 RenPyNode
  indent : OpOperand[IntLiteral] # 整数类型常量，每层缩进多少空格；无参数时不限制（应该只有读取的现成文件才会指定该值）

  def get_indent(self) -> int | None:
    if v := self.indent.get():
      assert isinstance(v, IntLiteral)
      return v.value
    return None

  def set_indent(self, indent : int) -> None:
    assert indent > 0
    self.indent.set_operand(0, IntLiteral.get(indent, self.context))

  @staticmethod
  def create(context : Context, name : str, loc : Location | None = None, indent : int | None = None):
    return RenPyScriptFileOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc, indent=indent)

# pylint: disable=invalid-name,too-many-public-methods
class RenPyASTVisitor:
  def visitChildren(self, v : Operation):
    for r in v.regions:
      for b in r.blocks:
        for op in b.body:
          if isinstance(op, RenPyNode):
            op.accept(self)

  def start_visit(self, v : RenPyScriptFileOp):
    assert isinstance(v, RenPyScriptFileOp)
    return self.visitChildren(v)

  def visitRenPyASMNode(self, v : RenPyASMNode):
    return self.visitChildren(v)
  def visitRenPyASMExpr(self, v : RenPyASMExpr):
    return self.visitChildren(v)
  def visitRenPyCharacterExpr(self, v : RenPyCharacterExpr):
    return self.visitChildren(v)
  def visitRenPyDefineNode(self, v : RenPyDefineNode):
    return self.visitChildren(v)
  def visitRenPySayNode(self, v : RenPySayNode):
    return self.visitChildren(v)
  def visitRenPyInitNode(self, v : RenPyInitNode):
    return self.visitChildren(v)
  def visitRenPyLabelNode(self, v : RenPyLabelNode):
    return self.visitChildren(v)
  def visitRenPyPythonNode(self, v : RenPyPythonNode):
    return self.visitChildren(v)
  def visitRenPyEarlyPythonNode(self, v : RenPyEarlyPythonNode):
    return self.visitChildren(v)
  def visitRenPyImageNode(self, v : RenPyImageNode):
    return self.visitChildren(v)
#  def visitRenPyTransformNode(self, v : RenPyTransformNode):
#    return self.visitChildren(v)
  def visitRenPyShowNode(self, v : RenPyShowNode):
    return self.visitChildren(v)
  def visitRenPySceneNode(self, v : RenPySceneNode):
    return self.visitChildren(v)
  def visitRenPyWithNode(self, v : RenPyWithNode):
    return self.visitChildren(v)
  def visitRenPyHideNode(self, v : RenPyHideNode):
    return self.visitChildren(v)
  def visitRenPyPlayNode(self, v : RenPyPlayNode):
    return self.visitChildren(v)
  def visitRenPyStopNode(self, v : RenPyStopNode):
    return self.visitChildren(v)
  def visitRenPyVoiceNode(self, v : RenPyVoiceNode):
    return self.visitChildren(v)
  def visitRenPyCallNode(self, v : RenPyCallNode):
    return self.visitChildren(v)
  def visitRenPyReturnNode(self, v : RenPyReturnNode):
    return self.visitChildren(v)
  def visitRenPyMenuItemNode(self, v : RenPyMenuItemNode):
    return self.visitChildren(v)
  def visitRenPyMenuNode(self, v : RenPyMenuNode):
    return self.visitChildren(v)
  def visitRenPyJumpNode(self, v : RenPyJumpNode):
    return self.visitChildren(v)
  def visitRenPyPassNode(self, v : RenPyPassNode):
    return self.visitChildren(v)
  def visitRenPyCondBodyPair(self, v : RenPyCondBodyPair):
    return self.visitChildren(v)
  def visitRenPyWhileNode(self, v : RenPyWhileNode):
    return self.visitChildren(v)
  def visitRenPyIfNode(self, v : RenPyIfNode):
    return self.visitChildren(v)
  def visitRenPyDefaultNode(self, v : RenPyDefaultNode):
    return self.visitChildren(v)


@irdataop.IROperationDataclass
class RenPyModel(Operation):
  _script_region : SymbolTableRegion = irdataop.symtable_field(lookup_name="script") # RenPyScriptFileOp
  _asset_region : SymbolTableRegion = irdataop.symtable_field(lookup_name="asset") # RenPyAsset

  def get_script(self, scriptname : str) -> RenPyScriptFileOp:
    return self._script_region.get(scriptname)

  def add_script(self, script : RenPyScriptFileOp):
    self._script_region.add(script)

  def get_asset(self, name : str) -> RenPyFileAssetOp:
    return self._asset_region.get(name)

  def add_asset(self, asset : RenPyFileAssetOp):
    self._asset_region.add(asset)

  def scripts(self) -> typing.Iterable[RenPyScriptFileOp]:
    return self._script_region

  def assets(self) -> typing.Iterable[RenPyFileAssetOp]:
    return self._asset_region

  @staticmethod
  def create(context : Context) -> RenPyModel:
    return RenPyModel(init_mode=IRObjectInitMode.CONSTRUCT, context=context)

