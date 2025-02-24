import sys
from PySide6.QtWidgets import QApplication
from .mainwindow import MainWindow

def main():
  app = QApplication(sys.argv)
  QApplication.setOrganizationDomain("preppipe.org")
  QApplication.setOrganizationName("PrepPipe")
  QApplication.setApplicationName("PrepPipe GUI")
  MainWindow.initialize()
  window = MainWindow()
  window.show()
  sys.exit(app.exec())

if __name__ == "__main__":
  main()