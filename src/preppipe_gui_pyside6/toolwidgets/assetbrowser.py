# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QListWidgetItem
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFontMetrics, QFont, QMouseEvent
from ..componentwidgets.assetcardwidget import AssetCardWidget
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack, ImagePackDescriptor
from ..toolwidgetinterface import *
from ..forms.generated.ui_assetbrowserwidget import Ui_AssetBrowserWidget
from ..settingsdict import SettingsDict
from ..util.assettagmanager import AssetTagManager, AssetTagType
from ..mainwindowinterface import MainWindowInterface
from .tageditdialog import TagEditDialog
from .imagepack import ImagePackWidget

TR_gui_tool_assetbrowser = TranslationDomain("gui_tool_assetbrowser")

SETTINGS_KEY_CURRENT_TAG = "assetmanager/current_tag"

class TagListItem(QListWidgetItem):
  def __init__(self, display_text, semantic_tag):
    super().__init__(display_text)
    self.semantic_tag = semantic_tag

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  current_tag: str
  assets_by_tag: dict[str, tuple[TagListItem, list[str]]]
  '''
  dict[标签列表显示的tag,tuple[taglistitem,list[assetid]]] \n
  tagmanager和语言发生变化时更新的全局映射，\n
  用于快捷访问当前语言环境下标签对应的列表项和素材id列表，便于恢复上次打开的状态。
  '''

  asset_cards: dict[str, AssetCardWidget]
  '''当前标签下素材id对应的卡片，用于选中状态和tageditdialog等状态更新'''
  all_asset_ids: list[str]

  _tr_toolname_assetbrowser = TR_gui_tool_assetbrowser.tr("toolname_assetbrowser",
    en="Asset Browser",
    zh_cn="素材浏览器",
    zh_hk="素材瀏覽器",
  )
  _tr_tooltip_assetbrowser = TR_gui_tool_assetbrowser.tr("tooltip_assetbrowser",
    en="Browse and manage your assets with thumbnails",
    zh_cn="浏览和管理带有缩略图的素材",
    zh_hk="瀏覽和管理帶有縮圖的素材",
  )
  _tr_select_tag = TR_gui_tool_assetbrowser.tr("select_tag",
    en="Select a tag",
    zh_cn="选择一个标签",
    zh_hk="選擇一個標籤",
  )

  def __init__(self, parent: QWidget):
    super(AssetBrowserWidget, self).__init__(parent)
    self.ui = Ui_AssetBrowserWidget()
    self.ui.setupUi(self)
    self.current_tag = ""
    self.assets_by_tag = {}
    self.asset_cards = {}
    self.all_asset_ids = []
    self.all_tag_item = None
    self.last_opened_asset_id = None
    self.tag_manager = AssetTagManager.get_instance()
    self.tag_manager.tags_updated.connect(self._on_tags_updated)

    self.tags_font = QFont()
    self.name_font = QFont()
    self.name_font.setWeight(QFont.Weight.Bold)
    self.tags_font_metrics = QFontMetrics(self.tags_font)
    self.name_font_metrics = QFontMetrics(self.name_font)

    self.bind_text(self.ui.categoryTitleLabel.setText, self._tr_select_tag)
    self.ui.categoriesListWidget.itemClicked.connect(self.on_tag_selected)
    self.ui.thumbnailsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.ui.thumbnailsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    self.flow_layout = self.ui.thumbnailsFlowLayout
    self.flow_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    self.flow_layout.setVerticalSpacing(15)
    self.load_all_assets()
    self.load_tags()

    settings = SettingsDict.instance()
    semantic_tag = settings.get(SETTINGS_KEY_CURRENT_TAG, AssetTagManager.get_semantic_tag(AssetTagType.ALL))
    tag_text = self.tag_manager.get_tag_display_text(semantic_tag)

    if self.tag_manager.get_tag_semantic(tag_text) != semantic_tag or semantic_tag not in self.assets_by_tag:
      semantic_tag = AssetTagManager.get_semantic_tag(AssetTagType.ALL)
      tag_text = self.tag_manager.get_tr_all()

    settings[SETTINGS_KEY_CURRENT_TAG] = semantic_tag
    self.current_tag = tag_text
    self.ui.categoryTitleLabel.setText(self.current_tag)
    if semantic_tag == AssetTagManager.get_semantic_tag(AssetTagType.ALL):
      if self.all_tag_item:
        self.ui.categoriesListWidget.setCurrentItem(self.all_tag_item)
      else:
        self.ui.categoriesListWidget.setCurrentItem(self.ui.categoriesListWidget.item(0))
    else:
      tag_text = self.tag_manager.get_tag_display_text(semantic_tag)
      if tag_text in self.assets_by_tag:
        item, _ = self.assets_by_tag[tag_text]
        if item:
          self.ui.categoriesListWidget.setCurrentItem(item)
    self.load_asset_cards_for_tag(semantic_tag)

  def changeEvent(self, event):
    if event.type() == QEvent.PaletteChange:
      self._on_palette_changed(self.palette())
    super().changeEvent(event)

  def load_all_assets(self):
    asset_manager = AssetManager.get_instance()
    self.all_asset_ids = []
    for asset_id, asset_info in asset_manager._assets.items():
      asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        self.all_asset_ids.append(asset_id)

  def load_tags(self):
    tags_dict = self.tag_manager.get_tags_dict()
    asset_manager = AssetManager.get_instance()
    self.assets_by_tag.clear()

    # 初始化基于资产类型的分类标签
    for asset_id in self.all_asset_ids:
      category_tag = str(self.tag_manager.get_asset_type_tag(asset_id).translatable)
      # 只添加资产到对应分类，不修改tags_dict
      if category_tag not in self.assets_by_tag:
        self.assets_by_tag[category_tag] = (None, [asset_id])
      else:
        self.assets_by_tag[category_tag][1].append(asset_id)

    # 基于现有标签构建标签-资产对应关系
    for asset_id, tags in tags_dict.items():
      try:
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          for tag in tags:
            display_tag = self.tag_manager.get_tag_display_text(tag)

            if display_tag not in self.assets_by_tag:
              self.assets_by_tag[display_tag] = (None, [asset_id])
            else:
              _, asset_ids = self.assets_by_tag[display_tag]
              if asset_id not in asset_ids:
                asset_ids.append(asset_id)
      except Exception:
        continue

    self.update_tags_list()

  def update_tags_list(self):
    self.ui.categoriesListWidget.clear()

    # 添加ALL标签
    all_count = len(self.all_asset_ids)
    all_text = self.tag_manager.get_tr_all()
    all_item = TagListItem(f"{all_text} ({all_count})", semantic_tag=AssetTagManager.get_semantic_tag(AssetTagType.ALL))
    font = all_item.font()
    font.setBold(True)
    all_item.setFont(font)
    self.ui.categoriesListWidget.addItem(all_item)
    self.all_tag_item = all_item

    # 添加预设标签：立绘
    character_tag = self.tag_manager.get_tr_character()
    character_count = 0
    if character_tag in self.assets_by_tag:
      _, asset_ids = self.assets_by_tag[character_tag]
      character_count = len(asset_ids)
    character_item = TagListItem(f"{character_tag} ({character_count})", semantic_tag="character")
    font = character_item.font()
    font.setBold(True)
    character_item.setFont(font)
    self.ui.categoriesListWidget.addItem(character_item)

    # 添加预设标签：背景
    background_tag = self.tag_manager.get_tr_background()
    background_count = 0
    if background_tag in self.assets_by_tag:
      _, asset_ids = self.assets_by_tag[background_tag]
      background_count = len(asset_ids)
    background_item = TagListItem(f"{background_tag} ({background_count})", semantic_tag="background")
    font = background_item.font()
    font.setBold(True)
    background_item.setFont(font)
    self.ui.categoriesListWidget.addItem(background_item)

    # 更新assets_by_tag字典中的项目引用
    if character_tag in self.assets_by_tag:
      asset_ids = self.assets_by_tag[character_tag][1]
      self.assets_by_tag[character_tag] = (character_item, asset_ids)
    if background_tag in self.assets_by_tag:
      asset_ids = self.assets_by_tag[background_tag][1]
      self.assets_by_tag[background_tag] = (background_item, asset_ids)

    # 添加其他自定义标签
    asset_by_tag_changes = {}
    # 获取按显示文本升序排列的自定义标签
    for semantic_tag, display_text in self.tag_manager.get_sorted_tags():
      # 检查该标签是否在assets_by_tag中存在对应的资产
      if display_text in self.assets_by_tag:
        _, asset_ids = self.assets_by_tag[display_text]
        count = len(asset_ids)
        if count > 0:
          item = TagListItem(f"{display_text} ({count})", semantic_tag=semantic_tag)
          self.ui.categoriesListWidget.addItem(item)
          asset_by_tag_changes[display_text] = (item, asset_ids)

    self.assets_by_tag.update(asset_by_tag_changes)

  def on_tag_selected(self, item: TagListItem):
    display_text = item.text()
    self.current_tag = display_text
    self.ui.categoryTitleLabel.setText(self.current_tag)
    tag_semantic = item.semantic_tag
    settings = SettingsDict.instance()
    settings[SETTINGS_KEY_CURRENT_TAG] = tag_semantic
    self.load_asset_cards_for_tag(tag_semantic)

  def load_asset_cards_for_tag(self, tag: str):
    self.clear_asset_cards()

    if tag == AssetTagManager.get_semantic_tag(AssetTagType.ALL):
      # 显示所有资产
      current_asset_ids = self.all_asset_ids
    else:
      # 处理预设标签：立绘和背景
      if tag == "character":
        display_tag = self.tag_manager.get_tr_character()
      elif tag == "background":
        display_tag = self.tag_manager.get_tr_background()
      else:
        # 其他常规标签
        display_tag = tag
      current_asset_ids = self.assets_by_tag[display_tag][1]

    for asset_id in current_asset_ids:
      self.add_asset_card_to_flow(asset_id)

  def _create_asset_card(self, asset_id: str, card_width: int, card_height: int) -> QWidget:
    asset_card = AssetCardWidget(asset_id, card_width, card_height, self.name_font, self.tags_font, self)
    asset_card.clicked.connect(lambda aid, event: self.on_asset_card_clicked(aid, event))
    asset_card.tags_button_clicked.connect(lambda aid, button: self._on_tags_button_clicked(aid, button))

    is_selected = asset_id == self.last_opened_asset_id
    asset_card.set_selected(is_selected)

    return asset_card

  def add_asset_card_to_flow(self, asset_id: str):
    card_width = 160
    card_height = 192
    asset_card = self._create_asset_card(asset_id, card_width, card_height)
    self.flow_layout.addWidget(asset_card)

    self.asset_cards[asset_id] = asset_card

  def clear_asset_cards(self):
    while self.flow_layout.count() > 0:
      item = self.flow_layout.takeAt(0)
      if item.widget() is not None:
        item.widget().deleteLater()
      del item

    self.asset_cards.clear()

  def _on_palette_changed(self, palette):
    for _, widget in self.asset_cards.items():
      widget.update_style(palette)

  def _open_asset(self, asset_id: str):
    """打开资产的统一方法，被点击事件和右键菜单共用"""
    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(asset_id)
    if isinstance(asset, ImagePack):
      MainWindowInterface.getHandle(self).requestOpen(
        ImagePackWidget.getToolInfo(packid=asset_id)
      )

  def _deselect_last_opened_asset(self, asset_id: str):
    if self.last_opened_asset_id and self.last_opened_asset_id in self.asset_cards\
      and self.last_opened_asset_id != asset_id:
      self.asset_cards[self.last_opened_asset_id].set_selected(False)
    self.last_opened_asset_id = asset_id

  def on_asset_card_clicked(self, asset_id: str, event: QMouseEvent):
    self._deselect_last_opened_asset(asset_id)
    if event and event.button() == Qt.LeftButton:
      self._open_asset(asset_id)

  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="assetbrowser",
      name=cls._tr_toolname_assetbrowser,
      tooltip=cls._tr_tooltip_assetbrowser,
      widget=cls,
    )

  def _on_tags_button_clicked(self, asset_id: str, button):
    self._deselect_last_opened_asset(asset_id)
    self.open_tag_edit_dialog(asset_id, button)

  def open_tag_edit_dialog(self, asset_id, button):
    dialog = TagEditDialog(asset_id, self)
    dialog.tags_changed.connect(self._update_single_asset_tags)
    dialog.exec()

    button.setDown(False)
    button.clearFocus()
    button.update()

  def _update_single_asset_tags(self, asset_id):
    self.asset_cards[asset_id].update_tags()

  def _refresh_tags_and_restore_selection(self, update_asset_cards=True, update_card_texts=False):
    """刷新标签列表并恢复当前选择

    Args:
      update_asset_cards: 是否重新加载资产卡片
      update_card_texts: 是否更新现有资产卡片的文本（用于翻译更新）
    """
    current_semantic = None
    current_item = self.ui.categoriesListWidget.currentItem()
    if current_item:
      current_semantic = current_item.semantic_tag

    self.load_tags()

    # 保持当前选中的标签
    if current_semantic:
      for i in range(self.ui.categoriesListWidget.count()):
        item = self.ui.categoriesListWidget.item(i)
        if item.semantic_tag == current_semantic:
          self.ui.categoriesListWidget.setCurrentItem(item)
          self.current_tag = item.text()
          self.ui.categoryTitleLabel.setText(self.current_tag)

          if update_asset_cards:
            self.load_asset_cards_for_tag(current_semantic)
          elif update_card_texts:
            for asset_id, asset_card in self.asset_cards.items():
              asset_card.update_text()
          break
    elif not current_item and update_card_texts:
      # 当没有选中项且需要更新文本时，选择第一个标签
      self.ui.categoriesListWidget.setCurrentRow(0)
      first_item = self.ui.categoriesListWidget.item(0)
      if first_item:
        display_text = first_item.text()
        self.current_tag = display_text
        self.ui.categoryTitleLabel.setText(self.current_tag)

        for asset_id, asset_card in self.asset_cards.items():
          asset_card.update_text()

  def _on_tags_updated(self):
    self._refresh_tags_and_restore_selection(update_asset_cards=False, update_card_texts=False)

  def update_text(self):
    super().update_text()
    # 翻译更新时，只更新现有卡片的文本，不重新加载卡片
    self._refresh_tags_and_restore_selection(update_asset_cards=False, update_card_texts=True)
