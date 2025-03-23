from PySide6.QtCore import *

class WaitDialog:
  # TODO
  @staticmethod
  def long_running_operation_start():
    QCoreApplication.processEvents()
