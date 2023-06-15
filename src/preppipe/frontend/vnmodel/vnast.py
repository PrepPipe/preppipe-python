# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import enum
import typing

from ...irbase import *
from ...irdataop import *
from ..commandsyntaxparser import *
from ...vnmodel_v4 import *

@IROperationDataclass
class VNASTNodeBase(Operation):

  def get_short_str(self, indent : int = 0) -> str:
    return str(self)

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
  expression : OpOperand[StringLiteral] # 发言者状态、表情
  sayer : OpOperand[StringLiteral] # 发言者
  embed_voice : OpOperand[AudioAssetData] # 如果有嵌语音的话放这里

  def get_short_str(self, indent : int = 0) -> str:
    result = 'Say ' + self.nodetype.get().value.name[5:]
    has_sayer_or_expr = False
    if sayer := self.sayer.try_get_value():
      result += ' ' + sayer.get_string()
      has_sayer_or_expr = True
    if expr := self.expression.try_get_value():
      result += ' (' + expr.get_string() + ')'
      has_sayer_or_expr = True
    if has_sayer_or_expr:
      result += ':'
    result += ' ' + ''.join([str(u.value) for u in self.content.operanduses()])
    return result

  @staticmethod
  def create(context : Context, nodetype : VNASTSayNodeType, content : typing.Iterable[Value], expression : str | None = None, sayer : str | None = None, name : str = '', loc : Location | None = None):
    return VNASTSayNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc, nodetype=nodetype, content=content, expression=expression, sayer=sayer)

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
class VNSayMode(enum.Enum):
  MODE_DEFAULT = 0
  MODE_LONG_SPEECH = enum.auto()
  MODE_INTERLEAVED = enum.auto()

@IROperationDataclass
class VNSayModeChangeNode(VNASTNodeBase):
  target_mode : OpOperand[EnumLiteral[VNSayMode]]
  specified_sayers : OpOperand[StringLiteral]

  def get_short_str(self, indent : int = 0) -> str:
    return 'SayModeChange ' + self.target_mode.get().value.name[5:] + ' ' + ','.join([u.value.get_string() for u in self.specified_sayers.operanduses()])

class VNASTPendingAssetReference(Literal):
  # 该值仅作为值接在 VNAssetReference 中，不作为单独的结点

  def get_short_str(self, indent : int = 0) -> str:
    return 'PendingAssetRef "' + self.value + '"'

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

  def get_short_str(self, indent : int = 0) -> str:
    return 'AssetRef<' + self.kind.get().value.name[5:] + '> ' + self.operation.get().value.name[3:] + ' ' + self.get_target_str(self.asset.get(), indent) + ' [' + ','.join([ '"' + u.value.get_string() + '"' for u in self.descriptions.operanduses()]) + ']'

  @staticmethod
  def create(context : Context, kind : VNASTAssetKind, operation : VNASTAssetIntendedOperation, asset : VNASTPendingAssetReference | AssetData, name : str = '', loc : Location = None):
    return VNASTAssetReference(init_mode=IRObjectInitMode.CONSTRUCT, context=context, kind=kind, operation=operation, asset=asset, name=name, loc=loc)

@IROperationDataclass
class VNASTASMNode(VNASTNodeBase):
  backend : OpOperand[StringLiteral]
  body : OpOperand[StringListLiteral] # 即使是单行也是 StringListLiteral

  def get_short_str(self, indent : int = 0) -> str:
    result = "ASM"
    if backend := self.backend.try_get_value():
      result += '<' + backend.get_string() + '>'
    for u in self.body.operanduses():
      s : str = u.value.get_string()
      result += '\n' + '  '*(indent+1) + s
    return result

@IROperationDataclass
class VNASTNamespaceSwitchableValueSymbol(Symbol):
  # 我们使用命名空间的字符串作为 OpOperand 的名称
  # 根命名空间('/')除外，放在 defaultvalue 里面
  defaultvalue : OpOperand

  def get_value(self, ns : str) -> Value:
    if ns != '/':
      nstuple = VNNamespace.expand_namespace_str(ns)
      while len(nstuple) > 1 and self.try_get_operand_inst(ns) is None:
        nstuple = nstuple[:-1]
        ns = VNNamespace.stringize_namespace_path(nstuple)
      if operand := self.try_get_operand_inst(ns):
        return operand.get()
    return self.defaultvalue.get()

  def get_short_str(self, indent : int = 0) -> str:
    result = 'NSSwitchable ' + str(self.defaultvalue.get())
    for ns, operand in self.operands.items():
      if operand is self.defaultvalue:
        continue
      result += '\n' + '  '*(indent+1) + '"' + ns + '": ' + str(operand.get())
    return result

@IROperationDataclass
class VNASTSceneSwitchNode(VNASTNodeBase):
  destscene : OpOperand[StringLiteral]

  def get_short_str(self, indent : int = 0) -> str:
    return 'SceneSwitch ' + self.destscene.get().get_string()

@IROperationDataclass
class VNASTCharacterEntryNode(VNASTNodeBase):
  character : OpOperand[StringLiteral]

  def get_short_str(self, indent : int = 0) -> str:
    return 'CharacterEntry ' + self.character.get().get_string()

@IROperationDataclass
class VNASTCharacterStateChangeNode(VNASTNodeBase):
  character : OpOperand[StringLiteral]
  deststate : OpOperand[StringLiteral] # 可能不止一个值

  def get_short_str(self, indent : int = 0) -> str:
    return 'StateChange ' + self.character.get().get_string() + ': ' + ','.join([u.value.get_string() for u in self.deststate.operanduses()])

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

