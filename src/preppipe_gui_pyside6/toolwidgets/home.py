import functools
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from ..toolwidgetinterface import *
from ..mainwindowinterface import *
from ..guiassets import GUIAssetLoader
from ..forms.generated.ui_homewidget import Ui_HomeWidget
from .maininput import MainInputWidget
from .setting import SettingWidget

class HomeWidget(QWidget, ToolWidgetInterface):
  _tr_toolname_home = TR_gui_mainwindow.tr("toolname_home",
    en="Home",
    zh_cn="主页",
    zh_hk="主頁",
  )
  _tr_welcome_title = TR_gui_mainwindow.tr("welcome_title",
    en="Welcome to Preppipe Compiler",
    zh_cn="欢迎使用语涵编译器",
    zh_hk="歡迎使用語涵編譯器",
  )
  _tr_intro_1 = TR_gui_mainwindow.tr("intro_1",
    en="Preppipe Compiler is a visual novel development tool with simple-to-learn script format for fast prototyping and iterative development workflow. You can access the documentation by clicking the \"Help\" menu button.",
    zh_cn="语涵编译器是一个视觉小说开发工具，可使用易上手的剧本格式快速构建游戏演示，实现以快速迭代、结果导向为主的视觉小说开发流程。您可以点击“帮助”菜单按钮来打开文档。",
    zh_hk="語涵編譯器是一個視覺小說開發工具，可使用易上手的劇本格式快速構建遊戲演示，實現以快速迭代、結果導向為主的視覺小說開發流程。您可以點擊“幫助”菜單按鈕來打開文檔。",
  )
  _tr_intro_2 = TR_gui_mainwindow.tr("intro_2",
    en="PrepPipe Compiler requires a separate visual novel engine to run the generated game. The output of this program is the game project files for your specified engine. You can find the list of supported engines in the documentation. If you have a custom game engine, you can write a plugin to support it; please refer to the documentation for more information.",
    zh_cn="语涵编译器需要一个独立的视觉小说引擎来运行生成的游戏。本程序的输出是您指定引擎的游戏工程文件。您可以在文档中找到支持的引擎列表。自制游戏引擎可以通过编写插件进行支持，详情请见文档。",
    zh_hk="語涵編譯器需要一個獨立的視覺小說引擎來運行生成的遊戲。本程序的輸出是您指定引擎的遊戲工程文件。您可以在文檔中找到支持的引擎列表。自製遊戲引擎可以通過編寫插件進行支持，詳情請見文檔。",
  )
  _tr_main_functionality_entrypoint = TR_gui_mainwindow.tr("main_functionality_entrypoint",
    en="Main Features Entry",
    zh_cn="主要功能入口",
    zh_hk="主要功能入口",
  )
  BASE_TOOLS = [
    MainInputWidget,
    SettingWidget,
  ]
  @classmethod
  def getToolInfo(cls) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="home",
      name=HomeWidget._tr_toolname_home,
      widget=cls,
      uniquelevel=ToolWidgetUniqueLevel.SINGLE_INSTANCE,
    )

  def __init__(self, parent: QWidget):
    super(HomeWidget, self).__init__(parent)
    self.ui = Ui_HomeWidget()
    self.ui.setupUi(self)
    self.bind_text(self.ui.welcomeTitleLabel.setText, self._tr_welcome_title)
    self.bind_text(self.ui.intro1Label.setText, self._tr_intro_1)
    self.bind_text(self.ui.intro2Label.setText, self._tr_intro_2)
    self.bind_text(self.ui.mainEntryGroupBox.setTitle, self._tr_main_functionality_entrypoint)
    self.build_entry_groupbox(self.ui.mainEntryGroupBox, HomeWidget.BASE_TOOLS)

  def build_entry_groupbox(self, group : QGroupBox, entry_list : list):
    layout = QFormLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    group.setLayout(layout)
    for i, entry in enumerate(entry_list):
      name = None
      icon = None
      slot = None
      desc = None
      if isinstance(entry, type) and issubclass(entry, ToolWidgetInterface):
        entryinfo = entry.getToolInfo()
        name = entryinfo.name
        icon = entryinfo.icon_path
        slot = functools.partial(lambda entryinfo: MainWindowInterface.getHandle(self).requestOpen(entryinfo), entryinfo)
        desc = entryinfo.tooltip
      else:
        raise NotImplementedError("Entry type not supported")
      if name is None:
        raise RuntimeError("Entry name not set")
      if desc is None:
        desc = name
      button = QPushButton(name.get())
      if icon is not None:
        if iconpath := GUIAssetLoader.try_get_asset_path(icon):
          icon = QIcon(iconpath)
          button.setIcon(QIcon(icon))
          button.setIconSize(QSize(64, 64))
      button.clicked.connect(slot)
      button.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
      desc_label = QLabel(desc.get())
      desc_label.setWordWrap(True)
      layout.addRow(button, desc_label)
      self.bind_text(button.setText, name)
      self.bind_text(desc_label.setText, desc)
