# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import io

from preppipe.renpy.ast import RenPyASMNode, RenPyScriptFileOp
from .ast import *
from ..util import versioning

class RenPyExportVisitor(RenPyASTVisitor):
  indent_level : int
  indent_width : int # 每一层缩进的空格数量
  dest : io.TextIOBase
  def __init__(self, dest : io.TextIOBase, indent_width : int = 4) -> None:
    super().__init__()
    self.indent_level = 0
    self.indent_width = indent_width
    self.dest = dest
    assert indent_width > 0

  def start_visit(self, v: RenPyScriptFileOp) -> None:
    self.indent_level = 0
    self.walk_body(v.body, no_leading_newline=True)
    self.dest.write('\n')

  @staticmethod
  def drop_leading_ws(s : str, numws : int) -> str:
    for i in range(0, numws):
      if not s.startswith((' ', '\t')):
        break
      s = s[1:]
    return s

  @staticmethod
  def count_leading_ws(s : str, startcnt : int = 0) -> tuple[str, int]:
    while s.startswith((' ', '\t')):
      startcnt += 1
      s = s[1:]
    return (s, startcnt)

  def get_eol_with_ws(self, num_extra_indent_level : int = 0) -> str:
    return '\n' + ' '*self.indent_width * (self.indent_level+num_extra_indent_level)

  def stringtize_value_if_nondefault(self, value : Value, default : typing.Any) -> str | None:
    assert value is not None
    if value == default or isinstance(value, Literal) and value.value == default:
      return None
    if isinstance(value, StringLiteral):
      return '"' + value.get_string() + '"'
    if isinstance(value, RenPyASMNode):
      return 'r"""' + self.stringtize_asm(value.asm.get(), False) + '"""'
    if isinstance(value, BoolLiteral):
      if value.value:
        return "True"
      return "False"
    raise NotImplementedError()

  def populate_operand(self, pieces : list[str], name : str, o : OpOperand, default : typing.Any = None):
    if value := o.try_get_value():
      if s := self.stringtize_value_if_nondefault(value, default):
        pieces.append(", " + name + '=' + s)

  def stringtize_asm(self, sl : StringListLiteral, is_python : bool = False) -> str:
    # is_python: 如果是纯 Python 代码的话，我们需要在缩进之后再添加 "$ "
    assert isinstance(sl, StringListLiteral)
    pieces = []
    num_lines = 0
    input_indent = 0
    leadingws = 0 # 首行的空白字符数量
    for i in range(0, sl.get_num_operands()):
      line = sl.get_operand(i)
      assert isinstance(line, StringLiteral)
      linetext = line.get_string()
      num_indent_level = 0

      # 把输入中的缩进距离转换为输出的缩进距离
      if linetext.startswith((' ', '\t')):
        if num_lines == 0:
          # 首行有空格的话以下所有内容都先缩减掉相应的内容
          linetext, leadingws = RenPyExportVisitor.count_leading_ws(linetext, leadingws)
        else:
          if leadingws > 0:
            linetext = RenPyExportVisitor.drop_leading_ws(linetext, leadingws)
          # 如果此时还有空格，则判断是否是第一次用到缩进，是的话记录缩进距离
          if linetext.startswith((' ', '\t')):
            if input_indent == 0:
              linetext, input_indent = RenPyExportVisitor.count_leading_ws(linetext, input_indent)
            else:
              while linetext.startswith((' ', '\t')):
                num_indent_level += 1
                linetext = RenPyExportVisitor.drop_leading_ws(linetext, leadingws)
      if num_lines > 0:
        pieces.append(self.get_eol_with_ws(num_indent_level))
      if is_python:
        pieces.append("$ ")
      num_lines += 1
      pieces.append(linetext)
    return ''.join(pieces)

  RENPY_STR_ESCAPE_DICT : typing.ClassVar[dict[str, str]] = {
    '"' : r'\"',
    "'" : r"\'",
    '\n' : r"\n",
    '%' : r"\%",
    '[' : r"[[",
    '{' : r"{{",
  }
  RENPY_STR_STYLE_TAG_DICT : typing.ClassVar[dict[TextAttribute, str]] = {
    TextAttribute.Bold : 'b',
    TextAttribute.Italic : 'i',

  }

  @staticmethod
  def escapestr(s : str) -> str:
    s = s.replace('\\', r"\\")
    for k, v in RenPyExportVisitor.RENPY_STR_ESCAPE_DICT.items():
      s = s.replace(k, v)
    # renpy merges contiguous whitespaces
    # we need to preserve them if there are contiguous WS
    while True:
      pos = s.find('  ')
      if pos == -1:
        break
      length = 2
      while len(s) > pos+length and s[pos + length] == ' ':
        length += 1
      s = s[:pos] + r'\ ' * length + s[pos + length:]
    return s

  @staticmethod
  def stringmarshal(v : OpOperand) -> str:
    pieces = []
    for i in range(0, v.get_num_operands()):
      p = v.get_operand(i)
      if isinstance(p, StringLiteral):
        pieces.append(RenPyExportVisitor.escapestr(p.get_string()))
        continue
      if isinstance(p, TextFragmentLiteral):
        pre_stack = []
        post_stack = []
        style_tuple = p.style.value
        for attr, value in style_tuple:
          start_tag = ''
          end_tag = ''
          match attr:
            case TextAttribute.Bold:
              start_tag = 'b'
            case TextAttribute.Italic:
              start_tag = 'i'
            case TextAttribute.TextColor:
              assert isinstance(value, Color)
              start_tag = 'color=' + value.get_string()
              end_tag = 'color'
            case TextAttribute.BackgroundColor:
              assert isinstance(value, Color)
              start_tag = 'outlinecolor=' + value.get_string()
              end_tag = 'outlinecolor'
            case _: # TextAttribute.Size:
              continue
          if len(start_tag) == 0:
            continue
          if len(end_tag) == 0:
            end_tag = start_tag
          pre_stack.append('{' + start_tag + '}')
          post_stack.insert(0, '{/' + end_tag + '}')
        s = RenPyExportVisitor.escapestr(p.get_string())
        pieces.append(''.join(pre_stack) + s + ''.join(post_stack))
        continue
      raise NotImplementedError('String type not supported: ' + str(type(p)))
    return ''.join(pieces)

  RENPY_ERROR_SAYER_NAME : typing.ClassVar[str] = 'preppipe_error_sayer'

  def walk_body(self, b : Block, no_leading_newline : bool = False):
    for op in b.body:
      if isinstance(op, RenPyNode):
        if not no_leading_newline:
          self.dest.write(self.get_eol_with_ws())
        else:
          no_leading_newline = False
        op.accept(self)
      elif isinstance(op, ErrorOp):
        code : str = op.error_code
        msg : str = op.error_message.get_string()
        fullmsg = code + ": " + msg
        if not no_leading_newline:
          self.dest.write(self.get_eol_with_ws())
        else:
          no_leading_newline = False
        self.dest.write(self.RENPY_ERROR_SAYER_NAME + " \"" + self.escapestr(fullmsg) + '"')
      elif isinstance(op, MetadataOp):
        continue
      else:
        raise NotImplementedError("TODO")

  def walk_body_with_incr_level(self, b : Block):
    cur_level = self.indent_level
    self.indent_level += 1
    self.walk_body(b)
    self.indent_level = cur_level

  def collect_strings(self, o : OpOperand[StringLiteral]) -> list[str]:
    return [s.value.get_string() for s in o.operanduses()]

  def visitRenPyASMNode(self, v: RenPyASMNode):
    # 以这种方式碰到的 ASM 都视为 RenPy 脚本
    # 需要 Python 内容的地方都会由父节点直接处理
    self.dest.write(self.stringtize_asm(v.asm.get(), False))

  def visitRenPyCharacterExpr(self, v : RenPyCharacterExpr):
    pieces = ["Character(" + '"' + self.stringmarshal(v.displayname) + '"']
    self.populate_operand(pieces, "kind", v.kind, "")
    self.populate_operand(pieces, "image", v.image, "")
    self.populate_operand(pieces, "voice_tag", v.voicetag, "")
    self.populate_operand(pieces, "what_prefix", v.what_prefix, "")
    self.populate_operand(pieces, "what_suffix", v.what_suffix, "")
    self.populate_operand(pieces, "who_prefix", v.who_prefix, "")
    self.populate_operand(pieces, "who_suffix", v.who_suffix, "")
    self.populate_operand(pieces, 'dynamic', v.dynamic)
    self.populate_operand(pieces, 'condition', v.condition)
    self.populate_operand(pieces, 'interact', v.interact, True)
    self.populate_operand(pieces, 'advance', v.advance, True)
    # mode
    self.populate_operand(pieces, "mode", v.mode)
    self.populate_operand(pieces, "callback", v.callback, "")
    self.populate_operand(pieces, "ctc", v.ctc)
    self.populate_operand(pieces, "ctc_pause", v.ctc_pause)
    self.populate_operand(pieces, "ctc_timedpause", v.ctc_timedpause)
    self.populate_operand(pieces, "ctc_position", v.ctc_position)
    self.populate_operand(pieces, "screen", v.screen)
    if show_params := v.show_params.try_get_value():
      params = []
      for i in range(0, show_params.get_num_operands()):
        p = show_params.get_operand(i)
        params.append(p.get_string())
      pieces.append(', ' + ', '.join(params))
    self.dest.write(''.join(pieces))
    self.dest.write(')')

  def visitRenPyImageNode(self, v : RenPyImageNode):
    self.dest.write('image ' + ' '.join(self.collect_strings(v.codename)) + ' = ')
    self.visitRenPyASMNode(v.displayable.get())

  def visitRenPySayNode(self, v : RenPySayNode):
    pieces = []
    if sayer := v.who.try_get_value():
      pieces.append(sayer.get_varname_str())
    if v.persistent_attributes.get_num_operands() > 0:
      for i in range(0, v.persistent_attributes.get_num_operands()):
        a = v.persistent_attributes.get_operand(i).get_string()
        pieces.append(a)
    if v.temporary_attributes.get_num_operands() > 0:
      pieces.append('@')
      for i in range(0, v.temporary_attributes.get_num_operands()):
        a = v.temporary_attributes.get_operand(i).get_string()
        pieces.append(a)
    pieces.append('"' + RenPyExportVisitor.stringmarshal(v.what) + '"')
    if interact := v.interact.try_get_value():
      if not interact.value:
        pieces.append('noninteract')
    if identifier := v.identifier.try_get_value():
      s = identifier.get_string()
      if len(s) > 0:
        pieces.append('id')
        pieces.append(s)
    if withvalue := v.with_.try_get_value():
      s = withvalue.get_string()
      if len(s) > 0:
        pieces.append('with')
        pieces.append(s)
    self.dest.write(' '.join(pieces))
    return None

  def visitRenPyLabelNode(self, v : RenPyLabelNode):
    self.dest.write('label ' + v.codename.get().get_string())
    if v.parameters.has_value():
      self.dest.write('(')
      self.dest.write(','.join(self.collect_strings(v.parameters)))
      self.dest.write(')')
    self.dest.write(':')
    self.walk_body_with_incr_level(v.body)

  def visitRenPyDefineNode(self, v : RenPyDefineNode):
    assignstr = '=' if v.assign_operator.try_get_value() is None else v.assign_operator.get().get_string()
    self.dest.write('define ' + v.get_varname_str() + ' ' + assignstr + ' ')
    value = v.expr.get()
    if isinstance(value, RenPyCharacterExpr):
      self.visitRenPyCharacterExpr(value)
    elif isinstance(value, RenPyASMNode):
      self.visitRenPyASMNode(value)
    else:
      raise NotImplementedError()
    # done
    return None

  def visitRenPyShowNode(self, v : RenPyShowNode):
    raise NotImplementedError()

  def visitRenPyInitNode(self, v : RenPyInitNode):
    raise NotImplementedError()
    return self.visitChildren(v)


  def visitRenPyTransformNode(self, v : RenPyTransformNode):
    return self.visitChildren(v)

  def visitRenPySceneNode(self, v : RenPySceneNode):
    raise NotImplementedError()
  def visitRenPyWithNode(self, v : RenPyWithNode):
    raise NotImplementedError()
  def visitRenPyHideNode(self, v : RenPyHideNode):
    raise NotImplementedError()
  def visitRenPyCallNode(self, v : RenPyCallNode):
    raise NotImplementedError()
  def visitRenPyReturnNode(self, v : RenPyReturnNode):
    raise NotImplementedError()
  def visitRenPyMenuItemNode(self, v : RenPyMenuItemNode):
    raise NotImplementedError()
  def visitRenPyMenuNode(self, v : RenPyMenuNode):
    raise NotImplementedError()
  def visitRenPyJumpNode(self, v : RenPyJumpNode):
    raise NotImplementedError()
  def visitRenPyPassNode(self, v : RenPyPassNode):
    raise NotImplementedError()
  def visitRenPyCondBodyPair(self, v : RenPyCondBodyPair):
    raise NotImplementedError()
  def visitRenPyWhileNode(self, v : RenPyWhileNode):
    raise NotImplementedError()
  def visitRenPyIfNode(self, v : RenPyIfNode):
    raise NotImplementedError()
  def visitRenPyDefaultNode(self, v : RenPyDefaultNode):
    raise NotImplementedError()

  def visitRenPyPythonNode(self, v : RenPyPythonNode):
    raise NotImplementedError()
  def visitRenPyEarlyPythonNode(self, v : RenPyEarlyPythonNode):
    raise NotImplementedError()

def export_renpy(m : RenPyModel, out_path : str, template_dir : str = '') -> None:
  assert isinstance(m, RenPyModel)
  os.makedirs(out_path, exist_ok=True)
  # step 1: copy the template directory and the runtime
  if len(template_dir) > 0:
    shutil.copytree(template_dir, out_path, dirs_exist_ok=True)
  # now copy the runtime
  rtname = 'preppipert.rpy'
  rtsrc = os.path.join(os.path.dirname(os.path.abspath(__file__)), rtname)
  rtdest = os.path.join(out_path, rtname)
  rttitle = '# PrepPipe ' + versioning.get_version_string() + '\n'
  with open(rtdest, 'w') as dst:
    dst.write(rttitle)
    with open(rtsrc, 'r') as src:
      all = src.read()
      dst.write(all)

  # step 2: start walking all script files
  for script in m.scripts():
    scriptpath = os.path.join(out_path, script.name + '.rpy')
    parentdir = os.path.dirname(scriptpath)
    os.makedirs(parentdir, exist_ok=True)
    with open(scriptpath, 'w') as f:
      exporter = RenPyExportVisitor(f, indent_width=4)
      exporter.start_visit(script)

  # done for now
