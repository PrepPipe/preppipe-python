from preppipe.language import *
from .toolwidgetinterface import *

# 部分内容不止在 MainWindow 中使用，所以放在这里
TR_gui_mainwindow = TranslationDomain("gui_mainwindow")

class MainWindowInterface:
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def requestOpen(self, info : ToolWidgetInfo) -> None:
    raise NotImplementedError("Subclasses must implement the addTab() method.")

  def requestOpenWithType(self, widget : type[ToolWidgetInterface]) -> None:
    info = widget.getToolInfo()
    self.requestOpen(info)

  def requestOpenDocument(self, relpath : str | None) -> None:
    raise NotImplementedError("Subclasses must implement the requestOpenDocument() method.")

  def handleLanguageChange(self) -> None:
    raise NotImplementedError("Subclasses must implement the handleLanguageChange() method.")

  tr_toolname_maininput = TR_gui_mainwindow.tr("toolname_maininput",
    en="Main Pipeline Entry",
    zh_cn="主管线入口",
    zh_hk="主管線入口",
  )
  tr_toolname_analysis = TR_gui_mainwindow.tr("toolname_analysis",
    en="Analysis Tools",
    zh_cn="分析工具",
    zh_hk="分析工具",
  )
  tr_toolname_export_renpy = TR_gui_mainwindow.tr("toolname_export_renpy",
    en="Ren'Py Export",
    zh_cn="Ren'Py 导出",
    zh_hk="Ren'Py 導出",
  )
  tr_toolname_export_webgal = TR_gui_mainwindow.tr("toolname_export_webgal",
    en="WebGal Export",
    zh_cn="WebGal 导出",
    zh_hk="WebGal 導出",
  )
