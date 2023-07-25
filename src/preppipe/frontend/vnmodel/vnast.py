# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import enum
import typing

from preppipe.irbase import IRJsonExporter, IRJsonImporter

from ...irbase import *
from ...irdataop import *
from ..commandsyntaxparser import *
from ...vnmodel import *

@IROperationDataclass
class VNASTNodeBase(Operation):
  # 该结点是否只能出现在函数内
  TRAIT_FUNCTION_CONTEXT_ONLY : typing.ClassVar[bool] = True

  def get_short_str(self, indent : int = 0) -> str:
    return str(self)

  def accept(self, visitor):
    return getattr(visitor, 'visit' + type(self).__name__)(self)

  @staticmethod
  def get_target_str(node : Operation, indent : int = 0) -> str:
    if isinstance(node, VNASTNodeBase):
      return node.get_short_str(indent)
    return str(node)

@IRWrappedStatelessClassJsonName("vnast_say_type_e")
class VNASTSayNodeType(enum.Enum):
  TYPE_NARRATE = enum.auto() # 没有发言者、没有引号的发言内容
  TYPE_QUOTED  = enum.auto() # 没有发言者但内容被括弧括起来的内容
  TYPE_FULL    = enum.auto() # 有发言者的内容
  TYPE_SPECIAL = enum.auto() # 类似黑屏居中白字的效果 (其实是暂不支持。。。)

@IROperationDataclass
class VNASTSayNode(VNASTNodeBase):
  # 代表一个发言内容
  nodetype : OpOperand[EnumLiteral[VNASTSayNodeType]]
  content : OpOperand # StringLiteral | TextFragmentLiteral
  expression : OpOperand[StringLiteral] # 发言者状态、表情；可能不止一个字符串
  sayer : OpOperand[StringLiteral] # 发言者
  embed_voice : OpOperand[AudioAssetData] # 如果有嵌语音的话放这里

  # 在一些特殊情况下，我们可能会错误理解文本内容
  # 比如在长发言模式下：
  #     今天我们在此向大家介绍新项目：语涵编译器。
  # 有可能被理解为一个叫“今天我们在此向大家介绍新项目”的角色说了“语涵编译器”这样一句话
  # 这时会需要读取原始内容
  raw_content : OpOperand # StringLiteral | TextFragmentLiteral

  def get_short_str(self, indent : int = 0) -> str:
    result = 'Say ' + self.nodetype.get().value.name[5:]
    has_sayer_or_expr = False
    if sayer := self.sayer.try_get_value():
      result += ' ' + sayer.get_string()
      has_sayer_or_expr = True
    if self.expression.get_num_operands() > 0:
      result += ' (' + ','.join([u.value.get_string() for u in self.expression.operanduses()]) + ')'
      has_sayer_or_expr = True

    if has_sayer_or_expr:
      result += ':'
    result += ' ' + ''.join([str(u.value) for u in self.content.operanduses()])
    return result

  @staticmethod
  def create(context : Context, nodetype : VNASTSayNodeType, content : typing.Iterable[Value], expression : typing.Iterable[StringLiteral] | StringLiteral | str | None = None, raw_content : typing.Iterable[Value] | None = None, sayer : str | None = None, name : str = '', loc : Location | None = None):
    return VNASTSayNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc, nodetype=nodetype, content=content, expression=expression, raw_content=raw_content, sayer=sayer)

# ----------------------------------------------------------
# 该模式下发言者  |  <内容>  |  “<内容>”    |  角色：“<内容>”
# ----------------------------------------------------------
# 默认模式       |   旁白   | 最后说话的人   |   指定角色
# ----------------------------------------------------------
# 长发言模式     |  给定者  |    给定者      |   指定角色
# ----------------------------------------------------------
# 交替模式       |   旁白   | 按次序排列的人 |指定角色，修正说话者
# ----------------------------------------------------------

@IRWrappedStatelessClassJsonName("vnast_say_mode_e")
class VNASTSayMode(enum.Enum):
  MODE_DEFAULT = 0
  MODE_LONG_SPEECH = enum.auto()
  MODE_INTERLEAVED = enum.auto()

@IROperationDataclass
class VNASTSayModeChangeNode(VNASTNodeBase):
  target_mode : OpOperand[EnumLiteral[VNASTSayMode]]
  specified_sayers : OpOperand[StringLiteral]

  # 该结点可以放在函数外
  TRAIT_FUNCTION_CONTEXT_ONLY : typing.ClassVar[bool] = False

  # 默认模式不给定说话者
  # 长发言模式如果不给定说话者，则取最后一个说话的人；如果有歧义（比如这在一个基本块的开始，之前最后发言的角色不是同一人）则报错
  # 交替发言模式应有至少两个给定的说话者

  def get_short_str(self, indent : int = 0) -> str:
    return 'SayModeChange ' + self.target_mode.get().value.name[5:] + ' ' + ','.join([u.value.get_string() for u in self.specified_sayers.operanduses()])

  @staticmethod
  def create(context : Context, target_mode : VNASTSayMode, specified_sayers : typing.Iterable[StringLiteral] | None = None):
    return VNASTSayModeChangeNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, target_mode=target_mode, specified_sayers=specified_sayers)

