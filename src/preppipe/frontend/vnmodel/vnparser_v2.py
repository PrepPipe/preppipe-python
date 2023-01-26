# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ...irbase import *
from ..commandsyntaxparser import *
from ..commandsemantics import *
from ...vnmodel_v3 import *

# ------------------------------------------------------------------------------
# 内容声明命令
# ------------------------------------------------------------------------------

vn_command_ns = FrontendCommandNamespace.create(None, 'vnmodel')

class UnrecognizedCommandOp(ErrorOp):
  # 基本是从 GeneralCommandOp 那里抄来的
  _head_region : SymbolTableRegion # name + raw_args 
  _positionalarg_region : Region # single block, list of values
  _positionalarg_block : Block
  _keywordarg_region : SymbolTableRegion
  
  def __init__(self, src: GeneralCommandOp, **kwargs) -> None:
    super().__init__(src.name, src.location, 'vnparser-unrecognized-command', None, **kwargs)
    self._head_region = self._add_symbol_table('head')
    self._positionalarg_region = self._add_region('positional_arg')
    self._keywordarg_region = self._add_symbol_table('keyword_arg')
    self._positionalarg_block = self._positionalarg_region.add_block('')
    src_head = src.get_symbol_table('head')
    src_name_symbol = src_head.get('name')
    assert isinstance(src_name_symbol, CMDValueSymbol)
    name_symbol = CMDValueSymbol('name', src_name_symbol.location, src_name_symbol.value)
    self._head_region.add(name_symbol)
    src_rawarg_symbol = src_head.get('rawarg')
    if src_rawarg_symbol is not None:
      assert isinstance(src_rawarg_symbol, CMDValueSymbol)
      rawarg_symbol = CMDValueSymbol('rawarg', src_rawarg_symbol.location, src_rawarg_symbol.value)
      self._head_region.add(rawarg_symbol)
    src_positional_arg = src.get_region('positional_arg')
    assert src_positional_arg.get_num_blocks() == 1
    src_positional_arg_block = src_positional_arg.entry_block
    for op in src_positional_arg_block.body:
      assert isinstance(op, CMDPositionalArgOp)
      self._positionalarg_block.push_back(CMDPositionalArgOp(op.name, op.location, op.value))
    src_kwarg = src.get_symbol_table('keyword_arg')
    for op in src_kwarg:
      assert isinstance(op, CMDValueSymbol)
      self._keywordarg_region.add(CMDValueSymbol(op.name, op.location, op.value))

