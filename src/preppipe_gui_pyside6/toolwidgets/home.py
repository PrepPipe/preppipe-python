from PySide6.QtWidgets import *
from ..toolwidgetinterface import *
from ..mainwindowinterface import *
from ..forms.generated.ui_homewidget import Ui_HomeWidget

class HomeWidget(QWidget, ToolWidgetInterface):
  _tr_toolname_home = TR_gui_mainwindow.tr("toolname_home",
    en="Home",
    zh_cn="主页",
    zh_hk="主頁",
  )
  @classmethod
  def getToolInfo(cls) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="home",
      name=HomeWidget._tr_toolname_home,
      widget=cls,
    )

  def __init__(self, parent: QWidget):
    super(HomeWidget, self).__init__(parent)
    self.ui = Ui_HomeWidget()
    self.ui.setupUi(self)