class VNASTPendingAssetReference(LiteralExpr):
  # 该值仅作为值接在 VNAssetReference 中，不作为单独的结点
  # 为了保存 *args 和 **kwargs, 我们使用如下规则：
  # 1. 第一个参数 (self.get_value_tuple()[0]) 是名称
  # 2. 之后的每两个参数分别代表一个参数：
  #       <None, V> 表示一个值为 V 的按位参数
  #       <Name, V> 表示一个名为 name, 值为 V 的关键字参数
  # 不过大多数时候应该只有一个字符串参数(StringLiteral)

  def construct_init(self, *, context : Context, value_tuple: tuple[StringLiteral, ...], **kwargs) -> None:
    ty = VoidType.get(context)
    return super().construct_init(ty=ty, value_tuple=value_tuple, **kwargs)

  def get_short_str(self, indent : int = 0) -> str:
    return "PendingAssetRef " + self.get_short_str_noheading()

  def get_short_str_noheading(self, indent : int = 0) -> str:
    args : list[Literal] = []
    kwargs : dict[str, Literal] = {}
    result = '"' + self.populate_argdicts(args, kwargs) + '"'
    if len(args) > 0 or len(kwargs) > 0:
      argstrlist = []
      for v in args:
        argstrlist.append(str(v))
      for k, v in kwargs.items():
        argstr = k + '=' + str(v)
        argstrlist.append(argstr)
      result += '(' + ', '.join(argstrlist) + ')'
    return result

  def populate_argdicts(self, args : list[Literal], kwargs : dict[str, Literal]) -> str:
    # 把该结点的args/argnames 转换为 *args, **kwargs 的样式
    # 返回值是转场的名称
    vt = self.get_value_tuple()
    numoperands = len(vt)
    for i in range(1, numoperands, 2):
      name = vt[i]
      v = vt[i+1]
      if name is None:
        args.append(v)
      else:
        assert isinstance(name, StringLiteral)
        namestr = name.get_string()
        kwargs[namestr] = v
    aname = vt[0]
    assert isinstance(aname, StringLiteral)
    return aname.get_string()

  def __str__(self) -> str:
    return self.get_short_str()

  @staticmethod
  def prepare_value_tuple(value : StringLiteral | str, args : list[Literal] | None, kwargs : dict[str, Literal] | None, context : Context) -> tuple[Literal, ...]:
    if isinstance(value, str):
      value = StringLiteral.get(value, context)
    valuelist : list = [value]
    if args is not None:
      for a in args:
        valuelist.append(None)
        valuelist.append(a)
    if kwargs is not None:
      for k, v in kwargs.items():
        valuelist.append(StringLiteral.get(k, context))
        valuelist.append(v)
    return tuple(valuelist)

  @staticmethod
  def get(value : StringLiteral | str, args : list[Literal] | None, kwargs : dict[str, Literal] | None, context : Context):
    return VNASTPendingAssetReference._get_literalexpr_impl(VNASTPendingAssetReference.prepare_value_tuple(value, args, kwargs, context), context)


@IRWrappedStatelessClassJsonName("vnast_asset_intendop_e")
class VNASTAssetIntendedOperation(enum.Enum):
  OP_PUT = 0,
  OP_CREATE = enum.auto()
  OP_REMOVE = enum.auto()

@IRWrappedStatelessClassJsonName("vnast_asset_kind_e")
class VNASTAssetKind(enum.Enum):
  KIND_IMAGE = 0
  KIND_AUDIO = enum.auto()
  KIND_EFFECT = enum.auto()
  KIND_VIDEO = enum.auto()

@IROperationDataclass
class VNASTAssetReference(VNASTNodeBase):
  # 引用的是什么资源
  kind : OpOperand[EnumLiteral[VNASTAssetKind]]

  # 引用该资源是想做什么
  operation : OpOperand[EnumLiteral[VNASTAssetIntendedOperation]]

  # 资源本体
  asset : OpOperand # VNASTPendingAssetReference | AssetData

  # 如果图形等内容前、后跟了一段文字，尝试把文字内容理解为对资源的命名
  # 如 ['图1','视觉小说的大致制作过程与游戏框架']
  # 每段都是一个 StringLiteral
  descriptions : OpOperand[StringLiteral]

  transition : OpOperand # EnumLiteral[VNDefaultTransitionType] | ...

  def get_short_str(self, indent : int = 0) -> str:
    return 'AssetRef<' + self.kind.get().value.name[5:] + '> ' + self.operation.get().value.name[3:] + ' ' + self.get_target_str(self.asset.get(), indent) + ' [' + ','.join([ '"' + u.value.get_string() + '"' for u in self.descriptions.operanduses()]) + ']'

  @staticmethod
  def create(context : Context, kind : VNASTAssetKind, operation : VNASTAssetIntendedOperation, asset : VNASTPendingAssetReference | AssetData, transition : Value | None, name : str = '', loc : Location = None):
    return VNASTAssetReference(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind=kind, operation=operation, asset=asset, transition=transition, name=name, loc=loc)

