# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import PIL.Image
import os
import hashlib
from pathlib import Path
from PySide6.QtGui import QPixmap, QPainter, Qt
from PySide6.QtCore import QSize
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack, ImagePackDescriptor


class ThumbnailManager:
  """
  缩略图管理器类，负责生成、缓存和管理缩略图
  """

  # 默认缩略图尺寸
  DEFAULT_BACKGROUND_SIZE = (512, 288)  # 16:9
  DEFAULT_CHARACTER_SIZE = (288, 512)   # 9:16

  def __init__(self, cache_dir: str = None):
    """
    初始化缩略图管理器

    Args:
      cache_dir: 缩略图缓存目录，如果为None则使用默认目录
    """
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

    # 获取AssetManager实例
    self.asset_manager = AssetManager.get_instance()

  def generate_thumbnail_from_imagepack(
    self,
    asset_id: str,
    crop_region: tuple[int, int, int, int] | None = None,
    target_size: tuple[int, int] | None = None,
    use_default_sizes: bool = True
  ) -> PIL.Image.Image | None:
    """
    从打包好的图片素材包中基于第一个差分（composite）生成缩略图

    Args:
      asset_id: 图片素材包的ID
      crop_region: 截取区域，格式为 (left, top, right, bottom)，None表示使用整个图像
      target_size: 期望的缩略图尺寸，格式为 (width, height)，None表示不调整大小
      use_default_sizes: 是否使用默认尺寸策略（背景512x288，立绘288x512（9:16））

    Returns:
      PIL.Image.Image: 生成的缩略图，如果无法生成则返回None
    """
    # 获取图片素材包
    asset = self.asset_manager.get_asset(asset_id)

    if not isinstance(asset, ImagePack):
      return None

    try:
      # 获取描述符以确定图片包类型
      descriptor = ImagePack.get_descriptor_by_id(asset_id)
      # 确保图像数据已加载
      if not asset.is_imagedata_loaded():
        asset.load_imagedata()

      # 获取第一个差分图像（索引为0）
      if len(asset.composites) == 0:
        return None

      # 获取组合图像的ImageWrapper对象
      image_wrapper = asset.get_composed_image(0)

      # 获取PIL Image对象
      image = image_wrapper.get()

      # 根据图片包类型应用默认尺寸和裁剪策略
      if use_default_sizes:
        # 确定图片包类型
        pack_type = descriptor.get_image_pack_type()

        if pack_type == descriptor.ImagePackType.BACKGROUND:
          # 背景图片：缩放到512x288（16:9）
          final_target_size = self.DEFAULT_BACKGROUND_SIZE
          # 不应用特殊裁剪，使用提供的crop_region或全图
          if crop_region is not None:
            # 直接调用crop，PIL会处理范围检查
            image = image.crop(crop_region)
          # 调整大小
          image = image.resize(final_target_size, resample=PIL.Image.Resampling.LANCZOS)

        elif pack_type == descriptor.ImagePackType.CHARACTER:
          # 立绘：使用bbox信息确定面部位置，缩放到288x512（9:16）
          final_target_size = self.DEFAULT_CHARACTER_SIZE

          # 获取边界框信息（作为"头在哪"的参考）
          bbox_left, bbox_top, bbox_right, bbox_bottom = descriptor.bbox

          # 计算bbox中心点
          bbox_center_x = (bbox_left + bbox_right) // 2
          bbox_center_y = (bbox_top + bbox_bottom) // 2

          # 根据bbox大小计算裁剪区域，确保包含面部
          bbox_width = bbox_right - bbox_left
          bbox_height = bbox_bottom - bbox_top

          # 使用bbox大小的1.5倍作为裁剪区域的参考，确保包含整个头部和部分身体
          crop_size = max(bbox_width, bbox_height) * 1.5

          # 计算裁剪区域
          crop_left = max(0, int(bbox_center_x - crop_size // 2))
          crop_top = max(0, int(bbox_center_y - crop_size // 2))
          crop_right = min(image.width, int(bbox_center_x + crop_size // 2))
          crop_bottom = min(image.height, int(bbox_center_y + crop_size // 2))

          # 如果用户提供了裁剪区域，使用用户的设置
          if crop_region is not None:
            # 直接使用用户提供的裁剪区域
            crop_left, crop_top, crop_right, crop_bottom = crop_region

          # 裁剪图像
          image = image.crop((crop_left, crop_top, crop_right, crop_bottom))

          # 调整大小到288x512（9:16）
          image = image.resize(final_target_size, resample=PIL.Image.Resampling.LANCZOS)

      else:
        # 用户模式：使用提供的裁剪区域和目标尺寸
        # 应用裁剪（如果指定了裁剪区域）
        if crop_region is not None:
          # 直接调用crop，PIL会处理范围检查
          image = image.crop(crop_region)

        # 调整大小（如果指定了目标尺寸）
        if target_size is not None:
          # 使用LANCZOS重采样方法以获得更好的质量
          image = image.resize(target_size, resample=PIL.Image.Resampling.LANCZOS)

      return image

    except Exception as e:
      # 捕获所有异常，确保函数不会因为图像处理错误而崩溃
      print(f"Error generating thumbnail for {asset_id}: {e}")
      return None

  def get_thumbnail_path(self, asset_id: str, target_size: tuple[int, int] = None) -> str:
    """
    获取指定资产ID的缩略图缓存路径

    Args:
      asset_id: 资产ID
      target_size: 缩略图尺寸，如果为None则使用默认尺寸

    Returns:
      str: 缩略图的文件路径
    """
    # 生成唯一的文件名，包含资产ID和尺寸信息
    if target_size:
      size_str = f"_{target_size[0]}x{target_size[1]}"
    else:
      size_str = ""

    filename = f"{asset_id}_thumbnail{size_str}.png"
    return os.path.join(self.cache_dir, filename)

  def get_or_generate_thumbnail(self, asset_id: str) -> str | None:
    """
    获取或生成资产的缩略图路径

    Args:
      asset_id: 资产ID

    Returns:
      str | None: 缩略图路径，如果无法生成则返回None
    """
    # 首先尝试获取已缓存的路径
    cached_path = self.get_cached_thumbnail_path(asset_id)
    if cached_path:
      return cached_path

    # 如果缩略图不存在，尝试生成
    try:
      # 获取资产
      asset_manager = AssetManager.get_instance()
      asset = asset_manager.get_asset(asset_id)
      if not isinstance(asset, ImagePack):
        return None

      # 生成缩略图
      thumbnail = self.generate_thumbnail_from_imagepack(asset_id)
      if thumbnail is not None:
        # 确保目录存在
        os.makedirs(os.path.dirname(self.get_thumbnail_path(asset_id)), exist_ok=True)

        # 保存缩略图
        thumbnail.save(self.get_thumbnail_path(asset_id))

        # 再次调用get_cached_thumbnail_path以更新缓存
        return self.get_cached_thumbnail_path(asset_id)
    except Exception as e:
      print(f"Error generating thumbnail for asset {asset_id}: {e}")

    return None

  def get_pixmap_for_asset(self, asset_id: str, width: int, height: int,
                          is_character: bool = False, is_background: bool = False) -> QPixmap:
    """
    获取指定资产的QPixmap对象，并根据资产类型和目标尺寸进行缩放

    Args:
      asset_id: 资产ID
      width: 目标宽度
      height: 目标高度
      is_character: 是否为角色资产
      is_background: 是否为背景资产

    Returns:
      QPixmap: 处理后的QPixmap对象
    """
    # 获取缩略图路径
    thumbnail_path = self.get_or_generate_thumbnail(asset_id)

    if thumbnail_path and os.path.exists(thumbnail_path):
      # 加载图片
      pixmap = QPixmap(thumbnail_path)
      if not pixmap.isNull():
        # 根据资产类型进行适当的缩放
        return self.scale_pixmap_for_asset(pixmap, width, height, is_character, is_background)

    # 返回占位符图片
    return self.get_placeholder_pixmap(width, height)

  def get_scaled_pixmap(self, asset_id: str, width: int, height: int) -> QPixmap:
    """
    便捷方法：获取指定资产的缩放后的pixmap，自动判断资产类型

    Args:
      asset_id: 资产ID
      width: 目标宽度
      height: 目标高度

    Returns:
      QPixmap: 缩放后的pixmap
    """
    # 获取资产类型信息
    is_character, is_background = self.get_asset_type_info(asset_id)

    # 调用核心方法获取pixmap
    return self.get_pixmap_for_asset(asset_id, width, height, is_character, is_background)

  def get_cached_thumbnail_path(self, asset_id: str) -> str | None:
    """
    获取缓存的缩略图路径，包含缓存检查和更新逻辑

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
    thumbnail_path = self.get_thumbnail_path(asset_id)
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
    # 获取原始图片尺寸
    original_width = pixmap.width()
    original_height = pixmap.height()

    # 计算新的尺寸，根据资产类型选择不同的策略
    if is_character:
      # 角色立绘：保持宽高比，优先保证高度
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
      # 背景：保持宽高比，优先保证宽度
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

    # 缩放图片
    scaled_pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    # 创建并返回居中的pixmap
    return self._create_centered_pixmap(scaled_pixmap, width, height)

  def _create_centered_pixmap(self, scaled_pixmap: QPixmap, target_width: int, target_height: int) -> QPixmap:
    """
    创建一个目标尺寸的透明pixmap，并将缩放后的pixmap居中放置

    Args:
      scaled_pixmap: 缩放后的QPixmap对象
      target_width: 目标宽度
      target_height: 目标高度

    Returns:
      QPixmap: 居中放置的目标尺寸pixmap
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
    创建占位符图片

    Args:
      width: 宽度
      height: 高度
      text: 显示的文本

    Returns:
      QPixmap: 占位符QPixmap对象
    """
    placeholder = QPixmap(width, height)
    placeholder.fill(Qt.lightGray)

    # 添加占位符文字
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
    批量生成所有图片素材包的缩略图

    Args:
      output_dir: 输出目录路径，如果为None则使用默认缓存目录
      file_format: 输出图片格式，默认为'png'
      crop_region: 截取区域，格式为 (left, top, right, bottom)，None表示使用整个图像
      target_size: 期望的缩略图尺寸，格式为 (width, height)，None表示不调整大小
      use_default_sizes: 是否使用默认尺寸策略（背景512x288，立绘288x512（9:16））

    Returns:
      dict[str, str]: 生成的缩略图映射字典，键为素材包ID，值为生成的缩略图文件路径
    """
    # 如果指定了输出目录，使用它
    current_cache_dir = output_dir if output_dir else self.cache_dir

    # 确保输出目录存在
    Path(current_cache_dir).mkdir(parents=True, exist_ok=True)

    # 生成结果字典
    result = {}

    # 遍历所有资源
    for asset_id, _ in self.asset_manager._assets.items():
      try:
        # 获取资源并检查是否为ImagePack类型
        asset = self.asset_manager.get_asset(asset_id)
        if not isinstance(asset, ImagePack):
          continue

        # 根据参数选择生成方式
        if crop_region or target_size or not use_default_sizes or output_dir:
          # 使用指定参数生成缩略图
          thumbnail = self.generate_thumbnail_from_imagepack(
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
        # 捕获单个资源处理过程中的异常，记录并继续处理其他资源
        print(f"Error processing asset {asset_id}: {e}")
        continue

    return result

  def clear_cache(self, clear_memory: bool = True, clear_disk: bool = False):
    """
    清理缩略图缓存

    Args:
      clear_memory: 是否清理内存缓存
      clear_disk: 是否清理磁盘缓存
    """
    if clear_memory:
      self.thumbnail_cache.clear()

    if clear_disk:
      # 清理磁盘缓存
      for filename in os.listdir(self.cache_dir):
        if filename.endswith('_thumbnail.png'):
          try:
            os.remove(os.path.join(self.cache_dir, filename))
          except Exception:
            # 忽略删除错误
            pass

  def get_asset_type_info(self, asset_id: str) -> tuple[bool, bool]:
    """
    获取资产的类型信息

    Args:
      asset_id: 资产ID

    Returns:
      tuple[bool, bool]: (是否为角色资产, 是否为背景资产)
    """
    is_character = False
    is_background = False

    try:
      asset = self.asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        descriptor = ImagePack.get_descriptor_by_id(asset_id)
        if descriptor:
          pack_type = descriptor.get_image_pack_type()
          is_character = (pack_type == ImagePackDescriptor.ImagePackType.CHARACTER)
          is_background = (pack_type == ImagePackDescriptor.ImagePackType.BACKGROUND)
    except Exception:
      pass

    return is_character, is_background

# 创建全局缩略图管理器实例
_thumbnail_manager_instance = None

def get_thumbnail_manager(cache_dir: str = None) -> ThumbnailManager:
  """
  获取缩略图管理器的单例实例

  Args:
    cache_dir: 缩略图缓存目录，如果为None则使用默认目录

  Returns:
    ThumbnailManager: 缩略图管理器实例
  """
  global _thumbnail_manager_instance
  if _thumbnail_manager_instance is None or cache_dir:
    _thumbnail_manager_instance = ThumbnailManager(cache_dir)
  return _thumbnail_manager_instance

# 保留原有函数以保持向后兼容性
def generate_thumbnail_from_imagepack(
  asset_id: str,
  crop_region: tuple[int, int, int, int] | None = None,
  target_size: tuple[int, int] | None = None,
  use_default_sizes: bool = True
) -> PIL.Image.Image | None:
  """
  从打包好的图片素材包中基于第一个差分（composite）生成缩略图（全局函数，向后兼容）

  Args:
    asset_id: 图片素材包的ID
    crop_region: 截取区域，格式为 (left, top, right, bottom)，None表示使用整个图像
    target_size: 期望的缩略图尺寸，格式为 (width, height)，None表示不调整大小
    use_default_sizes: 是否使用默认尺寸策略（背景512x288，立绘288x512（9:16））

  Returns:
    PIL.Image.Image: 生成的缩略图，如果无法生成则返回None
  """
  # 使用单例模式获取ThumbnailManager实例
  manager = get_thumbnail_manager()

  # 调用管理器的相应方法（复用核心逻辑）
  return manager.generate_thumbnail_from_imagepack(asset_id, crop_region, target_size, use_default_sizes)


def get_imagepack_thumbnail_size(asset_id: str) -> tuple[int, int] | None:
  """
  获取图片素材包的原始尺寸

  Args:
    asset_id: 图片素材包的ID

  Returns:
    tuple[int, int]: 图片素材包的尺寸 (width, height)，如果无法获取则返回None
  """
  asset_manager = AssetManager.get_instance()
  asset = asset_manager.get_asset(asset_id)

  if isinstance(asset, ImagePack):
    return (asset.width, asset.height)

  return None


def generate_all_imagepack_thumbnails(
  output_dir: str,
  crop_region: tuple[int, int, int, int] | None = None,
  target_size: tuple[int, int] | None = None,
  file_format: str = 'png',
  use_default_sizes: bool = True
) -> dict[str, str]:
  """
  批量生成所有图片素材包的缩略图到指定目录（全局函数，向后兼容）

  Args:
    output_dir: 输出目录路径
    crop_region: 截取区域，格式为 (left, top, right, bottom)，None表示使用整个图像
    target_size: 期望的缩略图尺寸，格式为 (width, height)，None表示不调整大小
    file_format: 输出图片格式，默认为'png'
    use_default_sizes: 是否使用默认尺寸策略（背景512x288，立绘288x512（9:16））

  Returns:
    dict[str, str]: 生成的缩略图映射字典，键为素材包ID，值为生成的缩略图文件路径
  """
  # 使用新的ThumbnailManager
  manager = get_thumbnail_manager()

  # 直接调用管理器的generate_all_thumbnails方法，完全复用核心逻辑
  return manager.generate_all_thumbnails(
      output_dir=output_dir,
      file_format=file_format,
      crop_region=crop_region,
      target_size=target_size,
      use_default_sizes=use_default_sizes
  )

# 添加新的辅助函数
def get_scaled_pixmap_for_asset(asset_id: str, width: int, height: int) -> QPixmap:
  """
  获取指定资产的缩放后的QPixmap（全局函数，向后兼容）

  Args:
    asset_id: 资产ID
    width: 目标宽度
    height: 目标高度

  Returns:
    QPixmap: 缩放后的QPixmap
  """
  # 获取ThumbnailManager实例
  manager = get_thumbnail_manager()

  # 获取资产类型信息
  is_character, is_background = manager.get_asset_type_info(asset_id)

  # 调用管理器方法获取pixmap
  return manager.get_pixmap_for_asset(asset_id, width, height, is_character, is_background)

def get_asset_thumbnail_path(asset_id: str) -> str | None:
  """
  获取指定资产的缩略图路径，如果不存在则生成（全局函数，向后兼容）

  Args:
    asset_id: 资产ID

  Returns:
    str: 缩略图路径，如果无法生成则返回None
  """
  # 直接调用管理器的方法
  manager = get_thumbnail_manager()
  try:
    # 尝试获取缩略图路径，管理器内部会处理缓存逻辑
    return manager.get_or_generate_thumbnail(asset_id)
  except Exception as e:
    print(f"Error getting thumbnail path for asset {asset_id}: {e}")
    return None

if __name__ == '__main__':
  # 使用新的ThumbnailManager生成所有缩略图
  manager = get_thumbnail_manager('thumbnails')
  manager.generate_all_thumbnails()