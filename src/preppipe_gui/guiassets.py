# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import typing
import PIL
import PIL.Image
import preppipe
import preppipe.assets
from preppipe.assets.assetmanager import AssetManager

class GUIAssetLoader:
  GUI_ASSET_NAME : typing.ClassVar[str] = 'gui_assets'
  asset_rootpath : typing.ClassVar[typing.Optional[str]] = None

  @staticmethod
  def get_asset_rootpath() -> str | None:
    if GUIAssetLoader.asset_rootpath is None:
      inst = AssetManager.get_instance()
      if assets := inst.get_asset(GUIAssetLoader.GUI_ASSET_NAME):
        GUIAssetLoader.asset_rootpath = assets.path
    return GUIAssetLoader.asset_rootpath

  @staticmethod
  def try_get_asset_path(relpath : str) -> str | None:
    if asset_path := GUIAssetLoader.get_asset_rootpath():
      path = os.path.join(asset_path, relpath)
      if os.path.exists(path):
        return path
    return None

  @staticmethod
  def try_get_image_asset(relpath : str) -> PIL.Image.Image | None:
    if asset_path := GUIAssetLoader.try_get_asset_path(relpath=relpath):
      return PIL.Image.open(asset_path)
    return None