@IROperationDataclass
class VNASTSetBackgroundMusicNode(VNASTNodeBase):
  # 该结点不会在 VNASTTransitionNode 之下，因为它不需要和其他命令进行同步
  # 即使以后加淡入淡出也是这样
  bgm : OpOperand # VNASTPendingAssetReference | AudioAssetData
  transition : OpOperand # EnumLiteral[VNDefaultTransitionType] | ...

  @staticmethod
  def create(context : Context, bgm : Value, transition : Value | None, name : str = '', loc : Location | None = None):
    return VNASTSetBackgroundMusicNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, bgm=bgm, transition=transition, name=name, loc=loc)

@IROperationDataclass
class VNASTAssetDeclSymbol(Symbol):
  # 我们使用声明的名称来作为这个 VNASTAssetDeclSymbol 的名称
  kind : OpOperand[EnumLiteral[VNASTAssetKind]]
  asset : OpOperand # 实际的值

  def get_short_str(self, indent : int = 0) -> str:
    return 'AssetDecl ' + self.kind.get().value.name + str(self.asset.get())

  @staticmethod
  def create(context : Context, kind : VNASTAssetKind, asset : Value, name : str, loc : Location):
    return VNASTAssetDeclSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind=kind, asset=asset, name=name, loc=loc)

@IROperationDataclass
class VNASTASMNode(VNASTNodeBase):
  backend : OpOperand[StringLiteral]
  body : OpOperand[StringListLiteral] # 即使是单行也是 StringListLiteral

  # 该结点可以放在函数外
  TRAIT_FUNCTION_CONTEXT_ONLY : typing.ClassVar[bool] = False

  def get_short_str(self, indent : int = 0) -> str:
    result = "ASM"
    if backend := self.backend.try_get_value():
      result += '<' + backend.get_string() + '>'
    for u in self.body.get().operanduses():
      s : str = u.value.get_string()
      result += '\n' + '  '*(indent+1) + s
    return result

  def create(context : Context, body : StringListLiteral, backend : StringLiteral | None, name : str = '', loc : Location | None = None):
    if body:
      assert isinstance(body, StringListLiteral)
    if backend:
      assert isinstance(backend, StringLiteral)
    return VNASTASMNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, body=body, backend=backend, name=name, loc=loc)

@IROperationDataclass
class VNASTNamespaceSwitchableValueSymbol(Symbol):
  # 我们使用命名空间的字符串作为 OpOperand 的名称
  # 根命名空间('/')除外，放在 defaultvalue 里面
  defaultvalue : OpOperand

  def get_value(self, ns : str | tuple[str, ...]) -> Value:
    if ns == '/' or ns == ():
      return self.defaultvalue.get()

    if isinstance(ns, str):
      nstuple = VNNamespace.expand_namespace_str(ns)
    elif isinstance(ns, tuple):
      nstuple = ns
      ns = VNNamespace.stringize_namespace_path(nstuple)
    else:
      raise RuntimeError('Should not happen')

    while len(nstuple) > 1 and self.try_get_operand_inst(ns) is None:
      nstuple = nstuple[:-1]
      ns = VNNamespace.stringize_namespace_path(nstuple)

    if operand := self.try_get_operand_inst(ns):
      return operand.get()
    return self.defaultvalue.get()

  def set_value(self, ns : str, v : Value):
    if ns != '/':
      if operand := self.try_get_operand_inst(ns):
        operand.set_operand(0, v)
      else:
        self._add_operand_with_value(ns, v)
    else:
      self.defaultvalue.set_operand(0, v)

  def get_short_str(self, indent : int = 0) -> str:
    result = 'NSSwitchable ' + str(self.defaultvalue.get())
    for ns, operand in self.operands.items():
      if operand is self.defaultvalue:
        continue
      result += '\n' + '  '*(indent+1) + '"' + ns + '": ' + str(operand.get())
    return result

  @staticmethod
  def create(context : Context, name : str, defaultvalue : Value, loc : Location | None = None):
    return VNASTNamespaceSwitchableValueSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, defaultvalue=defaultvalue, name=name, loc=loc)

@IROperationDataclass
class VNASTSceneSwitchNode(VNASTNodeBase):
  destscene : OpOperand[StringLiteral]
  states : OpOperand[StringLiteral] # 场景状态

  def get_short_str(self, indent : int = 0) -> str:
    result = 'SceneSwitch '
    if destscene := self.destscene.try_get_value():
      result += destscene.get_string()
    else:
      result += '<Current>'
    if self.states.get_num_operands() > 0:
      statelist = []
      for u in self.states.operanduses():
        statelist.append(u.value.get_string())
      result += '(' + ', '.join(statelist) + ')'
    return result

  def create(context : Context, destscene : StringLiteral | str | None, states : typing.Iterable[StringLiteral] | None):
    return VNASTSceneSwitchNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, destscene=destscene, states=states)