class VNParser(FrontendParserBase):
  _result_op : VNModel
  _skip_ops : typing.Set[Operation]
  _insert_point : Operation
  _unbacked_block : Block

  def __init__(self, ctx: Context, command_ns: FrontendCommandNamespace) -> None:
    super().__init__(ctx, command_ns)
    self._result_op = VNModel(name = '', loc = ctx.null_location)
    self._skip_ops = set()
    self._insert_point = None
    self._unbacked_block = None
  
  def add_document(self, doc : IMDocumentOp):
    # 我们在 VNModel 中将该文档中的内容“转录”过去
    # 读不了的东西直接忽视（扔掉）
    # 现将插入位置初始化好
    self._unbacked_block = Block('Detached', self.context)
    self._insert_point = MetadataOp('Dummy', self.context.null_location)
    self._unbacked_block.push_back(self._insert_point)
    # 开始
    body_region = doc.body
    for paragraph in body_region.blocks:
      for op in paragraph.body:
        if op in self._skip_ops:
          self._skip_ops.remove(op)
          continue
        if isinstance(op, GeneralCommandOp):
          self.handle_command_op(op)
  
  def handle_command_unrecognized(self, op: GeneralCommandOp, opname: str) -> None:
    # 在插入点创建一个 UnrecognizedCommandOp
    # TODO 在这加自动匹配
    newop = UnrecognizedCommandOp(op)
    newop.insert_before(self._insert_point)
    print('Unrecognized command: ' + str(op))
  
  def handle_command_invocation(self, op: GeneralCommandOp, cmdinfo: FrontendCommandInfo):
    return super().handle_command_invocation(op, cmdinfo)
  
  def handle_command_ambiguous(self, commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo, matched_results: typing.List[typing.Tuple[callable, typing.List[typing.Any], typing.Dict[str, typing.Any], typing.List[typing.Tuple[str, typing.Any]]]], unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    raise NotImplementedError()
  
  def handle_command_no_match(self, commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo, unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    raise NotImplementedError()
  
  def handle_command_unique_invocation(self, commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo, target_cb: callable, target_args: typing.List[typing.Any], target_kwargs: typing.Dict[str, typing.Any], target_warnings: typing.List[typing.Tuple[str, typing.Any]], unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    print('Command ' + cmdinfo.cname + ': target_cb=' + str(target_cb) + ', args=' + str(target_args) + ', kwargs=' + str(target_kwargs) + ', warnings=' + str(target_warnings))
    target_cb(*target_args, **target_kwargs)
    return

# 把 VNParser 的定义包含进去，这样后面的类型标注可以顺利进行
_imports = globals()

# ------------------------------------------------------------------------------
# 内容声明命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, _imports, 'DeclImage', alias={
  '声明图片': {'name': '名称', 'path': '路径'}, # zh_CN
})
def cmd_image_decl(parser : VNParser, commandop : GeneralCommandOp, name : str, path : str):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclVariable', alias={
  '声明变量' : {'name': '名称', 'type': '类型', 'initializer': '初始值'},
})
def cmd_variable_decl(parser: VNParser, commandop : GeneralCommandOp, name : str, type : str, initializer : str):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclCharacter', alias={
  '声明角色' : {'name': '姓名'}, # zh_CN
})
def cmd_character_decl(parser: VNParser, commandop : GeneralCommandOp, name : str, ext : ListExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclCharacterSprite', alias={
  '声明角色立绘' : {'character_state_expr': '角色与状态表达式', 'image': '图片'}, # zh_CN
})
def cmd_character_sprite_decl(parser : VNParser, commandop : GeneralCommandOp, character_state_expr : CallExprOperand | str, image : str):
  # 定义一个角色的外观状态（一般是立绘差分，比如站姿、衣着、等），使得角色变换状态时能够切换立绘
  # 这必须是一个独立于角色声明的操作，因为更多角色外观等可以通过DLC等形式进行补足，所以它们可能处于不同的命名空间中
  # 在实际的内容中，一个角色的状态标签会有很多（包含衣着、站姿、表情等），
  # 我们先把这里声明的角色标签给匹配掉，剩余的标签喂给图像参数（应该是带差分的多层图片）
  # 我们预计用本命令指定角色的基础外观（比如站姿、衣着，确定哪组立绘），剩下的用来在立绘中选表情匹配的差分
  # 虽然我们基本上只用一个“状态标签”参数来进行匹配，但对人物而言，我们要求最后一个标签代表表情，
  # 这样文中可以用<人名><表情><内容>的方式来表达说明，并且表情标签所替代的标签没有歧义
  # （我们也可以支持表情标签的层级，永远从最右侧替换）
  pass

@CommandDecl(vn_command_ns, _imports, 'SetCharacterSayAttr', alias={
  '设置角色发言属性' : {'character_name': '角色姓名', 'state_tags': '状态标签',
                       'name_color': '名字颜色',
                       'display_name': '显示名',
                       'display_name_expression': '显示名表达式',
                       'content_color': '内容颜色',
                       'content_prefix': '内容前缀',
                       'content_suffix': '内容后缀',
                      }, # zh_CN
})
def cmd_character_say_attr(parser : VNParser, commandop : GeneralCommandOp, character_name : str, *, state_tags : str = '',
                           name_color : str = None, # 名字的颜色，None 保留默认值
                           display_name : str = None, # 显示的名字的内容，如果名字不是字面值的话就用 expression, 这项留空
                           display_name_expression : str = None, # 如果名字要从变量中取或者其他方式，这项就是用于求解的表达式
                           content_color : str = None, # 文本的颜色
                           content_prefix : str = '', # 文本前缀（比如如果要把所有文本都用『』括起来的话，那么这两个符号就是前缀和后缀）
                           content_suffix : str = '',
                          ):
  # 定义一个角色说话时名称的显示
  # 如果
  pass

