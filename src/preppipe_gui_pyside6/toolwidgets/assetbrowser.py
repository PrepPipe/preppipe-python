# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from typing import Tuple
from collections import OrderedDict
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack, ImagePackDescriptor
from ..toolwidgetinterface import *
from ..forms.generated.ui_assetbrowserwidget import Ui_AssetBrowserWidget
from ..settingsdict import SettingsDict
from ..util.asset_thumbnail import (
    get_thumbnail_manager,
    get_scaled_pixmap_for_asset,
    create_thumbnail_worker
)
from ..util.tagmanager import TagManager
from .tageditdialog import TagEditDialog
from preppipe_gui_pyside6.util.asset_widget_style import StyleManager

TR_gui_tool_assetbrowser = TranslationDomain("gui_tool_assetbrowser")

# 常量定义，保持与TranslationDomain一致
TRANSLATION_DOMAIN = "gui_tool_assetbrowser"

class ElidedWidgetBase:
    """文本省略处理的基础类（mixin类）

    提供通用的文本省略处理功能，可被按钮、标签等组件继承使用
    """
    def __init__(self):
        self._full_text = ''
        self._elide_margin = 10

    def setFullText(self, text):
        """设置完整文本"""
        self._full_text = text
        self._update_elided_text()
        self.update()

    def getFullText(self):
        """获取完整文本"""
        return self._full_text

    def setElideMargin(self, margin):
        """设置省略文本计算时的边距"""
        self._elide_margin = margin
        self._update_elided_text()
        self.update()

    def _calculate_elided_text(self, text=None, margin=None):
        """计算文本的省略版本

        Args:
            text: 可选，要计算的文本，如果未提供则使用_full_text
            margin: 可选，边距像素，如果未提供则使用_elide_margin

        Returns:
            省略后的文本字符串
        """
        target_text = text if text is not None else self._full_text
        target_margin = margin if margin is not None else self._elide_margin

        if not target_text:
            return ''
        # 获取字体度量对象
        font_metrics = self.fontMetrics()
        # 计算可用宽度（考虑边距）
        available_width = max(self.width() - target_margin, 0)
        # 计算省略文本
        return font_metrics.elidedText(target_text, Qt.ElideRight, available_width)

    def _update_elided_text(self):
        """更新省略文本

        子类需要重写此方法来实际设置省略后的文本
        """
        pass

    def resizeEvent(self, event):
        """处理组件大小变化事件，重新计算省略文本"""
        # 调用原始的resizeEvent方法
        if hasattr(super(), 'resizeEvent'):
            super().resizeEvent(event)
        self._update_elided_text()

class ElidedPushButton(QPushButton, ElidedWidgetBase):
    """自定义的按钮类，用于实现文本溢出控制"""
    def __init__(self, text, parent):
        # 初始化时使用空文本
        QPushButton.__init__(self, '', parent)
        ElidedWidgetBase.__init__(self)
        self.setFullText(text)
        self.setMouseTracking(True)

    def _update_elided_text(self):
        """更新省略文本"""
        elided_text = self._calculate_elided_text()
        QPushButton.setText(self, elided_text)

    def sizeHint(self):
        """提供合适的大小提示"""
        # 基于完整文本计算合适的宽度
        font_metrics = self.fontMetrics()
        text_width = font_metrics.horizontalAdvance(self.getFullText())
        # 添加内边距
        return QSize(text_width, QPushButton.sizeHint(self).height())

