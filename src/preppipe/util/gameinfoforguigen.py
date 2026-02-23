# SPDX-FileCopyrightText: 2026 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件定义了所有(1) GUI 生成功能可能需要，(2)可以从剧本（主管线）中获取的信息
# 主管线在运行时会生成这里定义的信息并将其保存到一个 json 文件中，后续 GUI 生成功能会读取这个文件
# 当用户不使用语涵编译器主管线时，也可以提供替代的 json 提供同样信息来使用 GUI 生成功能

import dataclasses
import enum
import json
from pathlib import Path
from ..language import *

@dataclasses.dataclass
class GameInfoTranslatableString:
  # 替代内部使用的 Translatable 用于输入输出
  # 如果是 dict 的话，语言目前应该只有 en, zh_cn, zh_hk
  data : str | dict[str, str]

  def get(self) -> str:
    if isinstance(self.data, str):
      return self.data
    for lang in Translatable.PREFERRED_LANG:
      if lang in self.data:
        return self.data[lang]
    assert "en" in self.data
    return self.data["en"]

  def __str__(self) -> str:
    return self.get()
  def get_json_repr(self) -> str | dict[str, str]:
    return self.data


class GalleryImageEntryType(enum.Enum):
  # 保存到 json 时，内容应是小写的字符串
  CG = enum.auto()  # CG，一般包含角色形象等
  BACKGROUND = enum.auto()  # 纯背景，没有角色


@dataclasses.dataclass
class GalleryImageEntryInfo:
  ref : list[str]  # 如果有多个则表示是一组图片，以第一张作封面
  kind : GalleryImageEntryType


@dataclasses.dataclass
class GalleryMusicEntryInfo:
  ref : str
  name : GameInfoTranslatableString


@dataclasses.dataclass
class GameInfoForGUIGen:
  gametitle : GameInfoTranslatableString

  # CG、背景图片的列表
  gallery_image_list : list[GalleryImageEntryInfo] = dataclasses.field(default_factory=list)

  # 背景音乐列表
  gallery_music_list : list[GalleryMusicEntryInfo] = dataclasses.field(default_factory=list)

  def get_json_repr(self) -> dict:
    return {
      'gametitle': self.gametitle.get_json_repr(),
      'gallery_image_list': [
        {'ref': e.ref, 'kind': e.kind.name.lower()}
        for e in self.gallery_image_list
      ],
      'gallery_music_list': [
        {'ref': e.ref, 'name': e.name.get_json_repr()}
        for e in self.gallery_music_list
      ],
    }

  @staticmethod
  def from_json_repr(d : dict) -> GameInfoForGUIGen:
    kind_map = {e.name.lower(): e for e in GalleryImageEntryType}
    return GameInfoForGUIGen(
      gametitle=GameInfoTranslatableString(data=d['gametitle']),
      gallery_image_list=[
        GalleryImageEntryInfo(ref=e['ref'], kind=kind_map[e['kind'].lower()])
        for e in d.get('gallery_image_list', [])
      ],
      gallery_music_list=[
        GalleryMusicEntryInfo(
          ref=e['ref'],
          name=GameInfoTranslatableString(data=e['name']),
        )
        for e in d.get('gallery_music_list', [])
      ],
    )
  def get_json_str(self) -> str:
    return json.dumps(self.get_json_repr(), ensure_ascii=False, indent=2)
  @staticmethod
  def from_json_str(s : str) -> GameInfoForGUIGen:
    return GameInfoForGUIGen.from_json_repr(json.loads(s))

  def save_json(self, path : str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(self.get_json_str(), encoding='utf-8')

  @staticmethod
  def load_json(path : str | Path) -> GameInfoForGUIGen:
    return GameInfoForGUIGen.from_json_str(Path(path).read_text(encoding='utf-8'))