@IROperationDataclass
class VNASTCharacterEntryNode(VNASTNodeBase):
  character : OpOperand[StringLiteral] # 角色名称
  states : OpOperand[StringLiteral] # 角色入场时的状态（如果有的话）

  def get_short_str(self, indent : int = 0) -> str:
    result = 'CharacterEntry ' + self.character.get().get_string()
    if self.states.get_num_operands() > 0:
      result += ' (' + ', '.join([u.value for u in self.states.operanduses()]) + ')'
    return result

  @staticmethod
  def create(context : Context, character : StringLiteral | str, states : typing.Iterable[StringLiteral] | None = None, name : str = '', loc : Location | None = None):
    return VNASTCharacterEntryNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, character=character, states=states, name=name, loc=loc)

@IROperationDataclass
class VNASTCharacterStateChangeNode(VNASTNodeBase):
  character : OpOperand[StringLiteral] # 如果需要根据环境求解的话可能没有值
  deststate : OpOperand[StringLiteral] # 可能不止一个值

  def get_short_str(self, indent : int = 0) -> str:
    result = 'StateChange '
    if ch := self.character.try_get_value():
      result += ch.get_string()
    else:
      result += '<default>'
    result += ': [' + ','.join([u.value.get_string() for u in self.deststate.operanduses()]) + ']'
    return result

  @staticmethod
  def create(context : Context, character : StringLiteral | str | None = None, deststate : typing.Iterable[StringLiteral] | None = None, name : str = '', loc : Location | None = None):
    return VNASTCharacterStateChangeNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, character=character, deststate=deststate)

@IROperationDataclass
class VNASTCharacterExitNode(VNASTNodeBase):
  character : OpOperand[StringLiteral] # 角色名称

  def get_short_str(self, indent : int = 0) -> str:
    return 'CharacterExit ' + self.character.get().get_string()

  @staticmethod
  def create(context : Context, character : StringLiteral | str, name : str = '', loc : Location | None = None):
    return VNASTCharacterExitNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, character=character, name=name, loc=loc)

