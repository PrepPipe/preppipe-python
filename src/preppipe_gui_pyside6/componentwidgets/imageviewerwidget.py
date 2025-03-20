from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *

class ImageViewerWidget(QGraphicsView):
  TR_gui_imageviewerwidget = TranslationDomain("gui_imageviewerwidget")
  _tr_export_as_png = TR_gui_imageviewerwidget.tr("export_as_png",
    en="Export as PNG",
    zh_cn="导出为 PNG",
    zh_hk="匯出為 PNG",
  )
  _tr_fit_to_view = TR_gui_imageviewerwidget.tr("fit_to_view",
    en="Fit View",
    zh_cn="自动缩放",
    zh_hk="自動縮放",
  )
  def __init__(self, parent: QWidget = None, context_menu_callback=None):
    super().__init__(parent)
    # Set smooth rendering
    self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    self.setMouseTracking(True)  # for slider show/hide on mouse moves

    self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

    # Set up the scene and pixmap item.
    self._scene = QGraphicsScene(self)
    self.setScene(self._scene)
    self._pixmap_item = QGraphicsPixmapItem()
    self._pixmap_item.setTransformationMode(Qt.SmoothTransformation)
    self._scene.addItem(self._pixmap_item)
    self._original_pixmap = None  # currently displayed QPixmap (unmodified)

    # Zoom factor (1.0 corresponds to 100%).
    self._current_scale = 1.0
    # When zooming out below this threshold, we will switch to a downscaled version.
    self._downscale_threshold = 1.0

    # flag to rescale the image when the widget is resized
    self.is_follow_resize = False

    # Transformation anchor for smooth zooming.
    self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
    self.setDragMode(QGraphicsView.NoDrag)  # we implement our own panning

    # For panning: record last mouse position when left button is pressed.
    self._last_mouse_pos = None

    # Create a horizontal slider for zoom control.
    self.slider = QSlider(Qt.Horizontal, self)
    self.slider.setMinimum(2)
    self.slider.setMaximum(400)
    self.slider.setValue(100)
    self.slider.valueChanged.connect(self.on_slider_value_changed)
    self.slider.hide()  # initially hidden

    # Timer to hide the slider after 1 second of inactivity.
    self._slider_timer = QTimer(self)
    self._slider_timer.setInterval(1000)
    self._slider_timer.setSingleShot(True)
    self._slider_timer.timeout.connect(self.try_hide_slider)

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

  @Slot()
  def try_hide_slider(self):
    if not self.slider.underMouse():
      self.slider.hide()
    else:
      self._slider_timer.start()

  def on_slider_value_changed(self, value: int):
    # Convert slider percentage to scale factor.
    scale = value / 100.0
    self.set_zoom(scale)

  def set_zoom(self, scale: float, mouseCursorAsZoomCenter = False):
    """Update zoom factor while preserving the current view center."""
    # Remember the current center in scene coordinates.
    if scale == self._current_scale:
      return
    center = self.mapToScene(self.viewport().rect().center())
    cursorpos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
    old_scale = self._current_scale
    # Update the scale.
    self._current_scale = scale
    # Set the new transformation.
    capped_old_scale = min(old_scale, self._downscale_threshold)
    scale_for_transform = max(scale, self._downscale_threshold)
    scale_for_updating_center = min(scale, self._downscale_threshold)
    self.setTransform(QTransform().scale(scale_for_transform, scale_for_transform))
    new_center = QPointF(center.x() / capped_old_scale, center.y() / capped_old_scale) * scale_for_updating_center
    self._update_displayed_pixmap(new_center)
    if mouseCursorAsZoomCenter:
      new_cursorpos = QPointF(cursorpos.x() / capped_old_scale, cursorpos.y() / capped_old_scale) * scale_for_updating_center
      curcursorpos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
      self.moveView(new_cursorpos.x() - curcursorpos.x(), new_cursorpos.y() - curcursorpos.y())
    self.is_follow_resize = False

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

    # Update the slider without triggering its signal.
    self.slider.blockSignals(True)
    self.slider.setValue(int(new_scale * 100))
    self.slider.blockSignals(False)

    self.set_zoom(new_scale, mouseCursorAsZoomCenter=True)
    event.accept()

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
      self.moveView(delta.x(), delta.y())
      event.accept()
    else:
      super().mouseMoveEvent(event)

  def moveView(self, dx: int, dy: int):
    self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - dx)
    self.verticalScrollBar().setValue(self.verticalScrollBar().value() - dy)
    self.is_follow_resize = False

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.LeftButton:
      self._last_mouse_pos = None
    super().mouseReleaseEvent(event)

  def setImage(self, pixmap: QPixmap):
    """
    Sets a new image. If the new image’s dimensions are the same as the current,
    the view position (pan/zoom) is preserved.
    """
    if self._original_pixmap is not None and self._original_pixmap.size() == pixmap.size():
      # Same dimensions: update the pixmap without resetting view.
      self._original_pixmap = pixmap
      center = self.mapToScene(self.viewport().rect().center())
      self._update_displayed_pixmap(center)
      return

    # New image or first image: update and reset view.
    self._original_pixmap = pixmap
    self._scene.setSceneRect(pixmap.rect())
    # Reset zoom factor.
    self._current_scale = 1.0
    self.slider.blockSignals(True)
    self.slider.setValue(100)
    self.slider.blockSignals(False)
    self.setTransform(QTransform().scale(1.0, 1.0))
    # recompute the minimum scale factor (the width and height must be at least 10 pixels)
    ratio_min = max(10 / pixmap.width(), 10 / pixmap.height())
    ratio_min_percentage = max(int(ratio_min * 100), 1)
    self.slider.setMinimum(ratio_min_percentage)
    self._update_displayed_pixmap()
    self.centerOn(self._pixmap_item)

  @Slot()
  def fit_to_view(self):
    if self._original_pixmap is None:
      return
    ratio_x = self.viewport().width() / self._original_pixmap.width()
    ratio_y = self.viewport().height() / self._original_pixmap.height()
    self.set_zoom(max(min(ratio_x, ratio_y), self.slider.minimum() / 100))
    self.is_follow_resize = True

  def _update_displayed_pixmap(self, center: QPointF | None = None):
    """
    Chooses the best pixmap version to display. For very large images,
    when zoomed out (scale < threshold), compute a downscaled version
    to avoid rendering artifacts.
    """
    if self._original_pixmap is None:
      return

    if self._current_scale < self._downscale_threshold:
      # Compute effective size: original dimensions multiplied by current scale.
      orig_size = self._original_pixmap.size()
      new_width = max(1, int(orig_size.width() * self._current_scale))
      new_height = max(1, int(orig_size.height() * self._current_scale))
      target_size = QSize(new_width, new_height)
      # Downscale using high-quality (smooth) transformation.
      downscaled = self._original_pixmap.toImage().scaled(
        target_size,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation
      )
      new_pixmap = QPixmap.fromImage(downscaled)
    else:
      # Use the full-resolution original.
      new_pixmap = self._original_pixmap
    self._pixmap_item.setPixmap(new_pixmap)
    # Update scene rect to match new pixmap.
    self._scene.setSceneRect(new_pixmap.rect())
    # Restore the previous center.
    if center is not None:
      self.centerOn(center)

  def contextMenuEvent(self, event: QContextMenuEvent):
    """Open a context menu on right-click."""
    menu = QMenu(self)
    export_action = menu.addAction(self._tr_export_as_png.get())
    export_action.triggered.connect(self.export_as_png)
    fit_action = menu.addAction(self._tr_fit_to_view.get())
    fit_action.triggered.connect(self.fit_to_view)
    # Allow outside code to add custom actions.
    if self.context_menu_callback:
      self.context_menu_callback(menu)
    # Execute the menu.
    menu.exec(event.globalPos())

  @Slot()
  def export_as_png(self):
    """Open a file dialog to export the current image as a PNG file."""
    if self._original_pixmap is None:
      return
    file_path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG Files (*.png)")
    if file_path:
      if not file_path.lower().endswith(".png"):
        file_path += ".png"
      # Save the original QPixmap.
      self._original_pixmap.save(file_path, "PNG")

  def resizeEvent(self, event: QResizeEvent):
    super().resizeEvent(event)
    if self.is_follow_resize:
      # Use delayed invocation to avoid flickering.
      QMetaObject.invokeMethod(self, "fit_to_view", Qt.QueuedConnection)
