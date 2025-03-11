from PySide6.QtCore import *

from preppipe.language import *
from ..forms.generated.ui_settingwidget import Ui_SettingWidget
from ..toolwidgetinterface import *
from ..mainwindowinterface import *
from ..settingsdict import *

TR_gui_setting = TranslationDomain("gui_setting")

class SettingWidget(QWidget, ToolWidgetInterface):
  ui : Ui_SettingWidget

  _tr_toolname = TR_gui_setting.tr("toolname",
    en="Setting",
    zh_cn="设置",
    zh_hk="設定",
  )
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
  _langs_dict = {
    "en": "English",
    "zh_cn": "中文（简体）",
    "zh_hk": "中文（繁體）",
  }

  def __init__(self, parent : QWidget):
    super(SettingWidget, self).__init__(parent)
    self.ui = Ui_SettingWidget()
    self.ui.setupUi(self)
    self.bind_text(lambda s : self.ui.tabWidget.setTabText(0, s), self._tr_tab_general)
    self.bind_text(self.ui.languageLabel.setText, self._tr_general_language)
    self.ui.languageComboBox.clear()
    for lang_code, lang_name in SettingsDict._langs_dict.items():
      self.ui.languageComboBox.addItem(lang_name, lang_code)
    self.ui.languageComboBox.setCurrentIndex(self.ui.languageComboBox.findData(SettingsDict.get_current_language()))
    self.ui.languageComboBox.currentIndexChanged.connect(self.on_languageComboBox_currentIndexChanged)

  def on_languageComboBox_currentIndexChanged(self, index):
    lang_code = self.ui.languageComboBox.currentData()
    self.language_updated(lang_code)

  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="setting",
      name=SettingWidget._tr_toolname,
      widget=cls,
    )

  @staticmethod
  def initialize():
    if lang := SettingsDict.instance().get("language"):
      SettingWidget.setLanguage(lang)

  def get_initial_value(self, key : str):
    match key:
      case "language":
        return SettingsDict.get_current_language()
      case _:
        raise RuntimeError("Unexpected key")

  def language_updated(self, lang):
    if lang == SettingsDict.get_current_language():
      return
    SettingWidget.setLanguage(lang)
    SettingsDict.instance()["language"] = lang
    MainWindowInterface.getHandle(self).handleLanguageChange()

  @staticmethod
  def setLanguage(lang_code : str) -> None:
    Translatable.language_update_preferred_langs([lang_code])
