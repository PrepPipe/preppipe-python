from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=4, spacing=3):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
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
        # 使用整数运算处理边距和坐标
        margins = self.contentsMargins()
        margin_left = int(margins.left())
        margin_top = int(margins.top())
        margin_right = int(margins.right())
        margin_bottom = int(margins.bottom())
        
        x = rect.x() + margin_left
        y = rect.y() + margin_top
        line_height = 0

        # 计算最大可用宽度，确保使用整数运算
        max_width = int(rect.width() - margin_left - margin_right)
        content_right = rect.x() + rect.width() - margin_right

        # 获取间距，确保使用整数
        horizontal_spacing = int(self.horizontalSpacing())
        vertical_spacing = int(self.verticalSpacing())

        for item in self._item_list:
            # 获取项目尺寸，确保使用整数
            item_size = item.sizeHint() if item.sizeHint().isValid() else self._item_size
            item_width = int(item_size.width())
            item_height = int(item_size.height())
            
            # 确保项目宽度不超过内容区域，添加额外的安全边界
            max_item_width = max_width - 2  # 2像素安全边界
            if item_width > max_item_width:
                item_width = max_item_width
            
            # 计算下一个项目的X坐标
            next_x = x + item_width + horizontal_spacing
            
            # 添加5像素安全边界用于换行判断，确保在边界情况下不会出现布局问题
            if next_x + 5 > content_right and line_height > 0:
                # 换行处理，重置X坐标，增加Y坐标
                x = rect.x() + margin_left
                y = y + line_height + vertical_spacing
                next_x = x + item_width + horizontal_spacing
                line_height = 0
            
            # 确保项目尺寸使用整数
            safe_width = item_width
            safe_height = item_height
            
            if not test_only:
                # 确保所有坐标使用整数，避免像素对齐问题
                item.setGeometry(QRect(int(x), int(y), safe_width, safe_height))

            # 更新X坐标和行高
            x = next_x
            line_height = max(line_height, safe_height)

        # 计算最终高度，考虑底部边距
        final_height = y + line_height + margin_bottom - rect.y()
        return final_height

    def setItemSize(self, size):
        """设置所有项目的统一大小"""
        self._item_size = size
        self.update()

    def itemSize(self):
        """获取项目大小"""
        return self._item_size