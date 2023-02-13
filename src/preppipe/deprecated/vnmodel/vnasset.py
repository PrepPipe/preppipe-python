# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNAsset(Symbol, AssetBase):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNImageAsset(VNAsset):
  _data_operand : OpOperand
  def __init__(self, name: str, loc: Location, data : ImageAssetData, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._data_operand = self._add_operand_with_value("data", data)
  
  @staticmethod
  def getFromFile(path : str, name : str, loc : Location) -> VNImageAsset:
    # get an image asset from file. It is not in any namespace yet
    data = ImageAssetData(loc.context, backing_store_path=path)
    return VNImageAsset(name, loc, data)
  
  @staticmethod
  def getFromData(image : PIL.Image.Image, name : str, loc : Location) -> VNImageAsset:
    data = ImageAssetData(loc.context, data = image)
    return VNImageAsset(name, loc, data)
  
  @property
  def format(self) -> str | None:
    # we can have no formats if the data is from a temporary PIL image
    data : ImageAssetData = self._data_operand.get()
    return data.format
  
  def getImageData(self) -> PIL.Image.Image:
    data : ImageAssetData = self._data_operand.get()
    return data.load()

class VNAudioAsset(VNAsset):
  _data_operand : OpOperand
  def __init__(self, name: str, loc: Location, data : AudioAssetData, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._data_operand = self._add_operand_with_value("data", data)
  
  @staticmethod
  def getFromFile(path : str, name : str, loc : Location) -> VNAudioAsset:
    # get an audio asset from file. It is not in any namespace yet
    data = AudioAssetData(loc.context, backing_store_path=path)
    return VNAudioAsset(name, loc, data)
  
  @staticmethod
  def getFromData(audio : pydub.AudioSegment, name : str, loc : Location) -> VNAudioAsset:
    data = AudioAssetData(loc.context, data = audio)
    return VNAudioAsset(name, loc, data)
  
  @property
  def format(self) -> str | None:
    # we can have no formats if the data is from a temporary audio segment
    data : AudioAssetData = self._data_operand.get()
    return data.format
  
  def getAudioData(self) -> pydub.AudioSegment:
    data : AudioAssetData = self._data_operand.get()
    return data.load()