@IROperationDataclass
class VNASTCodegenRegion(VNASTNodeBase):
  body : Block

  @staticmethod
  def get_short_str_for_codeblock(body : Block, indent : int = 0) -> str:
    if body.body.empty:
      return '[]'
    result = '['
    for op in body.body:
      result += '\n' + '  '*(indent+1) + VNASTNodeBase.get_target_str(op, indent+1)
    result += '\n' + '  '*indent + ']'
    return result

  def get_short_str(self, indent : int = 0) -> str:
    return "Codegen Region: " + self.get_short_str_for_codeblock(self.body, indent)

  def push_back(self, node : VNASTNodeBase | MetadataOp):
    self.body.push_back(node)

  @staticmethod
  def create(context : Context, name : str = '', loc : Location | None = None):
    return VNASTCodegenRegion(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IROperationDataclass
class VNASTFunction(VNASTCodegenRegion):
  # 代表一个函数

  # 如果在该函数定义前就有错误、警告内容，我们把这些东西放在这里
  prebody_md : Block

  def get_short_str(self, indent : int = 0) -> str:
    result = 'Function "' + self.name + '"'
    if len(self.prebody_md.body) > 0:
      result += '\n' + '  '*indent + 'prebody: ' + self.get_short_str_for_codeblock(self.prebody_md)
    result += '\n' + '  '*indent + 'body: ' + self.get_short_str_for_codeblock(self.body)
    return result

  @staticmethod
  def create(context : Context, name : str, loc : Location):
    return VNASTFunction(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IROperationDataclass
class VNASTTransitionNode(VNASTCodegenRegion):
  # 转场结点，用来包裹所有需要转场效果的事件（角色入场、退场，场景切换等）
  # 对于这些需要转场效果的事件的类，即使某些实例没有转场效果、立即发生，我们也用这个结点
  # 一些从来不会需要转场效果的事件（如角色状态切换）则不需要这个结点
  # 如果有多个子节点，则所有子节点的转场将同时进行
  # 由于转场效果的解析会在生成 VNAST 之后才会发生，创建该节点时我们需要尽可能地保留原来的参数
  # 为了同时保留 args 和 kwargs，如果转场表达式有 a 个 arg 和 k 个 kwarg, 那么：
  # 1. transition_args 有 (a+k) 项，前 a 项是 args 的值，后 k 项是 kwargs 的值
  # 2. transition_argnames 有 k 项，第 i 项对应第 i 个 kwargs 的值（即 transition_args 中第 a+i 项）
  # 这个结点只有在源文档中提供了转场时才有用，没有提供转场的话仍然依赖内部包裹的事件的默认转场

  transition_name : OpOperand[StringLiteral] # 转场效果的名称（如果有的话）
  transition_args : OpOperand[Literal] # 转场效果的所有参数
  transition_argnames : OpOperand[StringLiteral] # 如果对应的转场效果参数提供了名称（即它是 kwarg 之一），这里我们放对应的名称

  def get_short_str(self, indent : int = 0) -> str:
    result = 'Transition '
    if transition := self.transition_name.try_get_value():
      result += '"' + transition.get_string() + '"'
      if self.transition_args.get_num_operands() > 0:
        k = self.transition_argnames.get_num_operands()
        s = self.transition_args.get_num_operands()
        a = s-k
        argstrlist = []
        for i in range(0, a):
          arg = self.transition_args.get_operand(i)
          argstrlist.append(str(arg))
        for i in range(0, k):
          arg = self.transition_args.get_operand(i+a)
          argname = self.transition_argnames.get_operand(i)
          argstr = argname.get_string() + '=' + str(arg)
          argstrlist.append(argstr)
        result += '(' + ', '.join(argstrlist) + ')'
    else:
      result += '<None>'
    result += ' : ' + VNASTCodegenRegion.get_short_str_for_codeblock(self.body, indent+1)
    return result

  def populate_argdicts(self, args : list[Literal], kwargs : dict[str, Literal]) -> str:
    # 把该结点的args/argnames 转换为 *args, **kwargs 的样式
    # 返回值是转场的名称
    s = self.transition_args.get_num_operands()
    k = self.transition_argnames.get_num_operands()
    a = s-k
    for i in range(0, a):
      arg = self.transition_args.get_operand(i)
      args.append(arg)
    for i in range(0, k):
      arg = self.transition_args.get_operand(i+a)
      argname = self.transition_argnames.get_operand(i)
      kwargs[argname.get_string()] = arg
    if v := self.transition_name.try_get_value():
      return v.get_string()
    return ''

  def add_arg(self, arg : Literal):
    assert isinstance(arg, Literal)
    assert self.transition_argnames.get_num_operands() == 0
    self.transition_args.add_operand(arg)

  def add_kwarg(self, name : StringLiteral, value : Literal):
    assert isinstance(name, StringLiteral)
    assert isinstance(value, Literal)
    self.transition_args.add_operand(value)
    self.transition_argnames.add_operand(name)

  @staticmethod
  def create(context : Context, transition_name : StringLiteral | str | None = None, name : str = '', loc : Location | None = None):
    return VNASTTransitionNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, transition_name=transition_name, name=name, loc=loc)

@IROperationDataclass
class VNASTConditionalExecutionNode(VNASTNodeBase):
  # 条件分支
  conditions : OpOperand[StringLiteral]
  body: Block # 里面全是 VNASTCodegenRegion, conditions 里有多少个条件字符串，这里就有多少个 VNASTCodegenRegion

  def get_short_str(self, indent : int = 0) -> str:
    result = 'ConditionalExecution: ' + str(self.conditions.get_num_operands())
    operandindex = 0
    for op in self.body.body:
      result += '\n' + '  '*indent + 'condition "' + self.conditions.get_operand(operandindex).get_string() + '": '
      result += self.get_target_str(op, indent+1)
      operandindex += 1
    return result

@IROperationDataclass
class VNASTMenuNode(VNASTNodeBase):
  # 选单
  # 我们给每个选项一个纯数字名字的 OpOperand, 里面都是 StringLiteral | TextFragmentLiteral
  body: Block # 里面全是 VNASTCodegenRegion,

  # 如果块结束时没有控制流指令，块结束时应该发生什么
  # 如果什么都没有的话就是退出
  ATTR_FINISH_ACTION : typing.ClassVar[str] = 'finish_action'
  ATTR_FINISH_ACTION_LOOP : typing.ClassVar[str] = 'loop'

  def get_short_str(self, indent : int = 0) -> str:
    result = 'Menu '
    if action := self.get_attr(self.ATTR_FINISH_ACTION):
      result += action + ' '
    result += '"' + self.name + '":'
    operandindex = 0
    for op in self.body.body:
      assert isinstance(op, VNASTCodegenRegion)
      cond = self.get_operand_inst(str(operandindex))
      result += '\n' + '  '*(indent+1) + '"' + ''.join([str(u.value) for u in cond.operanduses()]) + '": ' + VNASTCodegenRegion.get_short_str_for_codeblock(op.body, indent+1)
      operandindex += 1
    return result

  def add_option(self, text : typing.Iterable[Value], loc : Location | None = None) -> VNASTCodegenRegion:
    index=0
    while self.try_get_operand_inst(str(index)) is not None:
      index += 1
    name = str(index)
    self._add_operand_with_value(name, text)
    r = VNASTCodegenRegion.create(self.context, name=name, loc=loc)
    self.body.push_back(r)
    return r

  @staticmethod
  def create(context : Context, name : str = '', loc : Location | None = None):
    return VNASTMenuNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IROperationDataclass
class VNASTBreakNode(VNASTNodeBase):
  # 用来跳出循环，现在只有选单会有循环

  def get_short_str(self, indent : int = 0) -> str:
    return 'Break'

  @staticmethod
  def create(context : Context, name : str = '', loc : Location | None = None):
    return VNASTBreakNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IROperationDataclass
class VNASTLabelNode(VNASTNodeBase):
  # 用来提供基于标签的跳转
  labelname : OpOperand[StringLiteral]

  def get_short_str(self, indent : int = 0) -> str:
    return '[Label "' + self.labelname.get().get_string() + '"]'

  @staticmethod
  def create(context : Context, labelname : StringLiteral | str):
    if isinstance(labelname, str):
      assert len(labelname) > 0
    elif isinstance(labelname, StringLiteral):
      assert len(labelname.get_string()) > 0
    return VNASTLabelNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, labelname=labelname)

