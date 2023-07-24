# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件实现在代码中内嵌多语言的翻译
# 我们想要如下独特的功能（因为 Python 自带的 gettext 没有，所以我们自己做）：
# 1. 我们想保证能够轻松在源代码中找到字符串使用的位置，不管是什么语言（所以翻译要内嵌）
# 2. 我们想让程序能够在内部找到某字段的当前所有翻译（比如读取命令时可以使用）
# 3. 我们想让用户能够自行定制所用语言的部分翻译（比如命令名要用户自行定义）
# 4. 部分用作输入的内容中，翻译要能够一对多（比如命令不止一种写法）

# 我们基本模仿 GNU 翻译的数据结构：
# 1. 每个模块都有一个翻译域，用来避免命名污染
# 2. 每段要翻译的内容都有一个独特的“译段”(Translatable)定义，包含原文和所有翻译内容

# 不过在过程上：
# 1. 所有翻译域、译段都得在初始化时创建（不一定要把翻译内容都包含进去，但一定要知道有要被翻译的东西）
# 2. 当初始化完成后（应该发生在插件读取完毕后、开始执行前），可以开始对翻译内容进行使用
#

from __future__ import annotations
import argparse
import typing
import dataclasses
import os
import locale

class TranslationDomain:
  ALL_DOMAINS : typing.ClassVar[dict[str, TranslationDomain]] = {}
  name : str
  elements : dict[str, Translatable]

  def __init__(self, name : str) -> None:
    assert isinstance(name, str) and len(name) > 0
    if name in self.ALL_DOMAINS:
      raise RuntimeError("TranslationDomain name clash:" + name)
    self.ALL_DOMAINS[name] = self
    self.name = name
    self.elements = {}

  def tr(self, code : str,
    en : str | list[str] | tuple[str], # 英语
    zh_cn : str | list[str] | tuple[str] | None = None, # 简中
    zh_hk : str | list[str] | tuple[str] | None = None, # 繁中
  ) -> Translatable:
    assert code not in self.elements
    candidates : dict[str, list[str]] = {}
    def add_lang(langcode : str, content : str | list[str] | tuple[str] | None):
      nonlocal candidates
      if content is None:
        return
      assert langcode not in candidates
      if isinstance(content, (list, tuple)):
        for s in content:
          assert isinstance(s, str)
        candidates[langcode] = list(content)
      elif isinstance(content, str):
        candidates[langcode] = [content]
      else:
        raise RuntimeError("Unexpected language expr format")
    add_lang("en",    en)
    add_lang("zh_cn", zh_cn)
    add_lang("zh_hk", zh_hk)
    result = Translatable(candidates=candidates, parent=self, code=code)
    self.elements[code] = result
    return result

  def get(self, code : str) -> Translatable:
    return self.elements[code]

  # 由于部分错误是任何地方都有可能碰到的，我们把一些常见的范式给放在这
  @property
  def assert_failure(self) -> Translatable:
    # 现在确实是 unreachable_exception，共用相同的错误信息
    return TR_preppipe.get("unreachable_exception")

  @property
  def unreachable(self) -> Translatable:
    return TR_preppipe.get("unreachable_exception")

  @property
  def not_implemented(self) -> Translatable:
    return TR_preppipe.get("not_implemented")

# 只用作基础代码的翻译内容
TR_preppipe = TranslationDomain("preppipe")

