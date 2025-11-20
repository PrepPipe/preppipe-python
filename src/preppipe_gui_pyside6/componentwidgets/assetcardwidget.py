#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资产卡片相关组件

包含用于资产浏览的自定义组件，如文本省略控件等
"""

from PySide6.QtWidgets import QPushButton, QLabel
from PySide6.QtCore import Qt
from PySide6.QtCore import Qt, QSize


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