@IROperationDataclass
class VNASTJumpNode(VNASTNodeBase):
  # 跳转到指定标签，不能到另一个函数
  target_label : OpOperand[StringLiteral]

  def get_short_str(self, indent : int = 0) -> str:
    return 'Jump "' + self.target_label.get().get_string() + '"'

  @staticmethod
  def create(context : Context, target : StringLiteral | str):
    if isinstance(target, str):
      assert len(target) > 0
    elif isinstance(target, StringLiteral):
      assert len(target.get_string()) > 0
    return VNASTJumpNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, target_label=target)

@IROperationDataclass
class VNASTCallNode(VNASTNodeBase):
  callee : OpOperand[StringLiteral]

  ATTR_TAILCALL : typing.ClassVar[str] = 'tailcall'

  def is_tail_call(self) -> bool:
    return self.get_attr(self.ATTR_TAILCALL) is True

  def get_short_str(self, indent : int = 0) -> str:
    result = 'TailCall' if self.is_tail_call() else 'Call'
    result += ' "' + self.callee.get().get_string() + '"'
    return result

  @staticmethod
  def create(context : Context, callee : StringLiteral | str, is_tail_call : bool = False):
    result = VNASTCallNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, callee=callee)
    if is_tail_call:
      result.set_attr(VNASTCallNode.ATTR_TAILCALL, True)
    return result

@IROperationDataclass
class VNASTReturnNode(VNASTNodeBase):
  @staticmethod
  def create(context : Context, name : str = '', loc : Location | None = None):
    return VNASTReturnNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IRWrappedStatelessClassJsonName("vnast_say_device_kind_e")
class VNASTSayDeviceKind(enum.Enum):
  KIND_ADV = enum.auto()
  KIND_NVL = enum.auto()

@IROperationDataclass
class VNASTChangeDefaultDeviceNode(VNASTNodeBase):
  destmode : OpOperand[EnumLiteral[VNASTSayDeviceKind]]

  # 该结点可以放在函数外
  TRAIT_FUNCTION_CONTEXT_ONLY : typing.ClassVar[bool] = False

@IROperationDataclass
class VNASTCharacterSayInfoSymbol(Symbol):
  # 使用继承的 name 作为显示的名称
  displayname_expr : OpOperand[StringLiteral] # 如果是表达式的话用这里的值（暂不支持）
  namestyle : OpOperand[TextStyleLiteral] # 大概只会用 TextColor 不过还是预留其他的
  saytextstyle : OpOperand[TextStyleLiteral]

  def copy_from(self, src):
    assert isinstance(src, VNASTCharacterSayInfoSymbol)
    # 照抄除了显示名和别名外的其他内容
    if src is self:
      return

    if v := src.namestyle.try_get_value():
      self.namestyle.set_operand(0, v)
    else:
      self.namestyle.drop_all_uses()

    if v := src.saytextstyle.try_get_value():
      self.saytextstyle.set_operand(0, v)
    else:
      self.saytextstyle.drop_all_uses()

  @staticmethod
  def create(context : Context, name : str, loc : Location | None = None):
    return VNASTCharacterSayInfoSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IROperationDataclass
class VNASTCharacterSymbol(Symbol):
  aliases : OpOperand[StringLiteral]
  sayinfo : SymbolTableRegion[VNASTCharacterSayInfoSymbol] # 所有发言表现的信息
  sprites : SymbolTableRegion[VNASTNamespaceSwitchableValueSymbol] # 名称是所有状态字符串用逗号','串起来的结果
  sideimages : SymbolTableRegion[VNASTNamespaceSwitchableValueSymbol]

  @staticmethod
  def create(context : Context, name : str, loc : Location | None = None):
    return VNASTCharacterSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

class VNASTVariableDeclSymbol(Symbol):
  # 变量的名字取自 Symbol 的名字
  vtype : OpOperand[StringLiteral]
  initializer : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, vtype : StringLiteral | str, initializer : StringLiteral | str, name : str, loc : Location | None = None):
    return VNASTVariableDeclSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, vtype=vtype, initializer=initializer, name=name, loc=loc)

