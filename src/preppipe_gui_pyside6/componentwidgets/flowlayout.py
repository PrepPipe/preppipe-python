from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=0):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._horizontal_spacing = spacing
        self._vertical_spacing = spacing
        self._item_list = []
        self._item_size = QSize(160, 200)

    def setHorizontalSpacing(self, spacing):
        """Set horizontal spacing between items"""
        self._horizontal_spacing = spacing
        self.update()

    def setVerticalSpacing(self, spacing):
        """Set vertical spacing between items"""
        self._vertical_spacing = spacing
        self.update()

    def setSpacing(self, spacing):
        """Set both horizontal and vertical spacing between items"""
        self._horizontal_spacing = spacing
        self._vertical_spacing = spacing
        self.update()

    def spacing(self):
        """Get current horizontal spacing (for compatibility)"""
        return self._horizontal_spacing

    def horizontalSpacing(self):
        """Get current horizontal spacing between items"""
        return self._horizontal_spacing

    def verticalSpacing(self):
        """Get current vertical spacing between items"""
        return self._vertical_spacing

    def addItem(self, item):
        self._item_list.append(item)

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
        x = rect.x() + self.contentsMargins().left()
        y = rect.y() + self.contentsMargins().top()
        line_height = 0

        horizontal_spacing = self.horizontalSpacing()
        vertical_spacing = self.verticalSpacing()
        margins = self.contentsMargins()

        available_width = rect.width() - margins.left() - margins.right()

        for item in self._item_list:
            item_size = item.sizeHint() if item.sizeHint().isValid() else self._item_size

            if item_size.width() > available_width:
                item_size.setWidth(available_width)

            if x + item_size.width() > rect.right() - margins.right():
                x = rect.x() + margins.left()
                y += line_height + vertical_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x += item_size.width() + horizontal_spacing
            line_height = max(line_height, item_size.height())

        return y + line_height + margins.bottom()

    def setItemSize(self, size):
        """设置所有项目的统一大小"""
        self._item_size = size
        self.update()

    def itemSize(self):
        """获取项目大小"""
        return self._item_size