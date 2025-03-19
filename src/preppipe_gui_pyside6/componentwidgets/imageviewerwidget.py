from PySide6.QtCore import Qt, QTimer, QPoint, QEvent
from PySide6.QtGui import QPixmap, QMouseEvent, QWheelEvent, QContextMenuEvent, QTransform, QPainter
from PySide6.QtWidgets import (
  QApplication,
  QGraphicsView,
  QGraphicsScene,
  QGraphicsPixmapItem,
  QSlider,
  QMenu,
  QFileDialog,
  QWidget,
  QVBoxLayout,
)
from preppipe.language import *

class ImageViewerWidget(QGraphicsView):
  TR_gui_imageviewerwidget = TranslationDomain("gui_imageviewerwidget")
  _tr_export_as_png = TR_gui_imageviewerwidget.tr("export_as_png",
    en="Export as PNG",
    zh_cn="导出为 PNG",
    zh_hk="匯出為 PNG",
  )
  def __init__(self, parent: QWidget = None, context_menu_callback=None):
    super().__init__(parent)
    # Set smooth rendering
    self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    self.setMouseTracking(True)  # for slider show/hide on mouse moves

    # Set up the scene and pixmap item.
    self._scene = QGraphicsScene(self)
    self.setScene(self._scene)
    self._pixmap_item = QGraphicsPixmapItem()
    self._pixmap_item.setTransformationMode(Qt.SmoothTransformation)
    self._scene.addItem(self._pixmap_item)
    self._pixmap = None  # currently displayed QPixmap

    # Zoom factor (1.0 corresponds to 100%).
    self._current_scale = 1.0

    # Transformation anchor for smooth zooming.
    self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
    self.setDragMode(QGraphicsView.NoDrag)  # we implement our own panning

    # For panning: record last mouse position when left button is pressed.
    self._last_mouse_pos = None

    # Create a horizontal slider for zoom control.
    self.slider = QSlider(Qt.Horizontal, self)
    self.slider.setMinimum(2)
    self.slider.setMaximum(200)
    self.slider.setValue(100)
    self.slider.valueChanged.connect(self.on_slider_value_changed)
    self.slider.hide()  # initially hidden

    # Timer to hide the slider after 1 second of inactivity.
    self._slider_timer = QTimer(self)
    self._slider_timer.setInterval(1000)
    self._slider_timer.setSingleShot(True)
    self._slider_timer.timeout.connect(self.slider.hide)

    # Callback for additional context menu actions.
    self.context_menu_callback = context_menu_callback

  def resizeEvent(self, event):
    # Position the slider at the bottom with a margin.
    margin = 10
    slider_height = 20
    self.slider.setGeometry(
      margin,
      self.height() - slider_height - margin,
      self.width() - 2 * margin,
      slider_height,
    )
    super().resizeEvent(event)

  def on_slider_value_changed(self, value: int):
    # Convert slider percentage to scale factor.
    scale = value / 100.0
    self.set_zoom(scale)

  def set_zoom(self, scale: float):
    """Update zoom factor while preserving the current view center."""
    # Remember the current center in scene coordinates.
    center = self.mapToScene(self.viewport().rect().center())
    self._current_scale = scale
    # Set the new transformation.
    self.setTransform(QTransform().scale(scale, scale))
    # Restore the center.
    self.centerOn(center)

  def wheelEvent(self, event: QWheelEvent):
    # Show the slider
    self.slider.show()
    self._slider_timer.start()  # restart timer on every move
    # Zoom in/out with the mouse wheel.
    delta = event.angleDelta().y()
    factor = 1.0 + delta / 240.0  # Adjust zoom sensitivity as needed.
    new_scale = self._current_scale * factor
    # Clamp scale to slider's min/max.
    min_scale = self.slider.minimum() / 100.0
    max_scale = self.slider.maximum() / 100.0
    new_scale = max(min_scale, min(new_scale, max_scale))
    self._current_scale = new_scale

    # Update the slider without triggering its signal.
    self.slider.blockSignals(True)
    self.slider.setValue(int(new_scale * 100))
    self.slider.blockSignals(False)

    self.set_zoom(new_scale)

  def mousePressEvent(self, event: QMouseEvent):
    if event.button() == Qt.LeftButton:
      # Begin panning.
      self._last_mouse_pos = event.pos()
      event.accept()
    else:
      super().mousePressEvent(event)

  def mouseMoveEvent(self, event: QMouseEvent):
    if event.buttons() & Qt.LeftButton and self._last_mouse_pos is not None:
      # Calculate movement delta.
      delta = event.pos() - self._last_mouse_pos
      self._last_mouse_pos = event.pos()
      # Adjust the scrollbars to pan.
      self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
      self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
      event.accept()
    else:
      super().mouseMoveEvent(event)

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.LeftButton:
      self._last_mouse_pos = None
    super().mouseReleaseEvent(event)

  def setImage(self, pixmap: QPixmap):
    """
    Set a new image.
    If the new image has the same dimensions as the current one,
    the view position (pan/zoom) is preserved.
    Otherwise, the view is reset.
    """
    if self._pixmap is not None:
      if self._pixmap.size() == pixmap.size():
        # Same dimensions: update the pixmap without resetting view.
        self._pixmap = pixmap
        self._pixmap_item.setPixmap(pixmap)
        return
    # New dimensions or first image: update and reset view.
    self._pixmap = pixmap
    self._pixmap_item.setPixmap(pixmap)
    self._scene.setSceneRect(pixmap.rect())

    # Reset zoom factor to 100%.
    self._current_scale = 1.0
    self.slider.blockSignals(True)
    self.slider.setValue(100)
    self.slider.blockSignals(False)
    self.setTransform(QTransform().scale(1.0, 1.0))
    self.centerOn(self._pixmap_item)

  def contextMenuEvent(self, event: QContextMenuEvent):
    """Open a context menu on right-click."""
    menu = QMenu(self)
    export_action = menu.addAction(self._tr_export_as_png.get())
    # Allow outside code to add custom actions.
    if self.context_menu_callback:
      self.context_menu_callback(menu)
    # Execute the menu.
    action = menu.exec(event.globalPos())
    if action == export_action:
      self.export_as_png()

  def export_as_png(self):
    """Open a file dialog to export the current image as a PNG file."""
    file_path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG Files (*.png)")
    if file_path:
      if not file_path.lower().endswith(".png"):
        file_path += ".png"
      # Save the original QPixmap.
      self._pixmap.save(file_path, "PNG")
