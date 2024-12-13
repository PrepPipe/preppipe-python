import typing
import types
import enum
import argparse
import inspect
import decimal
import os

import preppipe
import preppipe.pipeline_cmd
import preppipe.pipeline
import preppipe.irbase
import preppipe.inputmodel
import preppipe.frontend.commandsyntaxparser
import preppipe.frontend.commandsemantics
import preppipe.frontend.vnmodel.vnparser
import preppipe.language
import preppipe.nameresolution

# 本脚本用于将注册在前端的命令以及所用的翻译等信息全都扒出来，用于文档生成
# 我们需要生成两份内容：
# 1. 生成在 Doxygen 页面中的命令说明，偏程序员
# 2. 生成在 用户文档中的说明，偏用户
# 我们在这里维护（不包含在语涵编译器主程序 wheel 内的）命令文档

class OutputDestKind(enum.Enum):
  DOXYGEN = 0
  USER_LATEX = enum.auto()
  USER_MARKDOWN = enum.auto()

class FrontendCommandDumper:
  TR : preppipe.language.TranslationDomain = preppipe.language.TranslationDomain("ext_docs_frontend")
  _tr_cmdref = TR.tr("cmdref",
    en="Frontend Command Reference",
    zh_cn="前端命令列表",
    zh_hk="前端命令列表",
    )
  _tr_cmdstart = TR.tr("cmdstart",
    en='[',
    zh_cn="【",
    zh_hk="【",
  )
  _tr_cmdend = TR.tr("cmdend",
    en=']',
    zh_cn="】",
    zh_hk="】",
  )
  # 英文版需要后面加个空格
  _tr_cmd_namesep = TR.tr("cmdnamesep",
    en=": ",
    zh_cn="：",
    zh_hk="：",
  )
  _tr_cmd_paramsep = TR.tr("cmdsep",
    en=", ",
    zh_cn="，",
    zh_hk="，",
  )
  # 等号和井号(=,#)一般都是半角，不需要额外的版本
  _tr_no_docs = TR.tr("nodocs",
    en="No documentation available at this moment.",
    zh_cn="暂无文档",
    zh_hk="暫無文檔",
  )
  _tr_additiona_keywords = TR.tr("additional_keywords",
    en="Additional keywords used by the command:",
    zh_cn="命令使用了以下额外关键字：",
    zh_hk="命令使用了以下額外關鍵字：",
  )

  def get_command_ns(self) -> preppipe.frontend.commandsemantics.FrontendCommandNamespace:
    raise NotImplementedError()
  def run_pipeline(self)->None:
    raise NotImplementedError()
  def get_parser_type(self) -> typing.Type[preppipe.frontend.commandsemantics.FrontendParserBase]:
    raise NotImplementedError()
  def get_title(self) -> preppipe.language.Translatable:
    return FrontendCommandDumper._tr_cmdref
  def get_docs(self, cmdname : str) -> preppipe.language.Translatable:
    return self._tr_no_docs
  def get_additional_docs_doxygen(self, cmdname : str) -> preppipe.language.Translatable | None:
    return None

  LATEX_ESCAPES = {
    '#': "\\#",
    '$': "\\$",
    '%': "\\%",
    '&': "\\&",
    '^': r"\\textasciicircum{}",
    '_': "\\_",
    '{': "\\{",
    '}': "\\}",
    '~': r"\\textasciitilde{}",
  }

  def escape_str_latex(self, s : str):
    s = s.replace('\\', r"\\textbackslash{}")
    for k, v in self.LATEX_ESCAPES.items():
      s = s.replace(k, v)
    return s

  def escape_str_doxygen(self, s : str):
    # TODO
    return s

  def escape_str_markdown(self, s : str):
    # TODO
    return s

  _tr_extarg_list = TR.tr("extarg_list",
    en="List",
    zh_cn="列表",
    zh_hk="列表",
  )
  _tr_extarg_specialblock = TR.tr("extarg_specialblock",
    en="Special Block",
    zh_cn="特殊块",
    zh_hk="特殊塊",
  )
  _tr_extarg_table = TR.tr("extarg_table",
    en="Table",
    zh_cn="表格",
    zh_hk="表格",
  )
  _tr_extarg_general = TR.tr("extarg_general",
    en="Extended Argument",
    zh_cn="拓展参数",
    zh_hk="拓展參數",
  )
  _tr_extarg_sep = TR.tr("extarg_sep",
    en=" or ",
    zh_cn="或",
    zh_hk="或",
  )
  _tr_default_value = TR.tr("default_value",
    en="Default: ",
    zh_cn="默认值：",
    zh_hk="默認值：",
  )
  _tr_optional = TR.tr("optional",
    en="optional",
    zh_cn="可选",
    zh_hk="可選"
  )
  _tr_vtype_callexpr = TR.tr("vtype_callexpr",
    en="Call expression",
    zh_cn="调用表达式",
    zh_hk="調用表達式",
  )
  _tr_vtype_str = TR.tr("vtype_str",
    en="String",
    zh_cn="字符串",
    zh_hk="字符串",
  )
  _tr_vtype_float = TR.tr("vtype_float",
    en="Floating-point number",
    zh_cn="浮点数",
    zh_hk="浮點數",
  )
  _tr_vtype_int = TR.tr("vtype_int",
    en="Integer",
    zh_cn="整数",
    zh_hk="整數",
  )
  _tr_vtype_list = TR.tr("vtype_list",
    en="1-N of {{" + "{inner}" + "}}",
    zh_cn="1到N个{{" + "{inner}" + "}}",
    zh_hk="1到N個{{" + "{inner}" + "}}",
  )
  _tr_vtype_image = TR.tr("vtype_image",
    en="Embedded Image",
    zh_cn="内嵌图片",
    zh_hk="內嵌圖片",
  )
  _tr_vtype_audio = TR.tr("vtype_audio",
    en="Embedded Audio",
    zh_cn="内嵌音频",
    zh_hk="內嵌音頻",
  )
  _tr_any = TR.tr("any",
    en="Any content",
    zh_cn="任意内容",
    zh_hk="任意內容",
  )

  def check_is_extended_arg(self, a) -> preppipe.language.Translatable | None:
    if issubclass(a, preppipe.frontend.commandsemantics.ExtendDataExprBase):
      if issubclass(a, preppipe.frontend.commandsemantics.ListExprOperand):
        return self._tr_extarg_list
      if issubclass(a, preppipe.frontend.commandsemantics.SpecialBlockOperand):
        return self._tr_extarg_specialblock
      if issubclass(a, preppipe.frontend.commandsemantics.TableExprOperand):
        return self._tr_extarg_table
      return self._tr_extarg_general
    raise RuntimeError("Unexpected annotation: "+str(a))
    return None

  def get_type_annotation_str_impl(self, a, enumtr_list : list) -> str:
    if isinstance(a, types.UnionType):
      params = [self.get_type_annotation_str_impl(candidate, enumtr_list) for candidate in a.__args__ if candidate is not None]
      return self._tr_extarg_sep.get().join(params)
    elif isinstance(a, types.GenericAlias) or isinstance(a, typing._GenericAlias):
      if a.__origin__ != list:
        # 我们只支持 list ，不支持像是 dict 等
        raise RuntimeError('Generic alias for non-list types not supported')
      if len(a.__args__) != 1:
        # list[str] 可以， list[int | str] 可以， list[int, str] 不行
        raise RuntimeError('List type should have exactly one argument specifying the element type (can be union though)')
      inner = self.get_type_annotation_str_impl(a.__args__[0], enumtr_list)
      return self._tr_vtype_list.format(inner=inner)
    elif a is typing.Any:
      return self._tr_any.get()
    if isinstance(a, type):
      if issubclass(a, preppipe.frontend.commandsemantics.CallExprOperand):
        return self._tr_vtype_callexpr.get()
      if issubclass(a, (preppipe.irbase.StringLiteral, str)):
        return self._tr_vtype_str.get()
      if issubclass(a, (preppipe.irbase.FloatLiteral, decimal.Decimal, float)):
        return self._tr_vtype_float.get()
      if issubclass(a, (preppipe.irbase.IntLiteral, int)):
        return self._tr_vtype_int.get()
      if issubclass(a, preppipe.irbase.ImageAssetData):
        return self._tr_vtype_image.get()
      if issubclass(a, preppipe.irbase.AudioAssetData):
        return self._tr_vtype_audio.get()
      if issubclass(a, enum.Enum):
        trdict : dict[str, preppipe.language.Translatable] = getattr(a, "_translation_src")
        options = []
        for name, enumtr in trdict.items():
          options.append('"' + '","'.join(enumtr.get_current_candidates()) + '"')
          enumtr_list.append(enumtr)
        return '|'.join(options)
    raise NotImplementedError(str(a))

  def get_default_value_str(self, v) -> str:
    if isinstance(v, enum.Enum):
      # 如果是枚举值的话，尝试使用带翻译的名称
      trdict : dict[str, preppipe.language.Translatable] = getattr(type(v), "_translation_src")
      enumtr = trdict[v.name]
      return '"' + enumtr.get() + '"'
    return str(v)

  def get_type_annotation_as_str(self, a, default, enumtr_list : list) -> tuple[str | None, bool]:
    if a is None:
      return (None, False)

    # 第一个返回值是关于该标注的字符串类型的描述，第二个返回值指定这是否是拓展参数
    # 首先判断是否是拓展参数，对其特判
    l = preppipe.frontend.commandsemantics.FrontendParserBase.check_is_extend_data(a)
    if len(l) > 0:
      trlist = [self.check_is_extended_arg(t) for t in l]
      s = self._tr_extarg_sep.get().join([t.get() for t in trlist if t is not None])
      if default != inspect.Parameter.empty:
        s = self._tr_optional.get() + self._tr_cmd_namesep.get() + s
      return (s, True)
    # 剩下的情况下都不是拓展参数
    # 先排除几个特殊情况
    if isinstance(a, type) and issubclass(a, preppipe.frontend.commandsemantics.FrontendParserBase):
      return (None, False)
    if a == self.get_parser_type().get_state_type():
      return (None, False)
    if a in (preppipe.frontend.commandsyntaxparser.GeneralCommandOp,
             preppipe.irbase.Context):
      return (None, False)
    # 应该不是特殊情况而是正常参数了
    s = self.get_type_annotation_str_impl(a, enumtr_list)
    if default != inspect.Parameter.empty:
      if default is None:
        s = '<' + s + self._tr_cmd_paramsep.get() + self._tr_optional.get() + '>'
      else:
        s = '<' + s + self._tr_cmd_paramsep.get() + self._tr_default_value.get() + self.get_default_value_str(default) + '>'
    else:
      s = '<' + s + '>'
    return (s, False)

  _tr_cmd_invocation = TR.tr("cmd_invocation",
    en="Command Invocation",
    zh_cn="命令调用",
    zh_hk="命令調用",
  )
  _tr_cmd_docs = TR.tr("cmd_docs",
    en="Description",
    zh_cn="说明",
    zh_hk="說明",
  )
  _tr_cmd_tr = TR.tr("cmd_tr",
    en="Translation & Aliasing",
    zh_cn="翻译、别名项",
    zh_hk="翻譯、別名项",
  )
  _tr_cmd_tr_cmdname = TR.tr("cmd_tr_cmdname",
    en="Command Name ({name}): ",
    zh_cn="命令名（{name}）：",
    zh_hk="命令名（{name}）：",
  )
  _tr_cmd_tr_cmdname_noentry = TR.tr("cmd_tr_cmdname_noentry",
    en="(Command name has no entry yet and cannot customize.)",
    zh_cn="（命令名暂无翻译项，无法修改。）",
    zh_hk="（命令名暫無翻譯項，無法修改。）",
  )
  _tr_cmd_tr_params = TR.tr("cmd_tr_params",
    en="Parameter(s):",
    zh_cn="参数：",
    zh_hk="參數：",
  )
  _tr_cmd_tr_additional_keywords = TR.tr("cmd_tr_additional_keywords",
    en="Additional Keyword(s):",
    zh_cn="额外关键字：",
    zh_hk="額外關鍵字：",
  )
  _tr_cmd_uncategorized = TR.tr("cmd_uncategorized",
    en="Uncategorized",
    zh_cn="未分类",
    zh_hk="未分類",
  )

  # 这个后缀只为了在同时包含多个语言的页面时不至于起冲突
  pageref_suffix : str

  # 如果需要使用指定的标题的话，应该在这
  title_override : str | None

  # 如果未指定标题，用自带的标题且需要添加语言结尾（用来避免同时包含相同内容不同语言时出错），则设置此标记
  flag_title_add_language_suffix : bool

  def __init__(self):
    self.pageref_suffix = ''
    self.title_override = None
    self.flag_title_add_language_suffix = False

  def collect_docs(self, dest: OutputDestKind) -> str:
    ns = self.get_command_ns()
    rows = []

    def add_row(s : str):
      rows.append(s)

    def add_paragraph(s : str):
      rows.append('')
      rows.append(s)

    def get_tr_path(t : preppipe.language.Translatable):
      return t.parent.name + '/' + t.code

    def stringtize_tr(tr : preppipe.language.Translatable)->str:
      return '|'.join(tr.get_current_candidates())

    def add_list(l : list[preppipe.language.Translatable | tuple[preppipe.language.Translatable, list]], level: int, dump_tr_path : bool = False):
      nonlocal rows
      if len(l) == 0:
        return
      match dest:
        case OutputDestKind.DOXYGEN:
          pass
        case OutputDestKind.USER_LATEX:
          add_row('  '*level + r"\\begin{itemize}")
        case OutputDestKind.USER_MARKDOWN:
          # 添加空白行以开启新段落
          add_row('')
        case _:
          raise NotImplementedError()
      for v in l:
        if isinstance(v, preppipe.language.Translatable):
          s = stringtize_tr(v)
          if dump_tr_path:
            s += ': ' + get_tr_path(v)
          match dest:
            case OutputDestKind.DOXYGEN:
              add_row('  '*(level+1) + '- ' + s)
            case OutputDestKind.USER_LATEX:
              add_row('  '*level + "\\item" + s)
            case OutputDestKind.USER_MARKDOWN:
              add_row('  '*(level+1) + '* ' + s)
            case _:
              raise NotImplementedError()
        elif isinstance(v, tuple):
          head, inner = v
          s = stringtize_tr(head)
          if dump_tr_path:
            s += ': ' + get_tr_path(head)
          match dest:
            case OutputDestKind.DOXYGEN:
              add_row('  '*(level+1) + '- ' + s)
              add_list(inner, level+1, dump_tr_path)
            case OutputDestKind.USER_LATEX:
              add_row('  '*level + "\\item" + s)
              add_list(inner, level+1, dump_tr_path)
            case OutputDestKind.USER_MARKDOWN:
              add_row('  '*(level+1) + '* ' + s)
              add_list(inner, level+1, dump_tr_path)
            case _:
              raise NotImplementedError()
        else:
          raise NotImplementedError()
      match dest:
        case OutputDestKind.DOXYGEN:
          pass
        case OutputDestKind.USER_LATEX:
          add_row('  '*level + r"\\end{itemize}")
        case OutputDestKind.USER_MARKDOWN:
          add_row('')
        case _:
          pass

    pageref = "cmdref_" + '_'.join([s.strip() for s in ns.get_namespace_path()])
    if len(self.pageref_suffix) > 0:
      pageref += '_' + self.pageref_suffix
    if self.title_override is not None:
      final_title = self.title_override
    else:
      final_title = self.get_title().get()
      if self.flag_title_add_language_suffix:
        final_title += ' (' + self.pageref_suffix + ')'
    match dest:
      case OutputDestKind.DOXYGEN: # .dox file
        add_row("/*!")
        add_row("\\page " + pageref + ' ' + final_title)
      case OutputDestKind.USER_LATEX: # .tex file
        add_row("\\section{" + final_title + "}\\label{" + "sec:" + pageref + "}")
      case OutputDestKind.USER_MARKDOWN: # .md file
        add_row("# " + final_title)
      case _:
        raise NotImplementedError()

    items_by_category : list[tuple[str, list[preppipe.frontend.commandsemantics.FrontendCommandInfo]]] = []
    unknown_category_items : list[preppipe.frontend.commandsemantics.FrontendCommandInfo] = []

    if ns._expanded_category_tree is not None:
      category_index_dict : dict[int, list[preppipe.frontend.commandsemantics.FrontendCommandInfo]] = {}
      for k, v in ns.items():
        kind, data = v
        match kind:
          case preppipe.nameresolution.NamespaceNode.NameResolutionDataEntryKind.CanonicalEntry:
            assert isinstance(data, preppipe.frontend.commandsemantics.FrontendCommandInfo)
            assert data.cname == k
            if data.category_index is None:
              unknown_category_items.append(data)
            else:
              if data.category_index < 0:
                # 这一项应该隐藏
                continue
              if data.category_index not in category_index_dict:
                category_index_dict[data.category_index] = []
              category_index_dict[data.category_index].append(data)
          case _:
            continue
      for index in range(0, len(ns._expanded_category_tree)):
        category_label = '/'.join([s.get() if isinstance(s, preppipe.language.Translatable) else s for s in ns._expanded_category_tree[index]])
        category_items = category_index_dict[index] if index in category_index_dict else []
        items_by_category.append((category_label, category_items))
    else:
      # 没有分类信息，全部塞到 unknown_category_items 中
      for k, v in ns.items():
        kind, data = v
        match kind:
          case preppipe.nameresolution.NamespaceNode.NameResolutionDataEntryKind.CanonicalEntry:
            assert isinstance(data, preppipe.frontend.commandsemantics.FrontendCommandInfo)
            assert data.cname == k
            if data.category_index is not None and data.category_index < 0:
              # 这一项应该隐藏
              continue
            unknown_category_items.append(data)
          case _:
            continue
    if len(unknown_category_items) > 0:
      items_by_category.append((self._tr_cmd_uncategorized.get(), unknown_category_items))

    def start_part(part_name : str, part_ref : str):
      add_row('')
      match dest:
        case OutputDestKind.DOXYGEN:
          add_row("\\paragraph " + part_ref + ' ' + part_name)
        case OutputDestKind.USER_LATEX:
          add_row("\\paragraph{" + part_name + "}\\label{" + "sec:" + part_ref + "}")
        case OutputDestKind.USER_MARKDOWN:
          add_row("#### " + part_name)
        case _:
          raise NotImplementedError()

    for category_index, (category_label, items) in enumerate(items_by_category):
      add_row('')
      category_ref = pageref + '_c' + str(category_index)
      match dest:
        case OutputDestKind.DOXYGEN:
          add_row("\\section " + category_ref + ' ' + category_label)
        case OutputDestKind.USER_LATEX:
          add_row("\\subsection{" + category_label + "}\\label{" + "sec:" + category_ref + "}")
        case OutputDestKind.USER_MARKDOWN:
          add_row("## " + category_label)
        case _:
          raise NotImplementedError()

      for data in items:
        cmdsecref = category_ref + '_' + data.cname
        if data.name_tr is not None:
          fmtname = data.name_tr.get()
          all_cmdnames = data.name_tr.get_current_candidates()
        else:
          fmtname = data.cname
          all_cmdnames = [data.cname]

        add_row('')
        match dest:
          case OutputDestKind.DOXYGEN:
            add_row("\\subsection " + cmdsecref + ' ' + fmtname)
          case OutputDestKind.USER_LATEX:
            add_row("\\subsubsection{" + fmtname + "}\\label{" + "sec:" + cmdsecref + "}")
          case OutputDestKind.USER_MARKDOWN:
            add_row("### " + fmtname)
          case _:
            raise NotImplementedError()

        # 先把命令声明部分写清
        part_name = self._tr_cmd_invocation.get()
        part_ref = cmdsecref + '_cmd'
        start_part(part_name, part_ref)
        enumtr_list = []
        # 假设命令是 [命令1：参数1，参数2]，我们把 handler_list 中各项的参数都匹配上去
        # 如果命令名有多个名称（有可能），我们将后面的内容全都复制相应遍数
        # 如果命令参数有多个名称（几乎没有），我们用括号把所有备选项括起来
        # 命令主体部分写完之后再加
        handler_index = 0
        used_pnames : list[str] = []
        for cb, sig in data.handler_list:
          param_str = []
          handler_index += 1
          is_take_extended_arg : str | None = None
          for p in sig.parameters.values():
            # 名字(名字2，...) = <类型>
            pname = p.name
            if pname in data.param_tr:
              if pname not in used_pnames:
                used_pnames.append(pname)
              pname = stringtize_tr(data.param_tr[pname])
            typestr = "<?>"
            if p.annotation is not None:
              typestr, isextarg = self.get_type_annotation_as_str(p.annotation, p.default, enumtr_list)
              if typestr is None:
                # 如果该参数不是由用户提供的，我们在这里跳过这项参数
                continue
              elif isextarg is True:
                # 这是一个拓展参数项
                is_take_extended_arg = typestr
                continue
            param_str.append(pname + '=' + typestr)
          body = self._tr_cmd_paramsep.get().join(param_str)
          for cname in all_cmdnames:
            cur_str = self._tr_cmdstart.get() + cname
            if len(body) > 0:
              cur_str += self._tr_cmd_namesep.get() + body
            cur_str += self._tr_cmdend.get()
            if is_take_extended_arg:
              cur_str += " (+" + is_take_extended_arg + ')'
            add_paragraph(cur_str)
        # 如果命令有引用额外的关键字，我们以树状结构把它们排上
        if data.additional_keywords is not None and len(data.additional_keywords) > 0:
          add_paragraph(self._tr_additiona_keywords.get())
          add_list(data.additional_keywords, 0, False)

        docs = self.get_docs(data.cname)
        docs_text = [s.strip() for s in docs.get().splitlines()]

        # 详细介绍部分
        part_name = self._tr_cmd_docs.get()
        part_ref = cmdsecref + '_docs'
        start_part(part_name, part_ref)
        match dest:
          case OutputDestKind.DOXYGEN:
            for row in docs_text:
              add_paragraph(self.escape_str_doxygen(row))
            if additional := self.get_additional_docs_doxygen(data.cname):
              add_row(additional.get())
          case OutputDestKind.USER_LATEX:
            for row in docs_text:
              add_paragraph(self.escape_str_latex(row))
          case OutputDestKind.USER_MARKDOWN:
            for row in docs_text:
              add_paragraph(self.escape_str_markdown(row))
          case _:
            rows.extend(docs_text)
            add_row('')

        # 翻译、别名部分
        part_name = self._tr_cmd_tr.get()
        part_ref = cmdsecref + '_tr'
        start_part(part_name, part_ref)
        # 首先是命令名
        if data.name_tr is not None:
          cur_str = self._tr_cmd_tr_cmdname.format(name=self._tr_cmd_paramsep.get().join(all_cmdnames)) + get_tr_path(data.name_tr)
        else:
          cur_str = self._tr_cmd_tr_cmdname_noentry.get()
        add_paragraph(cur_str)
        # 然后是所有参数
        if len(used_pnames) > 0 or len(enumtr_list) > 0:
          add_paragraph(self._tr_cmd_tr_params.get())
          if len(used_pnames) > 0:
            add_list([data.param_tr[pname] for pname in used_pnames], 0, True)
          if len(enumtr_list) > 0:
            add_list(enumtr_list, 0, True)
        # 再然后是额外关键字
        if data.additional_keywords is not None and len(data.additional_keywords) > 0:
          add_paragraph(self._tr_cmd_tr_additional_keywords.get())
          add_list(data.additional_keywords, 0, True)
        # 结束命令
        match dest:
          case OutputDestKind.DOXYGEN:
            add_row('')
          case OutputDestKind.USER_LATEX:
            add_row('')
          case OutputDestKind.USER_MARKDOWN:
            add_row('')
          case _:
            raise NotImplementedError()
      # 当前类别所有命令处理完毕
    # 结束文件
    match dest:
      case OutputDestKind.DOXYGEN:
        add_row('*/')
      case _:
        pass
    add_row('')
    return '\n'.join(rows)


