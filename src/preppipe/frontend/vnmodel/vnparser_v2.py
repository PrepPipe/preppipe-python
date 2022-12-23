# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ...irbase import *
from ..commandsyntaxparser import *
from ..commandsemantics import *

vn_command_ns = FrontendCommandNamespace.create(None, 'vnmodel')

# ------------------------------------------------------------------------------
# 内容声明命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, 'DeclImage', alias={
  '声明图片': {'name': '名称', 'path': '路径'}, # zh_CN
})
def cmd_image_decl(parser : VNParser, commandop : GeneralCommandOp, name : str, path : str):
  pass

@CommandDecl(vn_command_ns, 'DeclVariable', alias={
  '声明变量' : {'name': '名称', 'type': '类型', 'initializer': '初始值'},
})
def cmd_variable_decl(parser: VNParser, commandop : GeneralCommandOp, name : str, type : str, initializer : str):
  pass

@CommandDecl(vn_command_ns, 'DeclCharacter', alias={
  '声明角色' : {'name': '姓名'}, # zh_CN
})
def cmd_character_decl(parser: VNParser, commandop : GeneralCommandOp, name : str):
  pass

@CommandDecl(vn_command_ns, 'DeclCharacterSprite', alias={
  '声明角色立绘' : {'character_name': '角色姓名', 'state_tags': '状态标签', 'image': '图片'}, # zh_CN
})
def cmd_character_sprite_decl(parser : VNParser, commandop : GeneralCommandOp, character_name : str, image : str, state_tags : str = ''):
  # 定义一个角色的外观状态（一般是立绘差分，比如站姿、衣着、等），使得角色变换状态时能够切换立绘
  # 这必须是一个独立于角色声明的操作，因为更多角色外观等可以通过DLC等形式进行补足，所以它们可能处于不同的命名空间中
  # 在实际的内容中，一个角色的状态标签会有很多（包含衣着、站姿、表情等），
  # 我们先把这里声明的角色标签给匹配掉，剩余的标签喂给图像参数（应该是带差分的多层图片）
  # 我们预计用本命令指定角色的基础外观（比如站姿、衣着，确定哪组立绘），剩下的用来在立绘中选表情匹配的差分
  # 虽然我们基本上只用一个“状态标签”参数来进行匹配，但对人物而言，我们要求最后一个标签代表表情，
  # 这样文中可以用<人名><表情><内容>的方式来表达说明，并且表情标签所替代的标签没有歧义
  # （我们也可以支持表情标签的层级，永远从最右侧替换）
  pass

@CommandDecl(vn_command_ns, 'SetCharacterSayAttr', alias={
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

@CommandDecl(vn_command_ns, 'DeclScene', alias={
  '声明场景' : {'name': '名称'}, # zh_CN
})
def cmd_scene_decl(parser : VNParser, commandop : GeneralCommandOp, name : str):
  pass

@CommandDecl(vn_command_ns, 'DeclSceneBackground', alias={
  '声明场景背景' : {'scene': '场景', 'state_tags' : '状态标签', 'background_image' : '背景图片'}, # zh_CN
})
def cmd_scene_background_decl(parser : VNParser, commandop : GeneralCommandOp, scene : str, state_tags : str, background_image : str):
  # 给场景定义一个可显示状态，使得“切换场景”可以更改背景
  pass

@CommandDecl(vn_command_ns, 'DeclAlias', alias={
  '声明别名' : {'alias_name': '别名名称', 'target':'目标', 'state_tags': '状态标签'}, # zh_CN
})
def cmd_alias_decl(parser : VNParser, commandop : GeneralCommandOp, alias_name : str, target : str, state_tags : str = ''):
  # (仅在解析时用到，不会在IR中)
  # 给目标添加别名（比如在剧本中用‘我’指代某个人）
  pass

# ------------------------------------------------------------------------------
# 内容操作命令
# ------------------------------------------------------------------------------
def cmd_character_entry(parser : VNParser, commandop : GeneralCommandOp, characters : str, transition : str):
  pass

def cmd_wait_finish(parser : VNParser, commandop : GeneralCommandOp):
  pass

def cmd_character_exit(parser : VNParser, commandop : GeneralCommandOp, characters : str, transition : str):
  pass

# ------------------------------------------------------------------------------
# 控制流相关的命令
# ------------------------------------------------------------------------------
@CommandDecl(vn_command_ns, 'Function', alias={
  ('Function', 'Section') : {}, # en
  ('函数', '章节') : {'name': '名称'}, # zh_CN
})
def cmd_set_function(parser : VNParser, commandop : GeneralCommandOp, name : str):
  pass

# ------------------------------------------------------------------------------
# 解析状态相关的命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, 'DefaultSayer', alias={
  '默认发言者': {'name': '名称'}, # zh_CN
})
def cmd_set_default_sayer(parser : VNParser, commandop : GeneralCommandOp, name : str):
  pass

class VNParser:
  pass
