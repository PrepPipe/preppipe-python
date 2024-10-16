# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import enum
import typing
import weakref
import tkinter as tk
import preppipe
from preppipe.language import *

_stringvar_simple_dict : dict[Translatable, tk.StringVar] = {} # Translatable -> StringVar
_object_watch_list : list[tuple[weakref.ref, typing.Callable]] = []

def get_string_var(tr : Translatable, master : tk.Widget | tk.Toplevel | None = None) -> tk.StringVar:
  if tr not in _stringvar_simple_dict:
    result = tk.StringVar(master=master)
    result.set(tr.get())
    _stringvar_simple_dict[tr] = result
    return result
  return _stringvar_simple_dict[tr]

def watch_language_change(obj : object, cb : typing.Callable):
  _object_watch_list.append((weakref.ref(obj), cb))

def set_language(lang : str):
  Translatable.language_update_preferred_langs([lang])

  for tr, sv in _stringvar_simple_dict.items():
    sv.set(tr.get())

  _object_watch_list_new = []
  for objref, cb in _object_watch_list:
    obj = objref()
    if obj is not None:
      cb()
      _object_watch_list_new.append((objref, cb))
  _object_watch_list.extend(_object_watch_list_new)