_DUMPERS : dict[str, typing.Type[FrontendCommandDumper]] = {}

def NSDecl(flag : str):
  def decorator_dumper(cls : typing.Type[FrontendCommandDumper]):
    _DUMPERS[flag] = cls
    return cls
  return decorator_dumper

@NSDecl("vn")
class _VNFrontendCommandDumper(FrontendCommandDumper):
  def get_command_ns(self):
    return preppipe.frontend.vnmodel.vnparser.vn_command_ns

  def run_pipeline(self):
    preppipe.pipeline.pipeline_main([
      "--test",
      "--vnparse"
    ])

  def get_parser_type(self):
    return preppipe.frontend.vnmodel.vnparser.VNParser

  tr : preppipe.language.TranslationDomain = preppipe.language.TranslationDomain("ext_docs_vn")

  tr.tr("Comment",
        en="Comments",zh_cn="内嵌注释")

  _tr_title = tr.tr("title",
    en="Visual Novel Commands Listing",
    zh_cn="视觉小说命令列表",
    zh_hk="視覺小說命令列表",
  )

  def get_title(self) -> preppipe.pipeline.Translatable:
    return self._tr_title

  def get_docs(self, cmdname: str) -> preppipe.language.Translatable:
    if doc := self.tr.elements.get(cmdname):
      return doc
    return super().get_docs(cmdname)