class Translatable:
  candidates : dict[str, list[str]]
  parent : TranslationDomain
  code : str

  # 这些是临时数据
  cached_str : str | None = None
  cached_allcandidates : tuple[str, ...] | None = None
  cached_ver : int # 最后一次更新 cached_str 时 PREFERRED_LANG_VER 的值

  # 以下是程序初始化时设定的
  PREFERRED_LANG : typing.ClassVar[list[str]] = []
  PREFERRED_LANG_VER : typing.ClassVar[int] = 0 # 每次修改 PREFERRED_LANG 时加1

  def __init__(self, candidates : dict[str, list[str]], parent : TranslationDomain, code : str) -> None:
    assert "en" in candidates
    self.candidates = candidates
    self.parent = parent
    self.code = code
    self.cached_str = None
    self.cached_ver = 0

  def get(self) -> str:
    if self.cached_str is not None and self.cached_ver == self.PREFERRED_LANG_VER:
      return self.cached_str
    self.flush_cache()
    for lang in self.PREFERRED_LANG:
      if lang in self.candidates:
        l = self.candidates[lang]
        if len(l) > 0:
          self.cached_str = l[0]
          return self.cached_str
    assert "en" in self.candidates
    self.cached_str = self.candidates["en"][0]
    return self.cached_str

  def get_with_msg(self, msg : str):
    # 一般用于在报错时追加部分没有翻译的错误提示
    # （只有程序内部错误的处理可以用这种方式，如果用户操作有错的话还是应该用带翻译的提示）
    result = self.get()
    if len(msg) > 0:
      result += '\n' + msg
    return result

  def get_all_candidates(self) -> tuple[str, ...]:
    if self.cached_allcandidates is not None:
      return self.cached_allcandidates
    self.flush_cache()
    resultset : set[str] = set()
    for vlist in self.candidates.values():
      for v in vlist:
        resultset.add(v)
    self.cached_allcandidates = tuple(resultset)
    return self.cached_allcandidates

  def dump(self) -> str:
    result = "TR " + self.parent.name + '.' + self.code + ":"
    for lang, l in self.candidates.items():
      result += "\n  " + lang + ": " + str(l)
    return result

  def flush_cache(self):
    self.cached_str = None
    self.cached_allcandidates = None
    self.cached_ver = self.PREFERRED_LANG_VER

  def __str__(self) -> str:
    return self.get()

  def format(self, *args : str, **kwargs : str):
    return self.get().format(*args, **kwargs)

  @staticmethod
  def _language_install_arguments(parser : argparse.ArgumentParser):
    parser.add_argument("--language", type=str, nargs=1)

  @staticmethod
  def _language_update_preferred_langs(language_list : list[str]):
    # 我们会在两个时候更新语言列表：
    # 1. 当程序刚刚启动，没有加载插件、没有读取命令行参数时
    # 2. 当程序开始初始化，加载了插件、刚刚读取完命令行参数，有可能在命令行上提供偏好的语言时
    supported_langs : dict[str, list[str]] = {
      "en" : [],
      "zh" : ["cn", "hk"],
    }
    # https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-lcid/a9eac961-e77d-41a6-90a5-ce1a8b0cdb9c
    supported_lang_alias_dict : dict[str, str | tuple[str, str]] = {
      "english" : "en",
      "chinese (simplified)"  : ("zh", "cn"),
      "chinese (traditional)" : ("zh", "hk"),
    }
    # 开始尝试初始化 Translatable.PREFERRED_LANG
    Translatable.PREFERRED_LANG.clear()
    Translatable.PREFERRED_LANG_VER += 1
    for l in language_list:
      if len(l) == 0:
        continue
      # 尝试把语言和地区标识分开
      l = l.lower().split('_')
      lang = l[0]
      region = ''
      if len(l) > 1:
        region = l[1]
      if lang not in supported_langs:
        # 看看是否有别名
        if lang in supported_lang_alias_dict:
          l = supported_lang_alias_dict[lang]
          if isinstance(l, str):
            lang = l
          else:
            lang, region = l
        else:
          # 无法识别的语言
          print("Unsupported language: " + lang)
          continue
      assert lang in supported_langs
      region_list = supported_langs[lang]
      if len(region_list) == 0:
        region = ''
      else:
        if region in region_list:
          pass
        else:
          region = region_list[0]
      final_lang_str = lang
      if len(region) > 0:
        final_lang_str = lang + '_' + region
      Translatable.PREFERRED_LANG.append(final_lang_str)

  @staticmethod
  def _init_lang_list():
    if t := locale.getlocale():
      # t 应该是类似 ('en_US', 'UTF-8') (Ubuntu) 或者 ('English_Canada', '936') (Windows) 这样的东西
      # 我们只要前一个值
      lang = t[0]
      assert isinstance(lang, str)
      Translatable._language_update_preferred_langs([lang])

  @staticmethod
  def _language_handle_arguments(parsed_args : argparse.Namespace, verbose : bool):
    # 如果命令行有提供语言，我们从命令行读取
    # 如果命令行没有提供，我们从系统中读取
    if lang := parsed_args.language:
      assert isinstance(lang, list) and len(lang) == 1
      lang_str = lang[0]
      assert isinstance(lang_str, str)
      language_list = lang_str.split(',')
      Translatable._language_update_preferred_langs(language_list)
      if verbose:
        print(Translatable._tr_lang_list.format(lang=str(Translatable.PREFERRED_LANG)))

  # 声明要在 Translatable 内，方便隐藏名称
  _tr_lang_list : typing.ClassVar[Translatable] = None

# 初始化要在外面，不然 tr() 执行的时候，Translatable 类还没有闭合，无法创建实例
Translatable._tr_lang_list = TR_preppipe.tr("lang_list",
  en="Preferred language(s): {lang}",
  zh_cn="使用语言： {lang}",
  zh_hk="使用語言： {lang}",
)

TR_preppipe.tr("unreachable_exception",
  en="An unexpected error happens and the program cannot continue. Please contact the developer to fix this.",
  zh_cn="程序遇到了程序员意料之外的情况，无法继续执行。请联系开发者来解决这个问题。",
  zh_hk="程序遇到了程序員意料之外的情況，無法繼續執行。請聯系開發者來解決這個問題。",
)
TR_preppipe.tr("not_implemented",
  en="The requested feature is not implemented and the program cannot continue. Please contact the developer to fix this.",
  zh_cn="所需的功能还没有完成，程序无法继续执行。请联系开发者来解决这个问题。",
  zh_hk="所需的功能還沒有完成，程序無法繼續執行。請聯系開發者來解決這個問題。",
)
