# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from typing import Tuple
from collections import OrderedDict
from PySide6.QtWidgets import QWidget, QVBoxLayout,  QPushButton, QSizePolicy, QLabel, QListWidgetItem, QLayout
from PySide6.QtCore import Qt, QSize, QThread, QMetaObject, Q_ARG
from PySide6.QtGui import QFontMetrics, QFont, QMouseEvent
from ..componentwidgets.assetcardwidget import ElidedLabel, ElidedPushButton
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack, ImagePackDescriptor
from ..toolwidgetinterface import *
from ..forms.generated.ui_assetbrowserwidget import Ui_AssetBrowserWidget
from ..settingsdict import SettingsDict
from ..util.tagmanager import TagManager
from ..util.asset_thumbnail import get_thumbnail_manager, create_thumbnail_worker
from ..mainwindowinterface import MainWindowInterface
from .tageditdialog import TagEditDialog
from .imagepack import ImagePackWidget
from preppipe_gui_pyside6.util.asset_widget_style import StyleManager

TR_gui_tool_assetbrowser = TranslationDomain("gui_tool_assetbrowser")

TRANSLATION_DOMAIN = "gui_tool_assetbrowser"

class TagListItem(QListWidgetItem):
  """标签列表项类，扩展QListWidgetItem以存储标签语义信息

  封装标签的语义标识和原始文本，避免需要从显示文本中解析信息
  """
  def __init__(self, display_text, semantic_tag=None, is_all_tag=False):
    """初始化标签列表项

    Args:
      display_text: 显示在UI上的文本
      semantic_tag: 标签的语义标识
      is_all_tag: 是否为"全部"标签
    """
    super().__init__(display_text)
    self.semantic_tag = semantic_tag
    self.is_all_tag = is_all_tag

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  SETTINGS_KEY_TAGS = "persistent/assetmanager/custom_asset_tags"
  SETTINGS_KEY_CURRENT_TAG = "persistent/assetmanager/current_tag"
  current_tag: str
  assets_by_tag: OrderedDict[str, Tuple[QListWidgetItem, dict[str, object]]]

  asset_cards: dict[str, QWidget]
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
  _tr_no_tags = TR_gui_tool_assetbrowser.tr("tagmanager_no_tags",
    en="No tags",
    zh_cn="无标签",
    zh_hk="無標籤",
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
    self.tag_manager = TagManager.get_instance()
    self.tag_buttons = {}

    self.tags_font = QFont()
    self.name_font = QFont()
    self.name_font.setWeight(QFont.Weight.Bold)
    self.tags_font_metrics = QFontMetrics(self.tags_font)
    self.name_font_metrics = QFontMetrics(self.name_font)

    self._update_theme_styles()
    self.bind_text(self.ui.categoryTitleLabel.setText, self._tr_select_tag)
    self.ui.categoriesListWidget.itemClicked.connect(self.on_tag_selected)
    self.ui.thumbnailsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.ui.thumbnailsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    self.flow_layout = self.ui.thumbnailsFlowLayout
    self.flow_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    self.flow_layout.setVerticalSpacing(15)
    self.ui.thumbnailsScrollAreaWidgetContents.resizeEvent = self._on_container_resized
    self.load_all_assets()
    self.load_tags()

    settings = SettingsDict.instance()
    saved_tag = settings.get(self.SETTINGS_KEY_CURRENT_TAG)
    if saved_tag:
      tag_semantic_category = self.tag_manager.get_tag_semantic(saved_tag)
      if tag_semantic_category not in ["all", "background", "character", "other"]:
        # 自定义标签
        tag_semantic_category = "custom"

      # 基于语义类别查找并选择对应的标签
      target_tag = None
      if tag_semantic_category != "custom":
        # 预定义标签
        if tag_semantic_category == "all":
          target_tag = self.tag_manager.get_tr_all()
        elif tag_semantic_category == "background":
          target_tag = self.tag_manager.get_tr_background()
        elif tag_semantic_category == "character":
          target_tag = self.tag_manager.get_tr_character()
        elif tag_semantic_category == "other":
          target_tag = self.tag_manager.get_tr_other()
      else:
        # 自定义标签，直接使用保存的文本
        target_tag = saved_tag

      # 查找并选中对应的标签
      if target_tag:
        # 特殊处理"全部"标签，直接选择索引0的项目
        if target_tag == self.tag_manager.get_tr_all():
          all_item = self.ui.categoriesListWidget.item(0)
          self.ui.categoriesListWidget.setCurrentItem(all_item)
          self.on_tag_selected(all_item)
        else:
          # 使用.get方法直接获取标签项，避免嵌套if语句
          # 如果标签不存在或对应的item为None，则默认选中"全部"标签
          item, _ = self.assets_by_tag.get(target_tag, (None, None))
          if item:
            self.ui.categoriesListWidget.setCurrentItem(item)
            self.on_tag_selected(item)
          else:
            all_item = self.ui.categoriesListWidget.item(0)
            self.ui.categoriesListWidget.setCurrentItem(all_item)
            self.on_tag_selected(all_item)

  def changeEvent(self, event):
    """重写changeEvent方法来监听系统主题变化"""
    if event.type() == QEvent.PaletteChange:
      # 系统主题变化时更新样式并重新应用所有缩略图的样式
      self._on_palette_changed(self.palette())
    super().changeEvent(event)

  def load_all_assets(self):
    """加载所有素材ID"""
    asset_manager = AssetManager.get_instance()
    self.all_asset_ids = []
    for asset_id, asset_info in asset_manager._assets.items():
      asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        self.all_asset_ids.append(asset_id)



  def load_tags(self):
    """从TagManager加载标签并统一合并归类"""
    tags_dict = self.tag_manager.get_tags_dict()
    self.assets_by_tag = OrderedDict()
    asset_manager = AssetManager.get_instance()

    background_tag = self.tag_manager.get_tr_background()
    character_tag = self.tag_manager.get_tr_character()
    other_tag = self.tag_manager.get_tr_other()

    # 根据素材类型自动分类
    for asset_id in self.all_asset_ids:
      try:
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          descriptor = ImagePack.get_descriptor_by_id(asset_id)
          if descriptor:
            pack_type = descriptor.get_image_pack_type()
            if pack_type == ImagePackDescriptor.ImagePackType.BACKGROUND:
              category_tag = background_tag
              semantic = "background"
            elif pack_type == ImagePackDescriptor.ImagePackType.CHARACTER:
              category_tag = character_tag
              semantic = "character"
            else:
              category_tag = other_tag
              semantic = "other"
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

    # 清理和规范化标签字典
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
    # 尝试加载上次选中的标签，如果不存在则默认选择全部
    settings = SettingsDict.instance()
    # 只保存和使用语义标识，不兼容旧版设置
    semantic_tag = settings.get(self.SETTINGS_KEY_CURRENT_TAG, "all")
    # 从语义标识获取显示文本
    tag_text = self.tag_manager.get_tag_display_text(semantic_tag)

    # 确保使用有效的语义标识
    if self.tag_manager.get_tag_semantic(tag_text) != semantic_tag:
      semantic_tag = "all"
      tag_text = self.tag_manager.get_tr_all()

    # 更新设置，确保保存的是语义标识
    settings[self.SETTINGS_KEY_CURRENT_TAG] = semantic_tag
    self.current_tag = tag_text
    self.ui.categoryTitleLabel.setText(self.current_tag)
    if semantic_tag == "all":
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

  def update_tags_list(self):
    """更新标签列表显示，同时显示标签对应的素材个数"""
    self.ui.categoriesListWidget.clear()
    all_count = len(self.all_asset_ids)
    all_text = self.tag_manager.get_tr_all()
    all_item = TagListItem(f"{all_text} ({all_count})", semantic_tag="all", is_all_tag=True)
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
      tag_semantic = "all"
    else:
      tag_semantic = item.semantic_tag
    settings = SettingsDict.instance()
    settings[self.SETTINGS_KEY_CURRENT_TAG] = tag_semantic
    self.load_asset_cards_for_tag(tag_semantic)

  def load_asset_cards_for_tag(self, tag: str):
    self.clear_asset_cards()
    self.asset_cards_loaded = False
    self._async_thumbnails_remaining = 0
    asset_ids_to_show = []
    if tag == "all":
      asset_ids_to_show = self.all_asset_ids
    else:
      display_tag = self.tag_manager.get_tag_display_text(tag)
      if display_tag in self.assets_by_tag:
        _, asset_dict = self.assets_by_tag[display_tag]
        asset_ids_to_show = list(asset_dict.keys())
    if not asset_ids_to_show:
      self.asset_cards_loaded = True
      return
    thumbnail_manager = get_thumbnail_manager()
    for asset_id in asset_ids_to_show:
      thumbnail_path = thumbnail_manager.get_or_generate_thumbnail(asset_id)
      if thumbnail_path:
        self.add_asset_card_to_flow(asset_id)
      else:
        self._async_thumbnails_remaining += 1
        worker = create_thumbnail_worker(asset_id)
        worker.signals.result.connect(self.on_asset_thumbnail_generated)
        thumbnail_manager.get_thread_pool().start(worker)

    if self._async_thumbnails_remaining == 0:
      self.asset_cards_loaded = True

  def _on_container_resized(self, event):
    QWidget.resizeEvent(self.ui.thumbnailsScrollAreaWidgetContents, event)

    current_width = self.ui.thumbnailsContainerWidget.width()

    if not hasattr(self, '_last_container_width'):
      self._last_container_width = -1

    if current_width != self._last_container_width:
      self._last_container_width = current_width

      if self.asset_cards and current_width > 0:
        card_width = self._calculate_optimal_card_width(current_width)
        card_height = int(card_width * 1.2)

        self.flow_layout.setItemSize(QSize(card_width, card_height))

        for asset_id, widget in self.asset_cards.items():
          widget.setFixedSize(card_width, card_height)

          for child in widget.findChildren(QLabel):
            if widget.findChildren(QLabel).index(child) == 0:
              layout = widget.layout()
              margins = layout.contentsMargins()
              spacing = layout.spacing()

              available_width = card_width - (margins.left() + margins.right())

              name_label_height = self.name_font_metrics.height()
              tags_label_height = self.tags_font_metrics.height()
              name_tags_height = name_label_height + tags_label_height + spacing
              available_height = card_height - (margins.top() + margins.bottom() + name_tags_height)

              child.setFixedSize(available_width, available_height)

              child._last_width = -1
              break
            elif hasattr(child, '_full_text'):
              child.resizeEvent(QResizeEvent(child.size(), child.size()))

    self.flow_layout.update()
    return event

  def _calculate_optimal_card_width(self, container_width):
    """根据容器宽度计算最佳卡片宽度，确保精确计算避免布局错误"""
    min_card_width = 160
    spacing = self.flow_layout.spacing()
    extra_safety_margin = 3
    columns = 1
    if container_width > min_card_width:
      theoretical_max_columns = (container_width + spacing) // (min_card_width + spacing)
      columns = min(theoretical_max_columns, 5)  # 限制最大列数，避免过窄
      while columns > 1:
        total_required_width = columns * min_card_width + (columns - 1) * spacing
        if total_required_width <= container_width:
          break
        columns -= 1
      if container_width >= min_card_width * 2 + spacing:
        columns = max(columns, 2)

    # 计算卡片宽度
    if columns > 1:
      available_space = container_width - (columns - 1) * spacing
      card_width = available_space // columns
      card_width = max(card_width, min_card_width)
      card_width = card_width - extra_safety_margin
    else:
      card_width = min(min_card_width, container_width - extra_safety_margin)

    card_width = max(100, card_width)
    return card_width

  def _create_asset_card(self, asset_id: str, card_width: int, card_height: int) -> QWidget:
    """创建资产卡片组件

    Args:
        asset_id: 资产的唯一标识符
        card_width: 卡片的宽度
        card_height: 卡片的高度

    Returns:
        配置完成的资产卡片Widget
    """
    container = self._create_card_container(card_width, card_height)
    self._add_image_section(container, asset_id, card_width, card_height)
    self._add_name_section(container, asset_id)
    self._add_tags_section(container, asset_id)
    self._setup_card_events(container, asset_id)
    return container

  def _create_card_container(self, card_width: int, card_height: int) -> QWidget:
    """创建卡片容器和基本布局

    Args:
        card_width: 卡片的宽度
        card_height: 卡片的高度

    Returns:
        配置好的卡片容器Widget
    """
    container = QWidget()
    container.setFixedSize(card_width, card_height)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    layout.setSizeConstraint(QLayout.SetFixedSize)
    StyleManager.apply_style(container, False)
    container.setContextMenuPolicy(Qt.NoContextMenu)
    return container

  def _add_image_section(self, container: QWidget, asset_id: str, card_width: int, card_height: int) -> QLabel:
    """添加图片部分到卡片容器

    确保所有类型的资产卡片（角色立绘和背景）使用统一的图片处理逻辑，避免布局差异。
    对所有类型卡片应用相同的尺寸计算、边距和缩放参数。

    Args:
        container: 卡片容器Widget
        asset_id: 资产的唯一标识符
        card_width: 卡片的宽度
        card_height: 卡片的高度

    Returns:
        创建的图片标签
    """
    image_label = QLabel()
    image_label.setAlignment(Qt.AlignCenter)
    StyleManager.apply_image_label_style(image_label)
    image_label.setMouseTracking(False)

    layout = container.layout()
    layout_margins = layout.contentsMargins()
    layout_spacing = layout.spacing()
    name_label_height = self.name_font_metrics.height()
    tags_label_height = self.tags_font_metrics.height()
    available_width = int(card_width - (layout_margins.left() + layout_margins.right()))
    available_height = int(card_height - (layout_margins.top() + layout_margins.bottom() +
                                      name_label_height + tags_label_height + layout_spacing))
    image_label.setFixedSize(available_width, available_height)

    thumbnail_manager = get_thumbnail_manager()
    scaled_pixmap = thumbnail_manager.get_scaled_pixmap(asset_id, available_width, available_height, margin_ratio=0.05)
    image_label.setPixmap(scaled_pixmap)

    image_label._last_width = available_width
    image_label._last_height = available_height
    image_label.resizeEvent = lambda event, img=image_label, aid=asset_id: self._update_image_on_resize(event, img, aid)

    layout.addWidget(image_label)
    return image_label

  def _add_name_section(self, container: QWidget, asset_id: str) -> ElidedLabel:
    """添加名称部分到卡片容器

    Args:
        container: 卡片容器Widget
        asset_id: 资产的唯一标识符

    Returns:
        创建的名称标签
    """
    name_label = ElidedLabel()
    name_label.setAlignment(Qt.AlignCenter)
    name_label.setWordWrap(False)  # 禁止自动换行
    name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    name_label.setMinimumHeight(name_label.fontMetrics().height() + 8)  # 保持足够的高度
    name_label.setTextInteractionFlags(Qt.NoTextInteraction)
    name_label.setProperty("is_name_label", True)

    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(asset_id)
    friendly_name = asset_id  # 默认使用asset_id
    if isinstance(asset, ImagePack):
        descriptor = ImagePack.get_descriptor_by_id(asset_id)
        if descriptor:
            name_obj = descriptor.get_name()
            if hasattr(name_obj, 'get'):
                friendly_name = name_obj.get()
            elif name_obj:
                friendly_name = name_obj

    name_label.setFullText(friendly_name)
    name_label.setFont(self.name_font)
    StyleManager.apply_label_style(name_label)
    name_label.setMouseTracking(False)

    container.layout().addWidget(name_label)
    return name_label

  def _add_tags_section(self, container: QWidget, asset_id: str) -> ElidedPushButton:
    """添加标签部分到卡片容器

    Args:
        container: 卡片容器Widget
        asset_id: 资产的唯一标识符

    Returns:
        创建的标签按钮
    """
    # 加载标签
    asset_tags = self.tag_manager.get_asset_tags(asset_id)
    # 转换标签为翻译后的文本
    translated_tags = self.tag_manager.translate_tags(asset_tags)

    tags_text = ", ".join(sorted(translated_tags))
    no_tags_text = self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
    tags_button = ElidedPushButton(tags_text if tags_text else no_tags_text, container)
    tags_button.setObjectName(f"tags_button_{asset_id}")

    # 使用标签字体作为标签按钮的字体
    tags_button.setFont(self.tags_font)
    tags_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    tag_button_height = int(self.tags_font_metrics.height() * 1.4)  # 进一步增加高度因子
    tags_button.setFixedHeight(tag_button_height)
    StyleManager.apply_tags_button_style(tags_button, tag_button_height)

    # 连接点击信号
    tags_button.clicked.connect(lambda: self.on_tags_button_clicked(asset_id, tags_button))
    tags_button._asset_id = asset_id

    if asset_id not in self.tag_buttons:
      self.tag_buttons[asset_id] = []
    self.tag_buttons[asset_id].append(tags_button)

    container.layout().addWidget(tags_button)
    return tags_button

  def _setup_card_events(self, container: QWidget, asset_id: str):
    """设置卡片的鼠标事件处理

    Args:
        container: 卡片容器Widget
        asset_id: 资产的唯一标识符
    """
    container.setMouseTracking(True)
    container.enterEvent = lambda event, aid=asset_id: self.on_asset_card_enter(aid)
    container.leaveEvent = lambda event, aid=asset_id: self.on_asset_card_leave(aid)
    container.mousePressEvent = lambda event, aid=asset_id: self.on_asset_card_clicked(aid, event)

    if asset_id == self.last_opened_asset_id:
      StyleManager.apply_style(container, True)
      for child in container.findChildren(QWidget):
        if child.property("is_name_label"):
          StyleManager.apply_label_style(child)

  def add_asset_card_to_flow(self, asset_id: str):
    """将资产卡片添加到流布局中，使用根据容器大小动态计算的尺寸

    使用ThumbnailManager单例获取资产的缩略图并创建卡片。
    """
    container_width = self.ui.thumbnailsContainerWidget.width()
    card_width = self._calculate_optimal_card_width(container_width)
    card_height = int(card_width * 1.2)
    asset_card = self._create_asset_card(asset_id, card_width, card_height)
    self.flow_layout.addWidget(asset_card)

    self.asset_cards[asset_id] = asset_card


  def _update_image_on_resize(self, event, image_label, asset_id):
    QLabel.resizeEvent(image_label, event)

    current_width = int(image_label.width())
    current_height = int(image_label.height())

    if current_width <= 1 or current_height <= 1:
      return  # 避免极端情况下的无效尺寸

    if not hasattr(image_label, '_last_width'):
      image_label._last_width = -1
    if not hasattr(image_label, '_last_height'):
      image_label._last_height = -1

    need_update = (current_width != image_label._last_width or
                  current_height != image_label._last_height)

    image_label._last_width = current_width
    image_label._last_height = current_height

    if need_update and current_width > 0 and current_height > 0:

      thumbnail_manager = get_thumbnail_manager()

      safe_width = max(1, current_width - 1)
      safe_height = max(1, current_height - 1)

      scaled_pixmap = thumbnail_manager.get_scaled_pixmap(asset_id, safe_width, safe_height, margin_ratio=0.05)
      image_label.setPixmap(scaled_pixmap)

  def clear_asset_cards(self):
    while self.flow_layout.count() > 0:
      item = self.flow_layout.takeAt(0)
      if item.widget() is not None:
        item.widget().deleteLater()
      del item

    self.asset_cards.clear()
    self.tag_buttons.clear()

  def on_asset_thumbnail_generated(self, asset_id: str, thumbnail_path: str):
    """当资产缩略图生成完成后调用"""
    if QThread.currentThread() != QApplication.instance().thread():
      QMetaObject.invokeMethod(self, 'on_asset_thumbnail_generated',
                              Qt.QueuedConnection,
                              Q_ARG(str, asset_id),
                              Q_ARG(str, thumbnail_path))
      return

    if thumbnail_path:
      self.add_asset_card_to_flow(asset_id)

      # 如果是最后打开的资源，更新其样式为选中样式
      if self.last_opened_asset_id and self.last_opened_asset_id == asset_id:
        if asset_id in self.asset_cards:
          StyleManager.apply_style(self.asset_cards[asset_id], True)

    self._async_thumbnails_remaining -= 1
    if self._async_thumbnails_remaining <= 0:
      self.asset_cards_loaded = True

  def on_asset_card_enter(self, asset_id: str):
    if asset_id in self.asset_cards:
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(self.asset_cards[asset_id], is_selected, True)
      for child in self.asset_cards[asset_id].findChildren(QLabel):
        if hasattr(child, '_full_text'):
          StyleManager.apply_label_style(child)

  def on_asset_card_leave(self, asset_id: str):
    if asset_id in self.asset_cards:
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(self.asset_cards[asset_id], is_selected)
      for child in self.asset_cards[asset_id].findChildren(QLabel):
        if hasattr(child, '_full_text'):
          StyleManager.apply_label_style(child)

      for child in self.asset_cards[asset_id].findChildren(QPushButton):
        if hasattr(child, '_asset_id') and child._asset_id == asset_id:
          child.resizeEvent(None)

  def _on_palette_changed(self, palette):
    """当系统调色板变化时更新主题样式"""
    self._update_theme_styles(palette)

  def _update_theme_styles(self, palette=None):
    self.normal_style = StyleManager.get_style('normal', palette)
    self.hover_style = StyleManager.get_style('hover', palette)
    self.selected_style = StyleManager.get_style('selected', palette)
    self.selected_hover_style = StyleManager.get_style('selected_hover', palette)
    self.normal_style_name_color = StyleManager.get_style('name_color', palette)
    self.image_background_color = StyleManager.get_style('image_background', palette)

    for asset_id, widget in self.asset_cards.items():
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(widget, is_selected, palette=palette)

      for child in widget.findChildren(QLabel):
          is_name = child.property("is_name_label") or child.text()
          if is_name:
            StyleManager.apply_label_style(child)

    for asset_id, buttons in self.tag_buttons.items():
      for button in buttons:
        height = button.height()
        StyleManager.apply_tags_button_style(button, height)

  def on_asset_card_clicked(self, asset_id: str, event: QMouseEvent):
      """处理资产卡片点击事件，打开详情页面"""
      if event.button() == Qt.LeftButton:
        asset_manager = AssetManager.get_instance()
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          if self.last_opened_asset_id and self.last_opened_asset_id in self.asset_cards:
            StyleManager.apply_style(self.asset_cards[self.last_opened_asset_id], False)
          self.last_opened_asset_id = asset_id
          StyleManager.apply_style(self.asset_cards[asset_id], True)
          for child in self.asset_cards[asset_id].findChildren(QLabel):
            if hasattr(child, '_full_text'):
              StyleManager.apply_label_style(child)
          MainWindowInterface.getHandle(self).requestOpen(
            ImagePackWidget.getToolInfo(packid=asset_id)
          )

  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="assetbrowser",
      name=cls._tr_toolname_assetbrowser,
      tooltip=cls._tr_tooltip_assetbrowser,
      widget=cls,
    )

  def on_tags_button_clicked(self, asset_id, button):
    if self.last_opened_asset_id != asset_id:
      if self.last_opened_asset_id and self.last_opened_asset_id in self.asset_cards:
        StyleManager.apply_style(self.asset_cards[self.last_opened_asset_id], False)
      self.last_opened_asset_id = asset_id
      StyleManager.apply_style(self.asset_cards[asset_id], True)
      for child in self.asset_cards[asset_id].findChildren(QLabel):
        if hasattr(child, '_full_text'):
          StyleManager.apply_label_style(child)

    self.open_tag_edit_dialog(asset_id, button)

  def open_tag_edit_dialog(self, asset_id, button=None):
    dialog = TagEditDialog(asset_id, self, self)
    dialog.exec()

    if button:
      button.setDown(False)
      button.clearFocus()
      button.update()

  def update_asset_card_tags(self, asset_id=None):
    if asset_id:
      self._update_single_asset_tags(asset_id)
    else:
      for asset_id_iter in self.asset_cards.keys():
        self._update_single_asset_tags(asset_id_iter)

  def _update_single_asset_tags(self, asset_id):
    if asset_id not in self.asset_cards:
      return

    asset_tags = self.tag_manager.get_asset_tags_display(asset_id)
    tags_text = ", ".join(sorted(asset_tags))

    if asset_id in self.tag_buttons:
      for button in self.tag_buttons[asset_id]:
        button._full_text = tags_text if tags_text else self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
        button.resizeEvent(None)
    else:
      asset_card_widget = self.asset_cards.get(asset_id)
      if asset_card_widget:
        tags_button = asset_card_widget.findChild(QPushButton, f"tags_button_{asset_id}")
        if tags_button:
          tags_button._full_text = tags_text if tags_text else self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
          tags_button.resizeEvent(None)

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

          if self.asset_cards_loaded:
            for asset_id in list(self.asset_cards.keys()):
              self._update_single_asset_tags(asset_id)

          self.load_asset_cards_for_tag(current_semantic)
          break
    elif not current_item:
      self.ui.categoriesListWidget.setCurrentRow(0)
      first_item = self.ui.categoriesListWidget.item(0)
      if first_item:
        display_text = first_item.text()
        self.current_tag = display_text
        self.ui.categoryTitleLabel.setText(self.current_tag)

        tag_semantic = first_item.semantic_tag
        self.load_asset_cards_for_tag(tag_semantic)

        if self.asset_cards_loaded:
          for asset_id in list(self.asset_cards.keys()):
            self._update_single_asset_tags(asset_id)