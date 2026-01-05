# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QTreeWidgetItem
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

class TagTreeItem(QTreeWidgetItem):
  semantic_tag_path: list[str]
  asset_ids: set[str]

  def __init__(self, display_text: str, semantic_tag_path: list[str], asset_ids: set[str], parent: QTreeWidgetItem = None):
    super().__init__(parent)
    self.setText(0, f"{display_text} ({len(asset_ids)})")
    self.semantic_tag_path = semantic_tag_path
    self.asset_ids = asset_ids

class CategoryTreeItem(TagTreeItem):
  item_by_tags: dict[str,TagTreeItem]

  def __init__(self, display_text: str, semantic_tag_path: list[str], asset_ids: set[str], parent: QTreeWidgetItem = None):
    super().__init__(display_text, semantic_tag_path, asset_ids, parent)
    self.item_by_tags = {}

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  current_tag: str

  asset_cards: dict[str, AssetCardWidget]
  '''当前标签下素材id对应的卡片，用于选中状态和tageditdialog等状态更新'''
  all_asset_ids: dict[str, int]
  '''素材ID到注册索引的映射，记录素材在AssetManager中的注册顺序'''

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
    self.asset_cards = {}
    self.all_asset_ids = {}
    self.last_opened_asset_id = None
    self.tag_manager = AssetTagManager.get_instance()
    self.tag_manager.tags_updated.connect(self._on_tags_updated)

    self.tags_font = QFont()
    self.name_font = QFont()
    self.name_font.setWeight(QFont.Weight.Bold)
    self.tags_font_metrics = QFontMetrics(self.tags_font)
    self.name_font_metrics = QFontMetrics(self.name_font)

    self.bind_text(self.ui.categoryTitleLabel.setText, self._tr_select_tag)
    self.ui.categoriesTreeWidget.itemClicked.connect(self.on_tag_selected)
    self.ui.thumbnailsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.ui.thumbnailsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    self.flow_layout = self.ui.thumbnailsFlowLayout
    self.flow_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    self.flow_layout.setVerticalSpacing(15)
    self.load_all_assets()
    self.load_tags()

    settings = SettingsDict.instance()
    saved_semantic_tag_path = settings.get(SETTINGS_KEY_CURRENT_TAG, [AssetTagManager.get_semantic_tag(AssetTagType.ALL)])

    if not isinstance(saved_semantic_tag_path, list):
      saved_semantic_tag_path = [saved_semantic_tag_path]

    target_item = None
    target_path = None

    def find_item_by_path(tree_item: QTreeWidgetItem, path: list[str]) -> TagTreeItem | None:
      if not path:
        return None
      if not isinstance(tree_item, TagTreeItem):
        return None
      if tree_item.semantic_tag_path == path:
        return tree_item
      for i in range(tree_item.childCount()):
        child = tree_item.child(i)
        if isinstance(child, TagTreeItem):
          result = find_item_by_path(child, path)
          if result:
            return result
      return None

    for i in range(self.ui.categoriesTreeWidget.topLevelItemCount()):
      top_item = self.ui.categoriesTreeWidget.topLevelItem(i)
      if isinstance(top_item, TagTreeItem):
        found = find_item_by_path(top_item, saved_semantic_tag_path)
        if found:
          target_item = found
          target_path = saved_semantic_tag_path
          break

    if not target_item:
      all_semantic = AssetTagManager.get_semantic_tag(AssetTagType.ALL)
      target_path = [all_semantic]
      for i in range(self.ui.categoriesTreeWidget.topLevelItemCount()):
        top_item = self.ui.categoriesTreeWidget.topLevelItem(i)
        if isinstance(top_item, TagTreeItem) and top_item.semantic_tag_path == target_path:
          target_item = top_item
          break

    if target_item:
      self.ui.categoriesTreeWidget.setCurrentItem(target_item)
      self.current_tag = target_item.text(0)
      self.ui.categoryTitleLabel.setText(self._get_tag_path_display_text(target_path))
      settings[SETTINGS_KEY_CURRENT_TAG] = target_path
      self.load_asset_cards_for_tag(target_item.asset_ids)

  def changeEvent(self, event):
    if event.type() == QEvent.PaletteChange:
      self._on_palette_changed(self.palette())
    super().changeEvent(event)

  def load_all_assets(self):
    asset_manager = AssetManager.get_instance()
    self.all_asset_ids = {}
    index = 0
    for asset_id, asset_info in asset_manager._assets.items():
      asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        self.all_asset_ids[asset_id] = index
        index += 1

  def _sort_tags(self, tag_semantics) -> list[str]:
    """对标签进行排序：预设标签按 enum.auto() 值排序，自定义标签按显示文本排序"""
    preset_tags = []
    custom_tags = []

    for tag_semantic in tag_semantics:
      preset_info = self.tag_manager.get_asset_preset_tag_from_semantic(tag_semantic)
      if preset_info:
        preset_tags.append((tag_semantic, preset_info.value))
      else:
        custom_tags.append(tag_semantic)

    preset_tags.sort(key=lambda x: x[1])
    custom_tags.sort(key=lambda x: self.tag_manager.get_tag_display_text(x))

    return [tag[0] for tag in preset_tags] + custom_tags

  def _get_asset_category_priority(self, asset_id: str) -> int:
    asset_type = self.tag_manager.get_asset_type_tag(asset_id)
    if asset_type == AssetTagType.BACKGROUND:
      return 0
    elif asset_type == AssetTagType.CHARACTER_SPRITE:
      return 1
    else:
      return 2

  def _get_asset_preset_tags_enum_sorted(self, asset_id: str) -> list[int]:
    preset_tags = []
    all_tags = self.tag_manager.get_asset_tags(asset_id)

    for tag_semantic in all_tags:
      preset_info = self.tag_manager.get_asset_preset_tag_from_semantic(tag_semantic)
      if preset_info:
        preset_tags.append(preset_info.value)
    return sorted(preset_tags)

  def _sort_asset_ids(self, asset_ids: list[str]) -> list[str]:
    """根据以下规则对素材ID进行排序：
    1. 分类标签不一样：背景素材在前
    2. 预设标签不一样：按照预设标签enum.auto()值的字典序排列
    3. 分类标签与预设标签都一致：按照素材在AssetManager里注册的顺序排列
    """
    return sorted(asset_ids, key=lambda asset_id: (
      self._get_asset_category_priority(asset_id),
      self._get_asset_preset_tags_enum_sorted(asset_id),
      self.all_asset_ids[asset_id]
    ))

  def _build_category_tree_item(self, category_type: AssetTagType) -> CategoryTreeItem:
    category_semantic = self.tag_manager.get_semantic_tag(category_type)
    category_display_text = self.tag_manager.get_tag_display_text(category_semantic)

    category_asset_ids = set()
    for asset_id in self.all_asset_ids.keys():
      asset_type_tag = self.tag_manager.get_asset_type_tag(asset_id)
      if asset_type_tag == category_type:
        category_asset_ids.add(asset_id)

    category_item = CategoryTreeItem(
      category_display_text,
      [category_semantic],
      category_asset_ids
    )
    font = category_item.font(0)
    font.setBold(True)
    category_item.setFont(0, font)

    tag_to_assets = {}

    for asset_id in category_asset_ids:
      asset_tags = self.tag_manager.get_asset_tags(asset_id)
      for tag_semantic in asset_tags:
        if self.tag_manager.get_asset_tag_type_from_semantic(tag_semantic):
          continue
        if tag_semantic not in tag_to_assets:
          tag_to_assets[tag_semantic] = set()
        tag_to_assets[tag_semantic].add(asset_id)

    sorted_tags = self._sort_tags(tag_to_assets.keys())
    for tag_semantic in sorted_tags:
      asset_ids = tag_to_assets[tag_semantic]
      tag_display_text = self.tag_manager.get_tag_display_text(tag_semantic)
      tag_item = TagTreeItem(
        tag_display_text,
        [category_semantic, tag_semantic],
        asset_ids,
        category_item
      )
      category_item.item_by_tags[tag_semantic] = tag_item

    return category_item

  def _build_all_category_tree_item(self, other_categories: list[CategoryTreeItem]) -> CategoryTreeItem:
    all_semantic = self.tag_manager.get_semantic_tag(AssetTagType.ALL)
    all_display_text = self.tag_manager.get_tag_display_text(all_semantic)

    all_asset_ids = set(self.all_asset_ids.keys())
    all_item = CategoryTreeItem(
      all_display_text,
      [all_semantic],
      all_asset_ids
    )
    font = all_item.font(0)
    font.setBold(True)
    all_item.setFont(0, font)

    common_tags:dict[str,int] = {}
    for category_item in other_categories:
      for tag_semantic, tag_item in category_item.item_by_tags.items():
        if tag_semantic not in common_tags:
          common_tags[tag_semantic] = 0
        common_tags[tag_semantic] += 1

    sorted_common_tags = self._sort_tags(common_tags.keys())
    for tag_semantic in sorted_common_tags:
      count = common_tags[tag_semantic]
      if count == len(other_categories):
        common_asset_ids = set.union(*[category_item.item_by_tags[tag_semantic].asset_ids for category_item in other_categories])
        if common_asset_ids:
          tag_display_text = self.tag_manager.get_tag_display_text(tag_semantic)
          tag_item = TagTreeItem(
            tag_display_text,
            [all_semantic, tag_semantic],
            common_asset_ids,
            all_item
          )
          all_item.item_by_tags[tag_semantic] = tag_item
          all_item.addChild(tag_item)

    return all_item

  def load_tags(self):
    self.update_tags_list()

  def update_tags_list(self):
    self.ui.categoriesTreeWidget.clear()

    background_item = self._build_category_tree_item(AssetTagType.BACKGROUND)
    character_item = self._build_category_tree_item(AssetTagType.CHARACTER_SPRITE)

    other_categories:list[CategoryTreeItem] = []
    other_categories.append(character_item)
    other_categories.append(background_item)

    all_item = self._build_all_category_tree_item(other_categories=other_categories)

    self.ui.categoriesTreeWidget.addTopLevelItem(all_item)

    for category_item in other_categories:
      self.ui.categoriesTreeWidget.addTopLevelItem(category_item)

    self.ui.categoriesTreeWidget.expandAll()

  def _get_tag_path_display_text(self, semantic_tag_path: list[str]) -> str:
    return "/".join([self.tag_manager.get_tag_display_text(tag) for tag in semantic_tag_path])

  def on_tag_selected(self, item: TagTreeItem):
    display_text = item.text(0)
    self.current_tag = display_text
    semantic_tag_path = item.semantic_tag_path
    self.ui.categoryTitleLabel.setText(self._get_tag_path_display_text(semantic_tag_path))
    settings = SettingsDict.instance()
    settings[SETTINGS_KEY_CURRENT_TAG] = semantic_tag_path
    self.load_asset_cards_for_tag(item.asset_ids)

  def load_asset_cards_for_tag(self, asset_ids: list[str]):
    self.clear_asset_cards()
    # 应用排序规则
    sorted_asset_ids = self._sort_asset_ids(asset_ids)
    for asset_id in sorted_asset_ids:
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
    current_semantic_tag_path = None
    current_item = self.ui.categoriesTreeWidget.currentItem()
    if current_item and isinstance(current_item, TagTreeItem):
      current_semantic_tag_path = current_item.semantic_tag_path

    self.load_tags()

    def find_item_by_path(tree_item: QTreeWidgetItem, path: list[str]) -> TagTreeItem | None:
      if not path:
        return None
      if not isinstance(tree_item, TagTreeItem):
        return None
      if tree_item.semantic_tag_path == path:
        return tree_item
      for i in range(tree_item.childCount()):
        child = tree_item.child(i)
        if isinstance(child, TagTreeItem):
          result = find_item_by_path(child, path)
          if result:
            return result
      return None

    if current_semantic_tag_path:
      for i in range(self.ui.categoriesTreeWidget.topLevelItemCount()):
        top_item = self.ui.categoriesTreeWidget.topLevelItem(i)
        if isinstance(top_item, TagTreeItem):
          found = find_item_by_path(top_item, current_semantic_tag_path)
          if found:
            self.ui.categoriesTreeWidget.setCurrentItem(found)
            self.current_tag = found.text(0)
            self.ui.categoryTitleLabel.setText(self._get_tag_path_display_text(current_semantic_tag_path))
            settings = SettingsDict.instance()
            settings[SETTINGS_KEY_CURRENT_TAG] = current_semantic_tag_path

            if update_asset_cards:
              self.load_asset_cards_for_tag(current_semantic_tag_path)
            elif update_card_texts:
              for asset_id, asset_card in self.asset_cards.items():
                asset_card.update_text()
            break
    elif not current_item and update_card_texts:
      self.ui.categoriesTreeWidget.setCurrentRow(0)
      first_item = self.ui.categoriesTreeWidget.topLevelItem(0)
      if first_item and isinstance(first_item, TagTreeItem):
        self.current_tag = first_item.text(0)
        self.ui.categoryTitleLabel.setText(self._get_tag_path_display_text(first_item.semantic_tag_path))

        for asset_id, asset_card in self.asset_cards.items():
          asset_card.update_text()

  def _on_tags_updated(self):
    self._refresh_tags_and_restore_selection(update_asset_cards=False, update_card_texts=False)

  def update_text(self):
    super().update_text()
    # 翻译更新时，只更新现有卡片的文本，不重新加载卡片
    self._refresh_tags_and_restore_selection(update_asset_cards=False, update_card_texts=True)
