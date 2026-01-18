from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QWidgetItem


class FlowLayout(QLayout):
  """
  流式布局管理器，将组件按水平方向排列，一行空间不足时自动换行。
  """
  _horizontal_spacing: int
  _vertical_spacing: int
  _item_list: list[QWidgetItem]
  _item_size: QSize

  def __init__(self, parent=None, margin=4, spacing=3):
    super().__init__(parent)
    if parent is not None:
      self.setContentsMargins(margin, margin, margin, margin)
    self._horizontal_spacing = spacing
    self._vertical_spacing = spacing
    self._item_list = []
    self._item_size = QSize(160, 200)

  def setHorizontalSpacing(self, spacing):
    self._horizontal_spacing = spacing
    self.update()

  def setVerticalSpacing(self, spacing):
    self._vertical_spacing = spacing
    self.update()

  def setSpacing(self, spacing):
    self._horizontal_spacing = spacing
    self._vertical_spacing = spacing
    self.update()

  def spacing(self):
    return self._horizontal_spacing

  def horizontalSpacing(self):
    return self._horizontal_spacing

  def verticalSpacing(self):
    return self._vertical_spacing

  def addItem(self, item):
    self._item_list.append(item)

  def insertWidget(self, index, widget):
    item = QWidgetItem(widget)
    self._item_list.insert(index, item)
    self.update()

  def count(self):
    return len(self._item_list)

  def itemAt(self, index):
    if 0 <= index < len(self._item_list):
      return self._item_list[index]
    return None

  def takeAt(self, index):
    if 0 <= index < len(self._item_list):
      return self._item_list.pop(index)
    return None

  def expandingDirections(self):
    return Qt.Orientations(Qt.Orientation(0))

  def hasHeightForWidth(self):
    return True

  def heightForWidth(self, width):
    return self._do_layout(QRect(0, 0, width, 0), False)

  def setGeometry(self, rect):
    super().setGeometry(rect)
    self._do_layout(rect, True)

  def sizeHint(self):
    return self.minimumSize()

  def minimumSize(self):
    if not self._item_list:
      return QSize()

    size = QSize()
    for item in self._item_list:
      size = size.expandedTo(item.minimumSize())

    margins = self.contentsMargins()
    size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
    return size

  def _do_layout(self, rect, test_only):
    margins = self.contentsMargins()
    margin_left = int(margins.left())
    margin_top = int(margins.top())
    margin_right = int(margins.right())
    margin_bottom = int(margins.bottom())

    x = rect.x() + margin_left
    y = rect.y() + margin_top
    line_height = 0

    max_width = int(rect.width() - margin_left - margin_right)
    content_right = rect.x() + rect.width() - margin_right

    # 直接访问间距属性，避免方法调用可能的问题
    horizontal_spacing = int(self._horizontal_spacing)
    vertical_spacing = int(self._vertical_spacing)

    for item in self._item_list:
      item_size = item.sizeHint() if item.sizeHint().isValid() else self._item_size
      item_width = int(item_size.width())
      item_height = int(item_size.height())

      if item_width > max_width:
        item_width = max_width

      next_x = x + item_width + horizontal_spacing

      if next_x > content_right and line_height > 0:
        # 换行处理
        x = rect.x() + margin_left
        y = y + line_height + vertical_spacing
        next_x = x + item_width + horizontal_spacing
        line_height = 0

      safe_width = item_width
      safe_height = item_height

      if not test_only:
        # 确保所有坐标使用整数，避免像素对齐问题
        item.setGeometry(QRect(int(x), int(y), safe_width, safe_height))

      x = next_x
      line_height = max(line_height, safe_height)

    final_height = y + line_height + margin_bottom - rect.y()
    return final_height

  def setItemSize(self, size):
    self._item_size = size
    self.update()

  def itemSize(self):
    return self._item_size