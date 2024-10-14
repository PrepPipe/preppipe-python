# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import enum
import weakref
import tkinter as tk
import preppipe
from preppipe.language import *

_stringvar_dict : dict[Translatable, list[weakref.ref]] = {}

def get_string_var(tr : Translatable, master : tk.Widget | tk.Toplevel | None = None) -> tk.StringVar:
  result = tk.StringVar(master=master)
  result.set(tr.get())
  cur_list = None
  if tr not in _stringvar_dict:
    cur_list = []
    _stringvar_dict[tr] = cur_list
  else:
    cur_list = _stringvar_dict[tr]
  while len(cur_list) > 0:
    if cur_list[-1]() is None:
      cur_list.pop()
    else:
      break
  cur_list.append(weakref.ref(result))
  return result

def set_language(lang : str):
  Translatable.language_update_preferred_langs([lang])
  dead_trs = []
  to_shrink_trs = []
  for tr, svlist in _stringvar_dict.items():
    num_alive = 0
    num_dead = 0
    for svref in svlist:
      if sv := svref():
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
    _stringvar_dict[tr] = [svref for svref in _stringvar_dict[tr] if svref() is not None]
