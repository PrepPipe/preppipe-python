# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

"""Abstraction for input sources"""


##
# @namespace preppipe.inputmodel
# @~english @brief Abstraction for input sources
# @~chinese @brief 输入内容的抽象层
# @~
#
# **TESTBOLD**
#
# <details open>
# <summary>English</summary>
# Test detailed doc
# </details>
#
# <details open>
# <summary>中文</summary>
# 测试中文
# </details>
#
#
#

##
# @file preppipe/inputmodel.py
# @~english @brief See preppipe.inputmodel for documentation
# @~chinese @brief 请从 preppipe.inputmodel 查看文档
# @~

# from tabnanny import check
# from tkinter.font import names
import typing
import PIL.Image
import importlib
import hashlib
import enum

from .irbase import *
from .irdataop import *
from .commontypes import *
from .exceptions import *

@IRObjectJsonTypeName("im_element_op")
class IMElementOp(Operation):
  # InputModel 中代表内容的Operation (可能是文本也可能是图案等）。这个类将内容的值与位置信息组合起来。
  # 如果是文本内容，如果部分文本由特殊格式（比如加粗或是有背景色），content 有可能包含不止一个 Value
  # 如果是非文本内容，每个这类 IMElementOp 只会包含一个 Value
  # 如果是特殊段内容应该用下面的 IMSpecialBlockOp 表述
  _content_operand : OpOperand

  def construct_init(self, *, content : Value | typing.Iterable[Value], name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_operand_with_value('content', content)

  def post_init(self) -> None:
    super().post_init()
    self._content_operand = self.get_operand_inst('content')

  @staticmethod
  def create(content : Value | typing.Iterable[Value], name : str, loc : Location):
    return IMElementOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, content=content, name=name, loc=loc)

  @property
  def content(self):
    return self._content_operand

  @staticmethod
  def collect_text_from_paragraph(b : Block) -> tuple[str, list[AssetData]]:
    # 把给定段落（以块表示）的文本提取出来：
    # 所有文本内容都会只保留字符串
    # 所有资源会被替换成 '\0' 并加到资源列表中
    # 如果段落中有其他不是 IMElementOp 的操作项（比如命令等）则直接忽略
    return _collect_text_from_paragraph_impl(b)

@IRObjectJsonTypeName("im_err_element_op")
class IMErrorElementOp(ErrorOp):
  # 该类代表读取中发生的错误
  # 内容项是对内容的最合适的形式的表述，错误项是关于该错误的字符串描述
  #_error_operand : OpOperand
  _content_operand : OpOperand

  def construct_init(self, *, content : Value | typing.Iterable[Value], error_code: str, error_msg: StringLiteral | None = None, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(error_code=error_code, error_msg=error_msg, name=name, loc=loc, **kwargs)
    self._add_operand_with_value('content', content)

  def post_init(self) -> None:
    super().post_init()
    self._content_operand = self.get_operand_inst('content')

  @staticmethod
  def create(name: str, loc: Location, content : Value | typing.Iterable[Value], error_code : str, error_msg : StringLiteral | None = None):
    return IMErrorElementOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, content=content, error_code=error_code, error_msg=error_msg, name=name, loc=loc)

  @property
  def content(self):
    return self._content_operand

@IROperationDataclass
@IRObjectJsonTypeName("im_specialblock_op")
class IMSpecialBlockOp(Operation):
  # 特殊块可以用来在文本中内嵌无格式的内容，或是描述其他特殊格式的文本
  # 一般用于内嵌后端指令
  # 如果有多行， content 中应该有多个 StringLiteral 的值
  content : OpOperand[StringLiteral]

  # 我们用属性来描述为什么这段文本会被作为特殊块
  ATTR_REASON : typing.ClassVar[str] = 'reason'
  ATTR_REASON_BG_HIGHLIGHT : typing.ClassVar[str] = 'bg_highlight' # 这段文本有段落背景色
  ATTR_REASON_CENTERED : typing.ClassVar[str] = 'centered' # 这段文本不是“正文”而是各种标题

  def is_created_by_background_highlighting(self):
    return self.get_attr(self.ATTR_REASON) == self.ATTR_REASON_BG_HIGHLIGHT

  def is_created_by_centered_text(self):
    return self.get_attr(self.ATTR_REASON) == self.ATTR_REASON_CENTERED

  @staticmethod
  def create(content : Value | typing.Iterable[Value], reason : str, name : str, loc : Location):
    assert reason in [
      IMSpecialBlockOp.ATTR_REASON_BG_HIGHLIGHT,
      IMSpecialBlockOp.ATTR_REASON_CENTERED,
    ]
    result = IMSpecialBlockOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, content=content, name=name, loc=loc)
    result.set_attr(IMSpecialBlockOp.ATTR_REASON, reason)
    return result

