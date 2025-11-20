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

# 常量定义，保持与TranslationDomain一致
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

  def get_semantic_tag(self):
    """获取标签的语义标识"""
    return self.semantic_tag

  def is_all(self):
    """判断是否为"全部"标签"""
    return self.is_all_tag

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  # 设置字典中存储标签的键
  SETTINGS_KEY_TAGS = "persistent/assetmanager/custom_asset_tags"
  SETTINGS_KEY_CURRENT_TAG = "persistent/assetmanager/current_tag"
  # 当前选中的标签
  current_tag: str
  # 标签到素材的映射字典，格式：{tag_name: Tuple[QListWidgetItem, dict[asset_id: asset_object]]}
  assets_by_tag: OrderedDict[str, Tuple[QListWidgetItem, dict[str, object]]]

  # 资产卡片字典，用于快速访问
  asset_cards: dict[str, QWidget]
  # 所有素材ID列表
  all_asset_ids: list[str]

  # 工具名称和提示信息
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
  # "无标签"提示文本
  _tr_no_tags = TR_gui_tool_assetbrowser.tr("tagmanager_no_tags",
    en="No tags",
    zh_cn="无标签",
    zh_hk="無標籤",
  )
  # "选择标签"提示文本
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
    # 存储"全部"标签项的映射
    self.all_tag_item = None
    # 缩略图加载状态标志
    # 上次打开的素材ID
    self.last_opened_asset_id = None
    # 获取标签管理器单例
    self.tag_manager = TagManager.get_instance()
    # 用于存储标签按钮的引用
    self.tag_buttons = {}

    # 字体缓存 - 预先创建并缓存字体以提高性能
    self.tags_font = QFont()
    # 创建名称标签使用的加粗字体缓存
    self.name_font = QFont()
    self.name_font.setWeight(QFont.Weight.Bold)
    # 缓存字体度量以避免重复计算
    self.tags_font_metrics = QFontMetrics(self.tags_font)
    self.name_font_metrics = QFontMetrics(self.name_font)

    # 初始化当前样式引用
    self._update_theme_styles()
    # 绑定文本
    self.bind_text(self.ui.categoryTitleLabel.setText, self._tr_select_tag)
    # 连接信号槽
    self.ui.categoriesListWidget.itemClicked.connect(self.on_tag_selected)
    # 禁用横向滚动条
    self.ui.thumbnailsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    # 允许垂直滚动条根据需要显示
    self.ui.thumbnailsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    # 直接使用UI文件中定义的FlowLayout
    self.flow_layout = self.ui.thumbnailsFlowLayout
    self.flow_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    # 设置更大的垂直间距以优化卡片之间的行距
    self.flow_layout.setVerticalSpacing(15)
    # 连接大小变化信号，当窗口大小改变时重新调整布局
    self.ui.thumbnailsScrollAreaWidgetContents.resizeEvent = self._on_container_resized
    # 加载所有素材和标签
    self.load_all_assets()
    self.load_tags()

    # 从设置中加载之前保存的标签选择（考虑多语言情况）
    settings = SettingsDict.instance()
    saved_tag = settings.get(self.SETTINGS_KEY_CURRENT_TAG)
    if saved_tag:
      # 识别保存标签的语义类别（不依赖于语言）
      # 直接使用TagManager获取语义标识，更好地支持多语言
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

  # 移除_initialize_semantic_mappings方法，因为语义映射完全由TagManager管理

  # 移除代理方法，直接使用TagManager的相应方法
  # _clean_and_normalize_tags_dict和_translate_tags已不再需要

  def load_tags(self):
    """从TagManager加载标签并统一合并归类"""
    # 使用TagManager获取标签字典
    tags_dict = self.tag_manager.get_tags_dict()
    # 初始化标签到素材的映射字典
    self.assets_by_tag = OrderedDict()
    # 从assetmanager获取所有素材
    asset_manager = AssetManager.get_instance()
    # 语义映射由TagManager自动处理，无需在此初始化

    # 获取当前语言的标签文本
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
            # 根据类型确定标签
            if pack_type == ImagePackDescriptor.ImagePackType.BACKGROUND:
              category_tag = background_tag
              semantic = "background"
            elif pack_type == ImagePackDescriptor.ImagePackType.CHARACTER:
              category_tag = character_tag
              semantic = "character"
            else:
              category_tag = other_tag
              semantic = "other"
            # 检查是否有自定义标签设置
            has_custom_tags = asset_id in tags_dict and tags_dict[asset_id]
            # 确保标签存在于assets_by_tag中
            if category_tag not in self.assets_by_tag:
              self.assets_by_tag[category_tag] = (None, {})
            # 添加资产到映射
            _, asset_dict = self.assets_by_tag[category_tag]
            asset_dict[asset_id] = asset
            # 自动为资产添加类型标签，但仅在没有自定义标签的情况下
            if not has_custom_tags:
              if asset_id not in tags_dict:
                tags_dict[asset_id] = set()
              # 使用语义标识存储
              tags_dict[asset_id].add(semantic)
      except Exception:
        continue

    # 清理和规范化标签字典
    tags_dict = self.tag_manager.clean_and_normalize_tags_dict(tags_dict)

    # 现在处理标签到素材的映射
    for asset_id, tags in tags_dict.items():
      try:
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          for tag in tags:
            # 使用TagManager获取标签的显示文本
            display_tag = self.tag_manager.get_tag_display_text(tag)

            # 确保标签存在于assets_by_tag中，并且直接添加素材
            if display_tag not in self.assets_by_tag:
              self.assets_by_tag[display_tag] = (None, {asset_id: asset})
            else:
              # 如果标签已存在，添加素材到现有字典
              _, asset_dict = self.assets_by_tag[display_tag]
              asset_dict[asset_id] = asset
      except Exception:
        # 忽略获取素材失败的情况
        continue

    # 保存更新后的标签字典
    self.tag_manager.save_tags_dict(tags_dict)
    # 显示标签列表
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
    # 选中对应的标签项
    # 优先使用保存的引用或直接索引
    if semantic_tag == "all":
      # 特殊处理"全部"标签，直接选择索引0的项目或使用保存的引用
      if self.all_tag_item:
        self.ui.categoriesListWidget.setCurrentItem(self.all_tag_item)
      else:
        self.ui.categoriesListWidget.setCurrentItem(self.ui.categoriesListWidget.item(0))
    else:
      # 尝试直接从assets_by_tag获取标签项
      tag_text = self.tag_manager.get_tag_display_text(semantic_tag)
      if tag_text in self.assets_by_tag:
        item, _ = self.assets_by_tag[tag_text]
        if item:
          self.ui.categoriesListWidget.setCurrentItem(item)
    self.load_asset_cards_for_tag(semantic_tag)

  def update_tags_list(self):
    """更新标签列表显示，同时显示标签对应的素材个数"""
    self.ui.categoriesListWidget.clear()
    # 添加"全部"列表项
    all_count = len(self.all_asset_ids)
    all_text = self.tag_manager.get_tr_all()
    all_item = TagListItem(f"{all_text} ({all_count})", semantic_tag="all", is_all_tag=True)
    font = all_item.font()
    font.setBold(True)
    all_item.setFont(font)
    self.ui.categoriesListWidget.addItem(all_item)
    # 保存"全部"标签项的引用
    self.all_tag_item = all_item
    # 添加所有实际标签
    for tag in self.assets_by_tag.keys():
      count = len(self.assets_by_tag[tag][1])
      # 只显示有素材的标签
      if count > 0:
        # 获取标签的语义标识
        semantic_tag = self.tag_manager.tag_text_to_semantic.get(tag, tag)
        # 使用TagListItem替代普通QListWidgetItem
        item = TagListItem(f"{tag} ({count})", semantic_tag=semantic_tag)
        self.ui.categoriesListWidget.addItem(item)
        # 更新assets_by_tag字典中的TagListItem引用
        _, asset_dict = self.assets_by_tag[tag]
        self.assets_by_tag[tag] = (item, asset_dict)
        # 确保标签的映射关系存在
        if tag not in self.tag_manager.tag_text_to_semantic:
          self.tag_manager.add_custom_tag_mapping(tag, tag)

  def on_tag_selected(self, item: TagListItem):
    """当用户从分类列表中选择一个标签时调用"""
    display_text = item.text()
    self.current_tag = display_text
    self.ui.categoryTitleLabel.setText(self.current_tag)
    # 获取标签的语义标识
    if item.is_all():
      tag_semantic = "all"
    else:
      tag_semantic = item.get_semantic_tag()
    # 保存当前选中的标签语义标识到设置
    settings = SettingsDict.instance()
    settings[self.SETTINGS_KEY_CURRENT_TAG] = tag_semantic
    # 加载对应的资产卡片
    self.load_asset_cards_for_tag(tag_semantic)

  def load_asset_cards_for_tag(self, tag: str):
    """加载指定标签的资产卡片，预定义标签使用语义标识，自定义标签直接使用原始文本"""
    # 清空现有资产卡片
    self.clear_asset_cards()
    self.asset_cards_loaded = False
    self._async_thumbnails_remaining = 0
    asset_ids_to_show = []
    # 确定要显示的素材
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
    # 获取缩略图管理器实例
    thumbnail_manager = get_thumbnail_manager()
    # 检查并生成缩略图
    for asset_id in asset_ids_to_show:
      # 使用ThumbnailManager获取或生成缩略图
      thumbnail_path = thumbnail_manager.get_or_generate_thumbnail(asset_id)
      if thumbnail_path:
        # 使用缓存的缩略图路径
        self.add_asset_card_to_flow(asset_id)
      else:
        # 增加异步缩略图计数
        self._async_thumbnails_remaining += 1
        # 使用ThumbnailManager的线程池异步生成缩略图
        worker = create_thumbnail_worker(asset_id)
        worker.signals.result.connect(self.on_asset_thumbnail_generated)
        thumbnail_manager.get_thread_pool().start(worker)

    # 如果没有异步缩略图需要生成，则设置为已加载完成
    if self._async_thumbnails_remaining == 0:
      self.asset_cards_loaded = True

  def _on_container_resized(self, event):
    """当容器大小改变时重新调整布局"""
    # 调用原始QWidget的resizeEvent方法
    QWidget.resizeEvent(self.ui.thumbnailsScrollAreaWidgetContents, event)

    current_width = self.ui.thumbnailsContainerWidget.width()

    # 检查是否需要重新布局
    if not hasattr(self, '_last_container_width'):
      self._last_container_width = -1

    if current_width != self._last_container_width:
      # 记录当前宽度
      self._last_container_width = current_width

      # 如果有资产卡片，智能调整卡片大小而不是重新加载
      if self.asset_cards and current_width > 0:
        # 计算最佳卡片大小
        card_width = self._calculate_optimal_card_width(current_width)
        card_height = int(card_width * 1.2)

        # 更新FlowLayout中的项目大小
        self.flow_layout.setItemSize(QSize(card_width, card_height))

        # 为每个资产卡片调整内部元素大小
        for asset_id, widget in self.asset_cards.items():
          # 调整卡片容器大小
          widget.setFixedSize(card_width, card_height)

          # 找到内部的图像标签并调整
          for child in widget.findChildren(QLabel):
            # 假设第一个QLabel是图像标签
            if widget.findChildren(QLabel).index(child) == 0:
              # 获取布局信息
              layout = widget.layout()
              margins = layout.contentsMargins()
              spacing = layout.spacing()

              # 计算图像可用空间
              available_width = card_width - (margins.left() + margins.right())

              # 计算图像高度
              name_label_height = self.name_font_metrics.height()
              tags_label_height = self.tags_font_metrics.height()
              name_tags_height = name_label_height + tags_label_height + spacing
              available_height = card_height - (margins.top() + margins.bottom() + name_tags_height)

              # 设置图像标签大小
              child.setFixedSize(available_width, available_height)

              # 更新图像缩放
              child._last_width = -1  # 强制重新调整大小
              break
            # 处理名称标签和标签标签，更新其文本省略
            elif hasattr(child, '_full_text'):  # 保留此检查，因为不是所有QLabel都有_full_text
              # 触发文本省略更新
              child.resizeEvent(QResizeEvent(child.size(), child.size()))

    # 通知FlowLayout更新布局
    self.flow_layout.update()

    return event

  def _calculate_optimal_card_width(self, container_width):
    """根据容器宽度计算最佳卡片宽度"""
    # 最小卡片宽度
    min_card_width = 160
    # 获取间距
    spacing = self.flow_layout.spacing()
    # 计算可显示的最大列数
    columns = max(1, container_width // (min_card_width + spacing))
    # 限制最小列数为2
    if container_width >= min_card_width * 2 + spacing:
      columns = max(columns, 2)
    # 计算卡片宽度
    if columns > 1:
      card_width = (container_width - (columns - 1) * spacing) // columns
      # 确保卡片宽度不小于最小宽度
      card_width = max(card_width, min_card_width)
    else:
      # 单列时，使用最小宽度但不超过容器宽度
      card_width = min(min_card_width, container_width)
    return card_width

  def _create_asset_card(self, asset_id: str, card_width: int, card_height: int) -> QWidget:
    """创建资产卡片组件
    
    将卡片创建过程拆分为多个子方法，提高代码的可读性和可维护性。
    
    Args:
        asset_id: 资产的唯一标识符
        card_width: 卡片的宽度
        card_height: 卡片的高度
        
    Returns:
        配置完成的资产卡片Widget
    """
    # 创建卡片容器
    container = self._create_card_container(card_width, card_height)
    # 添加图片部分
    self._add_image_section(container, asset_id, card_width, card_height)
    # 添加名称部分
    self._add_name_section(container, asset_id)
    # 添加标签部分
    self._add_tags_section(container, asset_id)
    # 设置事件处理
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
    # 创建资产卡片容器
    container = QWidget()
    container.setFixedSize(card_width, card_height)
    layout = QVBoxLayout(container)
    # 设置布局参数
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    layout.setSizeConstraint(QLayout.SetFixedSize)
    # 设置容器样式
    StyleManager.apply_style(container, False)
    # 设置右键菜单禁用
    container.setContextMenuPolicy(Qt.NoContextMenu)
    return container
    
  def _add_image_section(self, container: QWidget, asset_id: str, card_width: int, card_height: int) -> QLabel:
    """添加图片部分到卡片容器
    
    Args:
        container: 卡片容器Widget
        asset_id: 资产的唯一标识符
        card_width: 卡片的宽度
        card_height: 卡片的高度
        
    Returns:
        创建的图片标签
    """
    # 创建图片标签
    image_label = QLabel()
    image_label.setAlignment(Qt.AlignCenter)
    # 使用StyleManager应用图片标签样式
    StyleManager.apply_image_label_style(image_label)
    image_label.setMouseTracking(False)
    
    # 获取布局并计算图片标签的大小
    layout = container.layout()
    layout_margins = layout.contentsMargins()
    layout_spacing = layout.spacing()
    # 计算名称和标签的高度
    name_label_height = self.name_font_metrics.height()
    tags_label_height = self.tags_font_metrics.height()
    # 计算图片区域的可用空间
    available_width = card_width - (layout_margins.left() + layout_margins.right())
    available_height = card_height - (layout_margins.top() + layout_margins.bottom() +
                                      name_label_height + tags_label_height + layout_spacing)
    # 设置图片标签固定大小
    image_label.setFixedSize(available_width, available_height)
    
    # 获取缩略图管理器
    thumbnail_manager = get_thumbnail_manager()
    # 使用ThumbnailManager获取缩放后的pixmap，传递margin_ratio参数
    scaled_pixmap = thumbnail_manager.get_scaled_pixmap(asset_id, available_width, available_height, margin_ratio=0.05)
    # 设置图片并确保居中显示
    image_label.setPixmap(scaled_pixmap)
    
    # 记录当前尺寸，避免不必要的更新
    image_label._last_width = available_width
    image_label._last_height = available_height
    # 连接图片标签的调整大小信号以更新图片
    image_label.resizeEvent = lambda event, img=image_label, aid=asset_id: self._update_image_on_resize(event, img, aid)
    
    # 添加到布局
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
    # 创建名称标签 - 使用自定义的ElidedLabel类来实现文本溢出控制
    name_label = ElidedLabel()
    name_label.setAlignment(Qt.AlignCenter)
    name_label.setWordWrap(False)  # 禁止自动换行
    # 设置名称标签为自适应宽度策略
    name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    name_label.setMinimumHeight(name_label.fontMetrics().height() + 8)  # 保持足够的高度
    name_label.setTextInteractionFlags(Qt.NoTextInteraction)
    # 添加属性标识，方便在更新主题时识别
    name_label.setProperty("is_name_label", True)
    
    # 获取友好名称
    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(asset_id)
    friendly_name = asset_id  # 默认使用asset_id
    if isinstance(asset, ImagePack):
        descriptor = ImagePack.get_descriptor_by_id(asset_id)
        if descriptor:
            # 使用get_name()方法获取友好名称
            name_obj = descriptor.get_name()
            if hasattr(name_obj, 'get'):
                # 如果是Translatable对象
                friendly_name = name_obj.get()
            elif name_obj:
                # 如果是普通字符串
                friendly_name = name_obj
    
    # 使用自定义方法设置完整文本，让ElidedLabel内部处理文本省略
    name_label.setFullText(friendly_name)
    # 使用缓存的name_font作为名称标签的字体（加粗效果）
    name_label.setFont(self.name_font)
    # 使用StyleManager应用标签样式
    StyleManager.apply_label_style(name_label)
    name_label.setMouseTracking(False)
    
    # 添加到布局
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
    
    # 创建标签按钮 - 使用自定义的ElidedPushButton类来实现文本溢出控制
    tags_text = ", ".join(sorted(translated_tags))
    no_tags_text = self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
    tags_button = ElidedPushButton(tags_text if tags_text else no_tags_text, container)
    tags_button.setObjectName(f"tags_button_{asset_id}")
    
    # 使用标签字体作为标签按钮的字体
    tags_button.setFont(self.tags_font)
    # 设置按钮的大小策略 - 使用固定高度而非最小高度
    tags_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    # 设置固定高度而不是最小高度，进一步增加按钮高度使其更大
    tag_button_height = int(self.tags_font_metrics.height() * 1.4)  # 进一步增加高度因子
    tags_button.setFixedHeight(tag_button_height)
    # 使用样式管理器设置按钮样式
    StyleManager.apply_tags_button_style(tags_button, tag_button_height)
    
    # 连接点击信号
    tags_button.clicked.connect(lambda: self.on_tags_button_clicked(asset_id, tags_button))
    # 存储标签按钮的asset_id，用于标识和后续更新
    tags_button._asset_id = asset_id
    
    # 存储按钮引用
    if asset_id not in self.tag_buttons:
      self.tag_buttons[asset_id] = []
    self.tag_buttons[asset_id].append(tags_button)
    
    # 添加到布局
    container.layout().addWidget(tags_button)
    return tags_button
    
  def _setup_card_events(self, container: QWidget, asset_id: str):
    """设置卡片的鼠标事件处理
    
    Args:
        container: 卡片容器Widget
        asset_id: 资产的唯一标识符
    """
    # 设置鼠标事件处理
    container.setMouseTracking(True)
    container.enterEvent = lambda event, aid=asset_id: self.on_asset_card_enter(aid)
    container.leaveEvent = lambda event, aid=asset_id: self.on_asset_card_leave(aid)
    container.mousePressEvent = lambda event, aid=asset_id: self.on_asset_card_clicked(aid, event)
    
    # 恢复上次选中的高亮状态
    if asset_id == self.last_opened_asset_id:
      # 使用StyleManager统一应用选中样式
      StyleManager.apply_style(container, True)
      # 确保name_label保持透明背景，不受选中样式影响
      for child in container.findChildren(QWidget):
        if child.property("is_name_label"):
          StyleManager.apply_label_style(child)

  def add_asset_card_to_flow(self, asset_id: str):
    """将资产卡片添加到流布局中，使用根据容器大小动态计算的尺寸

    使用ThumbnailManager单例获取资产的缩略图并创建卡片。
    """
    # 计算最佳卡片大小
    container_width = self.ui.thumbnailsContainerWidget.width()
    card_width = self._calculate_optimal_card_width(container_width)
    card_height = int(card_width * 1.2)
    # 创建资产卡片
    asset_card = self._create_asset_card(asset_id, card_width, card_height)
    # 添加到FlowLayout
    self.flow_layout.addWidget(asset_card)

    # 存储到字典中以便后续访问
    self.asset_cards[asset_id] = asset_card


  def _update_image_on_resize(self, event, image_label, asset_id):
    """当图片标签大小改变时更新图片"""
    # 调用原始QLabel的resizeEvent方法
    QLabel.resizeEvent(image_label, event)

    current_width = image_label.width()
    current_height = image_label.height()

    # 初始化属性（如果不存在）
    if not hasattr(image_label, '_last_width'):
      image_label._last_width = -1
    if not hasattr(image_label, '_last_height'):
      image_label._last_height = -1

    # 只有当尺寸实际变化时才更新
    need_update = (current_width != image_label._last_width or
                  current_height != image_label._last_height)

    # 更新尺寸记录
    image_label._last_width = current_width
    image_label._last_height = current_height

    # 只有在需要更新且尺寸有效时才进行处理
    if need_update and current_width > 0 and current_height > 0:

      # 获取缩略图管理器
      thumbnail_manager = get_thumbnail_manager()

      # 使用ThumbnailManager获取缩放后的pixmap，传递margin_ratio参数以确保与缩略图处理逻辑兼容
      scaled_pixmap = thumbnail_manager.get_scaled_pixmap(asset_id, current_width, current_height, margin_ratio=0.05)
      image_label.setPixmap(scaled_pixmap)

  def clear_asset_cards(self):
    """清空资产卡片流布局"""
    # 删除所有布局项
    while self.flow_layout.count() > 0:
      item = self.flow_layout.takeAt(0)
      if item.widget() is not None:
        item.widget().deleteLater()
      # 移除布局项本身
      del item

    # 清理引用字典
    self.asset_cards.clear()
    self.tag_buttons.clear()

  def on_asset_thumbnail_generated(self, asset_id: str, thumbnail_path: str):
    """当资产缩略图生成完成后调用"""
    # 检查是否是主线程
    if QThread.currentThread() != QApplication.instance().thread():
      # 在主线程中调用此方法
      QMetaObject.invokeMethod(self, 'on_asset_thumbnail_generated',
                              Qt.QueuedConnection,
                              Q_ARG(str, asset_id),
                              Q_ARG(str, thumbnail_path))
      return

    if thumbnail_path:
      # 添加到流布局
      self.add_asset_card_to_flow(asset_id)

      # 如果是最后打开的资源，更新其样式为选中样式
      if self.last_opened_asset_id and self.last_opened_asset_id == asset_id:
        if asset_id in self.asset_cards:
          StyleManager.apply_style(self.asset_cards[asset_id], True)

    # 减少异步缩略图计数并检查是否所有缩略图都已生成
    # 直接使用_async_thumbnails_remaining属性，因为它在load_asset_cards_for_tag中总是被初始化
    self._async_thumbnails_remaining -= 1
    if self._async_thumbnails_remaining <= 0:
      self.asset_cards_loaded = True

  def on_asset_card_enter(self, asset_id: str):
    """处理鼠标进入资产卡片事件"""
    if asset_id in self.asset_cards:
      # 应用悬浮样式
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(self.asset_cards[asset_id], is_selected, True)
      # 更新子组件样式
      for child in self.asset_cards[asset_id].findChildren(QLabel):
        if hasattr(child, '_full_text'):  # 保留此检查，因为不是所有QLabel都有_full_text
          StyleManager.apply_label_style(child)

  def on_asset_card_leave(self, asset_id: str):
    """处理鼠标离开资产卡片事件"""
    if asset_id in self.asset_cards:
      # 应用普通样式
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(self.asset_cards[asset_id], is_selected)
      # 更新子组件样式
      for child in self.asset_cards[asset_id].findChildren(QLabel):
        if hasattr(child, '_full_text'):  # 保留此检查，因为不是所有QLabel都有_full_text
          StyleManager.apply_label_style(child)

      # 更新标签按钮样式
      for child in self.asset_cards[asset_id].findChildren(QPushButton):
        if hasattr(child, '_asset_id') and child._asset_id == asset_id:  # 保留_asset_id检查
          # 直接调用resizeEvent，因为所有标签按钮都有此方法
          child.resizeEvent(None)

  def _on_palette_changed(self, palette):
    """当系统调色板变化时更新主题样式"""
    self._update_theme_styles(palette)

  def _update_theme_styles(self, palette=None):
    """检测系统主题并更新样式"""
    # 更新样式引用
    self.normal_style = StyleManager.get_style('normal', palette)
    self.hover_style = StyleManager.get_style('hover', palette)
    self.selected_style = StyleManager.get_style('selected', palette)
    self.selected_hover_style = StyleManager.get_style('selected_hover', palette)
    self.normal_style_name_color = StyleManager.get_style('name_color', palette)
    self.image_background_color = StyleManager.get_style('image_background', palette)

    # 重新应用样式到所有资产卡片
    for asset_id, widget in self.asset_cards.items():
      # 根据是否为选中状态应用不同样式
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(widget, is_selected, palette=palette)

      # 更新所有子标签的样式
      for child in widget.findChildren(QLabel):
          # 检查是否为名字标签或图片标签
          # 对于名字标签，设置文本颜色
          # 直接使用text属性，因为所有QLabel都有这个方法
          is_name = child.property("is_name_label") or child.text()
          if is_name:
            StyleManager.apply_label_style(child)

    # 更新标签按钮样式
    for asset_id, buttons in self.tag_buttons.items():
      for button in buttons:
        # 直接使用height方法，因为所有QPushButton都有这个方法
        height = button.height()
        StyleManager.apply_tags_button_style(button, height)

  def on_asset_card_clicked(self, asset_id: str, event: QMouseEvent):
      """处理资产卡片点击事件，打开详情页面"""
      if event.button() == Qt.LeftButton:
        # 检查是否为ImagePack类型的资源
        asset_manager = AssetManager.get_instance()
        asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        # 取消之前选中项的高亮 - 使用正常样式
        if self.last_opened_asset_id and self.last_opened_asset_id in self.asset_cards:
          StyleManager.apply_style(self.asset_cards[self.last_opened_asset_id], False)
        # 更新上次打开的资源ID并高亮当前项 - 使用选中样式
        self.last_opened_asset_id = asset_id
        StyleManager.apply_style(self.asset_cards[asset_id], True)
        # 特别处理名字子组件
        for child in self.asset_cards[asset_id].findChildren(QLabel):
          # 保留_full_text检查，因为不是所有QLabel都有这个自定义属性
          if hasattr(child, '_full_text'):
            StyleManager.apply_label_style(child)
        # 请求打开ImagePackWidget
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
    """处理标签按钮点击事件"""
    # 执行选中高亮逻辑
    if self.last_opened_asset_id!=asset_id:
      if self.last_opened_asset_id and self.last_opened_asset_id in self.asset_cards:
        StyleManager.apply_style(self.asset_cards[self.last_opened_asset_id], False)
      # 更新上次打开的资源ID并高亮当前项
      self.last_opened_asset_id = asset_id
      StyleManager.apply_style(self.asset_cards[asset_id], True)
      # 更新名字子组件样式
      for child in self.asset_cards[asset_id].findChildren(QLabel):
        # 保留_full_text检查，因为不是所有QLabel都有这个自定义属性
        if hasattr(child, '_full_text'):
          StyleManager.apply_label_style(child)

    # 然后打开标签编辑对话框
    self.open_tag_edit_dialog(asset_id, button)

  def open_tag_edit_dialog(self, asset_id, button=None):
    """打开标签编辑对话框"""
    dialog = TagEditDialog(asset_id, self, self)
    dialog.exec()

    if button:
      button.setDown(False)
      button.clearFocus()
      button.update()

  def update_asset_card_tags(self, asset_id=None):
    """更新现有资产卡片的标签文本"""
    # 如果指定了asset_id，只更新该资产的标签
    if asset_id:
      self._update_single_asset_tags(asset_id)
    else:
      # 否则更新所有资产的标签
      for asset_id_iter in self.asset_cards.keys():
        self._update_single_asset_tags(asset_id_iter)

  def _update_single_asset_tags(self, asset_id):
    """更新单个资产的标签显示"""
    if asset_id not in self.asset_cards:
      return

    # 获取资产的显示标签
    asset_tags = self.tag_manager.get_asset_tags_display(asset_id)
    tags_text = ", ".join(sorted(asset_tags))

    # 尝试从tag_buttons字典中获取按钮
    if asset_id in self.tag_buttons:
      for button in self.tag_buttons[asset_id]:
        button._full_text = tags_text if tags_text else self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
        # 直接调用resizeEvent，因为所有标签按钮都有此方法
        button.resizeEvent(None)
    else:
      # 如果没找到，尝试从资产卡片小部件中查找
      asset_card_widget = self.asset_cards.get(asset_id)
      if asset_card_widget:
        tags_button = asset_card_widget.findChild(QPushButton, f"tags_button_{asset_id}")
        if tags_button:
          tags_button._full_text = tags_text if tags_text else self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
          # 直接调用resizeEvent，因为所有标签按钮都有此方法
          tags_button.resizeEvent(None)

  def update_text(self):
    super().update_text()

    current_semantic = None
    current_item = self.ui.categoriesListWidget.currentItem()
    if current_item:
      current_semantic = current_item.get_semantic_tag()

    self.load_tags()

    if current_semantic:
      for i in range(self.ui.categoriesListWidget.count()):
        item = self.ui.categoriesListWidget.item(i)
        # 直接使用TagListItem的语义标识进行匹配
        if item.get_semantic_tag() == current_semantic:
          self.ui.categoriesListWidget.setCurrentItem(item)
          # 使用完整的显示文本作为标题
          self.current_tag = item.text()
          self.ui.categoryTitleLabel.setText(self.current_tag)

          # 语言切换时，如果有选中的标签分类，只更新当前显示的资产标签
          # 这样避免不必要的全部更新，提高性能
          if self.asset_cards_loaded:
            # 只更新当前加载的资产卡片对应的资产标签
            for asset_id in list(self.asset_cards.keys()):
              self._update_single_asset_tags(asset_id)

          self.load_asset_cards_for_tag(current_semantic)
          break
    elif not current_item:
      self.ui.categoriesListWidget.setCurrentRow(0)
      first_item = self.ui.categoriesListWidget.item(0)
      if first_item:
        # 使用完整的显示文本作为标题
        display_text = first_item.text()
        self.current_tag = display_text
        self.ui.categoryTitleLabel.setText(self.current_tag)

        # 直接从TagListItem获取语义标识
        # 所有标签列表项都应该是TagListItem类型
        tag_semantic = first_item.get_semantic_tag()
        self.load_asset_cards_for_tag(tag_semantic)

        # 同样，只更新当前加载的资产卡片对应的资产标签
        if self.asset_cards_loaded:
          for asset_id in list(self.asset_cards.keys()):
            self._update_single_asset_tags(asset_id)