class ElidedLabel(QLabel, ElidedWidgetBase):
    """自定义的标签类，用于实现文本溢出控制"""
    def __init__(self, text='', parent=None):
        # 初始化时使用空文本
        QLabel.__init__(self, '', parent)
        ElidedWidgetBase.__init__(self)
        self.setElideMargin(8)  # 设置边距为8
        self.setFullText(text)
        self.setWordWrap(False)
        self.setAlignment(Qt.AlignCenter)  # 设置文本居中对齐

    def _update_elided_text(self):
        """更新省略文本"""
        elided_text = self._calculate_elided_text()
        QLabel.setText(self, elided_text)

    def sizeHint(self):
        """提供合适的大小提示"""
        # 基于完整文本计算合适的宽度
        font_metrics = self.fontMetrics()
        text_width = font_metrics.horizontalAdvance(self.getFullText())
        # 添加内边距
        return QSize(text_width + 16, QLabel.sizeHint(self).height())

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  # 设置字典中存储标签的键
  SETTINGS_KEY_TAGS = "persistent/assetmanager/custom_asset_tags"
  SETTINGS_KEY_CURRENT_TAG = "persistent/assetmanager/current_tag"
  # 当前选中的标签
  current_tag: str
  # 标签到素材的映射字典，格式：{tag_name: Tuple[QListWidgetItem, dict[asset_id: asset_object]]}
  assets_by_tag: OrderedDict[str, Tuple[QListWidgetItem, dict[str, object]]]
  # 缩略图缓存字典
  thumbnail_cache: dict[str, str]
  # 用于异步加载的线程池
  thread_pool: QThreadPool
  # 缩略图容器字典，用于快速访问
  thumbnail_items: dict[str, QWidget]
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

  # 标签编辑相关提示
  _tr_tag_edit_hint = TR_gui_tool_assetbrowser.tr("tag_edit_hint",
    en="Click tag to edit, press Delete to remove",
    zh_cn="单击标签编辑，按Delete键删除",
    zh_hk="單擊標籤編輯，按Delete鍵删除",
  )

  _tr_tag_edit_current_hint = TR_gui_tool_assetbrowser.tr("tag_edit_current_hint",
    en="Enter to add new tag, click tag to delete",
    zh_cn="Enter添加新标签，点击标签删除",
    zh_hk="Enter添加新標籤，點擊標籤刪除",
  )

  # "无标签"提示文本
  _tr_no_tags = TR_gui_tool_assetbrowser.tr("tagmanager_no_tags",
    en="No tags",
    zh_cn="无标签",
    zh_hk="無標籤",
  )

  def __init__(self, parent: QWidget):
    super(AssetBrowserWidget, self).__init__(parent)
    self.ui = Ui_AssetBrowserWidget()
    self.ui.setupUi(self)
    self.current_tag = ""
    self.assets_by_tag = OrderedDict()  # 使用有序字典，保持标签添加顺序
    self.thumbnail_cache = {}
    self.thread_pool = QThreadPool()
    self.thumbnail_items = {}
    self.all_asset_ids = []
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
    # 监听系统主题变化通过重写changeEvent方法
    # 绑定文本
    self.bind_text(self.ui.categoryTitleLabel.setText, TR_gui_tool_assetbrowser.tr("select_tag",
      en="Select a tag",
      zh_cn="选择一个标签",
      zh_hk="選擇一個標籤",
    ))
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
      tag_semantic_category = None
      if saved_tag in ["All", "全部"]:
        tag_semantic_category = "all"
      elif saved_tag in ["Background", "背景"]:
        tag_semantic_category = "background"
      elif saved_tag in ["Character", "立绘", "立繪"]:
        tag_semantic_category = "character"
      elif saved_tag in ["Other", "其他"]:
        tag_semantic_category = "other"
      else:
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
        for i in range(self.ui.categoriesListWidget.count()):
          item = self.ui.categoriesListWidget.item(i)
          if item and item.text() == target_tag:
            self.ui.categoriesListWidget.setCurrentItem(item)
            # 触发标签选择事件
            self.on_tag_selected(item)
            break

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
            # 添加到对应标签的素材映射
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
    # 查找与当前标签匹配的列表项
    for i in range(self.ui.categoriesListWidget.count()):
      item = self.ui.categoriesListWidget.item(i)
      item_text = item.text()

      # 特殊处理"全部"标签，它可能显示为"全部 (数量)"
      if semantic_tag == "all":
        if item_text.startswith(self.tag_manager.get_tr_all()):
          self.ui.categoriesListWidget.setCurrentItem(item)
          break
      # 普通标签处理 - 匹配显示文本
      elif ' (' in item_text:
        # 如果列表项包含计数，只比较标签名部分
        if item_text.split(' (')[0] == tag_text:
          self.ui.categoriesListWidget.setCurrentItem(item)
          break
      # 普通标签处理 - 无计数情况
      elif item_text == tag_text:
        self.ui.categoriesListWidget.setCurrentItem(item)
        break

    # 我们已经在第一个循环中处理了所有可能的标签情况，包括语义标识查找
    # 如果未找到标签，保持当前设置不变

    # 加载所选标签的缩略图
    self.load_thumbnails_for_tag(semantic_tag)

  def update_tags_list(self):
    """更新标签列表显示，同时显示标签对应的素材个数"""
    self.ui.categoriesListWidget.clear()

    # 添加一个特殊的"全部"列表项（默认选中），这不是一个真正的标签
    all_count = len(self.all_asset_ids)
    all_text = self.tag_manager.get_tr_all()
    all_item = QListWidgetItem(f"{all_text} ({all_count})")
    font = all_item.font()
    font.setBold(True)
    all_item.setFont(font)
    self.ui.categoriesListWidget.addItem(all_item)

    # 添加所有实际标签（按添加顺序）
    for tag in self.assets_by_tag.keys():
      # 获取该标签对应的素材个数
      count = len(self.assets_by_tag[tag][1])
      # 只显示有素材的标签
      if count > 0:
        item = QListWidgetItem(f"{tag} ({count})")
        self.ui.categoriesListWidget.addItem(item)
        # 确保标签的映射关系存在
        if tag not in self.tag_manager.tag_text_to_semantic:
          self.tag_manager.add_custom_tag_mapping(tag, tag)

  def save_tags(self):
    """保存标签到设置字典"""
    # 直接使用TagManager，无需额外的代理方法
    pass  # 实际上不需要执行任何操作，因为TagManager会自动保存

  def on_tag_selected(self, item: QListWidgetItem):
    """当用户从分类列表中选择一个标签时调用"""
    display_text = item.text()
    if ' (' in display_text:
      tag_text = display_text.split(' (')[0]
    else:
      tag_text = display_text

    # 获取当前标签文本用于显示
    self.current_tag = tag_text
    self.ui.categoryTitleLabel.setText(self.current_tag)

    # 特殊处理"全部"列表项，直接使用"all"语义
    if tag_text == self.tag_manager.get_tr_all():
      tag_semantic = "all"
    else:
      # 对于实际标签，获取其语义标识
      tag_semantic = self.tag_manager.get_tag_semantic(self.current_tag)

    # 保存当前选中的标签语义标识到设置
    settings = SettingsDict.instance()
    settings[self.SETTINGS_KEY_CURRENT_TAG] = tag_semantic

    # 加载对应的缩略图
    self.load_thumbnails_for_tag(tag_semantic)

  def get_thumbnail_cache_dir(self) -> str:
    """获取缩略图缓存目录"""
    thumbnail_manager = get_thumbnail_manager()
    return thumbnail_manager.get_thumbnail_cache_dir()

  def load_thumbnails_for_tag(self, tag: str):
    """加载指定标签的缩略图，预定义标签使用语义标识，自定义标签直接使用原始文本"""
    # 清空现有缩略图
    self.clear_thumbnails()
    # 获取要显示的素材ID列表
    asset_ids_to_show = []
    asset_manager = AssetManager.get_instance()
    # 确定要显示的素材
    if tag == "all":
      # 显示所有素材（对应"全部"特殊选项）
      asset_ids_to_show = self.all_asset_ids
    else:
      # 查找对应的显示标签文本
      display_tag = self.tag_manager.get_tag_display_text(tag)
      # 从assets_by_tag获取该标签下的所有素材ID
      if display_tag in self.assets_by_tag:
        _, asset_dict = self.assets_by_tag[display_tag]
        asset_ids_to_show = list(asset_dict.keys())
    if not asset_ids_to_show:
      return
    # 获取缩略图管理器实例，使用当前应用的缓存目录
    cache_dir = self.get_thumbnail_cache_dir()
    thumbnail_manager = get_thumbnail_manager(cache_dir)
    # 检查并生成缩略图
    for asset_id in asset_ids_to_show:
      # 尝试获取已存在的缩略图路径
      thumbnail_path = thumbnail_manager.get_or_generate_thumbnail(asset_id)
      if thumbnail_path:
        # 直接使用缓存
        self.thumbnail_cache[asset_id] = thumbnail_path
        self.add_thumbnail_to_flow(asset_id)
      else:
        # 异步生成缩略图
        worker = create_thumbnail_worker(asset_id, cache_dir)
        worker.signals.result.connect(self.on_thumbnail_generated)
        self.thread_pool.start(worker)

  def _on_container_resized(self, event):
    """当容器大小改变时重新调整布局"""
    # 直接调用原始QWidget的resizeEvent方法
    QWidget.resizeEvent(self.ui.thumbnailsScrollAreaWidgetContents, event)

    # 获取当前容器宽度
    current_width = self.ui.thumbnailsContainerWidget.width()

    # 检查是否需要重新布局（初始化时或宽度实际变化时）
    if not hasattr(self, '_last_container_width') or current_width != self._last_container_width:
      # 记录当前宽度
      self._last_container_width = current_width

      # 如果有缩略图，智能调整缩略图大小而不是重新加载
      if self.thumbnail_items and current_width > 0:
        # 计算最佳缩略图大小
        card_width = self._calculate_optimal_card_width(current_width)
        card_height = int(card_width * 1.2)  # 保持1:1.2的宽高比

        # 更新FlowLayout中的项目大小
        self.flow_layout.setItemSize(QSize(card_width, card_height))

        # 为每个缩略图调整内部元素大小
        for asset_id, widget in self.thumbnail_items.items():
          # 调整缩略图容器大小
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

              # 计算图像高度（减去名称和标签的高度）
              name_label_height = self.name_font_metrics.height()
              tags_label_height = self.tags_font_metrics.height()
              name_tags_height = name_label_height + tags_label_height + spacing
              available_height = card_height - (margins.top() + margins.bottom() + name_tags_height)

              # 设置图像标签大小
              child.setFixedSize(available_width, available_height)

              # 更新图像缩放
              if hasattr(child, '_last_width'):
                child._last_width = -1  # 强制重新调整大小
                break
            # 处理名称标签和标签标签，更新其文本省略
            elif hasattr(child, '_full_text'):
              # 触发文本省略更新
              if hasattr(child, 'resizeEvent') and child.resizeEvent:
                child.resizeEvent(QResizeEvent(child.size(), child.size()))

    # 通知FlowLayout更新布局
    self.flow_layout.update()

    return event

  def _calculate_optimal_card_width(self, container_width):
    """根据容器宽度计算最佳卡片宽度"""
    # 最小卡片宽度（保证可读性）
    min_card_width = 160
    # 获取间距
    spacing = self.flow_layout.spacing()
    # 计算可显示的最大列数
    columns = max(1, container_width // (min_card_width + spacing))
    # 限制最小列数为2，除非容器宽度实在太小
    if container_width >= min_card_width * 2 + spacing:
      columns = max(columns, 2)
    # 计算卡片宽度，确保能均匀分布在容器中
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

    Args:
        asset_id: 资产ID
        card_width: 卡片宽度
        card_height: 卡片高度

    Returns:
        构建好的资产卡片QWidget
    """
    # 创建缩略图容器
    thumbnail_container = QWidget()
    thumbnail_container.setFixedSize(card_width, card_height)
    container_layout = QVBoxLayout(thumbnail_container)
    # 设置布局参数，增加内边距使内容在卡牌中有更好的视觉效果
    container_layout.setContentsMargins(8, 8, 8, 8)
    container_layout.setSpacing(6)
    container_layout.setSizeConstraint(QLayout.SetFixedSize)
    # 创建图片标签
    image_label = QLabel()
    image_label.setAlignment(Qt.AlignCenter)
    # 使用StyleManager应用图片标签样式
    StyleManager.apply_image_label_style(image_label)
    image_label.setMouseTracking(False)
    # 计算图片标签的大小
    layout_margins = container_layout.contentsMargins()
    layout_spacing = container_layout.spacing()
    # 计算名称和标签的高度
    name_label_height = self.name_font_metrics.height()
    tags_label_height = self.tags_font_metrics.height()
    # 计算图片区域的可用空间
    available_width = card_width - (layout_margins.left() + layout_margins.right())
    available_height = card_height - (layout_margins.top() + layout_margins.bottom() +
                                      name_label_height + tags_label_height + layout_spacing)
    # 设置图片标签固定大小
    image_label.setFixedSize(available_width, available_height)
    # 使用新的ThumbnailManager获取缩放后的pixmap
    scaled_pixmap = get_scaled_pixmap_for_asset(asset_id, available_width, available_height)
    # 设置图片并确保居中显示
    image_label.setPixmap(scaled_pixmap)
    # 记录当前尺寸，避免不必要的更新
    image_label._last_width = available_width
    image_label._last_height = available_height
    # 连接图片标签的调整大小信号以更新图片
    image_label.resizeEvent = lambda event, img=image_label, aid=asset_id: self._update_image_on_resize(event, img, aid)

    # 创建名称标签 - 使用自定义的ElidedLabel类来实现文本溢出控制
    name_label = ElidedLabel()
    name_label.setAlignment(Qt.AlignCenter)
    name_label.setWordWrap(False)  # 禁止自动换行
    # 使用StyleManager应用标签样式
    StyleManager.apply_label_style(name_label)
    name_label.setMouseTracking(False)
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
    # 加载标签
    asset_tags = self.tag_manager.get_asset_tags(asset_id)
    # 转换标签为翻译后的文本
    translated_tags = self.tag_manager.translate_tags(asset_tags)
    # 创建标签按钮 - 使用自定义的ElidedPushButton类来实现文本溢出控制
    tags_text = ", ".join(sorted(translated_tags))
    no_tags_text = self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
    tags_button = ElidedPushButton(tags_text if tags_text else no_tags_text, thumbnail_container)
    tags_button.setObjectName(f"tags_button_{asset_id}")
    # 使用标签字体作为标签按钮的字体
    tags_button.setFont(self.tags_font)
    # 使用缓存的name_font作为名称标签的字体（加粗效果）
    name_label.setFont(self.name_font)
    # 设置按钮的大小策略 - 使用固定高度而非最小高度
    tags_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    # 设置固定高度而不是最小高度，进一步增加按钮高度使其更大
    tag_button_height = int(tags_label_height * 1.4)  # 进一步增加高度因子
    tags_button.setFixedHeight(tag_button_height)
    # 使用样式管理器设置按钮样式
    StyleManager.apply_tags_button_style(tags_button, tag_button_height)
    tags_button.clicked.connect(lambda: self.on_tags_button_clicked(asset_id, tags_button))
    # 存储标签按钮的asset_id，用于标识和后续更新
    tags_button._asset_id = asset_id
    # 存储按钮引用
    if asset_id not in self.tag_buttons:
      self.tag_buttons[asset_id] = []
    self.tag_buttons[asset_id].append(tags_button)
    # 添加到容器布局 - 保持图片、名称、标签的顺序
    container_layout.addWidget(image_label)
    container_layout.addWidget(name_label)
    container_layout.addWidget(tags_button)
    # 设置容器样式 - 使用StyleManager统一应用
    StyleManager.apply_style(thumbnail_container, False)
    # 确保name_label保持透明背景，不受容器样式影响，并使用当前主题的文本颜色
    # 使用StyleManager统一应用标签样式
    StyleManager.apply_label_style(name_label)
    # 设置右键菜单禁用，因为我们不使用上下文菜单
    thumbnail_container.setContextMenuPolicy(Qt.NoContextMenu)
    # 设置鼠标事件处理
    thumbnail_container.setMouseTracking(True)
    thumbnail_container.enterEvent = lambda event, aid=asset_id: self.on_thumbnail_enter(aid)
    thumbnail_container.leaveEvent = lambda event, aid=asset_id: self.on_thumbnail_leave(aid)
    thumbnail_container.mousePressEvent = lambda event, aid=asset_id: self.on_thumbnail_clicked(aid, event)
    # 恢复上次选中的高亮状态
    if asset_id == self.last_opened_asset_id:
      # 使用StyleManager统一应用选中样式
      StyleManager.apply_style(thumbnail_container, True)
      # 确保name_label保持透明背景，不受选中样式影响
      StyleManager.apply_label_style(name_label)

    return thumbnail_container

  def add_thumbnail_to_flow(self, asset_id: str):
    """将缩略图添加到流布局中，使用根据容器大小动态计算的尺寸"""
    # 计算最佳卡片大小
    container_width = self.ui.thumbnailsContainerWidget.width()
    card_width = self._calculate_optimal_card_width(container_width)
    card_height = int(card_width * 1.2)  # 保持1:1.2的宽高比
    # 创建资产卡片
    thumbnail_container = self._create_asset_card(asset_id, card_width, card_height)
    # 添加到FlowLayout
    self.flow_layout.addWidget(thumbnail_container)

    # 存储到字典中以便后续访问
    self.thumbnail_items[asset_id] = thumbnail_container


  def _update_image_on_resize(self, event, image_label, asset_id):
    """当图片标签大小改变时更新图片"""
    # 直接调用原始QLabel的resizeEvent方法
    QLabel.resizeEvent(image_label, event)

    # 添加宽度跟踪，避免频繁更新
    current_width = image_label.width()
    current_height = image_label.height()

    # 检查是否已初始化或尺寸实际发生变化
    if not hasattr(image_label, '_last_width') or not hasattr(image_label, '_last_height'):
      # 初始化时需要更新
      need_update = True
    else:
      # 只有当尺寸实际变化时才更新
      need_update = (current_width != image_label._last_width or
                    current_height != image_label._last_height)

    # 更新尺寸记录
    image_label._last_width = current_width
    image_label._last_height = current_height

    # 只有在需要更新且尺寸有效时才进行处理
    if need_update and current_width > 0 and current_height > 0:

      # 使用新的ThumbnailManager获取缩放后的pixmap
      scaled_pixmap = get_scaled_pixmap_for_asset(asset_id, current_width, current_height)
      image_label.setPixmap(scaled_pixmap)

  def clear_thumbnails(self):
    """清空缩略图流布局，确保删除所有布局项"""
    # 删除所有布局项，包括widget和非widget项
    while self.flow_layout.count() > 0:
      item = self.flow_layout.takeAt(0)
      if item.widget() is not None:
        item.widget().deleteLater()
      # 移除布局项本身
      del item

    # 清理所有引用字典，防止访问已删除的C++对象
    self.thumbnail_items.clear()
    self.tag_buttons.clear()
    # 保留last_opened_asset_id，这样重新加载缩略图时可以恢复选中状态

  def on_thumbnail_generated(self, asset_id: str, thumbnail_path: str):
    """当缩略图生成完成后调用"""
    # 检查是否是主线程，如果不是，使用信号槽机制切换到主线程
    if QThread.currentThread() != QApplication.instance().thread():
      # 在主线程中调用此方法
      QMetaObject.invokeMethod(self, 'on_thumbnail_generated',
                              Qt.QueuedConnection,
                              Q_ARG(str, asset_id),
                              Q_ARG(str, thumbnail_path))
      return

    if thumbnail_path:
      # 缓存缩略图路径
      self.thumbnail_cache[asset_id] = thumbnail_path
      # 添加到流布局
      self.add_thumbnail_to_flow(asset_id)

      # 如果是最后打开的资源，更新其样式为选中样式
      if self.last_opened_asset_id and self.last_opened_asset_id == asset_id:
        if asset_id in self.thumbnail_items:
          StyleManager.apply_style(self.thumbnail_items[asset_id], True)

  def on_thumbnail_enter(self, asset_id: str):
    """处理鼠标进入缩略图事件"""
    if asset_id in self.thumbnail_items:
      # 使用样式管理器应用悬浮样式
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(self.thumbnail_items[asset_id], is_selected, True)
      # 确保所有子组件保持正确的样式
      # 根据是否有_full_text属性来区分名称标签和图片标签
      for child in self.thumbnail_items[asset_id].findChildren(QLabel):
        if hasattr(child, '_full_text'):
          StyleManager.apply_label_style(child)

  def on_thumbnail_leave(self, asset_id: str):
    """处理鼠标离开缩略图事件"""
    if asset_id in self.thumbnail_items:
      # 使用样式管理器应用普通样式
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(self.thumbnail_items[asset_id], is_selected)
      # 确保所有子组件恢复到初始状态的样式
      # 根据是否有_full_text属性来区分名称标签和图片标签
      for child in self.thumbnail_items[asset_id].findChildren(QLabel):
        if hasattr(child, '_full_text'):
          StyleManager.apply_label_style(child)

      # 确保标签按钮样式也恢复正确
      for child in self.thumbnail_items[asset_id].findChildren(QPushButton):
        if hasattr(child, '_asset_id') and child._asset_id == asset_id:
          # 保持标签按钮的原始样式不变，只确保文本省略正确
          if hasattr(child, 'resizeEvent') and callable(child.resizeEvent):
            child.resizeEvent(None)

  def _on_palette_changed(self, palette):
    """当系统调色板变化时更新主题样式"""
    self._update_theme_styles(palette)
    # 样式应用逻辑已在_update_theme_styles中实现

  def _update_theme_styles(self, palette=None):
    """检测系统主题并更新样式"""
    # 使用样式管理器更新主题
    theme = StyleManager.detect_theme(palette)

    # 更新当前样式引用
    self.normal_style = StyleManager.get_style('normal', palette)
    self.hover_style = StyleManager.get_style('hover', palette)
    self.selected_style = StyleManager.get_style('selected', palette)
    self.selected_hover_style = StyleManager.get_style('selected_hover', palette)
    self.normal_style_name_color = StyleManager.get_style('name_color', palette)
    self.image_background_color = StyleManager.get_style('image_background', palette)

    # 重新应用样式到所有缩略图项
    for asset_id, widget in self.thumbnail_items.items():
      # 根据是否为选中状态应用不同样式
      is_selected = asset_id == self.last_opened_asset_id
      StyleManager.apply_style(widget, is_selected, palette=palette)

      # 更新所有子标签的样式
      for child in widget.findChildren(QLabel):
        # 检查是否为名字标签或图片标签
        # 对于名字标签，设置文本颜色
        is_name = child.property("is_name_label") or (hasattr(child, "text") and child.text())
        if is_name:
          StyleManager.apply_label_style(child)

    # 更新标签按钮样式
    for asset_id, buttons in self.tag_buttons.items():
      for button in buttons:
        if hasattr(button, 'height'):
          height = button.height()
          StyleManager.apply_tags_button_style(button, height)

  def on_thumbnail_clicked(self, asset_id: str, event: QMouseEvent):
    """处理缩略图点击事件，打开详情页面"""
    # 只有左键点击才打开详情页面
    if event.button() == Qt.LeftButton:
      from ..mainwindowinterface import MainWindowInterface
      from .imagepack import ImagePackWidget
      from preppipe.util.imagepack import ImagePack
      # 检查是否为ImagePack类型的资源
      asset_manager = AssetManager.get_instance()
      asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        # 取消之前选中项的高亮 - 使用正常样式
        if self.last_opened_asset_id and self.last_opened_asset_id in self.thumbnail_items:
          StyleManager.apply_style(self.thumbnail_items[self.last_opened_asset_id], False)
        # 更新上次打开的资源ID并高亮当前项 - 使用选中样式
        self.last_opened_asset_id = asset_id
        StyleManager.apply_style(self.thumbnail_items[asset_id], True)
        # 特别处理名字子组件
        for child in self.thumbnail_items[asset_id].findChildren(QLabel):
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
    """处理标签按钮点击事件，先执行选中高亮逻辑，再打开标签编辑对话框"""
    # 执行与资产卡片点击相同的选中高亮逻辑
    # 取消之前选中项的高亮
    if self.last_opened_asset_id!=asset_id:
      if self.last_opened_asset_id and self.last_opened_asset_id in self.thumbnail_items:
        StyleManager.apply_style(self.thumbnail_items[self.last_opened_asset_id], False)
      # 更新上次打开的资源ID并高亮当前项
      self.last_opened_asset_id = asset_id
      StyleManager.apply_style(self.thumbnail_items[asset_id], True)
      # 特别处理名字子组件
      for child in self.thumbnail_items[asset_id].findChildren(QLabel):
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

  def update_thumbnail_tags(self, asset_id=None):
    """更新现有缩略图的标签文本，而不重新加载整个缩略图

    Args:
      asset_id: 可选参数，指定要更新的资产ID。如果为None，则更新所有资产的标签
    """
    # 如果指定了asset_id，只更新该资产的标签
    if asset_id:
      self._update_single_asset_tags(asset_id)
    else:
      # 否则更新所有资产的标签
      for asset_id_iter in self.thumbnail_items.keys():
        self._update_single_asset_tags(asset_id_iter)

  def _update_single_asset_tags(self, asset_id):
    """更新单个资产的标签显示"""
    if asset_id not in self.thumbnail_items:
      return

    # 直接使用TagManager获取资产的显示标签
    asset_tags = self.tag_manager.get_asset_tags_display(asset_id)
    tags_text = ", ".join(sorted(asset_tags))

    # 尝试从tag_buttons字典中获取按钮
    if asset_id in self.tag_buttons:
      for button in self.tag_buttons[asset_id]:
        button._full_text = tags_text if tags_text else self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
        if hasattr(button, 'resizeEvent'):
          button.resizeEvent(None)
    else:
      # 如果没找到，尝试从缩略图小部件中查找
      thumbnail_widget = self.thumbnail_items.get(asset_id)
      if thumbnail_widget:
        tags_button = thumbnail_widget.findChild(QPushButton, f"tags_button_{asset_id}")
        if tags_button:
          tags_button._full_text = tags_text if tags_text else self._tr_no_tags.get() if isinstance(self._tr_no_tags, Translatable) else self._tr_no_tags
          if hasattr(tags_button, 'resizeEvent'):
            tags_button.resizeEvent(None)

  def update_text(self):
    super().update_text()

    current_semantic = None
    current_item = self.ui.categoriesListWidget.currentItem()
    if current_item:
      display_text = current_item.text()
      if ' (' in display_text:
        tag_text = display_text.split(' (')[0]
      else:
        tag_text = display_text

      if tag_text == self.tag_manager.get_tr_all():
        current_semantic = "all"
      else:
        # 使用TagManager获取标签的语义
        current_semantic = self.tag_manager.get_tag_semantic(tag_text)

    self.load_tags()

    if current_semantic:
      target_text = self.tag_manager.get_tag_display_text(current_semantic)
      for i in range(self.ui.categoriesListWidget.count()):
        item = self.ui.categoriesListWidget.item(i)
        if item:
          display_text = item.text()
          if ' (' in display_text:
            tag_text = display_text.split(' (')[0]
          else:
            tag_text = display_text

          if tag_text == target_text:
            self.ui.categoriesListWidget.setCurrentItem(item)
            self.current_tag = target_text
            self.ui.categoryTitleLabel.setText(self.current_tag)
            self.update_thumbnail_tags()

            if hasattr(self, 'load_thumbnails_for_tag'):
              self.load_thumbnails_for_tag(current_semantic)
            break
    elif not current_item:
      if self.ui.categoriesListWidget.count() > 0:
        self.ui.categoriesListWidget.setCurrentRow(0)
        first_item = self.ui.categoriesListWidget.item(0)
        if first_item:
          display_text = first_item.text()
          if ' (' in display_text:
            tag_text = display_text.split(' (')[0]
          else:
            tag_text = display_text
          self.current_tag = tag_text
          self.ui.categoryTitleLabel.setText(self.current_tag)

          tag_semantic = self.tag_manager.get_tag_semantic(tag_text)
          if hasattr(self, 'load_thumbnails_for_tag'):
            self.load_thumbnails_for_tag(tag_semantic)
        self.update_thumbnail_tags()