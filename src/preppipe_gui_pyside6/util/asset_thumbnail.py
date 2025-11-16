# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import PIL.Image
import os
import threading
from pathlib import Path
from PySide6.QtGui import QPixmap, QPainter, Qt
from PySide6.QtCore import QObject, Signal, QThreadPool, QThread
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack


class ThumbnailManager:
  """
  缩略图管理器单例类，统一负责所有资产缩略图的生成、缓存和管理

  公共API接口：
  - get_pixmap_for_asset: 获取指定资产的QPixmap对象
  - get_scaled_pixmap: 获取指定尺寸的缩放后pixmap
  - generate_all_thumbnails: 批量生成所有图片素材包的缩略图
  - clear_cache: 清理内存和磁盘缓存
  """

  # 默认缩略图尺寸
  DEFAULT_BACKGROUND_SIZE = (512, 288)  # 16:9
  DEFAULT_CHARACTER_SIZE = (288, 512)   # 9:16

  def __init__(self, cache_dir: str = None):
    """
    初始化缩略图管理器
    """
    # 初始化线程锁
    self._lock = threading.RLock()

    # 设置缓存目录
    if cache_dir is None:
      # 使用项目根目录下的thumbnails文件夹作为默认缓存目录
      self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                   'thumbnails')
    else:
      self.cache_dir = cache_dir

    # 确保缓存目录存在
    Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    # 缩略图缓存字典，用于内存缓存
    self.thumbnail_cache = {}

    # 线程池，用于异步生成缩略图
    self._thread_pool = QThreadPool()
    self._thread_pool.setMaxThreadCount(4)

    # 获取AssetManager实例
    self.asset_manager = AssetManager.get_instance()

  def _generate_thumbnail_from_imagepack(
    self,
    asset_id: str,
    crop_region: tuple[int, int, int, int] | None = None,
    target_size: tuple[int, int] | None = None,
    use_default_sizes: bool = True
  ) -> PIL.Image.Image | None:
    """
    【内部方法】从打包好的图片素材包中基于第一个差分生成缩略图

    Args:
      asset_id: 图片素材包的ID
      crop_region: 截取区域，格式为 (left, top, right, bottom)，None表示使用整个图像
      target_size: 期望的缩略图尺寸，格式为 (width, height)，None表示不调整大小
      use_default_sizes: 是否使用默认尺寸策略（背景512x288，立绘288x512）

    Returns:
      PIL.Image.Image: 生成的缩略图，如果无法生成则返回None
    """
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

      if use_default_sizes:
        pack_type = descriptor.get_image_pack_type()

        if pack_type == descriptor.ImagePackType.BACKGROUND:
          final_target_size = self.DEFAULT_BACKGROUND_SIZE
          if crop_region is not None:
            image = image.crop(crop_region)
          image = image.resize(final_target_size, resample=PIL.Image.Resampling.LANCZOS)

        elif pack_type == descriptor.ImagePackType.CHARACTER:
          final_target_size = self.DEFAULT_CHARACTER_SIZE
          bbox_left, bbox_top, bbox_right, bbox_bottom = descriptor.bbox

          # 计算bbox中心点和裁剪区域
          bbox_center_x = (bbox_left + bbox_right) // 2
          bbox_center_y = (bbox_top + bbox_bottom) // 2
          bbox_width = bbox_right - bbox_left
          bbox_height = bbox_bottom - bbox_top
          crop_size = max(bbox_width, bbox_height) * 1.5

          # 计算默认裁剪区域
          crop_left = max(0, int(bbox_center_x - crop_size // 2))
          crop_top = max(0, int(bbox_center_y - crop_size // 2))
          crop_right = min(image.width, int(bbox_center_x + crop_size // 2))
          crop_bottom = min(image.height, int(bbox_center_y + crop_size // 2))

          # 使用用户提供的裁剪区域（如果有）
          if crop_region is not None:
            crop_left, crop_top, crop_right, crop_bottom = crop_region

          image = image.crop((crop_left, crop_top, crop_right, crop_bottom))
          image = image.resize(final_target_size, resample=PIL.Image.Resampling.LANCZOS)

      else:
        # 用户模式
        if crop_region is not None:
          image = image.crop(crop_region)

        if target_size is not None:
          image = image.resize(target_size, resample=PIL.Image.Resampling.LANCZOS)

      return image

    except Exception as e:
      print(f"Error generating thumbnail for {asset_id}: {e}")
      return None

  def _get_thumbnail_path(self, asset_id: str, target_size: tuple[int, int] = None) -> str:
    """
    【内部方法】获取指定资产ID的缩略图缓存路径

    Args:
      asset_id: 资产ID，用于标识唯一的资产
      target_size: 缩略图尺寸，如果为None则使用默认尺寸

    Returns:
      str: 缩略图的完整文件路径
    """
    # 生成唯一的文件名，包含资产ID和尺寸信息
    size_str = f"_{target_size[0]}x{target_size[1]}" if target_size else ""
    filename = f"{asset_id}_thumbnail{size_str}.png"
    return os.path.join(self.cache_dir, filename)

  def get_or_generate_thumbnail(self, asset_id: str) -> str | None:
    """
    获取或生成资产的缩略图路径

    Args:
      asset_id: 资产的唯一标识符

    Returns:
      str | None: 成功时返回缩略图文件路径，失败时返回None
    """
    # 首先尝试获取已缓存的路径
    cached_path = self._get_cached_thumbnail_path(asset_id)
    if cached_path:
      return cached_path

    # 如果缩略图不存在，尝试生成
    try:
      asset = self.asset_manager.get_asset(asset_id)
      if not isinstance(asset, ImagePack):
        return None

      thumbnail = self._generate_thumbnail_from_imagepack(asset_id)
      if thumbnail is not None:
        # 确保目录存在
        os.makedirs(os.path.dirname(self._get_thumbnail_path(asset_id)), exist_ok=True)

        # 保存缩略图
        thumbnail.save(self._get_thumbnail_path(asset_id))

        # 再次调用_get_cached_thumbnail_path以更新缓存
        return self._get_cached_thumbnail_path(asset_id)
    except Exception as e:
      print(f"Error generating thumbnail for asset {asset_id}: {e}")

    return None

  def get_pixmap_for_asset(self, asset_id: str, width: int, height: int,
                          is_character: bool = False, is_background: bool = False) -> QPixmap:
    """
    【公共API】获取指定资产的QPixmap对象，并根据资产类型和目标尺寸进行缩放

    Args:
      asset_id: 资产的唯一标识符
      width: 目标宽度
      height: 目标高度
      is_character: 是否为角色立绘资产，影响缩放策略
      is_background: 是否为背景资产，影响缩放策略

    Returns:
      QPixmap: 适用于UI显示的图片对象
    """
    # 获取缩略图路径
    thumbnail_path = self.get_or_generate_thumbnail(asset_id)

    if thumbnail_path and os.path.exists(thumbnail_path):
      pixmap = QPixmap(thumbnail_path)
      if not pixmap.isNull():
        return self.scale_pixmap_for_asset(pixmap, width, height, is_character, is_background)

    # 返回占位符图片
    return self.get_placeholder_pixmap(width, height)

  def get_scaled_pixmap(self, asset_id: str, width: int, height: int) -> QPixmap:
    """
    【公共API】获取指定资产的缩放后的pixmap，自动判断资产类型

    自动识别资产类型并应用适当的缩放策略。

    Args:
      asset_id: 资产ID
      width: 目标宽度
      height: 目标高度

    Returns:
      QPixmap: 按照指定尺寸缩放后的图片对象
    """
    # 获取资产类型信息并调用核心方法
    is_character, is_background = self._get_asset_type_info(asset_id)
    return self.get_pixmap_for_asset(asset_id, width, height, is_character, is_background)

  def _get_cached_thumbnail_path(self, asset_id: str) -> str | None:
    """
    【内部方法】获取缓存的缩略图路径

    Args:
      asset_id: 资产ID

    Returns:
      str | None: 缩略图路径，如果不存在则返回None
    """
    # 检查缓存中是否已存在
    if asset_id in self.thumbnail_cache:
      thumbnail_path = self.thumbnail_cache[asset_id]
      if os.path.exists(thumbnail_path):
        return thumbnail_path
      # 如果缓存路径不存在，移除缓存项
      del self.thumbnail_cache[asset_id]

    # 如果缓存中不存在，尝试获取缩略图路径
    thumbnail_path = self._get_thumbnail_path(asset_id)
    if os.path.exists(thumbnail_path):
      # 更新缓存
      self.thumbnail_cache[asset_id] = thumbnail_path
      return thumbnail_path

    return None

  def scale_pixmap_for_asset(self, pixmap: QPixmap, width: int, height: int,
                            is_character: bool, is_background: bool) -> QPixmap:
    """
    根据资产类型和目标尺寸缩放QPixmap

    Args:
      pixmap: 原始QPixmap对象
      width: 目标宽度
      height: 目标高度
      is_character: 是否为角色资产
      is_background: 是否为背景资产

    Returns:
      QPixmap: 缩放后的QPixmap对象
    """
    original_width = pixmap.width()
    original_height = pixmap.height()

    # 计算新的尺寸，根据资产类型选择不同的策略
    if is_character:
      # 角色立绘：优先保证高度
      scale_factor = height / original_height
      new_width = int(original_width * scale_factor)

      # 如果宽度超出目标宽度，调整缩放比例
      if new_width > width:
        scale_factor = width / original_width
        new_width = width
        new_height = int(original_height * scale_factor)
      else:
        new_height = height
    elif is_background:
      # 背景：优先保证宽度
      scale_factor = width / original_width
      new_height = int(original_height * scale_factor)

      # 如果高度超出目标高度，调整缩放比例
      if new_height > height:
        scale_factor = height / original_height
        new_width = int(original_width * scale_factor)
        new_height = height
      else:
        new_width = width
    else:
      # 其他资产：简单保持宽高比
      scaled_pixmap = pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
      return self._create_centered_pixmap(scaled_pixmap, width, height)

    # 缩放图片并居中
    scaled_pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return self._create_centered_pixmap(scaled_pixmap, width, height)

  def _create_centered_pixmap(self, scaled_pixmap: QPixmap, target_width: int, target_height: int) -> QPixmap:
    """
    【内部方法】创建一个目标尺寸的透明pixmap，并将缩放后的pixmap居中放置

    将源pixmap按比例缩放并居中放置在目标尺寸的画布上，保持背景透明。

    Args:
      scaled_pixmap: 缩放后的QPixmap对象
      target_width: 目标宽度
      target_height: 目标高度

    Returns:
      QPixmap: 居中放置的目标尺寸pixmap，背景为透明
    """
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
    """
    【内部方法】创建占位符图片

    当缩略图无法生成或加载时使用的默认占位图，显示灰色背景和提示文字。

    Args:
      width: 图片宽度
      height: 图片高度
      text: 显示的提示文本，默认为"No Image"

    Returns:
      QPixmap: 灰色背景的占位符QPixmap对象
    """
    placeholder = QPixmap(width, height)
    placeholder.fill(Qt.lightGray)

    painter = QPainter(placeholder)
    painter.drawText(placeholder.rect(), Qt.AlignCenter, text)
    painter.end()

    return placeholder

  def generate_all_thumbnails(self, output_dir: str | None = None,
                             file_format: str = 'png',
                             crop_region: tuple[int, int, int, int] | None = None,
                             target_size: tuple[int, int] | None = None,
                             use_default_sizes: bool = True) -> dict[str, str]:
    """
    【公共API】批量生成所有图片素材包的缩略图

    异步生成所有图片素材包的缩略图，支持自定义输出目录、格式、裁剪区域和目标尺寸。
    根据资产类型自动选择适当的缩放策略，确保缩略图质量和比例。

    Args:
      output_dir: 输出目录路径，如果为None则使用默认缓存目录
      file_format: 输出图片格式，默认为'png'
      crop_region: 截取区域，格式为 (left, top, right, bottom)，None表示使用整个图像
      target_size: 期望的缩略图尺寸，格式为 (width, height)，None表示不调整大小
      use_default_sizes: 是否使用默认尺寸策略（背景512x288，立绘288x512）

    Returns:
      dict[str, str]: 生成的缩略图映射字典，键为素材包ID，值为生成的缩略图文件路径
    """
    # 如果指定了输出目录，使用它
    current_cache_dir = output_dir if output_dir else self.cache_dir

    # 确保输出目录存在
    Path(current_cache_dir).mkdir(parents=True, exist_ok=True)

    result = {}

    # 遍历所有资源
    for asset_id, _ in self.asset_manager._assets.items():
      try:
        asset = self.asset_manager.get_asset(asset_id)
        if not isinstance(asset, ImagePack):
          continue

        # 根据参数选择生成方式
        if crop_region or target_size or not use_default_sizes or output_dir:
          # 使用指定参数生成缩略图
            thumbnail = self._generate_thumbnail_from_imagepack(
                asset_id, crop_region, target_size, use_default_sizes
            )
            if thumbnail is not None:
              # 保存缩略图到文件
              filename = f"{asset_id}_thumbnail.{file_format.lower()}"
              filepath = os.path.join(current_cache_dir, filename)
              thumbnail.save(filepath)
              # 更新内存缓存
              self.thumbnail_cache[asset_id] = filepath
              result[asset_id] = filepath
        else:
          # 使用默认方法获取缩略图
          thumbnail_path = self.get_or_generate_thumbnail(asset_id)
          if thumbnail_path:
            result[asset_id] = thumbnail_path

      except Exception as e:
        print(f"Error processing asset {asset_id}: {e}")
        continue

    return result

  def clear_cache(self, clear_memory: bool = True, clear_disk: bool = False):
    """
    【公共API】清理缩略图缓存

    清理内存中的缓存和/或磁盘上的缓存文件，释放系统资源。
    可以选择性地只清理内存缓存或磁盘缓存，或者两者都清理。

    Args:
      clear_memory: 是否清理内存缓存，默认为True
      clear_disk: 是否清理磁盘缓存，默认为False
    """
    if clear_memory:
      self.thumbnail_cache.clear()

    if clear_disk:
      # 清理磁盘缓存
      for filename in os.listdir(self._get_thumbnail_cache_dir()):
        if filename.endswith('_thumbnail.png'):
          try:
            os.remove(os.path.join(self.cache_dir, filename))
          except Exception:
            # 忽略删除错误
            pass

  def _get_asset_type_info(self, asset_id: str):
    """【内部方法】获取资产类型信息"""
    is_character = False
    is_background = False
    asset = self.asset_manager.get_asset(asset_id)
    if isinstance(asset, ImagePack):
      descriptor = ImagePack.get_descriptor_by_id(asset_id)
      if descriptor:
        pack_type = descriptor.get_image_pack_type()
        is_character = pack_type == descriptor.ImagePackType.CHARACTER
        is_background = pack_type == descriptor.ImagePackType.BACKGROUND
    return is_character, is_background

  def _get_thumbnail_cache_dir(self) -> str:
    """【内部方法】获取缩略图缓存目录"""
    return self.cache_dir

# 创建全局缩略图管理器实例
_thumbnail_manager_instance = None
# 用于单例创建的线程锁
_thumbnail_manager_lock = threading.RLock()

def get_thumbnail_manager(cache_dir: str = None) -> ThumbnailManager:
  """获取缩略图管理器实例（单例模式）

  Args:
    cache_dir: 缩略图缓存目录，如果为None则使用默认目录

  Returns:
    ThumbnailManager: 全局唯一的缩略图管理器实例
  """
  global _thumbnail_manager_instance

  # 双检锁模式确保线程安全
  if _thumbnail_manager_instance is None:
    with _thumbnail_manager_lock:
      if _thumbnail_manager_instance is None:
        _thumbnail_manager_instance = ThumbnailManager(cache_dir)
  elif cache_dir and _thumbnail_manager_instance.cache_dir != cache_dir:
    # 如果提供了不同的缓存目录，创建新实例
    with _thumbnail_manager_lock:
      if _thumbnail_manager_instance.cache_dir != cache_dir:
        _thumbnail_manager_instance = ThumbnailManager(cache_dir)

  return _thumbnail_manager_instance


# 缩略图生成工作线程信号类
class ThumbnailGeneratorWorkerSignals(QObject):
  """
  缩略图生成工作线程的信号类
  """
  # 结果信号：资产ID和缩略图路径
  result = Signal(str, str)

# 缩略图生成工作线程类
class ThumbnailGeneratorWorker(QThread):
  """
  缩略图生成工作线程，用于异步生成缩略图
  """
  def __init__(self, asset_id: str, cache_dir: str = None):
    """
    初始化工作线程

    Args:
      asset_id: 资产ID
      cache_dir: 缩略图缓存目录
    """
    super().__init__()
    self.asset_id = asset_id
    self.cache_dir = cache_dir
    self.signals = ThumbnailGeneratorWorkerSignals()

  def run(self):
    """
    运行工作线程，生成缩略图
    """
    # 获取缩略图管理器实例并生成缩略图
    thumbnail_manager = get_thumbnail_manager(self.cache_dir)
    thumbnail_path = thumbnail_manager.get_or_generate_thumbnail(self.asset_id)

    # 发送结果信号
    self.signals.result.emit(self.asset_id, thumbnail_path or "")

def create_thumbnail_worker(asset_id: str, cache_dir: str = None) -> ThumbnailGeneratorWorker:
  """创建缩略图生成工作线程实例

  Args:
    asset_id: 资产ID
    cache_dir: 缩略图缓存目录，如果为None则使用默认目录

  Returns:
    ThumbnailGeneratorWorker: 缩略图生成工作线程实例
  """
  return ThumbnailGeneratorWorker(asset_id, cache_dir)