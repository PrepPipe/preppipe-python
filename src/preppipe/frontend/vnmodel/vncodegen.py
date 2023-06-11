# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import enum
import typing

from ...irbase import *
from ...vnmodel_v4 import *

@dataclasses.dataclass
class VNASTNodeBase:
  name : str
  loc : Location

@dataclasses.dataclass
class VNASTSayNodeBase(VNASTNodeBase):
  # 所有发言的基类

  content : list[Value]

@dataclasses.dataclass
class VNASTNarrateNode(VNASTSayNodeBase):
  # 没有引号的发言，只有内容，没有发言者
  pass

@dataclasses.dataclass
class VNASTQuotedSayNode(VNASTSayNodeBase):
  # 有引号的发言，只有内容，没有发言者
  pass

@dataclasses.dataclass
class VNASTFullSayNode(VNASTSayNodeBase):
  # 显式提供了发言者的发言
  sayer : str

# ----------------------------------------------------------
# 该模式下发言者  |  <内容>  |  “<内容>”    |  角色：“<内容>”
# ----------------------------------------------------------
# 默认模式       |   旁白   | 最后说话的人   |   指定角色
# ----------------------------------------------------------
# 长发言模式     |  给定者  |    给定者      |   指定角色
# ----------------------------------------------------------
# 交替模式       |   旁白   | 按次序排列的人 |指定角色，修正说话者
# ----------------------------------------------------------

class VNSayMode(enum.Enum):
  MODE_DEFAULT = 0
  MODE_LONG_SPEECH = enum.auto()
  MODE_INTERLEAVED = enum.auto()

class VNSayModeChangeNode(VNASTNodeBase):
  target_mode : VNSayMode
  specified_sayers : list[str]

@dataclasses.dataclass
class VNASTPendingAssetReference:
  # 该值仅作为值接在 VNAssetReference 中，不作为单独的结点
  assetref : str

class VNASTAssetIntendedOperation(enum.Enum):
  OP_PUT = 0,
  OP_CREATE = enum.auto()
  OP_REMOVE = enum.auto()

class VNASTAssetKind(enum.Enum):
  KIND_IMAGE = 0
  KIND_AUDIO = enum.auto()
  KIND_EFFECT = enum.auto()
  KIND_VIDEO = enum.auto()

@dataclasses.dataclass
class VNASTAssetReference(VNASTNodeBase):
  # 引用的是什么资源
  kind : VNASTAssetKind

  # 引用该资源是想做什么
  operation : VNASTAssetIntendedOperation

  # 资源本体
  asset : VNASTPendingAssetReference | Value

  # 如果图形等内容前、后跟了一段文字，尝试把文字内容理解为对资源的命名
  # 如 ['图1','视觉小说的大致制作过程与游戏框架']
  descriptions : list[str]

@dataclasses.dataclass
class VNASTASMNode(VNASTNodeBase):
  backend : str
  body : StringListLiteral

@dataclasses.dataclass
class VNASTNamespaceSwitchableValue(typing.Generic[T]):
  baseline : T
  namespace_dict : dict[str, T]

  def get_value(self, ns : str) -> T:
    if ns != '/':
      nstuple = VNNamespace.expand_namespace_str(ns)
      while ns not in self.namespace_dict and len(nstuple) > 1:
        nstuple = nstuple[:-1]
        ns = VNNamespace.stringize_namespace_path(nstuple)
      if ns in self.namespace_dict:
        return self.namespace_dict[ns]
    return self.baseline

@dataclasses.dataclass
class VNASTSceneSwitchNode(VNASTNodeBase):
  destscene : str

@dataclasses.dataclass
class VNASTCharacterEntryNode(VNASTNodeBase):
  character : str

@dataclasses.dataclass
class VNASTCharacterStateChangeNode(VNASTNodeBase):
  character : str
  deststate : list[str]

@dataclasses.dataclass
class VNASTCodegenRegion:
  body : list[VNASTNodeBase]

@dataclasses.dataclass
class VNASTFunction(VNASTCodegenRegion):
  # 代表一个函数

  # 如果在该函数定义前就有错误、警告内容，我们把这些东西放在这里
  prebody_md : list[MetadataOp]

@dataclasses.dataclass
class VNASTConditionalExecutionNode(VNASTNodeBase):
  # 条件分支
  conditions : list[str]
  body: list[VNASTCodegenRegion]

@dataclasses.dataclass
class VNASTMenuNode(VNASTNodeBase):
  # 选单
  options : list[list[Value]] # 每个选项的文本是个 list[Value]
  body: list[VNASTCodegenRegion]

  # 一般默认结束动作是退出并继续，这个标志可使选项循环
  loop_when_done : bool = False

@dataclasses.dataclass
class VNASTBreakNode(VNASTNodeBase):
  # 用来跳出循环，现在只有选单会有循环
  pass

@dataclasses.dataclass
class VNASTLabelNode(VNASTNodeBase):
  # 用来提供基于标签的跳转
  labelname : str

@dataclasses.dataclass
class VNASTJumpNode(VNASTNodeBase):
  # 跳转到指定标签，不能到另一个函数
  target_label : str

class VNASTSayDeviceKind(enum.Enum):
  KIND_ADV = enum.auto()
  KIND_NVL = enum.auto()

@dataclasses.dataclass
class VNASTChangeDefaultDeviceNode(VNASTNodeBase):
  destmode : VNASTSayDeviceKind

@dataclasses.dataclass
class VNASTCharacterSayInfo:
  # 使用继承的 name 作为显示的名称
  displayname_expr : str # 如果是表达式的话用这里的值
  state_tags : list[str] # 当使用这里的状态标签时适用该记录里的信息
  namecolor : Color | None
  textcolor : Color | None

@dataclasses.dataclass
class VNASTCharacterInfo:
  namespace : str
  say_conds : dict[str, VNASTCharacterSayInfo] # 所有发言表现的信息
  sprites : dict[tuple[str], VNASTNamespaceSwitchableValue[VNASTPendingAssetReference | Value]]

@dataclasses.dataclass
class VNASTSceneInfo:
  namespace : str

@dataclasses.dataclass
class VNASTFileInfo:
  name : str
  loc : Location
  namespace : str = '' # 空字符串表示没有提供，'/'才是根命名空间
  functions : list[VNASTFunction] = dataclasses.field(default_factory=list)
  aliases : dict[str, str] = dataclasses.field(default_factory=dict) # 所有声明的别名都在这
  pending_md : list[MetadataOp] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class VNAST:
  files : list[VNASTFileInfo] = dataclasses.field(default_factory=list)
  characters : dict[str, VNASTCharacterInfo] = dataclasses.field(default_factory=dict)

def vncodegen(ast : VNAST, ctx : Context) -> VNModel:
  return VNModel.create(ctx)
