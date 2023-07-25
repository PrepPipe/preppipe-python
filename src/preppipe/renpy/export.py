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
    if isinstance(value, RenPyASMExpr):
      return 'r"""' + value.get_string() + '"""'
    if isinstance(value, RenPyASMNode):
      return 'r"""' + self.stringtize_multiline_asm(value.asm.get(), False) + '"""'
    if isinstance(value, BoolLiteral):
      if value.value:
        return "True"
      return "False"
    raise NotImplementedError()

  def populate_operand(self, pieces : list[str], name : str, o : OpOperand, default : typing.Any = None):
    if value := o.try_get_value():
      if s := self.stringtize_value_if_nondefault(value, default):
        pieces.append(", " + name + '=' + s)

  def stringtize_multiline_asm(self, sl : StringListLiteral, is_require_python_escape : bool = False) -> str:
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
      if is_require_python_escape:
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
  RENPY_ERROR_SAYER_CUR : typing.ClassVar[Translatable] = TR_renpy.tr("preppipe_error_sayer",
    en="preppipe_error_sayer_en",
    zh_cn="preppipe_error_sayer_zh_cn",
    zh_hk="preppipe_error_sayer_zh_hk",
  )

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
        fullmsg = msg + ' (' + code + ')'
        if not no_leading_newline:
          self.dest.write(self.get_eol_with_ws())
        else:
          no_leading_newline = False
        self.dest.write(self.RENPY_ERROR_SAYER_CUR.get() + " \"" + self.escapestr(fullmsg) + '"')
      elif isinstance(op, MetadataOp):
        if isinstance(op, CommentOp):
          content = op.comment.get_string()
        else:
          content = str(op)
        for s in content.split('\n'):
          if not no_leading_newline:
            self.dest.write(self.get_eol_with_ws())
          else:
            no_leading_newline = False
          self.dest.write('# ' + s)
      else:
        raise NotImplementedError("TODO")

  def walk_body_with_incr_level(self, b : Block):
    cur_level = self.indent_level
    self.indent_level += 1
    if len(b.body) > 0:
      self.walk_body(b)
    else:
      self.dest.write(self.get_eol_with_ws())
      self.dest.write("pass")
    self.indent_level = cur_level

  def collect_strings(self, o : OpOperand[StringLiteral]) -> list[str]:
    return [s.value.get_string() for s in o.operanduses()]

  def visitRenPyASMNode(self, v: RenPyASMNode):
    # 以这种方式碰到的 ASM 都视为 RenPy 脚本
    # 需要 Python 内容的地方都会由父节点直接处理
    self.dest.write(self.stringtize_multiline_asm(v.asm.get(), False))

  def visitRenPyASMExpr(self, v : RenPyASMExpr):
    self.dest.write(v.get_string())

  def visitRenPyCharacterExpr(self, v : RenPyCharacterExpr):
    if v.displayname.try_get_value():
      displayname_str = '"' + self.stringmarshal(v.displayname) + '"'
    else:
      displayname_str = 'None'
    pieces = ["Character(" + displayname_str]

    # kind 值结果不能加引号，所以这里我们不使用 populate_operand()
    #self.populate_operand(pieces, "kind", v.kind, "")
    if kind := v.kind.try_get_value():
      if len(kind.get_string()) > 0:
        pieces.append(", kind=" + kind.get_string())

    self.populate_operand(pieces, "image", v.image, "")
    self.populate_operand(pieces, "voice_tag", v.voicetag, "")
    self.populate_operand(pieces, "what_color", v.what_color, "")
    self.populate_operand(pieces, "what_prefix", v.what_prefix, "")
    self.populate_operand(pieces, "what_suffix", v.what_suffix, "")
    self.populate_operand(pieces, "who_color", v.who_color, "")
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
    if v.show_params.has_value():
      params = []
      for i in range(0, v.show_params.get_num_operands()):
        p = v.show_params.get_operand(i)
        params.append(p.get_string())
      pieces.append(', ' + ', '.join(params))
    self.dest.write(''.join(pieces))
    self.dest.write(')')

  def visitRenPyImageNode(self, v : RenPyImageNode):
    self.dest.write('image ' + ' '.join(self.collect_strings(v.codename)) + ' = ')
    self.visitRenPyASMExpr(v.displayable.get())

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
    tailtags = ''
    if interact := v.interact.try_get_value():
      if not interact.value:
        tailtags += '{nw}' # nowait
    pieces.append('"' + RenPyExportVisitor.stringmarshal(v.what) + tailtags + '"')
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
    self.dest.write(self.get_eol_with_ws())
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

  def visitRenPyDefaultNode(self, v : RenPyDefaultNode):
    self.dest.write('default ' + v.get_varname_str() + ' = ' + v.expr.get().get_string())

  def visitRenPyShowNode(self, v : RenPyShowNode):
    pieces = ["show"]
    pieces.extend(self.collect_strings(v.imspec))
    if showas := v.showas.try_get_value():
      pieces.append('as')
      pieces.append(showas.get_string())
    if atl := v.atl.try_get_value():
      pieces.append('at')
      pieces.append(atl.get_string())
    if v.behind.has_value():
      pieces.append('behind')
      pieces.append(','.join(self.collect_strings(v.behind)))
    if zorder := v.zorder.try_get_value():
      pieces.append('zorder')
      pieces.append(str(zorder.value))
    if onlayer := v.onlayer.try_get_value():
      pieces.append('onlayer')
      pieces.append(onlayer.get_string())
    self.dest.write(' '.join(pieces))
    if with_ := v.with_.try_get_value():
      self.dest.write(' ')
      self.visitRenPyWithNode(with_)

  def visitRenPySceneNode(self, v : RenPySceneNode):
    self.dest.write('scene ' + ' '.join(self.collect_strings(v.imspec)))
    if with_ := v.with_.try_get_value():
      self.dest.write(' ')
      self.visitRenPyWithNode(with_)

  def visitRenPyHideNode(self, v : RenPyHideNode):
    self.dest.write('hide ' + ' '.join(self.collect_strings(v.imspec)))
    if onlayer := v.onlayer.try_get_value():
      self.dest.write('onlayer ' + onlayer.get_string())
    if with_ := v.with_.try_get_value():
      self.dest.write(' ')
      self.visitRenPyWithNode(with_)

  def visitRenPyPlayNode(self, v : RenPyPlayNode):
    channel = v.channel.get().get_string()
    audiospec = v.audiospec.get().get_string()
    result = ['play', channel, audiospec]
    if fadein := v.fadein.try_get_value():
      result.append('fadein')
      result.append(str(fadein.value))
    if fadeout := v.fadeout.try_get_value():
      result.append('fadeout')
      result.append(str(fadeout.value))
    self.dest.write(' '.join(result))

  def visitRenPyStopNode(self, v : RenPyStopNode):
    self.dest.write('stop ' + v.channel.get().get_string())

  def visitRenPyVoiceNode(self, v : RenPyVoiceNode):
    self.dest.write('voice ' + v.audiospec.get().get_string())

  def visitRenPyWithNode(self, v : RenPyWithNode):
    self.dest.write('with ' + ' '.join(self.collect_strings(v.expr)))

  def visitRenPyCallNode(self, v : RenPyCallNode):
    self.dest.write('call ')
    if is_expr_l := v.is_expr.try_get_value():
      if is_expr_l.value:
        self.dest.write("expression ")
    self.dest.write(v.label.get().get_string())
    if v.arguments.has_value():
      self.dest.write('(')
      self.dest.write(','.join(self.collect_strings(v.arguments)))
      self.dest.write(')')

  def visitRenPyReturnNode(self, v : RenPyReturnNode):
    self.dest.write("return")
    if retval := v.expr.try_get_value():
      self.dest.write(' ' + retval.get_string())

  def visitRenPyJumpNode(self, v : RenPyJumpNode):
    self.dest.write("jump ")
    if is_expr_l := v.is_expr.try_get_value():
      if is_expr_l.value:
        self.dest.write("expression ")
    self.dest.write(v.target.get().get_string())

  def visitRenPyPassNode(self, v : RenPyPassNode):
    self.dest.write("pass")

  def visitRenPyMenuItemNode(self, v : RenPyMenuItemNode):
    self.dest.write('"' + self.stringmarshal(v.label) + '"')
    if arguments := v.arguments.try_get_value():
      self.dest.write('(' + arguments.get_string() + ')')
    if condition := v.condition.try_get_value():
      self.dest.write(" if ")
      self.dest.write(condition.get_string())
    self.dest.write(':')
    self.walk_body_with_incr_level(v.body)

  def visitRenPyMenuNode(self, v : RenPyMenuNode):
    self.dest.write("menu")
    if varname := v.varname.try_get_value():
      if len(varname.get_string()) > 0:
        self.dest.write(' ' + varname.get_string())
    if arguments := v.arguments.try_get_value():
      self.dest.write('(' + arguments.get_string() + ')')
    self.dest.write(':')
    if menuset := v.menuset.try_get_value():
      self.dest.write(self.get_eol_with_ws(1) + 'set ' + menuset.get_string())
    self.walk_body_with_incr_level(v.items)

  def visitRenPyCondBodyPair(self, v : RenPyCondBodyPair):
    raise RuntimeError("Should not be visited")

  def visitRenPyWhileNode(self, v : RenPyWhileNode):
    self.dest.write('while ' + v.condition.get().get_string() + ':')
    self.walk_body_with_incr_level(v.body)

  def visitRenPyIfNode(self, v : RenPyIfNode):
    is_first_branch = True
    for branch in v.entries.body:
      assert isinstance(branch, RenPyCondBodyPair)
      if condition := branch.condition.try_get_value():
        if is_first_branch:
          self.dest.write('if ')
          is_first_branch = False
        else:
          self.dest.write(self.get_eol_with_ws())
          self.dest.write('elif ')
        self.dest.write(condition.get_string() + ':')
      else:
        if is_first_branch:
          raise RuntimeError("if statement without condition")
        self.dest.write(self.get_eol_with_ws())
        self.dest.write('else:')
      self.walk_body_with_incr_level(branch.body)

  def visitRenPyInitNode(self, v : RenPyInitNode):
    self.dest.write('init')
    if priority := v.priority.try_get_value():
      self.dest.write(' ' + str(priority.value))
    if code := v.pythoncode.try_get_value():
      # init python
      self.dest.write(' python:')
      curlevel = self.indent_level
      self.indent_level += 1
      asmstr = self.stringtize_multiline_asm(code.asm.get(), False)
      if len(asmstr) == 0:
        asmstr = "pass"
      self.dest.write(self.get_eol_with_ws())
      self.dest.write(asmstr)
      self.indent_level = curlevel
    else:
      # init
      self.dest.write(':')
      self.walk_body_with_incr_level(v.body)

