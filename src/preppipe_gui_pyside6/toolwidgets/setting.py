import os
import tempfile
import traceback
from PySide6.QtCore import *
from PySide6.QtWidgets import QWidget

from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from ..forms.generated.ui_settingwidget import Ui_SettingWidget
from ..toolwidgetinterface import *
from ..mainwindowinterface import *
from ..settingsdict import *
from ..componentwidgets.filelistinputwidget import FileListInputWidget
from .errordialog import ErrorDialog

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
  _tr_general_temporary_path = TR_gui_setting.tr("general_temporary_path",
    en="Temporary Directory",
    zh_cn="临时目录",
    zh_hk="臨時目錄",
  )
  _tr_general_renpy_sdk_path = TR_gui_setting.tr("general_renpy_sdk_path",
    en="Default Ren'Py SDK Path",
    zh_cn="默认 Ren'Py SDK 路径",
    zh_hk="預設 Ren'Py SDK 路徑",
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
  _tr_tab_assets = TR_gui_setting.tr("tab_assets",
    en="Assets",
    zh_cn="素材",
    zh_hk="素材",
  )
  _tr_assets_directories = TR_gui_setting.tr("assets_directories",
    en="Extra Asset Directories",
    zh_cn="额外素材目录",
    zh_hk="額外素材目錄",
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
  _tr_asset_import_error_title = TR_gui_setting.tr("asset_import_error_title",
    en="Extra Asset Import Failed",
    zh_cn="外部素材导入失败",
    zh_hk="外部素材導入失敗",
  )
  _tr_asset_import_error_summary = TR_gui_setting.tr("asset_import_error_summary",
    en="An error occurred while loading or building extra assets. If you need to contact the developer, please send the error message and asset configuration together.",
    zh_cn="加载或构建外部素材时发生错误。如需联系开发者，请将报错信息和素材配置一起发送。",
    zh_hk="加載或構建外部素材時發生錯誤。如需聯繫開發者，請將報錯信息和素材配置一起發送。",
  )
  _tr_reimport = TR_gui_setting.tr("reimport",
    en="Re-import",
    zh_cn="重新导入",
    zh_hk="重新導入",
  )

  def __init__(self, parent : QWidget):
    super(SettingWidget, self).__init__(parent)
    self.ui = Ui_SettingWidget()
    self.ui.setupUi(self)
    self.bind_text(lambda s : self.ui.tabWidget.setTabText(0, s), self._tr_tab_general)
    self.bind_text(self.ui.languageLabel.setText, self._tr_general_language)
    self.bind_text(self.ui.mainPipelineGroupBox.setTitle, MainWindowInterface.tr_toolname_maininput)
    self.bind_text(self.ui.temporaryPathLabel.setText, self._tr_general_temporary_path)
    self.bind_text(self.ui.debugModeCheckBox.setText, self._tr_general_debug)
    self.bind_text(self.ui.debugModeCheckBox.setToolTip, self._tr_general_debug_desc)
    self.ui.languageComboBox.clear()
    for lang_code, lang_name in SettingsDict._langs_dict.items():
      self.ui.languageComboBox.addItem(lang_name, lang_code)
    self.ui.languageComboBox.setCurrentIndex(self.ui.languageComboBox.findData(SettingsDict.get_current_language()))
    self.ui.languageComboBox.currentIndexChanged.connect(self.on_languageComboBox_currentIndexChanged)
    self.ui.debugModeCheckBox.setChecked(True if SettingsDict.instance().get("mainpipeline/debug", False) else False)
    self.ui.debugModeCheckBox.toggled.connect(self.on_debugModeCheckBox_toggled)
    self.ui.temporaryPathWidget.setDirectoryMode(True)
    self.ui.temporaryPathWidget.setFieldName(self._tr_general_temporary_path)
    self.ui.temporaryPathWidget.setCurrentPath(SettingsDict.get_current_temp_dir())
    self.ui.temporaryPathWidget.filePathUpdated.connect(self.on_temporaryPathWidget_changed)
    self.add_translatable_widget_child(self.ui.temporaryPathWidget)

    self.bind_text(self.ui.renpySdkPathLabel.setText, self._tr_general_renpy_sdk_path)
    self.ui.renpySdkPathWidget.setDirectoryMode(True)
    self.ui.renpySdkPathWidget.setFieldName(self._tr_general_renpy_sdk_path)
    if p := SettingsDict.get_renpy_sdk_path():
      self.ui.renpySdkPathWidget.setCurrentPath(p)
    self.ui.renpySdkPathWidget.filePathUpdated.connect(self.on_renpySdkPathWidget_changed)
    self.add_translatable_widget_child(self.ui.renpySdkPathWidget)

    # Set up assets tab
    self.bind_text(lambda s : self.ui.tabWidget.setTabText(1, s), self._tr_tab_assets)
    self.ui.assetDirectoriesWidget.setDirectoryMode(True)
    self.ui.assetDirectoriesWidget.setFieldName(self._tr_assets_directories)
    # Load current directories from settings
    current_dirs = SettingsDict.get_user_asset_directories()
    for dir_path in current_dirs:
      self.ui.assetDirectoriesWidget.addPath(dir_path)
    self.ui.assetDirectoriesWidget.listChanged.connect(self.on_assetDirectoriesWidget_changed)
    self.ui.assetDirectoriesWidget.addCustomContextMenuAction(
      self._tr_reimport,
      self._on_asset_reimport,
      enabled_if=lambda: len(self.ui.assetDirectoriesWidget.getCurrentList()) > 0,
    )
    self.add_translatable_widget_child(self.ui.assetDirectoriesWidget)

  def _on_asset_reimport(self, path: str) -> None:
    asset_manager = AssetManager.get_instance()
    try:
      if path:
        asset_manager.try_load_extra_assets(path, force_rebuild=True)
      else:
        asset_manager.reload_extra_assets()
    except Exception as e:  # pylint: disable=broad-except
      SettingWidget._show_asset_import_error(self, e)

  def on_languageComboBox_currentIndexChanged(self, index):
    lang_code = self.ui.languageComboBox.currentData()
    self.language_updated(lang_code)

  def on_debugModeCheckBox_toggled(self, checked):
    SettingsDict.instance()["mainpipeline/debug"] = True if checked else False

  def on_temporaryPathWidget_changed(self, path):
    SettingsDict.instance()["mainpipeline/temporarypath"] = path if path != tempfile.gettempdir() else None

  def on_renpySdkPathWidget_changed(self, path):
    SettingsDict.instance()["renpy/sdk_path"] = path if path and path.strip() else None

  def on_assetDirectoriesWidget_changed(self):
    # Get current list from widget
    current_list = self.ui.assetDirectoriesWidget.getCurrentList()
    # Save to settings
    SettingsDict.set_user_asset_directories(current_list)
    # Update environment variable immediately
    existing = os.getenv(AssetManager.EXTRA_ASSETS_ENV, "")
    if current_list:
      if existing:
        combined = os.pathsep.join(current_list + [existing])
      else:
        combined = os.pathsep.join(current_list)
      os.environ[AssetManager.EXTRA_ASSETS_ENV] = combined
    else:
      # If no user directories, keep only existing env var
      if existing:
        os.environ[AssetManager.EXTRA_ASSETS_ENV] = existing
      else:
        # Remove the env var if it exists but is empty
        if AssetManager.EXTRA_ASSETS_ENV in os.environ:
          del os.environ[AssetManager.EXTRA_ASSETS_ENV]
    # Reload assets if AssetManager instance exists
    try:
      asset_manager = AssetManager.get_instance()
      asset_manager.reload_extra_assets()
    except Exception as e:  # pylint: disable=broad-except
      SettingWidget._show_asset_import_error(self, e)

  @staticmethod
  def _show_asset_import_error(parent: QWidget, exc: Exception) -> None:
    tb_str = traceback.format_exc()
    title = SettingWidget._tr_asset_import_error_title.get()
    summary = SettingWidget._tr_asset_import_error_summary.get()
    dlg = ErrorDialog(parent, title, summary, tb_str)
    dlg.exec()

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
