# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import antlr4
from antlr4.error.ErrorListener import ErrorListener, ConsoleErrorListener

class ErrorListenerBase(ErrorListener):
  # since we run command scanning in every single paragraph in the input text,
  # we expect a lot of errors here and we don't want to report them
  # so we just record whether there is a failure or not and done
  _error_occurred : bool
  _error_column : int
  _error_msg : str

  def __init__(self):
    super().__init__()
    self._error_occurred = False
    self._error_column = 0
    self._error_msg = ''

  def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
    if not self._error_occurred:
      assert isinstance(column, int)
      assert isinstance(msg, str)
      self._error_occurred = True
      self._error_column = column
      self._error_msg = msg

  @property
  def error_occurred(self):
    return self._error_occurred

  def get_first_error_msg(self) -> str:
    return self._error_msg

  def get_first_error_column(self) -> int:
    return self._error_column

def setup_error_listener(parser : antlr4.Parser | antlr4.Lexer) -> ErrorListenerBase:
  err = ErrorListenerBase()
  parser.addErrorListener(err)
  parser.addErrorListener(ConsoleErrorListener())
  return err