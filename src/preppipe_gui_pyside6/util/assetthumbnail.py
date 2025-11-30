# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import PIL.Image
import os
import threading
from pathlib import Path
from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QPixmap, QPainter, Qt
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack
from ..settingsdict import SettingsDict


class ThumbnailManager:
  """缩略图管理器单例类，统一负责所有资产缩略图的生成、缓存和管理"""

  DEFAULT_BACKGROUND_SIZE = (512, 288)  # 16:9
  DEFAULT_CHARACTER_SIZE = (288, 512)   # 9:16

  def __init__(self, cache_dir: str = None):
    """初始化缩略图管理器"""
    self._lock = threading.RLock()

    if cache_dir is None:
      base_dir = SettingsDict.get_executable_base_dir()
      self.cache_dir = os.path.join(base_dir, 'thumbnails')
    else:
      self.cache_dir = cache_dir

    Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
    self.thumbnail_cache = {}
    self.asset_manager = AssetManager.get_instance()
    self._thread_pool = QThreadPool()
    self._thread_pool.setMaxThreadCount(4)

  def _generate_thumbnail_from_imagepack(
    self,
    asset_id: str,
    target_size: tuple[int, int] | None = None
  ) -> PIL.Image.Image | None:
    """从图片素材包中生成缩略图"""
    asset = self.asset_manager.get_asset(asset_id)

    if not isinstance(asset, ImagePack):
      return None

    try:
      descriptor = ImagePack.get_descriptor_by_id(asset_id)
      if not asset.is_imagedata_loaded():
        asset.load_imagedata()

      if len(asset.composites) == 0:
        return None

      image_wrapper = asset.get_composed_image(0)
      image = image_wrapper.get()

      # 角色图像自动裁剪
      if descriptor.get_image_pack_type() == descriptor.ImagePackType.CHARACTER:
        bbox_left, bbox_top, bbox_right, bbox_bottom = descriptor.bbox
        image = image.crop((bbox_left, bbox_top, bbox_right, bbox_bottom))

      # 确定目标尺寸
      final_target_size = target_size
      if final_target_size is None:
        pack_type = descriptor.get_image_pack_type()
        if pack_type == descriptor.ImagePackType.BACKGROUND:
          final_target_size = self.DEFAULT_BACKGROUND_SIZE
        elif pack_type == descriptor.ImagePackType.CHARACTER:
          final_target_size = self.DEFAULT_CHARACTER_SIZE

      # 缩放处理
      if final_target_size is not None:
        original_width, original_height = image.size
        scale_x = final_target_size[0] / original_width
        scale_y = final_target_size[1] / original_height
        scale_factor = min(scale_x, scale_y)

        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        resized_image = image.resize((new_width, new_height), resample=PIL.Image.Resampling.LANCZOS)

        # 创建并居中放置结果图像
        result_image = PIL.Image.new('RGBA', final_target_size, (255, 255, 255, 0))
        paste_x = (final_target_size[0] - new_width) // 2
        paste_y = (final_target_size[1] - new_height) // 2
        result_image.paste(resized_image, (paste_x, paste_y))
        image = result_image

      return image

    except Exception as e:
      print(f"Error generating thumbnail for {asset_id}: {e}")
      return None

  def _get_thumbnail_path(self, asset_id: str, target_size: tuple[int, int] = None) -> str:
    """获取指定资产ID的缩略图缓存路径"""
    size_str = f"_{target_size[0]}x{target_size[1]}" if target_size else ""
    filename = f"{asset_id}_thumbnail{size_str}.png"
    return os.path.join(self.cache_dir, filename)

  def get_or_generate_thumbnail(self, asset_id: str) -> str | None:
    """获取或生成资产的缩略图路径"""
    # 检查内存缓存
    if asset_id in self.thumbnail_cache:
      thumbnail_path = self.thumbnail_cache[asset_id]
      if os.path.exists(thumbnail_path):
        return thumbnail_path
      del self.thumbnail_cache[asset_id]

    # 检查磁盘缓存
    thumbnail_path = self._get_thumbnail_path(asset_id)
    if os.path.exists(thumbnail_path):
      self.thumbnail_cache[asset_id] = thumbnail_path
      return thumbnail_path

    # 生成缩略图
    try:
      asset = self.asset_manager.get_asset(asset_id)
      if not isinstance(asset, ImagePack):
        return None

      thumbnail = self._generate_thumbnail_from_imagepack(asset_id)
      if thumbnail is not None:
        thumbnail.save(thumbnail_path)
        self.thumbnail_cache[asset_id] = thumbnail_path
        return thumbnail_path
    except Exception as e:
      print(f"Error generating thumbnail for asset {asset_id}: {e}")

    return None

  def get_pixmap_for_asset(self, asset_id: str, width: int, height: int,
                          margin_ratio: float = 0.05) -> QPixmap:
    """获取指定资产的QPixmap对象，并根据目标尺寸进行缩放，预留一定比例的空白"""
    thumbnail_path = self.get_or_generate_thumbnail(asset_id)

    if thumbnail_path and os.path.exists(thumbnail_path):
      pixmap = QPixmap(thumbnail_path)
      if not pixmap.isNull():
        return self.scale_pixmap_for_asset(pixmap, width, height, margin_ratio=margin_ratio)

    return self.get_placeholder_pixmap(width, height)

  def scale_pixmap_for_asset(self, pixmap: QPixmap, width: int, height: int,
                            margin_ratio: float = 0.05) -> QPixmap:
    """根据目标尺寸缩放QPixmap，预留一定比例的空白"""
    # 计算可用区域
    available_width = int(width * (1 - 2 * margin_ratio))
    available_height = int(height * (1 - 2 * margin_ratio))

    # 计算缩放后的尺寸
    scale_factor = min(available_width / pixmap.width(), available_height / pixmap.height())
    new_size = (int(pixmap.width() * scale_factor), int(pixmap.height() * scale_factor))

    scaled_pixmap = pixmap.scaled(new_size[0], new_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return self._create_centered_pixmap(scaled_pixmap, width, height)

  def generate_all_thumbnails(self, output_dir: str | None = None,
                             file_format: str = 'png',
                             target_size: tuple[int, int] | None = None) -> dict[str, str]:
    """批量生成所有图片素材包的缩略图"""
    current_cache_dir = output_dir if output_dir else self.cache_dir
    Path(current_cache_dir).mkdir(parents=True, exist_ok=True)

    result = {}

    for asset_id, _ in self.asset_manager._assets.items():
      try:
        asset = self.asset_manager.get_asset(asset_id)
        if not isinstance(asset, ImagePack):
          continue

        # 根据参数选择不同的生成方式
        if target_size or output_dir:
          thumbnail = self._generate_thumbnail_from_imagepack(asset_id, target_size)
          if thumbnail is not None:
            filepath = os.path.join(current_cache_dir, f"{asset_id}_thumbnail.{file_format.lower()}")
            thumbnail.save(filepath)
            self.thumbnail_cache[asset_id] = filepath
            result[asset_id] = filepath
        else:
          thumbnail_path = self.get_or_generate_thumbnail(asset_id)
          if thumbnail_path:
            result[asset_id] = thumbnail_path

      except Exception as e:
        print(f"Error processing asset {asset_id}: {e}")

    return result

  def _create_centered_pixmap(self, scaled_pixmap: QPixmap, target_width: int, target_height: int) -> QPixmap:
    """创建目标尺寸的透明pixmap，并将缩放后的pixmap居中放置"""
    result = QPixmap(target_width, target_height)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.drawPixmap(
      (target_width - scaled_pixmap.width()) // 2,
      (target_height - scaled_pixmap.height()) // 2,
      scaled_pixmap
    )
    painter.end()
    return result

  def get_placeholder_pixmap(self, width: int, height: int, text: str = "No Image") -> QPixmap:
    """创建占位符图片"""
    placeholder = QPixmap(width, height)
    placeholder.fill(Qt.lightGray)

    painter = QPainter(placeholder)
    painter.drawText(placeholder.rect(), Qt.AlignCenter, text)
    painter.end()

    return placeholder

  def clear_cache(self, clear_memory: bool = True, clear_disk: bool = False):
    """清理缩略图缓存"""
    if clear_memory:
      self.thumbnail_cache.clear()

    if clear_disk:
      for filename in os.listdir(self.cache_dir):
        if filename.endswith('_thumbnail.png'):
          try:
            os.remove(os.path.join(self.cache_dir, filename))
          except Exception:
            pass

  def generate_thumbnail_async(self, asset_id: str, result_callback) -> None:
    """异步生成缩略图"""
    worker = create_thumbnail_worker(asset_id)
    worker.signals.result.connect(result_callback)
    self._thread_pool.start(worker)

from PySide6.QtCore import QRunnable, Signal, QObject, Slot


class WorkerSignals(QObject):
  """工作线程信号"""
  result = Signal(str, str)  # asset_id, thumbnail_path


class CreateThumbnailWorker(QRunnable):
  """异步生成缩略图的工作线程类"""

  def __init__(self, asset_id: str):
    super().__init__()
    self.asset_id = asset_id
    self.signals = WorkerSignals()

  @Slot()
  def run(self):
    """执行缩略图生成任务"""
    thumbnail_manager = get_thumbnail_manager()
    thumbnail_path = thumbnail_manager.get_or_generate_thumbnail(self.asset_id)
    self.signals.result.emit(self.asset_id, thumbnail_path)

# 创建全局缩略图管理器实例
_thumbnail_manager_instance = None
_thumbnail_manager_lock = threading.RLock()

def get_thumbnail_manager(cache_dir: str = None) -> ThumbnailManager:
  """获取缩略图管理器实例（单例模式）"""
  global _thumbnail_manager_instance

  # 双重检查锁定模式
  if _thumbnail_manager_instance is None:
    with _thumbnail_manager_lock:
      if _thumbnail_manager_instance is None:
        _thumbnail_manager_instance = ThumbnailManager(cache_dir)
  elif cache_dir and _thumbnail_manager_instance.cache_dir != cache_dir:
    with _thumbnail_manager_lock:
      if _thumbnail_manager_instance.cache_dir != cache_dir:
        _thumbnail_manager_instance = ThumbnailManager(cache_dir)

  return _thumbnail_manager_instance

def create_thumbnail_worker(asset_id: str) -> CreateThumbnailWorker:
  """创建缩略图生成工作线程"""
  return CreateThumbnailWorker(asset_id)