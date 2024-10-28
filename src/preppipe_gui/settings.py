# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import sys
import os
import shelve
import threading
import collections
import collections.abc

_bundle_dir = '.'
if getattr(sys, 'frozen', False):
  # we are running in a bundle
  _bundle_dir = sys._MEIPASS # type: ignore
else:
  # we are running in a normal Python environment
  _bundle_dir = os.path.dirname(os.path.abspath(__file__))

def get_bundle_dir() -> str:
  return _bundle_dir

class SettingsDict(collections.abc.MutableMapping):
  _settings_file_path : typing.ClassVar[str] = os.path.join(_bundle_dir, "preppipe_gui.settings.db")
  _settings_instance : typing.ClassVar['SettingsDict | None'] = None

  lock : threading.Lock
  shelf : shelve.Shelf

  @staticmethod
  def instance():
    if SettingsDict._settings_instance is None:
      SettingsDict._settings_instance = SettingsDict(SettingsDict._settings_file_path)
    return SettingsDict._settings_instance

  @staticmethod
  def finalize() -> None:
    if SettingsDict._settings_instance is not None:
      SettingsDict._settings_instance.close()
      SettingsDict._settings_instance = None

  def __init__(self, filename='settings.db'):
    self.filename = filename
    self.lock = threading.Lock()
    self.shelf = shelve.open(self.filename, writeback=True)

  def __getitem__(self, key):
    with self.lock:
      return self.shelf[key]

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
