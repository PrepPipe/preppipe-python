#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资产卡片组件

用于在资产浏览器中显示单个资产的卡片组件，包含资产缩略图、名称和标签信息
"""

from PySide6.QtWidgets import QPushButton, QLabel, QWidget, QVBoxLayout, QSizePolicy, QLayout
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QResizeEvent,QFontMetrics, QFont,QMouseEvent
from preppipe.language import TranslationDomain
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack
from ..util.tagmanager import TagManager
from ..util.asset_thumbnail import get_thumbnail_manager
from ..util.asset_widget_style import StyleManager


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
    # 直接调用父类的resizeEvent方法
    super().resizeEvent(event)
    self._update_elided_text()


class ElidedPushButton(QPushButton, ElidedWidgetBase):
  """自定义的按钮类，用于实现文本溢出控制"""
  def __init__(self, text='', parent=None):
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

# 翻译定义域在全局顶部
TR_gui_assetcardwidget = TranslationDomain("gui_assetcardwidget")

class AssetCardWidget(QPushButton):
  """
  资产卡片组件，用于在资产浏览器中显示单个资产

  包含资产缩略图、名称和标签信息，并处理相关交互事件
  """

  _tr_no_tags = TR_gui_assetcardwidget.tr("assetcardwidget_no_tags",
    en="No tags",
    zh_cn="无标签",
    zh_hk="無標籤",
  )

  clicked = Signal(str,QMouseEvent)  # 点击信号，传递资产ID和鼠标事件
  tags_button_clicked = Signal(str,QPushButton)  # 标签按钮点击信号，传递资产ID

  def __init__(self, asset_id: str, width: int, height: int, name_font=None, tags_font=None, parent=None):
    """
    初始化资产卡片

    Args:
      asset_id: 资产的唯一标识符
      width: 卡片宽度
      height: 卡片高度
      name_font: 名称区域字体，如果为None则使用默认字体
      tags_font: 标签区域字体，如果为None则使用默认字体
      parent: 父级Widget
    """
    # 调用父类初始化
    QPushButton.__init__(self, parent)

    # 初始化核心属性
    self.asset_id = asset_id

    # 初始化状态变量
    self._is_selected = False
    self._is_hovered = False

    # 字体设置
    self.name_font = name_font if name_font else QFont()
    self.tags_font = tags_font if tags_font else QFont()
    self.name_font.setWeight(QFont.Weight.Bold)

    # 字体度量信息
    self.name_font_metrics = QFontMetrics(self.name_font)
    self.tags_font_metrics = QFontMetrics(self.tags_font)

    # 创建标签按钮引用
    self.tags_button = None

    # 初始化UI
    self._initialize_ui(width, height)

  def _initialize_ui(self, width: int, height: int):
    """
    初始化卡片UI结构 - 与原始实现保持一致的初始化顺序和样式设置

    Args:
      width: 卡片宽度
      height: 卡片高度
    """
    self.setFixedSize(width, height)
    self.layout = QVBoxLayout(self)
    self.layout.setContentsMargins(8, 8, 8, 8)
    self.layout.setSpacing(6)
    self.layout.setSizeConstraint(QLayout.SetFixedSize)

    # 应用样式 - 与原始实现保持一致的样式应用顺序
    StyleManager.apply_style(self, False)
    self.setContextMenuPolicy(Qt.NoContextMenu)

    # 添加各个部分 - 与原始实现保持相同的创建顺序
    self._create_image_section(width, height)
    self._create_name_section()
    self._create_tags_section()

    # 设置事件处理 - 与原始实现保持一致的事件设置
    self._setup_events()

    # 触发更新以确保所有组件正确显示
    self.update()

  def _create_image_section(self, card_width: int, card_height: int):
    """
    创建图片显示区域

    Args:
      card_width: 卡片宽度
      card_height: 卡片高度
    """
    self.image_label = QLabel()
    self.image_label.setAlignment(Qt.AlignCenter)
    StyleManager.apply_image_label_style(self.image_label)
    self.image_label.setMouseTracking(False)

    # 计算图片区域尺寸
    layout_margins = self.layout.contentsMargins()
    layout_spacing = self.layout.spacing()

    # 使用从构造函数传入的字体度量信息
    name_label_height = self.name_font_metrics.height()
    tags_label_height = self.tags_font_metrics.height()

    available_width = int(card_width - (layout_margins.left() + layout_margins.right()))
    available_height = int(card_height - (layout_margins.top() + layout_margins.bottom() +
                    name_label_height + tags_label_height + layout_spacing))

    self.image_label.setFixedSize(available_width, available_height)

    # 加载缩略图 - 与原始实现保持一致，直接使用available_width和available_height
    thumbnail_manager = get_thumbnail_manager()
    scaled_pixmap = thumbnail_manager.get_scaled_pixmap(self.asset_id, available_width, available_height, margin_ratio=0.05)
    self.image_label.setPixmap(scaled_pixmap)

    self.image_label._last_width = -1  # 初始化为-1，确保首次resizeEvent会触发更新
    self.image_label._last_height = -1

    # 设置尺寸变化事件
    self.image_label.resizeEvent = lambda event, img=self.image_label, aid=self.asset_id: self._update_image_on_resize(event, img, aid)

    self.layout.addWidget(self.image_label)

  def _create_name_section(self):
    """
    创建名称显示区域
    """
    self.name_label = ElidedLabel()
    self.name_label.setAlignment(Qt.AlignCenter)
    self.name_label.setWordWrap(False)
    self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # 使用从构造函数传入的字体
    self.name_label.setFont(self.name_font)

    # 设置最小高度
    self.name_label.setMinimumHeight(self.name_font_metrics.height() + 8)
    self.name_label.setTextInteractionFlags(Qt.NoTextInteraction)
    self.name_label.setProperty("is_name_label", True)

    # 获取资产名称
    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(self.asset_id)
    friendly_name = self.asset_id  # 默认使用asset_id

    if isinstance(asset, ImagePack):
      descriptor = ImagePack.get_descriptor_by_id(self.asset_id)
      if descriptor:
        name_obj = descriptor.get_name()
        if name_obj:
          friendly_name = name_obj.get()

    # 设置名称文本
    self.name_label.setFullText(friendly_name)

    # 应用样式
    StyleManager.apply_label_style(self.name_label)
    self.name_label.setMouseTracking(False)

    self.layout.addWidget(self.name_label)

  def _create_tags_section(self):
    """
    创建标签显示区域 - 与原始实现保持一致的标签按钮创建逻辑
    """
    # 获取标签管理器和标签 - 使用与旧版相同的标签获取方法
    tag_manager = TagManager.get_instance()
    asset_tags = tag_manager.get_asset_tags_display(self.asset_id)
    tags_text = ", ".join(sorted(asset_tags))

    # 创建标签按钮
    self.tags_button = ElidedPushButton(tags_text if tags_text else self._tr_no_tags.get(), self)
    self.tags_button.setObjectName(f"tags_button_{self.asset_id}")

    # 使用从构造函数传入的字体
    self.tags_button.setFont(self.tags_font)
    self.tags_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # 设置按钮高度
    tag_button_height = int(self.tags_font_metrics.height() * 1.4)
    self.tags_button.setFixedHeight(tag_button_height)

    # 应用样式 - 与原始实现保持一致的样式应用
    StyleManager.apply_tags_button_style(self.tags_button, tag_button_height)

    # 连接信号 - 保持与原始实现相同的事件处理
    self.tags_button.clicked.connect(self._on_tags_button_clicked)
    self.tags_button._asset_id = self.asset_id

    self.layout.addWidget(self.tags_button)

  def _setup_events(self):
    """
    设置卡片事件处理 - 与原始实现保持一致的鼠标跟踪设置
    """
    # 与原始实现保持一致的鼠标跟踪设置
    self.setMouseTracking(True)

  # 事件处理方法
  def enterEvent(self, event):
    """
    鼠标进入卡片事件 - 与原始实现保持一致的事件处理逻辑
    """
    # 调用父类的enterEvent确保标准行为
    QWidget.enterEvent(self, event)

    # 更新悬停状态并应用样式 - 与原始实现保持相同的处理顺序
    self._is_hovered = True
    self._update_style()

  def leaveEvent(self, event):
    """
    鼠标离开卡片事件 - 与原始实现保持一致的事件处理逻辑
    """
    # 调用父类的leaveEvent确保标准行为
    QWidget.leaveEvent(self, event)

    # 更新悬停状态并应用样式 - 与原始实现保持相同的处理顺序
    self._is_hovered = False
    self._update_style()

    # 触发标签按钮的resizeEvent以更新省略文本
    if self.tags_button:
      self.tags_button.resizeEvent(None)

  def mousePressEvent(self, event):
    """
    鼠标点击卡片事件 - 与原始实现保持一致的事件处理逻辑
    """
    QWidget.mousePressEvent(self, event)
    self.clicked.emit(self.asset_id,event)

  def _on_tags_button_clicked(self):
    """
    标签按钮点击处理 - 与原始实现保持一致的事件处理逻辑
    """
    # 与原始实现保持一致，直接发射信号
    self.tags_button_clicked.emit(self.asset_id,self.tags_button)

    # 确保按钮状态正确 - 清除焦点和按下状态
    self.tags_button.setDown(False)
    self.tags_button.clearFocus()
    self.tags_button.update()

  def _update_image_on_resize(self, event, image_label, asset_id):
    """
    处理图片区域尺寸变化 - 与原始实现保持一致的逻辑

    Args:
      event: 事件对象
      image_label: 图片标签
      asset_id: 资产ID
    """
    # 调用原始的resizeEvent
    if event:
      QLabel.resizeEvent(image_label, event)

    current_width = int(image_label.width())
    current_height = int(image_label.height())

    if current_width <= 1 or current_height <= 1:
      return  # 避免极端情况下的无效尺寸

    # 重置_last_width和_last_height以确保图片会被更新
    image_label._last_width = -1
    image_label._last_height = -1

    need_update = (current_width != image_label._last_width or
            current_height != image_label._last_height)

    image_label._last_width = current_width
    image_label._last_height = current_height

    if need_update and current_width > 0 and current_height > 0:
      thumbnail_manager = get_thumbnail_manager()
      # 与原始实现保持一致，使用减1的安全尺寸
      safe_width = max(1, current_width - 1)
      safe_height = max(1, current_height - 1)

      scaled_pixmap = thumbnail_manager.get_scaled_pixmap(
        asset_id, safe_width, safe_height, margin_ratio=0.05)
      image_label.setPixmap(scaled_pixmap)

  def update_tags(self):
    """
    更新卡片的标签显示 - 与原始实现保持一致的标签更新逻辑
    """
    if not self.tags_button:
      return

    # 获取标签管理器和标签 - 使用与原始实现相同的标签获取方法
    tag_manager = TagManager.get_instance()
    asset_tags = tag_manager.get_asset_tags_display(self.asset_id)
    tags_text = ", ".join(sorted(asset_tags))

    # 更新标签按钮文本 - 与原始实现保持相同的更新方式
    self.tags_button.setFullText(tags_text if tags_text else self._tr_no_tags.get())

  def set_selected(self, selected: bool):
    """
    设置卡片选中状态 - 与原始实现保持一致的选中样式应用

    Args:
      selected: 是否选中
    """
    self._is_selected = selected
    self._update_style()

  def _update_style(self):
    """
    更新卡片样式 - 与原始实现保持一致的样式更新逻辑
    """
    # 应用样式 - 与原始实现使用相同的参数和方法
    StyleManager.apply_style(self, self._is_selected, self._is_hovered)

    # 更新各个组件的样式 - 确保与原始实现保持相同的样式应用顺序
    try:
      if self.name_label:
        StyleManager.apply_label_style(self.name_label)
        # 确保名称标签文本重新计算
        size = self.name_label.size()
        event = QResizeEvent(size, size)
        self.name_label.resizeEvent(event)
    except AttributeError:
      pass

    try:
      if self.image_label:
        StyleManager.apply_image_label_style(self.image_label)
    except AttributeError:
      pass

    try:
      if self.tags_button:
        # 与原始实现保持一致，使用按钮高度作为参数
        height = self.tags_button.height()
        StyleManager.apply_tags_button_style(self.tags_button, height)
        # 确保标签按钮文本重新计算
        self.tags_button.resizeEvent(None)
    except AttributeError:
      pass

  def _on_theme_updated(self, palette=None):
    """
    处理主题更新事件 - 与原始实现保持一致的主题更新逻辑

    Args:
      palette: 调色板对象，如果为None则使用当前调色板
    """
    # 应用新样式到各个组件 - 与原始实现保持相同的样式应用顺序和方法
    StyleManager.apply_style(self, self._is_selected, self._is_hovered, palette=palette)

    try:
      if self.name_label:
        StyleManager.apply_label_style(self.name_label)
        # 确保名称标签文本重新计算
        size = self.name_label.size()
        event = QResizeEvent(size, size)
        self.name_label.resizeEvent(event)
    except AttributeError:
      pass

    try:
      if self.image_label:
        StyleManager.apply_image_label_style(self.image_label)
    except AttributeError:
      pass

    try:
      if self.tags_button:
        # 与原始实现保持一致，使用相同的参数
        height = self.tags_button.height()
        StyleManager.apply_tags_button_style(self.tags_button, height)
        # 确保标签按钮文本重新计算
        self.tags_button.resizeEvent(None)
    except AttributeError:
      pass

  def update_theme(self, palette=None):
    """
    更新主题样式

    Args:
      palette: 调色板对象，如果为None则使用当前调色板
    """
    # 调用主题更新处理方法，并传递palette参数
    self._on_theme_updated(palette)