@IROperationDataclass
class VNASTFunction(VNASTCodegenRegion):
  # 代表一个函数

  # 如果在该函数定义前就有错误、警告内容，我们把这些东西放在这里
  prebody_md : Block

  def get_short_str(self, indent : int = 0) -> str:
    result = 'Function "' + self.name + '"'
    if len(self.prebody_md) > 0:
      result += '\n' + '  '*indent + 'prebody: ' + self.get_short_str_for_codeblock(self.prebody_md)
    result += '\n' + '  '*indent + 'body: ' + self.get_short_str_for_codeblock(self.body)
    return result

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

@IROperationDataclass
class VNASTBreakNode(VNASTNodeBase):
  # 用来跳出循环，现在只有选单会有循环

  def get_short_str(self, indent : int = 0) -> str:
    return 'Break'

@IROperationDataclass
class VNASTLabelNode(VNASTNodeBase):
  # 用来提供基于标签的跳转
  labelname : OpOperand[StringLiteral]

@IROperationDataclass
class VNASTJumpNode(VNASTNodeBase):
  # 跳转到指定标签，不能到另一个函数
  target_label : OpOperand[StringLiteral]

@IRWrappedStatelessClassJsonName("vnast_say_device_kind_e")
class VNASTSayDeviceKind(enum.Enum):
  KIND_ADV = enum.auto()
  KIND_NVL = enum.auto()

@IROperationDataclass
class VNASTChangeDefaultDeviceNode(VNASTNodeBase):
  destmode : OpOperand[EnumLiteral[VNASTSayDeviceKind]]

@IROperationDataclass
class VNASTCharacterSayInfoSymbol(Symbol):
  # 使用继承的 name 作为显示的名称
  displayname_expr : OpOperand[StringLiteral] # 如果是表达式的话用这里的值
  aliases : OpOperand[StringLiteral]
  state_tags : OpOperand[StringLiteral] # 当使用这里的状态标签时适用该记录里的信息；很可能不止一个值
  namestyle : OpOperand[TextStyleLiteral] # 大概只会用 TextColor 不过还是预留其他的
  saytextstyle : OpOperand[TextStyleLiteral]

@IROperationDataclass
class VNASTCharacterSymbol(Symbol):
  aliases : OpOperand[StringLiteral]
  namespace : OpOperand[StringLiteral]
  sayinfo : SymbolTableRegion[VNASTCharacterSayInfoSymbol] # 所有发言表现的信息
  sprites : SymbolTableRegion[VNASTNamespaceSwitchableValueSymbol]

@IROperationDataclass
class VNASTSceneSymbol(Symbol):
  aliases : OpOperand[StringLiteral]
  namespace : OpOperand[StringLiteral]

@IROperationDataclass
class VNASTFileInfo(VNASTNodeBase):
  namespace : OpOperand[StringLiteral] # 无参数表示没有提供（取默认情况），'/'才是根命名空间
  functions : Block # 全是 VNASTFunction
  pending_content : Block # VNASTNodeBase | MetadataOp
  # 现在我们把别名直接存储到被起别名的对象上

  def get_short_str(self, indent : int = 0) -> str:
    result = 'File "' + self.name + '"'
    if ns := self.namespace.try_get_value():
      result += ' NS: ' + ns.get_string()
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
  files : Block # VNASTFileInfo
  characters : SymbolTableRegion[VNASTCharacterSymbol]
  scenes : SymbolTableRegion[VNASTSceneSymbol]

  def get_short_str(self, indent : int = 0) -> str:
    result = 'VNAST'
    result += '\n' + '  '*indent + 'Characters: ' + str(len(self.characters))
    for ch in self.characters:
      result += '\n' + '  '*(indent+1) + VNASTNodeBase.get_target_str(ch, indent+1)
    result += '\n' + '  '*indent + 'Files: ' + str(len(self.files.body))
    for f in self.files.body:
      result += '\n' + '  '*(indent+1) + VNASTNodeBase.get_target_str(f, indent+1)
    return result

  @staticmethod
  def create(name : str, context : Context):
    return VNAST(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name)

class UnrecognizedCommandOp(ErrorOp):
  # 基本是从 GeneralCommandOp 那里抄来的
  _head_region : SymbolTableRegion # name + raw_args
  _positionalarg_region : Region # single block, list of values
  _positionalarg_block : Block
  _keywordarg_region : SymbolTableRegion

  def construct_init(self, *, src_op : GeneralCommandOp | None = None,  **kwargs) -> None:
    super().construct_init(error_code='vnparser-unrecognized-command', error_msg=None, **kwargs)
    self._head_region = self._add_symbol_table('head')
    self._positionalarg_region = self._add_region('positional_arg')
    self._keywordarg_region = self._add_symbol_table('keyword_arg')
    self._positionalarg_block = self._positionalarg_region.create_block('')
    src_head = src_op.get_symbol_table('head')
    src_name_symbol = src_head.get('name')
    assert isinstance(src_name_symbol, CMDValueSymbol)
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
      self._keywordarg_region.add(CMDValueSymbol(op.name, op.location, op.value))

  def post_init(self) -> None:
    super().post_init()
    self._head_region = self.get_symbol_table('head')
    self._positionalarg_region = self.get_region('positional_arg')
    self._positionalarg_block = self._positionalarg_region.blocks.front
    self._keywordarg_region = self.get_symbol_table('keyword_arg')

  @staticmethod
  def create(src_op : GeneralCommandOp):
    return UnrecognizedCommandOp(init_mode=IRObjectInitMode.CONSTRUCT, context=src_op.context, src_op=src_op)