import sys
import os
from PySide6.QtWidgets import QApplication
import preppipe
import preppipe.pipeline
import preppipe.pipeline_cmd
from .mainwindow import MainWindow
from .settingsdict import SettingsDict

def gui_main(settings_path : str | None = None):
  # 判断是使用 GUI 还是其他工具、管线
  is_gui_specified = False
  is_other_tool_specified = False
  if toolname := os.environ.get("PREPPIPE_TOOL"):
    if len(toolname) > 0:
      if toolname == "gui":
        is_gui_specified = True
      else:
        is_other_tool_specified = True
  if is_gui_specified or is_other_tool_specified:
    is_gui = is_gui_specified
  else:
    is_gui = len(sys.argv) == 1

  if not is_gui:
    preppipe.pipeline.pipeline_main()
    return

  if settings_path is not None:
    SettingsDict.try_set_settings_dir(settings_path)

  app = QApplication(sys.argv)
  QApplication.setOrganizationDomain("preppipe.org")
  QApplication.setOrganizationName("PrepPipe")
  QApplication.setApplicationName("PrepPipe GUI")
  MainWindow.initialize()
  window = MainWindow()
  window.show()
  app.exec()

  SettingsDict.finalize()

if __name__ == "__main__":
  gui_main()