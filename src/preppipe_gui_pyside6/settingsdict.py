# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import sys
import os
import shelve
import threading
import collections
import collections.abc
import tempfile
from preppipe.language import *

def get_executable_base_dir() -> str:
  if getattr(sys, 'frozen', False):
    return os.path.dirname(sys.executable)
  return os.path.dirname(os.path.abspath(__file__))

class SettingsDict(collections.abc.MutableMapping):
  _executable_base_dir : typing.ClassVar[str] = get_executable_base_dir()
  _settings_instance : typing.ClassVar['SettingsDict | None'] = None

  lock : threading.Lock
  shelf : shelve.Shelf

  @staticmethod
  def instance() -> 'SettingsDict':
    if SettingsDict._settings_instance is None:
      SettingsDict._settings_instance = SettingsDict(os.path.join(SettingsDict._executable_base_dir, "preppipe_gui.settings.db"))
      if SettingsDict._settings_instance is None:
        raise RuntimeError("SettingsDict instance failed to initialize")
    return SettingsDict._settings_instance

  @staticmethod
  def finalize() -> None:
    if SettingsDict._settings_instance is not None:
      SettingsDict._settings_instance.close()
      SettingsDict._settings_instance = None

  @staticmethod
  def try_set_settings_dir(path : str) -> None:
    if SettingsDict._settings_instance is not None:
      raise RuntimeError("SettingsDict instance already exists. Cannot change settings directory after initialization")
    if getattr(sys, 'frozen', False):
      return
    SettingsDict._executable_base_dir = os.path.abspath(path)
    if not os.path.isdir(SettingsDict._executable_base_dir):
      raise FileNotFoundError(f"Path '{SettingsDict._executable_base_dir}' does not exist")

  def __init__(self, filename='settings.db'):
    self.filename = filename
    self.lock = threading.Lock()
    self.shelf = shelve.open(self.filename, writeback=True)

  def __getitem__(self, key):
    raise RuntimeError("Please use get() to properly handle missing keys (instead of raising KeyError)")
    #with self.lock:
    #  return self.shelf[key]

  def __setitem__(self, key, value):
    with self.lock:
      self.shelf[key] = value
      self.shelf.sync()

  def __delitem__(self, key):
    with self.lock:
      del self.shelf[key]
      self.shelf.sync()

  def __len__(self):
    with self.lock:
      return len(self.shelf)

  def update(self, *args, **kwargs):
    with self.lock:
      self.shelf.update(*args, **kwargs)
      self.shelf.sync()

  def get(self, key, default=None):
    with self.lock:
      return self.shelf.get(key, default)

  def close(self):
    with self.lock:
      self.shelf.close()

  def __iter__(self):
    with self.lock:
      return iter(self.shelf)

  def items(self):
    with self.lock:
      return list(self.shelf.items())

  def keys(self):
    with self.lock:
      return list(self.shelf.keys())

  def values(self):
    with self.lock:
      return list(self.shelf.values())

  def __contains__(self, key):
    with self.lock:
      return key in self.shelf

  def sync(self):
    with self.lock:
      self.shelf.sync()

  def clear(self):
    with self.lock:
      self.shelf.clear()
      self.shelf.sync()

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()

  # 为了避免循环依赖，我们在这里把其他获取当前设置值的函数放在这里
  _langs_dict = {
    "en": "English",
    "zh_cn": "中文（简体）",
    "zh_hk": "中文（繁體）",
  }
  @staticmethod
  def get_current_language() -> str:
    if inst := SettingsDict.instance():
      if lang := inst.get("language"):
        return lang
    for candidate in Translatable.PREFERRED_LANG:
      if candidate in SettingsDict._langs_dict:
        return candidate
    return "en"

  @staticmethod
  def get_current_temp_dir() -> str:
    if inst := SettingsDict.instance():
      if tempdir := inst.get("mainpipeline/temporarypath"):
        return tempdir
    return tempfile.gettempdir()
