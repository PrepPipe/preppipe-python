# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import PIL.Image
import os
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack


def generate_thumbnail_from_imagepack(
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
  # 获取AssetManager实例并尝试获取图片素材包
  asset_manager = AssetManager.get_instance()
  asset = asset_manager.get_asset(asset_id)

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
        final_target_size = (512, 288)
        # 不应用特殊裁剪，使用提供的crop_region或全图
        if crop_region is not None:
          # 直接调用crop，PIL会处理范围检查
          image = image.crop(crop_region)
        # 调整大小
        image = image.resize(final_target_size, resample=PIL.Image.Resampling.LANCZOS)

      elif pack_type == descriptor.ImagePackType.CHARACTER:
        # 立绘：使用bbox信息确定面部位置，缩放到288x512（9:16）
        final_target_size = (288, 512)

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

  except Exception:
      # 捕获所有异常，确保函数不会因为图像处理错误而崩溃
      return None


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
  批量生成所有图片素材包的缩略图到指定目录

  Args:
    output_dir: 输出目录路径
    crop_region: 截取区域，格式为 (left, top, right, bottom)，None表示使用整个图像
    target_size: 期望的缩略图尺寸，格式为 (width, height)，None表示不调整大小
    file_format: 输出图片格式，默认为'png'
    use_default_sizes: 是否使用默认尺寸策略（背景512x288，立绘288x512（9:16））

  Returns:
    dict[str, str]: 生成的缩略图映射字典，键为素材包ID，值为生成的缩略图文件路径
  """
  # 确保输出目录存在
  if not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)

  # 获取AssetManager实例
  asset_manager = AssetManager.get_instance()

  # 生成结果字典
  result = {}

  # 遍历所有资源
  for asset_id, asset_info in asset_manager._assets.items():
    try:
      # 获取资源并检查是否为ImagePack类型
      asset = asset_manager.get_asset(asset_id)
      if not isinstance(asset, ImagePack):
        continue

      # 生成缩略图
      thumbnail = generate_thumbnail_from_imagepack(asset_id, crop_region, target_size, use_default_sizes)
      if thumbnail is not None:
        # 保存缩略图到文件
        filename = f"{asset_id}_thumbnail.{file_format.lower()}"
        filepath = os.path.join(output_dir, filename)
        thumbnail.save(filepath)
        result[asset_id] = filepath

    except Exception:
      # 捕获单个资源处理过程中的异常，继续处理其他资源
      continue

  return result

if __name__ == '__main__':
  # 使用默认尺寸策略生成所有缩略图
  generate_all_imagepack_thumbnails('thumbnails', use_default_sizes=True)