def _main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--namespace", type=str, choices=_DUMPERS.keys(), required=True)
  parser.add_argument("--title", type=str, nargs=1)
  parser.add_argument("--doxygen", type=str, nargs=1)
  parser.add_argument("--latex", type=str, nargs=1)
  parser.add_argument("--markdown", type=str, nargs=1)
  parser.add_argument("--add-language-suffix-in-title", type=bool, default=False)
  args = parser.parse_args()
  doxygen_path : str | None = None
  latex_path : str | None = None
  markdown_path : str | None = None
  is_output_set = False
  if args.doxygen:
    doxygen_path = args.doxygen[0]
    assert isinstance(doxygen_path, str)
    is_output_set = True
  if args.latex:
    latex_path = args.latex[0]
    assert isinstance(latex_path, str)
    is_output_set = True
  if args.markdown:
    markdown_path = args.markdown[0]
    assert isinstance(markdown_path, str)
    is_output_set = True
  if not is_output_set:
    parser.print_usage()
    return
  cls = _DUMPERS[args.namespace]
  dumper = cls()
  if lang := os.environ.get("PREPPIPE_LANGUAGE"):
    dumper.pageref_suffix = lang
    assert isinstance(dumper.pageref_suffix, str)
  if args.title:
    dumper.title_override = args.title[0]
    assert isinstance(dumper.title_override, str)
  if doxygen_path:
    res = dumper.collect_docs(OutputDestKind.DOXYGEN)
    with open(doxygen_path, 'w', encoding="utf-8") as f:
      f.write(res)
  if latex_path:
    res = dumper.collect_docs(OutputDestKind.USER_LATEX)
    with open(latex_path, 'w', encoding="utf-8") as f:
      f.write(res)
  if markdown_path:
    res = dumper.collect_docs(OutputDestKind.USER_MARKDOWN)
    with open(markdown_path, 'w', encoding="utf-8") as f:
      f.write(res)

if __name__ == "__main__":
  _main()
