# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from typing import Tuple
from collections import OrderedDict
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

SETTINGS_KEY_CURRENT_TAG = "persistent/assetmanager/current_tag"

class TagListItem(QListWidgetItem):
  def __init__(self, display_text, semantic_tag=None, is_all_tag=False):
    super().__init__(display_text)
    self.semantic_tag = semantic_tag
    self.is_all_tag = is_all_tag

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  current_tag: str
  assets_by_tag: OrderedDict[str, Tuple[QListWidgetItem, dict[str, object]]]

  asset_cards: dict[str, AssetCardWidget]
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
    self.assets_by_tag = OrderedDict[str, Tuple[QListWidgetItem, dict[str, object]]]()
    self.asset_cards = {}
    self.all_asset_ids = []
    self.all_tag_item = None
    self.last_opened_asset_id = None
    self.tag_manager = AssetTagManager.get_instance()
    self._current_asset_ids = []

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
    semantic_tag = settings.get(SETTINGS_KEY_CURRENT_TAG, AssetTagType.ALL.semantic)
    tag_text = self.tag_manager.get_tag_display_text(semantic_tag)

    if self.tag_manager.get_tag_semantic(tag_text) != semantic_tag:
      semantic_tag = AssetTagType.ALL.semantic
      tag_text = self.tag_manager.get_tr_all()

    settings[SETTINGS_KEY_CURRENT_TAG] = semantic_tag
    self.current_tag = tag_text
    self.ui.categoryTitleLabel.setText(self.current_tag)
    if semantic_tag == AssetTagType.ALL.semantic:
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
    self.assets_by_tag = OrderedDict()
    asset_manager = AssetManager.get_instance()

    background_tag = self.tag_manager.get_tr_background()
    character_tag = self.tag_manager.get_tr_character()
    other_tag = self.tag_manager.get_tr_other()

    for asset_id in self.all_asset_ids:
      try:
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          descriptor = ImagePack.get_descriptor_by_id(asset_id)
          if descriptor:
            pack_type = descriptor.get_image_pack_type()
            if pack_type == ImagePackDescriptor.ImagePackType.BACKGROUND:
              category_tag = background_tag
              semantic = AssetTagType.BACKGROUND.semantic
            elif pack_type == ImagePackDescriptor.ImagePackType.CHARACTER:
              category_tag = character_tag
              semantic = AssetTagType.CHARACTER_SPRITE.semantic
            else:
              category_tag = other_tag
              semantic = AssetTagType.OTHER.semantic
            has_custom_tags = asset_id in tags_dict and tags_dict[asset_id]
            if category_tag not in self.assets_by_tag:
              self.assets_by_tag[category_tag] = (None, {})
            _, asset_dict = self.assets_by_tag[category_tag]
            asset_dict[asset_id] = asset
            if not has_custom_tags:
              if asset_id not in tags_dict:
                tags_dict[asset_id] = set()
              tags_dict[asset_id].add(semantic)
      except Exception:
        continue

    tags_dict = self.tag_manager.clean_and_normalize_tags_dict(tags_dict)

    for asset_id, tags in tags_dict.items():
      try:
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          for tag in tags:
            display_tag = self.tag_manager.get_tag_display_text(tag)

            if display_tag not in self.assets_by_tag:
              self.assets_by_tag[display_tag] = (None, {asset_id: asset})
            else:
              _, asset_dict = self.assets_by_tag[display_tag]
              asset_dict[asset_id] = asset
      except Exception:
        continue

    self.tag_manager.save_tags_dict(tags_dict)
    self.update_tags_list()

  def update_tags_list(self):
    self.ui.categoriesListWidget.clear()
    all_count = len(self.all_asset_ids)
    all_text = self.tag_manager.get_tr_all()
    all_item = TagListItem(f"{all_text} ({all_count})", semantic_tag=AssetTagType.ALL.semantic, is_all_tag=True)
    font = all_item.font()
    font.setBold(True)
    all_item.setFont(font)
    self.ui.categoriesListWidget.addItem(all_item)
    self.all_tag_item = all_item
    for tag in self.assets_by_tag.keys():
      count = len(self.assets_by_tag[tag][1])
      if count > 0:
        semantic_tag = self.tag_manager.tag_text_to_semantic.get(tag, tag)
        item = TagListItem(f"{tag} ({count})", semantic_tag=semantic_tag)
        self.ui.categoriesListWidget.addItem(item)
        _, asset_dict = self.assets_by_tag[tag]
        self.assets_by_tag[tag] = (item, asset_dict)
        if tag not in self.tag_manager.tag_text_to_semantic:
          self.tag_manager.add_custom_tag_mapping(tag, tag)

  def on_tag_selected(self, item: TagListItem):
    display_text = item.text()
    self.current_tag = display_text
    self.ui.categoryTitleLabel.setText(self.current_tag)
    if item.is_all_tag:
      tag_semantic = AssetTagType.ALL.semantic
    else:
      tag_semantic = item.semantic_tag
    settings = SettingsDict.instance()
    settings[SETTINGS_KEY_CURRENT_TAG] = tag_semantic
    self.load_asset_cards_for_tag(tag_semantic)

  def load_asset_cards_for_tag(self, tag: str):
    self.clear_asset_cards()
    self._current_asset_ids = []

    if tag == AssetTagType.ALL.semantic:
      self._current_asset_ids = self.all_asset_ids
    else:
      display_tag = self.tag_manager.get_tag_display_text(tag)
      if display_tag in self.assets_by_tag:
        _, asset_dict = self.assets_by_tag[display_tag]
        self._current_asset_ids = list(asset_dict.keys())
    self._add_asset_cards()

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

  def _add_asset_cards(self):
    if not self._current_asset_ids:
      return

    for asset_id in self._current_asset_ids:
      self.add_asset_card_to_flow(asset_id)

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
    """处理资产卡片点击事件"""
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

  def update_text(self):
    super().update_text()

    current_semantic = None
    current_item = self.ui.categoriesListWidget.currentItem()
    if current_item:
      current_semantic = current_item.semantic_tag

    self.load_tags()

    if current_semantic:
      for i in range(self.ui.categoriesListWidget.count()):
        item = self.ui.categoriesListWidget.item(i)
        if item.semantic_tag == current_semantic:
          self.ui.categoriesListWidget.setCurrentItem(item)
          self.current_tag = item.text()
          self.ui.categoryTitleLabel.setText(self.current_tag)

          for asset_id, asset_card in self.asset_cards.items():
            asset_card.update_text()
          break
    elif not current_item:
      self.ui.categoriesListWidget.setCurrentRow(0)
      first_item = self.ui.categoriesListWidget.item(0)
      if first_item:
        display_text = first_item.text()
        self.current_tag = display_text
        self.ui.categoryTitleLabel.setText(self.current_tag)

        for asset_id, asset_card in self.asset_cards.items():
          asset_card.update_text()
