from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *


class StyleManager:
  """样式管理器，集中管理所有UI样式的定义和应用"""
  _styles = {
    'light': {
      'normal': "background-color: rgba(230, 230, 230, 1.0); border: 1px solid rgba(200, 200, 200, 1.0); border-radius: 8px; padding: 2px;",
      'hover': "background-color: rgba(210, 210, 210, 1.0); border: 1px solid rgba(180, 180, 180, 1.0); border-radius: 8px; padding: 2px;",
      'selected': "background-color: rgba(200, 215, 240, 1.0); border: 2px solid #4a90e2; border-radius: 8px; padding: 1px;",
      'selected_hover': "background-color: rgba(190, 205, 235, 1.0); border: 2px solid #3a80d2; border-radius: 8px; padding: 1px;",
      'name_color': '#000000',
      'image_background': '#f0f0f0',
      'image_label': "border: none; background-color: {image_background};",
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
      'image_label': "border: none; background-color: {image_background};",
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

  @staticmethod
  def detect_theme(palette=None):
    """检测当前系统主题是深色还是浅色"""
    if palette is None:
      palette = QApplication.palette()
    bg_color = palette.color(QPalette.Window)
    # 计算颜色亮度 (HSL亮度公式)
    brightness = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255
    return 'dark' if brightness < 0.5 else 'light'

  @staticmethod
  def get_style(style_name, palette=None):
    """获取指定样式"""
    theme = StyleManager.detect_theme(palette)
    return StyleManager._styles[theme].get(style_name, "")

  @staticmethod
  def get_tags_button_style(height, palette=None):
    """获取标签按钮样式，根据高度动态计算圆角"""
    theme = StyleManager.detect_theme(palette)
    radius = height // 2
    styles = []
    for key, template in StyleManager._styles[theme].get('tags_button', {}).items():
      style = template.replace('{radius}', str(radius))
      style = style.replace('{height}', str(height))
      styles.append(style)
    return "\n".join(styles)
    
  @staticmethod
  def apply_tags_button_style(button, height, palette=None):
    """应用标签按钮样式到按钮部件
    
    Args:
        button: 要应用样式的按钮部件
        height: 按钮高度
        palette: 调色板，如果为None则使用当前应用调色板
    """
    style = StyleManager.get_tags_button_style(height, palette)
    button.setStyleSheet(style)

  @staticmethod
  def get_tag_block_style(palette=None):
    """获取标签块样式"""
    theme = StyleManager.detect_theme(palette)
    tag_block_styles = StyleManager._styles[theme].get('tag_block', {})
    return "\n".join(tag_block_styles.values())
    
  @staticmethod
  def apply_tag_block_style(widget, palette=None):
    """应用标签块样式到部件
    
    Args:
        widget: 要应用样式的部件
        palette: 调色板，如果为None则使用当前应用调色板
    """
    style = StyleManager.get_tag_block_style(palette)
    widget.setStyleSheet(style)

  @staticmethod
  def apply_style(widget, is_selected=False, is_hover=False, palette=None):
    """应用样式到部件"""
    match (is_selected, is_hover):
      case (True, True):
        widget.setStyleSheet(StyleManager.get_style('selected_hover', palette))
      case (True, False):
        widget.setStyleSheet(StyleManager.get_style('selected', palette))
      case (False, True):
        widget.setStyleSheet(StyleManager.get_style('hover', palette))
      case (False, False):
        widget.setStyleSheet(StyleManager.get_style('normal', palette))

  @staticmethod
  def apply_label_style(label, palette=None):
    """应用样式到标签"""
    # 使用通用样式应用方法
    StyleManager.apply_style_to_widget(label, 'name_color', palette=palette)
  
  @staticmethod
  def apply_image_label_style(label, palette=None):
    """应用样式到图片标签"""
    theme = StyleManager.detect_theme(palette)
    image_background = StyleManager._styles[theme].get('image_background', '#f0f0f0')
    # 使用通用样式应用方法并传递背景色参数
    StyleManager.apply_style_to_widget(label, 'image_label', palette=palette, image_background=image_background)
  
  @staticmethod
  def apply_style_to_widget(widget, style_name, palette=None, **kwargs):
    """通用样式应用方法，减少代码重复
    
    Args:
        widget: 要应用样式的部件
        style_name: 样式名称
        palette: 调色板，如果为None则使用当前应用调色板
        **kwargs: 用于样式字符串格式化的额外参数
    """
    theme = StyleManager.detect_theme(palette)
    
    # 特殊处理name_color样式，因为它需要构建完整的样式字符串
    if style_name == 'name_color':
        color = StyleManager._styles[theme].get('name_color', '#000000')
        style = f"color: {color}; padding: 4px 0; border: none; background-color: transparent;"
    else:
        template = StyleManager.get_style(style_name, palette)
        # 应用额外参数进行格式化
        style = template.format(**kwargs)
    
    widget.setStyleSheet(style)