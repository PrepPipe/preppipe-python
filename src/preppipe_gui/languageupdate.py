# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import enum
import typing
import weakref
import tkinter as tk
import preppipe
from preppipe.language import *

_stringvar_dict : dict[Translatable, list[tuple[weakref.ref, bool, dict[str, str] | None]]] = {} # Translatable -> list of (weakref to StringVar, has_master, format_args)
_stringvar_alt_list : list[tuple[weakref.ref, typing.Callable[[], str]]] = []

def get_string_var(tr : Translatable, master : tk.Widget | tk.Toplevel | None = None, format_args : dict[str, str] | None = None) -> tk.StringVar:
  # 适用于单个 Translatable 使用 get() 或 format() 的情况
  cur_list = None
  if tr not in _stringvar_dict:
    cur_list = []
    _stringvar_dict[tr] = cur_list
  else:
    cur_list = _stringvar_dict[tr]
  while len(cur_list) > 0:
    if cur_list[-1][0]() is None:
      cur_list.pop()
    else:
      break
  # 看看有没有仍然有效且所有参数都相同的 StringVar，有的话复用已有的
  if master is None:
    for svref, has_master, format_args2 in cur_list:
      if sv := svref():
        if format_args2 == format_args and not has_master:
          return sv
  result = tk.StringVar(master=master)
  result.set(tr.get())
  cur_list.append((weakref.ref(result), (master is None), format_args))
  return result

def get_string_var_alt(master : tk.Widget | tk.Toplevel | None, cb : typing.Callable[[], str]) -> tk.StringVar:
  # 适用于稍复杂的情况（比如用到了两个 Translatable）
  result = tk.StringVar(master=master)
  result.set(cb())
  _stringvar_alt_list.append((weakref.ref(result), cb))
  return result

def set_language(lang : str):
  Translatable.language_update_preferred_langs([lang])

  # 先更新 _stringvar_dict 中的内容
  dead_trs = []
  to_shrink_trs = []
  for tr, svlist in _stringvar_dict.items():
    num_alive = 0
    num_dead = 0
    for svref, has_master, format_args in svlist:
      if sv := svref():
        if format_args is not None:
          sv.set(tr.format(**format_args))
        else:
          sv.set(tr.get())
        num_alive += 1
      else:
        num_dead += 1
    if num_alive == 0:
      dead_trs.append(tr)
    elif num_dead > 0:
      to_shrink_trs.append(tr)
  for tr in dead_trs:
    del _stringvar_dict[tr]
  for tr in to_shrink_trs:
    _stringvar_dict[tr] = [svtuple for svtuple in _stringvar_dict[tr] if svtuple[0]() is not None]

  # 再更新 _stringvar_alt_list 中的内容
  _stringvar_alt_list_new = []
  for svref, cb in _stringvar_alt_list:
    if sv := svref():
      sv.set(cb())
      _stringvar_alt_list_new.append((svref, cb))
  _stringvar_alt_list.clear()
  _stringvar_alt_list.extend(_stringvar_alt_list_new)