# TODO
def cmd_set_character_state(parser : VNParser, commandop : GeneralCommandOp):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclScene', alias={
  '声明场景' : {'name': '名称'}, # zh_CN
})
def cmd_scene_decl(parser : VNParser, commandop : GeneralCommandOp, name : str, ext : ListExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclSceneBackground', alias={
  '声明场景背景' : {'scene': '场景', 'state_tags' : '状态标签', 'background_image' : '背景图片'}, # zh_CN
})
def cmd_scene_background_decl(parser : VNParser, commandop : GeneralCommandOp, scene : str, state_tags : str, background_image : str):
  # 给场景定义一个可显示状态，使得“切换场景”可以更改背景
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclAlias', alias={
  '声明别名' : {'alias_name': '别名名称', 'target':'目标'}, # zh_CN
})
def cmd_alias_decl(parser : VNParser, commandop : GeneralCommandOp, alias_name : str, target : CallExprOperand):
  # (仅在解析时用到，不会在IR中)
  # 给目标添加别名（比如在剧本中用‘我’指代某个人）
  pass

# ------------------------------------------------------------------------------
# 内容操作命令
# ------------------------------------------------------------------------------
@CommandDecl(vn_command_ns, _imports, 'CharacterEnter', alias={
  '角色入场': {'characters': '角色', 'transition': '转场'}
})
def cmd_character_entry(parser : VNParser, commandop : GeneralCommandOp, characters : list[CallExprOperand], transition : CallExprOperand = None):
  pass

def cmd_wait_finish(parser : VNParser, commandop : GeneralCommandOp):
  pass

@CommandDecl(vn_command_ns, _imports, 'CharacterExit', alias={
  '角色退场': {'characters': '角色', 'transition': '转场'}
})
def cmd_character_exit(parser : VNParser, commandop : GeneralCommandOp, characters : list[CallExprOperand], transition : CallExprOperand = None):
  pass

@CommandDecl(vn_command_ns, _imports, 'SpecialEffect', alias={
  '特效': {'effect': '特效'}
})
def cmd_special_effect(parser : VNParser, commandop : GeneralCommandOp, effect : CallExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'SwitchCharacterState', alias={
  '切换角色状态': {'state_expr': '状态表达式'}
})
def cmd_switch_character_state(parser : VNParser, commandop : GeneralCommandOp, state_expr : list[str] | CallExprOperand):
  # 如果是个调用表达式，则角色名是调用的名称
  # 如果是一串标签字符串，则更改默认发言者的状态
  # 优先匹配一串字符串
  pass

@CommandDecl(vn_command_ns, _imports, 'SwitchScene', alias={
  '切换场景': {'scene': '场景'}
})
def cmd_switch_scene(parser : VNParser, commandop : GeneralCommandOp, scene: CallExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'HideImage', alias={
  '收起图片': {'image_name': '图片名', 'transition': '转场'}
})
def cmd_hide_image(parser : VNParser, commandop : GeneralCommandOp, image_name : str, transition : CallExprOperand = None):
  pass


# ------------------------------------------------------------------------------
# 控制流相关的命令
# ------------------------------------------------------------------------------
@CommandDecl(vn_command_ns, _imports, 'Function', alias={
  ('Function', 'Section') : {}, # en
  ('函数', '章节') : {'name': '名称'}, # zh_CN
})
def cmd_set_function(parser : VNParser, commandop : GeneralCommandOp, name : str):
  pass


@CommandDecl(vn_command_ns, _imports, 'Choice', alias={
  '选项': {'name': '名称', 'finish_action': '结束动作'}
})
def cmd_choice(parser : VNParser, commandop : GeneralCommandOp, ext : ListExprOperand, name : str, finish_action : CallExprOperand = CallExprOperand('continue')):
  pass

# ------------------------------------------------------------------------------
# 解析状态相关的命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, _imports, 'DefaultSayer', alias={
  '默认发言者': {'character_state_expr': '角色与状态表达式'}, # zh_CN
})
def cmd_set_default_sayer(parser : VNParser, commandop : GeneralCommandOp, character_expr : CallExprOperand):
  pass



@MiddleEndDecl('vn', input_decl=IMDocumentOp, output_decl=VNModel)
class VNParseTransform(TransformBase):
  _parser : VNParser
  def __init__(self, ctx: Context) -> None:
    super().__init__(ctx)
    self._parser = VNParser(ctx, vn_command_ns)
  
  def run(self) -> Operation | typing.List[Operation] | None:
    for doc in self.inputs:
      self._parser.add_document(doc)
    return VNModel('', self.context.null_location)