#  def visitRenPyTransformNode(self, v : RenPyTransformNode):
#    raise NotImplementedError()

  def visitRenPyPythonNode(self, v : RenPyPythonNode):
    # 如果没有 store/hide 且只有一行，我们使用内联的形式
    # 否则使用 python 块
    asm = v.code.get().asm.get()
    if len(asm.value) == 0:
      self.dest.write('$ # No code')
      return
    if asm.has_single_value():
      if not v.store.has_value() and not v.hide.has_value():
        self.dest.write(self.stringtize_multiline_asm(asm, True))
        return
    self.dest.write("python")
    if hide := v.hide.try_get_value():
      if hide.value:
        self.dest.write(" hide")
    if store := v.store.try_get_value():
      self.dest.write(" in " + store.get_string())
    self.dest.write(':')
    curlevel = self.indent_level
    self.indent_level += 1
    self.dest.write(self.get_eol_with_ws())
    self.dest.write(self.stringtize_multiline_asm(asm, False))
    self.indent_level = curlevel

  def visitRenPyEarlyPythonNode(self, v : RenPyEarlyPythonNode):
    assert not v.store.has_value() and not v.hide.has_value()
    asm = v.code.get().asm.get()
    if len(asm.value) == 0:
      return
    self.dest.write('python early:')
    curlevel = self.indent_level
    self.indent_level += 1
    self.dest.write(self.get_eol_with_ws())
    self.dest.write(self.stringtize_multiline_asm(asm, False))
    self.indent_level = curlevel

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
  with open(rtdest, 'w', encoding="utf-8") as dst:
    dst.write(rttitle)
    with open(rtsrc, 'r', encoding="utf-8") as src:
      all = src.read()
      dst.write(all)

  # step 2: start walking all script files
  for script in m.scripts():
    scriptpath = os.path.join(out_path, script.name + '.rpy')
    parentdir = os.path.dirname(scriptpath)
    os.makedirs(parentdir, exist_ok=True)
    with open(scriptpath, 'w', encoding="utf-8") as f:
      exporter = RenPyExportVisitor(f, indent_width=4)
      exporter.start_visit(script)

  # step 3: write all assets
  for file in m.assets():
    assetdata = file.get_asset_value()
    assert isinstance(assetdata, AssetData)
    filepath = os.path.join(out_path, file.name)
    parentdir = os.path.dirname(filepath)
    os.makedirs(parentdir, exist_ok=True)
    assetdata.export(filepath)

  # done for now
