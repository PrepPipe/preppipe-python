from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *


class StyleManager:
  """样式管理器，集中管理所有UI样式的定义和应用"""
  def __init__(self, parent=None):
    self.parent = parent
    # 初始化样式字典 - 包含深色和浅色模式的样式
    self.styles = {
        'light': {
            'normal': "background-color: rgba(230, 230, 230, 1.0); border: 1px solid rgba(200, 200, 200, 1.0); border-radius: 8px; padding: 2px;",
            'hover': "background-color: rgba(210, 210, 210, 1.0); border: 1px solid rgba(180, 180, 180, 1.0); border-radius: 8px; padding: 2px;",
            'selected': "background-color: rgba(200, 215, 240, 1.0); border: 2px solid #4a90e2; border-radius: 8px; padding: 1px;",
            'selected_hover': "background-color: rgba(190, 205, 235, 1.0); border: 2px solid #3a80d2; border-radius: 8px; padding: 1px;",
            'name_color': '#000000',
            'image_background': '#f0f0f0',
            'tag_block': {
                'normal': "QWidget { background-color: rgba(220, 220, 220, 0.95); border: none; border-radius: 12px; padding: 4px 8px; }",
                'hover': "QWidget:hover { background-color: rgba(200, 200, 200, 0.95); border: none; }"
            },
            'edit_line': "background-color: rgba(220, 220, 220, 0.95); border: none; border-radius: 12px; padding: 4px 8px; color: #000000;",
            'tags_button': {
                'normal': "ElidedPushButton { background-color: rgba(220, 220, 220, 0.95); border: 1px solid rgba(200, 200, 200, 0.95); border-radius: {radius}px; color: #000000; padding: 0px 10px; text-align: center; outline: none; height: {height}px; qproperty-flat: false; }",
                'hover': "ElidedPushButton:hover { background-color: rgba(230, 230, 230, 0.95); border-color: rgba(210, 210, 210, 0.95); border-radius: {radius}px; color: #000000; }",
                'pressed': "ElidedPushButton:pressed { background-color: rgba(230, 230, 230, 0.95); border-color: rgba(200, 200, 200, 0.95); border-radius: {radius}px; color: #000000; }",
                'focus': "ElidedPushButton:focus { background-color: rgba(220, 220, 220, 0.95); border: 1px solid rgba(200, 200, 200, 0.95); border-radius: {radius}px; color: #000000; outline: none; }",
                'flat': "ElidedPushButton:flat { border-radius: {radius}px; }"
            }
        },
        'dark': {
            'normal': "background-color: rgba(50, 50, 50, 1.0); border: 1px solid rgba(70, 70, 70, 1.0); border-radius: 8px; padding: 2px;",
            'hover': "background-color: rgba(60, 60, 60, 1.0); border: none; border-radius: 8px; padding: 2px;",
            'selected': "background-color: rgba(80, 80, 80, 1.0); border: none; border-radius: 8px; padding: 2px;",
            'selected_hover': "background-color: rgba(100, 100, 100, 1.0); border: none; border-radius: 8px; padding: 2px;",
            'name_color': '#ffffff',
            'image_background': '#3a3a3a',
            'tag_block': {
                'normal': "QWidget { background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: 12px; padding: 4px 8px; }",
                'hover': "QWidget:hover { background-color: rgba(85, 85, 85, 0.95); border: none; }"
            },
            'edit_line': "background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: 12px; padding: 4px 8px; color: #CCCCCC;",
            'tags_button': {
                'normal': "ElidedPushButton { background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: {radius}px; color: #CCCCCC; padding: 0px 10px; text-align: center; outline: none; height: {height}px; qproperty-flat: false; }",
                'hover': "ElidedPushButton:hover { background-color: rgba(85, 85, 85, 0.95); border: none; border-radius: {radius}px; color: #DDDDDD; }",
                'pressed': "ElidedPushButton:pressed { background-color: rgba(85, 85, 85, 0.95); border: none; border-radius: {radius}px; color: #DDDDDD; }",
                'focus': "ElidedPushButton:focus { background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: {radius}px; color: #CCCCCC; outline: none; }",
                'flat': "ElidedPushButton:flat { border: none; border-radius: {radius}px; }"
            }
        }
    }
    self.current_theme = None
    self.current_styles = {}
    self._update_theme()

  def _detect_theme(self, palette=None):
    """检测当前系统主题是深色还是浅色"""
    if palette is None:
      palette = self.parent.palette() if self.parent else QApplication.palette()
    bg_color = palette.color(QPalette.Window)
    # 计算颜色亮度 (HSL亮度公式)
    brightness = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255
    return 'dark' if brightness < 0.5 else 'light'

  def _update_theme(self, palette=None):
    """更新当前主题并加载对应的样式"""
    theme = self._detect_theme(palette)
    if theme != self.current_theme:
      self.current_theme = theme
      self.current_styles = self.styles[theme]
    return self.current_theme

  def get_style(self, style_name):
    """获取指定样式"""
    return self.current_styles.get(style_name, "")

  def get_tags_button_style(self, height):
    """获取标签按钮样式，根据高度动态计算圆角"""
    radius = height // 2
    styles = []
    for key, template in self.current_styles.get('tags_button', {}).items():
      # 使用字符串替换而不是format方法，避免花括号解析问题
      style = template.replace('{radius}', str(radius))
      style = style.replace('{height}', str(height))
      styles.append(style)
    return "\n".join(styles)

  def get_tag_block_style(self):
    """获取标签块样式"""
    tag_block_styles = self.current_styles.get('tag_block', {})
    return "\n".join(tag_block_styles.values())

  def apply_style_to_thumbnail(self, widget, is_selected=False, is_hover=False):
    """应用样式到缩略图部件"""
    if is_selected and is_hover:
      widget.setStyleSheet(self.get_style('selected_hover'))
    elif is_selected:
      widget.setStyleSheet(self.get_style('selected'))
    elif is_hover:
      widget.setStyleSheet(self.get_style('hover'))
    else:
      widget.setStyleSheet(self.get_style('normal'))