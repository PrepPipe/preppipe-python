# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import enum
import time
import threading

class MessageHandler:
  class MessageImportance(enum.Enum):
    Error = enum.auto()
    CriticalWarning = enum.auto()
    Warning = enum.auto()
    Info = enum.auto()

    def get_short_name(self):
      match self:
        case MessageHandler.MessageImportance.Error:
          return "E"
        case MessageHandler.MessageImportance.CriticalWarning:
          return "C"
        case MessageHandler.MessageImportance.Warning:
          return "W"
        case MessageHandler.MessageImportance.Info:
          return "I"
        case _:
          return "?" # should not happen

  _instance = None
  _starttime = time.time()
  _mutex = threading.Lock()

  @staticmethod
  def install_message_handler(handler):
    # subclass MessageHandler and call this function to install the handler
    assert isinstance(handler, MessageHandler)
    MessageHandler._instance = handler

  def message(self, importance : MessageImportance, msg : str, file : str = "", location: str = ""):
    # usually the location string contains the file path
    # use location if available
    MessageHandler._mutex.acquire()
    curtime = time.time()
    locstring = ""
    if len(location) > 0:
      locstring = location
    elif len(file) > 0:
      locstring = file

    if len(locstring) > 0:
      locstring += ': '

    print("[{time:.3f} {imp}] {loc}{msg}".format(time=(curtime - MessageHandler._starttime), imp=importance.get_short_name(), loc=locstring, msg=msg), flush=True)
    MessageHandler._mutex.release()

  @staticmethod
  def get():
    if MessageHandler._instance is None:
      MessageHandler._instance = MessageHandler()
    return MessageHandler._instance

  @staticmethod
  def info(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageHandler.MessageImportance.Info, msg, file, location)

  @staticmethod
  def warning(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageHandler.MessageImportance.Warning, msg, file, location)

  @staticmethod
  def critical_warning(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageHandler.MessageImportance.CriticalWarning, msg, file, location)

  @staticmethod
  def error(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageHandler.MessageImportance.Error, msg, file, location)
