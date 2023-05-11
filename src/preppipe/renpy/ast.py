# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ..irbase import *
from .. import irdataop

# 在此我们定义 RenPy 语法的一个子集，以供我们对 Renpy 进行生成
# （有朝一日应该也能把读取 Renpy 的功能做进来吧。。）
# 我们使用 IR 形式组成 AST 的结构，这样便于我们使用 IR 提供的一系列功能

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
  asm : OpOperand[StringListLiteral] # 带一个 StringListLiteral，每行一个字符串，行首空格保留（只会有空格，RenPy不支持Tab缩进），行末尾没有\r\n这种EOL

  @staticmethod
  def create(context : Context, asm : StringLiteral | StringListLiteral, name : str = '', loc : Location | None = None) -> RenPyASMNode:
    if isinstance(asm, StringLiteral):
      asm = StringListLiteral.get(context, (asm,))
    return RenPyASMNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, asm=asm, name=name, loc=loc)


@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyCharacterExpr(RenPyNode, Value):
  displayname : OpOperand[StringLiteral]
  kind        : OpOperand[StringLiteral] # str （可以指定另一个 Character 并获取默认值，或者指定 adv / nvl）
  image       : OpOperand[StringLiteral] # str (头像图片)
  voicetag    : OpOperand[StringLiteral] # str (voice_tag)
  what_prefix : OpOperand[StringLiteral]
  what_suffix : OpOperand[StringLiteral]
  who_prefix  : OpOperand[StringLiteral]
  who_suffix  : OpOperand[StringLiteral]
  dynamic   : OpOperand[RenPyASMNode] # 取一个从 RenPyASMNode 来的值
  condition : OpOperand[RenPyASMNode] # 取一个从 RenPyASMNode 来的值
  interact  : OpOperand[BoolLiteral] # bool，是否等待用户点击
  advance   : OpOperand[BoolLiteral] # bool, 用户是否可以通过点击来继续。（不行的话可能必须要点一个链接或是执行其他操作来继续）
  mode      : OpOperand[StringLiteral] # str: https://www.renpy.org/doc/html/modes.html#modes
  callback  : OpOperand[StringLiteral] # str, 一个函数名
  ctc             : OpOperand[RenPyASMNode] # RenPyASMNode, displayable expr
  ctc_pause       : OpOperand[RenPyASMNode]
  ctc_timedpause  : OpOperand[RenPyASMNode]
  ctc_position    : OpOperand[StringLiteral] # str : enum {"nestled", "nestled-close", "fixed"}
  screen      : OpOperand[StringLiteral] # str : 用来显示对话的 Screen 的名称
  show_params : OpOperand[StringListLiteral] # RenPyASMNode，应该是一串 "show_param1=xxx" "show_param2=yyy" 这样的参数
  body        : Block # 放需要的 RenPyASMNode

  @staticmethod
  def create(context : Context, displayname : StringLiteral | str) -> RenPyCharacterExpr:
    return RenPyCharacterExpr(init_mode=IRObjectInitMode.CONSTRUCT, context=context, displayname=displayname)

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyDefineNode(RenPyNode, Value):
  # 用来定义像角色、图片等信息
  # https://www.renpy.org/doc/html/python.html#define-statement
  # store : str = 'store'
  # varname : str
  # operator : enum: '=', '+=', '|='
  # expr : RenPyCharacterExpr / RenPyImageExpr / RenPyASMNode
  store : OpOperand[StringLiteral]
  varname : OpOperand[StringLiteral]
  assign_operator : OpOperand[StringLiteral] # enum: '=', '+=', '|='
  expr : OpOperand[Value] # RenPyCharacterExpr / RenPyImageExpr / RenPyASMNode
  body : Block

  @staticmethod
  def create(context : Context, varname : StringLiteral | str, expr : Value) -> RenPyDefineNode:
    return RenPyDefineNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, varname=varname, expr=expr)

  @staticmethod
  def create_character(context : Context, varname : StringLiteral | str, displayname : StringLiteral | str) -> tuple[RenPyDefineNode, RenPyCharacterExpr]:
    charexpr = RenPyCharacterExpr.create(context, displayname)
    defnode = RenPyDefineNode.create(context, varname=varname, expr=charexpr)
    defnode.body.push_back(charexpr)
    return (defnode, charexpr)

  def get_varname_str(self) -> str:
    vname = self.varname.get().get_string()
    if s := self.store.try_get_value():
      return s.get_string() + '.' + vname
    return vname

@irdataop.IROperationDataclass
class RenPySayNode(RenPyNode):
  #'who' 发言者
  #'what' 发言内容
  # 'with_' with 从句
  # 'interact', bool, 是否等待玩家点击
  # 'attributes' --> 'persistent_attributes', 执行后持久施加给角色的属性
  # 'temporary_attributes', 只在该发言时施加给角色的属性
  # 'identifier',发言的ID，用于与语音绑定等
  # 'arguments' 忽略
  # 'rollback', 忽略
  # <who> [<attribute>] [@ <temporary attribute>] <what> [noninteract] [id <identifier>] [with <with_>]
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
  # priority : int
  # body : region
  priority : OpOperand[IntLiteral]
  body : Block

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
  body : Block