@IROperationDataclass
class VNASTCharacterTempSayAttrNode(VNASTNodeBase):
  # 我们用这个结点来表示，接下来的内容里，
  # 某个角色的显示名称或发言显示方式可以变成该结点指定的样式
  # 如果该结点在函数内，则效果持续到函数结束
  # 如果该结点在函数外，则效果持续到文件结束
  # 如果多个角色同时拥有相同的显示名（比如多个角色都用 ??? 表示），
  # 则需要在状态表达式的第一项中包含角色的真实名字
  # 注意，这里包含的发言属性并没有从角色声明处获得默认值，因为这结点可能不在声明角色的文件里
  # 所以后面处理时需要复制默认值再进行覆盖
  character : OpOperand[StringLiteral] # 角色的真实名字
  sayinfo : SymbolTableRegion[VNASTCharacterSayInfoSymbol] # 大概只会有一个结点

  # 该结点可以放在函数外
  TRAIT_FUNCTION_CONTEXT_ONLY : typing.ClassVar[bool] = False

  @staticmethod
  def create(context : Context, character : StringLiteral | str, name : str = '', loc : Location | None = None):
    return VNASTCharacterTempSayAttrNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, character=character, name=name, loc=loc)

@IROperationDataclass
class VNASTTempAliasNode(VNASTNodeBase):
  # 我们用这个结点表示接下来我们可以使用 alias 中的名字指代 target
  # 该命令本身不影响任何演出因素（包括角色发言属性等），只是作为简化录入的辅助
  alias : OpOperand[StringLiteral]
  target : OpOperand[StringLiteral]

  # 该结点可以放在函数外
  TRAIT_FUNCTION_CONTEXT_ONLY : typing.ClassVar[bool] = False

  @staticmethod
  def create(context : Context, alias : StringLiteral | str, target : StringLiteral | str,  name : str = '', loc : Location | None = None):
    return VNASTTempAliasNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, alias=alias, target=target, name=name, loc=loc)

@IROperationDataclass
class VNASTSceneSymbol(Symbol):
  aliases : OpOperand[StringLiteral]
  backgrounds : SymbolTableRegion[VNASTNamespaceSwitchableValueSymbol] # 名称是所有状态字符串用逗号','串起来的结果

  @staticmethod
  def create(context : Context, name : str, loc : Location | None = None):
    return VNASTSceneSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc)

@IROperationDataclass
class VNASTFileInfo(VNASTNodeBase):
  namespace : OpOperand[StringLiteral] # 无参数表示没有提供（取默认情况），'/'才是根命名空间
  functions : Block # 全是 VNASTFunction
  assetdecls : SymbolTableRegion[VNASTAssetDeclSymbol] # 可以按名查找的资源声明
  characters : SymbolTableRegion[VNASTCharacterSymbol] # 在该文件中正式声明的角色
  variables : SymbolTableRegion[VNASTVariableDeclSymbol] # 在该文件中声明的变量
  scenes : SymbolTableRegion[VNASTSceneSymbol]
  pending_content : Block # VNASTNodeBase | MetadataOp
  # 现在我们把别名直接存储到被起别名的对象上

  def get_short_str(self, indent : int = 0) -> str:
    result = 'File "' + self.name + '"'
    if ns := self.namespace.try_get_value():
      result += ' NS: ' + ns.get_string()

    def dump_table(r : SymbolTableRegion, header : str):
      nonlocal result
      if len(r) > 0:
        result += '\n' + '  '*indent + header + ': ' + str(len(r))
        for symb in r:
          result += '\n' + '  '*(indent+1) + VNASTNodeBase.get_target_str(symb, indent+1)

    dump_table(self.characters, 'Characters')
    dump_table(self.scenes, 'Scenes')
    dump_table(self.assetdecls, 'AssetDecls')
    dump_table(self.variables, 'Variables')

    if len(self.pending_content.body) > 0:
      result += '\n' + '  '*indent + 'PendingContent:' + VNASTCodegenRegion.get_short_str_for_codeblock(self.pending_content, indent+1)
    for func in self.functions.body:
      result += '\n' + '  '*indent + self.get_target_str(func, indent)
    return result

  @staticmethod
  def create(name : str, loc : Location, namespace : StringLiteral | str | None = None):
    return VNASTFileInfo(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc, namespace=namespace)

@IROperationDataclass
class VNAST(Operation):
  screen_resolution : OpOperand[IntTupleLiteral]
  files : Block # VNASTFileInfo

  def get_short_str(self, indent : int = 0) -> str:
    width, height = self.screen_resolution.get().value
    result = 'VNAST [' + str(width) + 'x' + str(height) + '] "' + self.name + '": ' + str(len(self.files.body)) + ' File(s)'
    for f in self.files.body:
      result += '\n' + '  '*(indent+1) + VNASTNodeBase.get_target_str(f, indent+1)
    return result

  @staticmethod
  def create(name : str, screen_resolution : IntTupleLiteral, context : Context):
    return VNAST(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, screen_resolution=screen_resolution)

