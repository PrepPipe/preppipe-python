from PySide6.QtCore import *

from preppipe.language import *
from ..forms.generated.ui_settingwidget import Ui_SettingWidget
from ..toolwidgetinterface import *
from ..mainwindowinterface import *
from ..settingsdict import *

TR_gui_setting = TranslationDomain("gui_setting")

class SettingWidget(QWidget, ToolWidgetInterface):
  ui : Ui_SettingWidget

  _tr_tab_general = TR_gui_setting.tr("tab_general",
    en="General",
    zh_cn="通用",
    zh_hk="通用",
  )
  _tr_general_language = TR_gui_setting.tr("general_language",
    en="Language",
    zh_cn="语言",
    zh_hk="語言",
  )
  _tr_general_debug = TR_gui_setting.tr("general_debug",
    en="Generate Debug Outputs",
    zh_cn="生成调试输出",
    zh_hk="生成調試輸出",
  )
  _tr_general_debug_desc = TR_gui_setting.tr("general_debug_desc",
    en="Enable debug mode to dump internal information (IRs, etc) to files. This makes execution slower.",
    zh_cn="启用调试模式以将内部信息（IR等）保存到文件中。执行过程会变慢。",
    zh_hk="啟用調試模式以將內部信息（IR等）保存到文件中。執行過程會變慢。",
  )
  _langs_dict = {
    "en": "English",
    "zh_cn": "中文（简体）",
    "zh_hk": "中文（繁體）",
  }
  _tr_desc = TR_gui_setting.tr("desc",
    en="Edit settings here. Currently only language and debug settings are supported.",
    zh_cn="在这里编辑设置。目前仅支持语言与调试设置。",
    zh_hk="在這裡編輯設置。目前僅支持語言與調試設置。",
  )

  def __init__(self, parent : QWidget):
    super(SettingWidget, self).__init__(parent)
    self.ui = Ui_SettingWidget()
    self.ui.setupUi(self)
    self.bind_text(lambda s : self.ui.tabWidget.setTabText(0, s), self._tr_tab_general)
    self.bind_text(self.ui.languageLabel.setText, self._tr_general_language)
    self.bind_text(self.ui.mainPipelineGroupBox.setTitle, MainWindowInterface.tr_toolname_maininput)
    self.bind_text(self.ui.debugModeCheckBox.setText, self._tr_general_debug)
    self.bind_text(self.ui.debugModeCheckBox.setToolTip, self._tr_general_debug_desc)
    self.ui.languageComboBox.clear()
    for lang_code, lang_name in SettingsDict._langs_dict.items():
      self.ui.languageComboBox.addItem(lang_name, lang_code)
    self.ui.languageComboBox.setCurrentIndex(self.ui.languageComboBox.findData(SettingsDict.get_current_language()))
    self.ui.languageComboBox.currentIndexChanged.connect(self.on_languageComboBox_currentIndexChanged)
    self.ui.debugModeCheckBox.setChecked(True if SettingsDict.instance().get("mainpipeline/debug", False) else False)
    self.ui.debugModeCheckBox.toggled.connect(self.on_debugModeCheckBox_toggled)

  def on_languageComboBox_currentIndexChanged(self, index):
    lang_code = self.ui.languageComboBox.currentData()
    self.language_updated(lang_code)

  def on_debugModeCheckBox_toggled(self, checked):
    SettingsDict.instance()["mainpipeline/debug"] = True if checked else False

  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="setting",
      name=MainWindowInterface.tr_toolname_settings,
      tooltip=cls._tr_desc,
      widget=cls,
    )

  @staticmethod
  def initialize():
    if lang := SettingsDict.instance().get("language"):
      SettingWidget.setLanguage(lang)

  def language_updated(self, lang):
    if lang == SettingsDict.get_current_language():
      return
    SettingWidget.setLanguage(lang)
    SettingsDict.instance()["language"] = lang
    MainWindowInterface.getHandle(self).handleLanguageChange()

  @staticmethod
  def setLanguage(lang_code : str) -> None:
    Translatable.language_update_preferred_langs([lang_code])
