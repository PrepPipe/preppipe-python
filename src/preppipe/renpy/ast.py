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

class RenPyNode(Operation):
  # 代表一个 AST 节点的基类，对应 renpy 的 renpy/ast.py
  pass

@irdataop.IROperationDataclassWithValue(VoidType)
class RenPyASMNode(RenPyNode, Value):
  asm : OpOperand[StringListLiteral] # 带一个 StringListLiteral，每行一个字符串，行首空格保留（只会有空格，RenPy不支持Tab缩进），行末尾没有\r\n这种EOL

  @staticmethod
  def create(context : Context, asm : StringLiteral | StringListLiteral, name : str = '', loc : Location | None = None) -> RenPyASMNode:
    if isinstance(asm, StringLiteral):
      asm = StringListLiteral.get(context, (asm,))
    return RenPyASMNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, asm=asm, name=name, loc=loc)

class RenPySayNode(RenPyNode):
  #'who' 发言者
  #'what' 发言内容
  # 'with_' with 从句
  # 'interact', bool, 是否等待玩家点击
  # 'attributes', 执行后持久施加给角色的属性
  # 'temporary_attributes', 只在该发言时施加给角色的属性
  # 'identifier',发言的ID，用于与语音绑定等
  # 'arguments' 忽略
  # 'rollback', 忽略
  # <who> [<attribute>] [@ <temporary attribute>] <what> [noninteract] [id <identifier>] [with <with_>]
  pass

class RenPyInitNode(RenPyNode):
  # RenPy 的 init 块
  # 除了优先级外基本上只有个 body
  # priority : int
  # body : region
  pass

class RenPyLabelNode(RenPyNode):
  # 主文章：RenPy Labels & Control Flow
  # https://www.renpy.org/doc/html/label.html#labels-control-flow
  # hide: 忽略
  #name : str
  #parameters: RenPyNode
  pass

class RenPyPythonNode(RenPyNode):
  # 普通的内嵌 Python 代码块
  # code : RenPyPyCodeObject
  # hide : bool # 是否使用局部词典、避免污染上层环境的变量词典
  # store : str = 'store' # 使用哪个 store 对象来存值，暂不支持
  pass

class RenPyEarlyPythonNode(RenPyPythonNode):
  pass

class RenPyImageNode(RenPyNode):
  #name : str
  #displayable : str # atl or PyCode
  pass

class RenPyTransformNode(RenPyNode):
  # store : str = 'store'
  # name : str
  # atl : ATL code block
  # parameters : 应该表述为类似 inspect.signature 的对象，
  pass

class RenPyShowNode(RenPyNode):
  # imspec: list[str]
  # atl
  pass

class RenPyShowLayerNode(RenPyNode):
  # 可以暂时不做
  # layer : str
  # at_list : list[str]
  # atl
  pass

class RenPyCameraNode(RenPyNode):
  # 语义和 ShowLayer 有细微差别，其他完全一样
  # 可以暂时不做
  # layer : str
  # at_list : list[str]
  # atl
  pass

class RenPySceneNode(RenPyNode):
  # 'imspec' : list[str]
  # 'layer' : str
  # 'atl',
  pass

class RenPyHideNode(RenPyNode):
  # 'imspec' : list[str]
  pass

class RenPyWithNode(RenPyNode):
  # expr : str
  # paired: 暂时不管
  pass

class RenPyCallNode(RenPyNode):
  # label : str
  # arguments: 暂时不管
  # expression : bool, 决定 label 是否是一个表达式
  pass

class RenPyReturnNode(RenPyNode):
  # expr : str
  pass

class RenPyMenuNode(RenPyNode):
  # https://www.renpy.org/doc/html/menus.html
  # items : list[tuple[label : str, condition : expr, block]]
  # set : str (执行选单时如果某项的标题已在 set 中存在，则该选项不会出现。用这个来实现“排除选项”的功能)
  # with_: with 从句
  # has_caption: bool, 暂时不管
  # arguments, item_arguments: 暂时不管
  pass

class RenPyJumpNode(RenPyNode):
  # target : str
  # expression : bool, target是否是表达式
  pass

class RenPyPassNode(RenPyNode):
  pass

class RenPyWhileNode(RenPyNode):
  # condition : bool expr
  # block
  pass

class RenPyIfNode(RenPyNode):
  # entries : list[tuple[condition : bool expr, block]]
  pass

# TODO UserStatement, PostUserStatement


@irdataop.IROperationDataclass
class RenPyCharacterExpr(RenPyNode):
  kind      : OpOperand[StringLiteral] # str （可以指定另一个 Character 并获取默认值，或者指定 adv / nvl）
  image     : OpOperand[StringLiteral] # str (头像图片)
  voicetag  : OpOperand[StringLiteral] # str (voice_tag)
  what_prefix : OpOperand[StringLiteral]
  what_suffix : OpOperand[StringLiteral]
  who_prefix  : OpOperand[StringLiteral]
  who_suffix  : OpOperand[StringLiteral]
  dynamic   : OpOperand[RenPyASMNode] # 取一个从 RenPyASMNode 来的值
  ondition  : OpOperand[RenPyASMNode] # 取一个从 RenPyASMNode 来的值
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


class RenPyDefineNode(RenPyNode):
  # 用来定义像角色、图片等信息
  # https://www.renpy.org/doc/html/python.html#define-statement
  # store : str = 'store'
  # varname : str
  # operator : enum: '=', '+=', '|='
  # expr : RenPyCharacterExpr / RenPyImageExpr / RenPyASMNode
  pass

class RenPyDefaultNode(RenPyNode):
  # 用来给变量做声明、赋初值
  # store : str = 'store'
  # varname : str
  # expr
  pass

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

  @staticmethod
  def create(context : Context) -> RenPyModel:
    return RenPyModel(init_mode=IRObjectInitMode.CONSTRUCT, context=context)