class UnrecognizedCommandOp(ErrorOp):
  # 基本是从 GeneralCommandOp 那里抄来的
  _head_region : SymbolTableRegion # name + raw_args
  _positionalarg_region : Region # single block, list of values
  _positionalarg_block : Block
  _keywordarg_region : SymbolTableRegion

  def construct_init(self, *, src_op : GeneralCommandOp,  **kwargs) -> None:
    src_head = src_op.get_symbol_table('head')
    src_name_symbol = src_head.get('name')
    assert isinstance(src_name_symbol, CMDValueSymbol)
    assert isinstance(src_name_symbol.value, StringLiteral)
    super().construct_init(error_code='vnparser-unrecognized-command', error_msg=src_name_symbol.value, **kwargs)
    self._head_region = self._add_symbol_table('head')
    self._positionalarg_region = self._add_region('positional_arg')
    self._keywordarg_region = self._add_symbol_table('keyword_arg')
    self._positionalarg_block = self._positionalarg_region.create_block('')

    name_symbol = CMDValueSymbol.create(name='name', loc=src_name_symbol.location, value=src_name_symbol.value)
    self._head_region.add(name_symbol)
    src_rawarg_symbol = src_head.get('rawarg')
    if src_rawarg_symbol is not None:
      assert isinstance(src_rawarg_symbol, CMDValueSymbol)
      rawarg_symbol = CMDValueSymbol.create(name='rawarg', loc=src_rawarg_symbol.location, value=src_rawarg_symbol.value)
      self._head_region.add(rawarg_symbol)
    src_positional_arg = src_op.get_region('positional_arg')
    assert src_positional_arg.get_num_blocks() == 1
    src_positional_arg_block = src_positional_arg.entry_block
    for op in src_positional_arg_block.body:
      assert isinstance(op, CMDPositionalArgOp)
      self._positionalarg_block.push_back(CMDPositionalArgOp.create(name=op.name, loc=op.location, value=op.value))
    src_kwarg = src_op.get_symbol_table('keyword_arg')
    for op in src_kwarg:
      assert isinstance(op, CMDValueSymbol)
      self._keywordarg_region.add(CMDValueSymbol.create(name=op.name, loc=op.location, value=op.value))

  def post_init(self) -> None:
    super().post_init()
    self._head_region = self.get_symbol_table('head')
    self._positionalarg_region = self.get_region('positional_arg')
    self._positionalarg_block = self._positionalarg_region.blocks.front
    self._keywordarg_region = self.get_symbol_table('keyword_arg')

  @staticmethod
  def create(src_op : GeneralCommandOp):
    return UnrecognizedCommandOp(init_mode=IRObjectInitMode.CONSTRUCT, context=src_op.context, src_op=src_op)

class VNASTVisitor:
  def visit(self, node : VNASTNodeBase):
    return node.accept(self)

  def visit_default_handler(self, node : VNASTNodeBase):
    raise NotImplementedError()

  def visitVNASTASMNode(self, node : VNASTASMNode):
    return self.visit_default_handler(node)
  def visitVNASTSayModeChangeNode(self, node : VNASTSayModeChangeNode):
    return self.visit_default_handler(node)
  def visitVNASTSayNode(self, node : VNASTSayNode):
    return self.visit_default_handler(node)
  def visitVNASTAssetReference(self, node : VNASTAssetReference):
    return self.visit_default_handler(node)
  def visitVNASTSetBackgroundMusicNode(self, node : VNASTSetBackgroundMusicNode):
    return self.visit_default_handler(node)
  def visitVNASTSceneSwitchNode(self, node : VNASTSceneSwitchNode):
    return self.visit_default_handler(node)
  def visitVNASTCharacterEntryNode(self, node : VNASTCharacterEntryNode):
    return self.visit_default_handler(node)
  def visitVNASTCharacterStateChangeNode(self, node : VNASTCharacterStateChangeNode):
    return self.visit_default_handler(node)
  def visitVNASTCharacterExitNode(self, node : VNASTCharacterExitNode):
    return self.visit_default_handler(node)
  def visitVNASTCodegenRegion(self, node : VNASTCodegenRegion):
    return self.visit_default_handler(node)
  def visitVNASTConditionalExecutionNode(self, node : VNASTConditionalExecutionNode):
    return self.visit_default_handler(node)
  def visitVNASTMenuNode(self, node : VNASTMenuNode):
    return self.visit_default_handler(node)
  def visitVNASTBreakNode(self, node : VNASTBreakNode):
    return self.visit_default_handler(node)
  def visitVNASTLabelNode(self, node : VNASTLabelNode):
    return self.visit_default_handler(node)
  def visitVNASTJumpNode(self, node : VNASTJumpNode):
    return self.visit_default_handler(node)
  def visitVNASTCallNode(self, node : VNASTCallNode):
    return self.visit_default_handler(node)
  def visitVNASTReturnNode(self, node : VNASTReturnNode):
    return self.visit_default_handler(node)
  def visitVNASTChangeDefaultDeviceNode(self, node : VNASTChangeDefaultDeviceNode):
    return self.visit_default_handler(node)
  def visitVNASTCharacterTempSayAttrNode(self, node : VNASTCharacterTempSayAttrNode):
    return self.visit_default_handler(node)
  def visitVNASTTempAliasNode(self, node : VNASTTempAliasNode):
    return self.visit_default_handler(node)
  def visitVNASTTransitionNode(self, node : VNASTTransitionNode):
    return self.visit_default_handler(node)
  def visitVNASTFunction(self, node : VNASTFunction):
    return self.visit_default_handler(node)
  def visitVNASTFileInfo(self, node : VNASTFileInfo):
    return self.visit_default_handler(node)
