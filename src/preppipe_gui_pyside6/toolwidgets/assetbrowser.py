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
  def __init__(self, parent, display_text, semantic_tag=None, is_category=False, parent_category=None):
    super().__init__(parent, [display_text])
    self.semantic_tag = semantic_tag
    self.is_category = is_category
    self.parent_category = parent_category

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  current_tag: str
  assets_by_tag: dict[str, tuple[TagTreeItem, list[str]]]
  '''
  dict[标签列表显示的tag,tuple[taglistitem,list[assetid]]]
  tagmanager和语言发生变化时更新的全局映射，
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
    self.ui.categoriesTreeWidget.itemClicked.connect(self.on_tag_selected)
    self.ui.thumbnailsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.ui.thumbnailsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    self.flow_layout = self.ui.thumbnailsFlowLayout
    self.flow_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    self.flow_layout.setVerticalSpacing(15)
    self.load_all_assets()
    self.load_tags()

    settings = SettingsDict.instance()
    tag_path = settings.get(SETTINGS_KEY_CURRENT_TAG, [AssetTagManager.get_semantic_tag(AssetTagType.ALL)])

    # 确保tag_path是列表格式
    if not isinstance(tag_path, list):
      tag_path = [tag_path]

    selected_item = None
    parent_category = None

    # 处理标签路径
    if len(tag_path) == 2:
      # 子标签路径：[父分类语义, 子标签语义]
      parent_semantic, child_semantic = tag_path
      for i in range(self.ui.categoriesTreeWidget.topLevelItemCount()):
        top_item = self.ui.categoriesTreeWidget.topLevelItem(i)
        if top_item.semantic_tag == parent_semantic:
          # 查找子标签
          for j in range(top_item.childCount()):
            child_item = top_item.child(j)
            if child_item.semantic_tag == child_semantic:
              selected_item = child_item
              parent_category = parent_semantic
              # 展开父项
              top_item.setExpanded(True)
              break
          break
    else:
      # 单标签路径：[分类语义]
      semantic_tag = tag_path[0]
      if semantic_tag == AssetTagManager.get_semantic_tag(AssetTagType.ALL):
        selected_item = self.all_tag_item
      else:
        for i in range(self.ui.categoriesTreeWidget.topLevelItemCount()):
          top_item = self.ui.categoriesTreeWidget.topLevelItem(i)
          if top_item.semantic_tag == semantic_tag:
            selected_item = top_item
            break
          # 检查子标签（兼容旧格式）
          for j in range(top_item.childCount()):
            child_item = top_item.child(j)
            if child_item.semantic_tag == semantic_tag:
              selected_item = child_item
              parent_category = top_item.semantic_tag
              # 展开父项
              top_item.setExpanded(True)
              break

    # 设置当前选中项和标题
    if selected_item:
      self.ui.categoriesTreeWidget.setCurrentItem(selected_item)
      display_text = selected_item.text(0)
      self.current_tag = display_text

      # 设置标签链标题
      if parent_category and not selected_item.is_category:
        parent_item = selected_item.parent()
        if parent_item:
          parent_text = parent_item.text(0)
          parent_display = parent_text.split(' (')[0] if ' (' in parent_text else parent_text
          # 保留子标签的数量部分
          self.ui.categoryTitleLabel.setText(f"{parent_display}-{display_text}")
        else:
          self.ui.categoryTitleLabel.setText(display_text)
      else:
        self.ui.categoryTitleLabel.setText(display_text)

      self.load_asset_cards_for_tag(selected_item.semantic_tag, parent_category)
    else:
      # 重置为默认标签
      semantic_tag = AssetTagManager.get_semantic_tag(AssetTagType.ALL)
      self.current_tag = self.tag_manager.get_tr_all()
      self.ui.categoryTitleLabel.setText(self.current_tag)
      settings[SETTINGS_KEY_CURRENT_TAG] = [semantic_tag]
      if self.all_tag_item:
        self.ui.categoriesTreeWidget.setCurrentItem(self.all_tag_item)
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
    self.ui.categoriesTreeWidget.clear()

    # 添加ALL标签作为顶层项
    all_count = len(self.all_asset_ids)
    all_text = self.tag_manager.get_tr_all()
    all_semantic = AssetTagManager.get_semantic_tag(AssetTagType.ALL)
    self.all_tag_item = TagTreeItem(None, f"{all_text} ({all_count})")
    font = self.all_tag_item.font(0)
    font.setBold(True)
    self.all_tag_item.setFont(0, font)
    self.all_tag_item.semantic_tag = all_semantic
    self.all_tag_item.is_category = True
    self.ui.categoriesTreeWidget.addTopLevelItem(self.all_tag_item)

    # 获取全部分类下的预设标签和自定义标签
    preset_tags, custom_tags = self.tag_manager.get_tags_for_category(all_semantic)

    # 添加预设标签作为子项
    if preset_tags:
      for semantic, display_text in preset_tags:
        # 计算该预设标签下的资产数量
        assets = self.tag_manager.get_assets_for_category_and_tag(all_semantic, semantic)
        count = len(assets)
        if count > 0:
          preset_item = TagTreeItem(self.all_tag_item, f"{display_text} ({count})")
          preset_item.semantic_tag = semantic
          preset_item.parent_category = all_semantic
          self.all_tag_item.addChild(preset_item)

    # 添加自定义标签作为子项
    if custom_tags:
      for semantic, display_text in custom_tags:
        # 计算该自定义标签下的资产数量
        assets = self.tag_manager.get_assets_for_category_and_tag(all_semantic, semantic)
        count = len(assets)
        if count > 0:
          custom_item = TagTreeItem(self.all_tag_item, f"{display_text} ({count})")
          custom_item.semantic_tag = semantic
          custom_item.parent_category = all_semantic
          self.all_tag_item.addChild(custom_item)

    # 添加预设分类标签：立绘
    character_tag = self.tag_manager.get_tr_character()
    character_count = 0
    if character_tag in self.assets_by_tag:
      _, asset_ids = self.assets_by_tag[character_tag]
      character_count = len(asset_ids)
    character_item = TagTreeItem(None, f"{character_tag} ({character_count})")
    font = character_item.font(0)
    font.setBold(True)
    character_item.setFont(0, font)
    character_semantic = AssetTagManager.get_semantic_tag(AssetTagType.CHARACTER_SPRITE)
    character_item.semantic_tag = character_semantic
    character_item.is_category = True
    self.ui.categoriesTreeWidget.addTopLevelItem(character_item)

    # 获取立绘分类下的预设标签和自定义标签
    preset_tags, custom_tags = self.tag_manager.get_tags_for_category(character_semantic)

    # 添加预设标签作为子项
    if preset_tags:
      for semantic, display_text in preset_tags:
        # 计算该预设标签下的资产数量
        assets = self.tag_manager.get_assets_for_category_and_tag(character_semantic, semantic)
        count = len(assets)
        if count > 0:
          preset_item = TagTreeItem(character_item, f"{display_text} ({count})")
          preset_item.semantic_tag = semantic
          preset_item.parent_category = character_semantic
          character_item.addChild(preset_item)

    # 添加自定义标签作为子项
    if custom_tags:
      for semantic, display_text in custom_tags:
        # 计算该自定义标签下的资产数量
        assets = self.tag_manager.get_assets_for_category_and_tag(character_semantic, semantic)
        count = len(assets)
        if count > 0:
          custom_item = TagTreeItem(character_item, f"{display_text} ({count})")
          custom_item.semantic_tag = semantic
          custom_item.parent_category = character_semantic
          character_item.addChild(custom_item)



    # 添加预设分类标签：背景
    background_tag = self.tag_manager.get_tr_background()
    background_count = 0
    if background_tag in self.assets_by_tag:
      _, asset_ids = self.assets_by_tag[background_tag]
      background_count = len(asset_ids)
    background_item = TagTreeItem(None, f"{background_tag} ({background_count})")
    font = background_item.font(0)
    font.setBold(True)
    background_item.setFont(0, font)
    background_semantic = AssetTagManager.get_semantic_tag(AssetTagType.BACKGROUND)
    background_item.semantic_tag = background_semantic
    background_item.is_category = True
    self.ui.categoriesTreeWidget.addTopLevelItem(background_item)

    # 获取背景分类下的预设标签和自定义标签
    preset_tags, custom_tags = self.tag_manager.get_tags_for_category(background_semantic)

    # 添加预设标签作为子项
    if preset_tags:
      for semantic, display_text in preset_tags:
        # 计算该预设标签下的资产数量
        assets = self.tag_manager.get_assets_for_category_and_tag(background_semantic, semantic)
        count = len(assets)
        if count > 0:
          preset_item = TagTreeItem(background_item, f"{display_text} ({count})")
          preset_item.semantic_tag = semantic
          preset_item.parent_category = background_semantic
          background_item.addChild(preset_item)

    # 添加自定义标签作为子项
    if custom_tags:
      for semantic, display_text in custom_tags:
        # 计算该自定义标签下的资产数量
        assets = self.tag_manager.get_assets_for_category_and_tag(background_semantic, semantic)
        count = len(assets)
        if count > 0:
          custom_item = TagTreeItem(background_item, f"{display_text} ({count})")
          custom_item.semantic_tag = semantic
          custom_item.parent_category = background_semantic
          background_item.addChild(custom_item)



    # 更新assets_by_tag字典中的项目引用
    if character_tag in self.assets_by_tag:
      asset_ids = self.assets_by_tag[character_tag][1]
      self.assets_by_tag[character_tag] = (character_item, asset_ids)
    if background_tag in self.assets_by_tag:
      asset_ids = self.assets_by_tag[background_tag][1]
      self.assets_by_tag[background_tag] = (background_item, asset_ids)

  def on_tag_selected(self, item: TagTreeItem):
    display_text = item.text(0)
    self.current_tag = display_text
    # 实现标签链标题：如果是子标签，显示"分类-子标签"格式
    if item.parent_category and not item.is_category:
      # 子标签：需要获取父分类的显示文本
      parent_item = item.parent()
      if parent_item:
        parent_text = parent_item.text(0)
        # 去除数量部分，如"立绘 (10)" → "立绘"
        parent_display = parent_text.split(' (')[0] if ' (' in parent_text else parent_text
        # 保留子标签的数量部分
        self.ui.categoryTitleLabel.setText(f"{parent_display}-{display_text}")
      else:
        self.ui.categoryTitleLabel.setText(display_text)
    else:
      # 顶层标签
      self.ui.categoryTitleLabel.setText(display_text)
    tag_semantic = item.semantic_tag
    settings = SettingsDict.instance()
    # 存储标签路径：[父分类语义, 子标签语义] 或 [分类语义]
    if item.parent_category and not item.is_category:
      parent_item = item.parent()
      tag_path = [parent_item.semantic_tag, tag_semantic]
    else:
      tag_path = [tag_semantic]
    settings[SETTINGS_KEY_CURRENT_TAG] = tag_path
    self.load_asset_cards_for_tag(tag_semantic, item.parent_category)

  def load_asset_cards_for_tag(self, tag: str, parent_category: str = None):
    self.clear_asset_cards()

    if tag == AssetTagManager.get_semantic_tag(AssetTagType.ALL):
      # 显示所有资产
      current_asset_ids = self.all_asset_ids
    elif parent_category:
      # 处理子标签：同时拥有分类和子标签的资产
      current_asset_ids = self.tag_manager.get_assets_for_category_and_tag(parent_category, tag)
    else:
      # 处理预设分类标签：立绘和背景
      if tag == AssetTagManager.get_semantic_tag(AssetTagType.CHARACTER_SPRITE):
        display_tag = self.tag_manager.get_tr_character()
      elif tag == AssetTagManager.get_semantic_tag(AssetTagType.BACKGROUND):
        display_tag = self.tag_manager.get_tr_background()
      else:
        # 其他常规标签
        display_tag = self.tag_manager.get_tag_display_text(tag)
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
    # 保存当前标签路径
    current_tag_path = None
    current_item = self.ui.categoriesTreeWidget.currentItem()
    if current_item:
      if current_item.parent_category and not current_item.is_category:
        # 子标签：[父分类语义, 子标签语义]
        parent_item = current_item.parent()
        if parent_item:
          current_tag_path = [parent_item.semantic_tag, current_item.semantic_tag]
      else:
        # 顶层标签：[标签语义]
        current_tag_path = [current_item.semantic_tag]

    self.load_tags()

    # 保持当前选中的标签
    if current_tag_path:
      selected_item = None
      parent_category = None

      # 处理标签路径
      if len(current_tag_path) == 2:
        # 子标签路径：[父分类语义, 子标签语义]
        parent_semantic, child_semantic = current_tag_path
        for i in range(self.ui.categoriesTreeWidget.topLevelItemCount()):
          top_item = self.ui.categoriesTreeWidget.topLevelItem(i)
          if top_item.semantic_tag == parent_semantic:
            # 查找子标签
            for j in range(top_item.childCount()):
              child_item = top_item.child(j)
              if child_item.semantic_tag == child_semantic:
                selected_item = child_item
                parent_category = parent_semantic
                # 展开父项
                top_item.setExpanded(True)
                break
            break
      else:
        # 单标签路径：[分类语义]
        semantic_tag = current_tag_path[0]
        if semantic_tag == AssetTagManager.get_semantic_tag(AssetTagType.ALL):
          selected_item = self.all_tag_item
        else:
          for i in range(self.ui.categoriesTreeWidget.topLevelItemCount()):
            top_item = self.ui.categoriesTreeWidget.topLevelItem(i)
            if top_item.semantic_tag == semantic_tag:
              selected_item = top_item
              break
            # 检查子标签
            for j in range(top_item.childCount()):
              child_item = top_item.child(j)
              if child_item.semantic_tag == semantic_tag:
                selected_item = child_item
                parent_category = top_item.semantic_tag
                # 展开父项
                top_item.setExpanded(True)
                break

      if selected_item:
        self.ui.categoriesTreeWidget.setCurrentItem(selected_item)
        display_text = selected_item.text(0)
        self.current_tag = display_text

        # 设置标签链标题
        if parent_category and not selected_item.is_category:
          parent_item = selected_item.parent()
          if parent_item:
            parent_text = parent_item.text(0)
            parent_display = parent_text.split(' (')[0] if ' (' in parent_text else parent_text
            child_display = display_text.split(' (')[0] if ' (' in display_text else display_text
            self.ui.categoryTitleLabel.setText(f"{parent_display}-{child_display}")
          else:
            self.ui.categoryTitleLabel.setText(display_text)
        else:
          self.ui.categoryTitleLabel.setText(display_text)

        if update_asset_cards:
          self.load_asset_cards_for_tag(selected_item.semantic_tag, parent_category)
        elif update_card_texts:
          for asset_id, asset_card in self.asset_cards.items():
            asset_card.update_text()
    elif not current_item and update_card_texts:
      # 当没有选中项且需要更新文本时，选择第一个标签
      if self.ui.categoriesTreeWidget.topLevelItemCount() > 0:
        first_item = self.ui.categoriesTreeWidget.topLevelItem(0)
        self.ui.categoriesTreeWidget.setCurrentItem(first_item)
        self.current_tag = first_item.text(0)
        self.ui.categoryTitleLabel.setText(self.current_tag)

        for asset_id, asset_card in self.asset_cards.items():
          asset_card.update_text()

  def _on_tags_updated(self):
    self._refresh_tags_and_restore_selection(update_asset_cards=False, update_card_texts=False)

  def update_text(self):
    super().update_text()
    # 翻译更新时，只更新现有卡片的文本，不重新加载卡片
    self._refresh_tags_and_restore_selection(update_asset_cards=False, update_card_texts=True)