@IRObjectJsonTypeName("im_frame_op")
class IMFrameOp(Operation):
  # frame 代表一个文档或文本框的顶层结构
  # 我们使用 IR 的 block 来代表文档内的一个 block，所以不需要专门的类；这些 block 将直接在 body 区内
  # (在前端，刚开始生成时，一个块代表一段（<p>），块内是一堆 IMElementOp)
  _body_region : Region

  def construct_init(self, *, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_region('body')

  def post_init(self) -> None:
    super().post_init()
    self._body_region = self.get_region('body')

  @property
  def body(self):
    return self._body_region

  @staticmethod
  def create(name : str, loc : Location):
    return IMFrameOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

@IRObjectJsonTypeName("im_list_op")
class IMListOp(Operation):
  # 该类代表一个列表(bullet point list / numbered list)
  # 虽然list也可作为资源（asset），但由于这样的列表可能会生成不同的结构（比如分支选项等），我们在前端先用这个类来表述，之后如果确定以资源的方式生成的话再把它们打包成资源。
  # 大部分的列表应该会被生成成其他东西，以表格活不到VNModel
  # 每个选项均是一个区

  def construct_init(self, *, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self.set_attr('IsNumbered', False)

  def get_item_region_name(self, index : int) -> str:
    return str(index)

  def get_num_items(self) -> int:
    return self.get_num_regions()

  @property
  def is_numbered(self) -> bool:
    v = self.get_attr('IsNumbered')
    assert isinstance(v, bool)
    return v

  @is_numbered.setter
  def is_numbered(self, v : bool) -> None:
    self.set_attr('IsNumbered', v)

  def add_list_item(self, start_base : int = 1) -> Region:
    index = self.get_num_items() + start_base
    return self._add_region(str(index))

  def get_item(self, index : int) -> Region:
    return self.get_region(self.get_item_region_name(index))

  def take_list_item(self, list_item : Region):
    name = ''
    if list_item.parent is not None:
      name = list_item.name
      list_item.remove_from_parent()
    if len(name) == 0 or name in self._regions:
      # create a new name
      index = self.get_num_items() + 1
      name = str(index)
      while name in self._regions:
        index += 1
        name = str(index)
    self._take_region(list_item, name)

  @staticmethod
  def create(name : str, loc : Location):
    return IMListOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

@IROperationDataclass
@IRObjectJsonTypeName("im_table_op")
class IMTableOp(Operation):
  # 该类代表一个表格（有可能只有一行或一列）
  # 表格不支持单元格合并，输入时合并的单元格将被差分，每个子单元格将复制原单元格的内容
  # （即合并的单元格视为子单元格共享相同的一份内容）
  rowcount : OpOperand[IntLiteral]
  columncount : OpOperand[IntLiteral]

  def _get_cell_operand_name(self, row : int, col : int) -> str:
    return 'cell_' + str(row) + '_' + str(col)

  def get_cell_operand(self, row : int, col : int) -> OpOperand:
    return self.get_operand_inst(self._get_cell_operand_name(row, col))

  def _custom_postinit_(self):
    rowcnt = self.rowcount.get().value
    columncnt = self.columncount.get().value
    assert rowcnt > 0 and columncnt > 0
    for row in range(0, rowcnt):
      for col in range(0, columncnt):
        name = self._get_cell_operand_name(row, col)
        if name not in self.operands:
          self._add_operand(name)

  @staticmethod
  def create(rowcount : int, columncount : int, name : str, loc : Location):
    return IMTableOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, rowcount=rowcount, columncount=columncount, name=name, loc=loc)

@IRObjectJsonTypeName("im_document_op")
class IMDocumentOp(IMFrameOp):
  # 该类代表一个完整的文档

  @staticmethod
  def create(name : str, loc : Location):
    return IMDocumentOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

def _collect_text_from_paragraph_impl(b : Block) -> tuple[str, list[AssetData]]:
  content_str = ''
  asset_list : typing.List[AssetData] = []
  for op in b.body:
    # 忽略所有非语义消息
    if isinstance(op, MetadataOp):
      continue
    if not isinstance(op, IMElementOp):
      # 碰到了一项非内容的，直接忽略
      continue
    # 找到了一项内容
    # 尝试读取内容并组成命令文本
    assert isinstance(op, IMElementOp)
    content_operand : OpOperand = op.content
    for i in range(0, content_operand.get_num_operands()):
      v = content_operand.get(i)
      if isinstance(v, (StringLiteral, TextFragmentLiteral)):
        content_str += v.get_string()
      elif isinstance(v, AssetData):
        content_str += '\0'
        asset_list.append(v)
      else:
        raise PPNotImplementedError('TODO support other possible element types in IMElementOp')

  return (content_str, asset_list)