@irdataop.IROperationDataclass
class RenPyEarlyPythonNode(RenPyPythonNode):
  pass

@irdataop.IROperationDataclass
class RenPyImageNode(RenPyNode):
  #name : str
  #displayable : str # atl or PyCode
  codename : OpOperand[StringLiteral]
  displayable : OpOperand[RenPyASMNode]
  body : Block

@irdataop.IROperationDataclass
class RenPyTransformNode(RenPyNode):
  # store : str = 'store'
  # name : str
  # atl : ATL code block
  # parameters : 应该表述为类似 inspect.signature 的对象
  codename : OpOperand[StringLiteral]
  store : OpOperand[StringLiteral]
  parameters : OpOperand[StringLiteral]
  atl : OpOperand[RenPyASMNode]
  body : Block

@irdataop.IROperationDataclass
class RenPyShowNode(RenPyNode):
  # imspec: list[str]
  # atl
  imspec : OpOperand[StringListLiteral]
  atl : OpOperand[RenPyASMNode] # at block
  body : Block # only for ATL
  behind : OpOperand[StringLiteral] # 0-N 个图片名

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
  imspec : OpOperand[StringListLiteral]
  layer : OpOperand[StringLiteral]
  atl : OpOperand[RenPyASMNode]
  body : Block # only for ATL

@irdataop.IROperationDataclass
class RenPyHideNode(RenPyNode):
  # 'imspec' : list[str]
  imspec : OpOperand[StringListLiteral]

@irdataop.IROperationDataclass
class RenPyWithNode(RenPyNode):
  # expr : str
  # paired: 暂时不管
  expr : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class RenPyCallNode(RenPyNode):
  # label : str
  # arguments: 暂时不管
  # expression : bool, 决定 label 是否是一个表达式
  label : OpOperand[StringLiteral]
  is_expr : OpOperand[BoolLiteral] # label 是否是表达式

@irdataop.IROperationDataclass
class RenPyReturnNode(RenPyNode):
  # expr : str
  expr : OpOperand[StringLiteral]

@irdataop.IROperationDataclass
class RenPyMenuItemNode(RenPyNode):
  # 用于 menu 命令
  # "<label>" (<arguments>) if <condition>:
  #    <body>
  label : OpOperand[TextLiteral]
  condition : OpOperand[StringLiteral]
  arguments : OpOperand[StringLiteral]
  body : Block

@irdataop.IROperationDataclass
class RenPyMenuNode(RenPyNode):
  # https://www.renpy.org/doc/html/menus.html
  # items : list[tuple[label : str, condition : expr, block]]
  # set : str (执行选单时如果某项的标题已在 set 中存在，则该选项不会出现。用这个来实现“排除选项”的功能)
  # with_: with 从句, 暂时不管
  # has_caption: bool, 暂时不管
  menuset : OpOperand[StringLiteral]
  arguments : OpOperand[StringLiteral]
  items : Block # 里面应该都是 RenPyMenuItemNode

@irdataop.IROperationDataclass
class RenPyJumpNode(RenPyNode):
  # target : str
  # expression : bool, target是否是表达式
  target : OpOperand[StringLiteral]
  is_expr : OpOperand[BoolLiteral] # target是否是表达式

@irdataop.IROperationDataclass
class RenPyPassNode(RenPyNode):
  pass

@irdataop.IROperationDataclass
class RenPyCondBodyPair(RenPyNode):
  # 用于 if 和 while
  condition : OpOperand[StringLiteral]
  body : Block


@irdataop.IROperationDataclass
class RenPyWhileNode(RenPyCondBodyPair):
  # condition : bool expr
  # block
  pass

@irdataop.IROperationDataclass
class RenPyIfNode(RenPyNode):
  # entries : list[tuple[condition : bool expr, block]]
  entries : Block # 里面应该是一串 RenPyCondBodyPair, 按照判断顺序排列



@irdataop.IROperationDataclass
class RenPyDefaultNode(RenPyNode):
  # 用来给变量做声明、赋初值
  # store : str = 'store'
  # varname : str
  # expr
  store : OpOperand[StringLiteral]
  varname : OpOperand[StringLiteral]
  expr : OpOperand[StringLiteral]
  body : Block

# 其他像 Screen 什么的先不做

@irdataop.IROperationDataclass
class RenPyFileAssetOp(Symbol):
  ref : OpOperand

  def get_asset_value(self) -> Value:
    return self.ref.get()

  @staticmethod
  def create(context : Context, assetref : Value, path : str, loc : Location | None = None):
    return RenPyFileAssetOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, ref=assetref, name=path, loc=loc)

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
  def visitRenPyTransformNode(self, v : RenPyTransformNode):
    return self.visitChildren(v)
  def visitRenPyShowNode(self, v : RenPyShowNode):
    return self.visitChildren(v)
  def visitRenPySceneNode(self, v : RenPySceneNode):
    return self.visitChildren(v)
  def visitRenPyWithNode(self, v : RenPyWithNode):
    return self.visitChildren(v)
  def visitRenPyHideNode(self, v : RenPyHideNode):
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

