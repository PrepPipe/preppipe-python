# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import mimetypes
import os, io, gc
import pathlib
import typing
import functools
import tempfile
import enum

import bidict
import PIL.Image
import pydub

class Color:
  """!
  @~english @brief %Color tuple with <r,g,b,a> all in range [0, 255]
  @~chinese @brief <r, g, b, a> 格式的代表颜色的元组。所有项都在 [0, 255] 区间
  """
  r : int = 0
  g : int = 0
  b : int = 0
  a : int = 255
  
  def __init__(self, r : int = 0, g: int = 0, b: int = 0, a: int = 255) -> None:
    self.r = r
    self.g = g
    self.b = b
    self.a = a
    self.validate()
  
  ##
  # @~english @brief Map of predefined color names to values. %Color names can be passed to Color.get()
  # @~chinese @brief 预设颜色到对应值的表。可在调用 Color.get() 时提供颜色名。
  #
  PredefinedColorMap = {
    "transparent": (0,0,0,0),
    "red":   (255,  0,    0,    255),
    "green": (0,    255,  0,    255),
    "blue":  (0,    0,    255,  255),
    "white": (255,  255,  255,  255),
    "black": (0,    0,    0,    255)
  }
  
  def red(self) -> int:
    return self.r
  
  def green(self) -> int:
    return self.g
  
  def blue(self) -> int:
    return self.b
  
  def alpha(self) -> int:
    return self.a
  
  def transparent(self) -> bool:
    return self.a == 0
  
  def validate(self) -> None:
    if self.r < 0 or self.r > 255:
      raise AttributeError("Color.r (" + str(self.r) + ") out of range [0, 255]")
    if self.g < 0 or self.g > 255:
      raise AttributeError("Color.g (" + str(self.g) + ") out of range [0, 255]")
    if self.b < 0 or self.b > 255:
      raise AttributeError("Color.b (" + str(self.b) + ") out of range [0, 255]")
    if self.a < 0 or self.a > 255:
      raise AttributeError("Color.a (" + str(self.a) + ") out of range [0, 255]")
  
  def getString(self) -> str:
    result = "#" + '{:02x}'.format(self.r) + '{:02x}'.format(self.g) + '{:02x}'.format(self.b)
    if self.a != 255:
      result += '{:02x}'.format(self.a)
    return result

  def __str__(self) -> str:
    return self.getString()
  
  @staticmethod
  def get(src: typing.Any):
    """!
    @~english @brief Try to get a color from a value (a string or color tuple)
    @~chinese @brief 用参数(一个字符串或是元组)构造一个颜色值
    @~
    
    <details open><summary>English(en)</summary>
    Returns a Color from one of the following argument:
    <ul>
      <li>str: "#rrggbb", "#rrggbbaa", or any predefined color names from PredefinedColorMap</li>
      <li>tuple: (r,g,b) or (r,g,b,a)
    </ul>
    This function raises AttributeError exception if the argument is not in any of the form above.
    </details>
    
    <details open><summary>中文(zh)</summary>
    用来创建颜色的参数必须是以下任意一种形式:
    <ul>
      <li>str (字符串): "#rrggbb", "#rrggbbaa", 或者任意在 PredefinedColorMap 中的预设颜色名称</li>
      <li>tuple (元组): (r,g,b) or (r,g,b,a)
    </ul>
    如果参数不符合要求，则抛出 AttributeError 异常。
    </details>
    """
    r = 0
    g = 0
    b = 0
    a = 255
    if isinstance(src, str):
      if src.startswith("#"):
        if len(src) >= 7:
          r = int(src[1:3], 16)
          g = int(src[3:5], 16)
          b = int(src[5:7], 16)
        if len(src) == 9:
          a = int(src[7:9], 16)
        elif len(src) != 7:
          raise AttributeError("Not a color: " + src)
      elif src in Color.PredefinedColorMap:
        t = Color.PredefinedColorMap[src]
        r = t[0]
        g = t[1]
        b = t[2]
        a = t[3]
    elif isinstance(src, tuple):
      if len(src) >= 3 and len(src) <= 4:
        r = src[0]
        g = src[1]
        b = src[2]
        if len(src) == 4:
          a = src[3]
      else:
        raise AttributeError("Not a color: " + src)
    else:
      raise AttributeError("Not a color: " + src)
    return Color(r, g, b, a)
  
  def to_tuple(self):
    if self.a == 255:
      return (self.r, self.g, self.b)
    return (self.r, self.g, self.b, self.a)
  

class FileType(enum.Enum):
  """!
  @~english @brief Enum for file type according to usage, mainly used for metadata like debug locations in source files
  @~chinese @brief (基于使用方式的)文件类型的枚举值，用于定位源文件位置等元数据
  """
  
  Unknown = 0
  
  ##
  # @~english @brief plain text, excluding Markdown or HTML
  # @~chinese @brief 纯文本，不包括Markdown或是HTML
  #
  Text = enum.auto() # loc: line, column
  
  Markdown = enum.auto() # loc: line, column, title path 
  HTML = enum.auto() # loc: line, column, elements path
  
  ##
  # @~english @brief any static, single-layer image types
  # @~chinese @brief 任意静态、单层图片类型
  #
  Image = enum.auto()
  """any static, single-layer image types"""
  
  ##
  # @~english @brief static, layered image, basically corresponds to a PSD file
  # @~chinese @brief 静态、多层的图片类型，基本上等同于PSD文件
  # @~
  # 
  # <details open><summary>English(en)</summary>
  # A layered image (at least) contains a list of image layers, from the bottom to top.<br>
  # Each image layer (at least) contains (1) a single static image, and (2) a unique layer name.
  # </details>
  #
  # <details open><summary>中文(zh)</summary>
  # 一个层叠图片(至少)包含一列图层(从底层到顶层)。每个图层(至少)包含(1)一个静态图片，以及(2)一个惟一的图层名。
  # </details>
  #
  LayeredImage = enum.auto()
  """static, layered image, basically corresponds to a PSD file"""
  
  Audio = enum.auto()
  Video = enum.auto()
  
  ##
  # @~english @brief OpenDocument/OfficeOpenXML word processing documents
  # @~chinese @brief OpenDocument/OfficeOpenXML (Word)文档
  #
  Document = enum.auto()
  """OpenDocument/OfficeOpenXML word processing documents"""
  
  ##
  # @~english @brief OpenDocument/OfficeOpenXML presentations
  # @~chinese @brief OpenDocument/OfficeOpenXML (PPT)演示
  #
  Presentation = enum.auto()
  """OpenDocument/OfficeOpenXML presentations"""
  
  ##
  # @~english @brief OpenDocument/OfficeOpenXML spreadsheet
  # @~chinese @brief OpenDocument/OfficeOpenXML (Excel)表格
  #
  Spreadsheet = enum.auto()
  """OpenDocument/OfficeOpenXML spreadsheet"""
  
  @staticmethod
  def get_from_mimetype(mimetype : str):
    special_dict : typing.Dict[str, FileType] = {
      # PSD File
      'image/vnd.adobe.photoshop' : FileType.LayeredImage,
      
      # EPS File
      'application/postscript': FileType.Image,
      
      # OpenDocument files
      'application/vnd.oasis.opendocument.text': FileType.Document,
      'application/vnd.oasis.opendocument.presentation': FileType.Presentation,
      'application/vnd.oasis.opendocument.spreadsheet': FileType.Spreadsheet,
      
      # HTML and markdown
      'text/html' : FileType.HTML,
      'text/markdown' : FileType.Markdown,
      
      # last item
      'application/octet-stream' : FileType.Unknown
    }
    if mimetype in special_dict:
      return special_dict[mimetype]
    if mimetype.startswith('text/'):
      return FileType.Text
    if mimetype.startswith('image/'):
      return FileType.Image
    if mimetype.startswith('audio/'):
      return FileType.Audio
    if mimetype.startswith('video/'):
      return FileType.Video
    return FileType.Unknown

class AssetBase:
  """!
  @~english @brief Base class for all assets (the non-code portion that we don't interpret)
  @~chinese @brief 所有资源(我们不作解读的非代码的部分)的基类
  @~
  
  @todo this class is not finished yet
  
  <details open><summary>English(en)</summary>
  The design of %AssetBase aims the following goals:
  <ul>
    <li> Big assets (like ones in 100MB scale or larger) does not hog memory (especially not indefinitely) unless they are actively used
    <li> For small assets (especially small images < 10KB) that are large in quantity, do not create too many small files, i.e. keep them in memory when possible
    <li> Collaborate with Python garbage collector so that we keep data in memory when possible, and spill data to disk when necessary
  </ul>
  We consider each asset to be (1) a single file content and (2) a Python object in manipulation-ready form, and each %AssetBase deals with the first half.<br>
  %AssetBase will use file-based (on-disk) backing store and in-memory "snapshot" to store the asset data, and %AssetBase will take care of when to spill data to disk and when to cache the data.<br>
  %AssetBase require that derived class can provide a python object in manipulation-ready form given the file data. %AssetBase do not make any assumption on this object in any way.<br>
  <br>
  We consider each %AssetBase (and their derived class) to be immutable. If any modification needs to be done on the asset, you need to:
  <ol>
    <li> Create a new asset with the new data
    <li> Redirect all uses of old asset to the new one
    <li> Erase the old asset
  </ol>
  Because %AssetBase intends to be the base class for all assets in all pipeline stages, we only keep minimal information that can be gathered without actually reading the asset content.<br>
  Currently we only keep a MIME Type to differentiate the format of assets, and the size of the asset.<br>
  We determine the canonical MIME Type of a file from the result of mimetypes.guess_type().<br>
  Derived class can add additional members for metadata if appropriate.<br>
  </details>
  
  <details open><summary>中文(zh)</summary>
  %AssetBase 的设计服务于以下目标：
  <ul>
    <li> 大体积资源 (100MB 规格或更大的那种) 未被使用时不浪费内存(特别是不一直占用内存)
    <li> 小体型、大数量的资源 (特别是<10KB的那种) 不会过多地产生小文件，即方便的话就保存在内存中
    <li> 与Python的垃圾回收机制协同，内存充足则把数据保留在内存中，不足的话才存到硬盘上
  </ul>
  我们把每个资源视作两部分：(1) 一个单独的文件的内容，和 (2) 一个可操作的 Python 对象。%AssetBase 类处理第一部分。<br>
  %AssetBase 将使用基于文件的(即存到硬盘上的)后备存储 (backing store), 以及(驻留内存的)快照 (snapshot) 来存储资源内容。 %AssetBase 会管理何时把数据存到硬盘，以及何时把数据缓存在内存中。<br>
  %AssetBase 要求子类在有文件内容时提供一个可操作的 Python 对象。除此之外，%AssetBase 不对这个对象作任何假设。<br>
  <br>
  每个 %AssetBase (及其子类)都是不可改变的(immutable)。如果需要对资源进行修改，你需要：
  <ol>
    <li> 创建一个拥有新数据的新资源对象
    <li> 将所有对旧资源的引用给导引到新资源
    <li> 去掉旧资源
  </ol>
  由于 %AssetBase 被设计为在所有阶段的所有资源的基类，我们只在这里保留最少的、能够不读取文件内容就能获得的信息。<br>
  目前我们只在此记录资源的 MIME 类型来区分资源的格式，以及资源的大小。<br>
  每种文件的标准的 MIME 类型由 mimetypes.guess_type() 的结果来决定。<br>
  如果合适的话，子类可以添加额外的成员来记录资源的元数据。<br>
  </details>
  """
  
  ##
  # @~english @brief Temporary directory path for backing store
  # @~chinese @brief 后备存储的临时目录
  # @~
  #
  # <details open><summary>English(en)</summary>
  # For each python environment (e.g., a Python interpreter process), we use a single temporary directory for backing store.<br>
  # If an %AssetBase having the backing store inside the temporary directory, we consider the asset to "own" the backing store.<br>
  # Otherwise, we consider the backing store to be a read-only source.<br>
  # </details>
  #
  # <details open><summary>中文(zh)</summary>
  # 我们在每个 Python 执行环境中 (比如一个 Python 解释器进程) 只使用一个临时目录来存放后备存储文件。<br>
  # 如果一个 %AssetBase 的后备存储在这个临时目录中，则我们认为这个资源独占这个后备存储文件。<br>
  # 不然的话，我们认为后备存储是一个只读的源。<br>
  # </details>
  #
  backing_dir : typing.ClassVar[tempfile.TemporaryDirectory] = None
  
  
  _memory_resident_data : bytes
  _backing_store_path : str
  _byte_size : int
  _mimetype : str
  _cache_insert_slot : typing.Any
  
  def __init__(self, mimetype : str, *, snapshot : bytes = None, backing_store_path : str = "") -> None:
    self._memory_resident_data = snapshot
    self._backing_store_path = backing_store_path
    self._byte_size = -1
    self._mimetype = mimetype
    self._cache_insert_slot = None
    if snapshot is not None:
      self._byte_size = len(snapshot)
    if len(backing_store_path) > 0:
      assert os.path.isabs(backing_store_path) and os.path.isfile(backing_store_path)
      if self._byte_size < 0:
        self._byte_size = os.stat(backing_store_path).st_size
  
  def valid(self) -> bool:
    if self._memory_resident_data is not None:
      return True
    if len(self._backing_store_path) > 0 and os.path.isfile(self._backing_store_path):
      return True
    return False
  
  def get_mime_type(self) -> str:
    """!
    @~english @brief get the MIME Type of this asset
    @~chinese @brief 返回这个资源的 MIME 类型
    """
    return self._mimetype
  
  def get_size(self) -> int:
    """!
    @~english @brief get the file size (in bytes) of this asset
    @~chinese @brief 返回这个资源的大小 (以字节为单位)
    """
    return self._byte_size
  
  def _export(self, memory_data : typing.Any, mimetype : str) -> bytes:
    """!
    @~english @brief export the asset object with the given format (must not be the original format)
    @~chinese @brief 将资源对象导出到指定格式 (一定不是原本的格式)
    """
    pass
  
  def _load(self, snapshot : bytes, mimetype : str) -> typing.Any:
    pass
  
  @functools.lru_cache
  def get(self):
    if self._cache_insert_slot is not None:
      return self._cache_insert_slot
    if self._memory_resident_data is not None:
      return self._load(self._memory_resident_data, self._mimetype)
    if len(self._backing_store_path) > 0 and os.path.isfile(self._backing_store_path):
      self._est_size = os.stat(self._backing_store_path).st_size
      with open(self._backing_store_path, "rb") as f:
        snapshot = f.read()
      return self._load(snapshot, self._mimetype)
    raise RuntimeError("Trying to get() from invalid asset object")
  
  def get_snapshot(self) -> bytes:
    if self._memory_resident_data is not None:
      return self._memory_resident_data
    if len(self._backing_store_path) > 0 and os.path.isfile(self._backing_store_path):
      self._est_size = os.stat(self._backing_store_path).st_size
      with open(self._backing_store_path, "rb") as f:
        snapshot = f.read()
      return snapshot
    raise RuntimeError("Trying to get_snapshot() from invalid asset object")
  
  def cache_data(self, memory_data : typing.Any):
    # insert the memory_data to get() cache result
    self._cache_insert_slot = memory_data
    result = self.get()
    assert result == memory_data
    self._cache_insert_slot = None
    
  # support for using objects as key in dictionary / in set
  def __hash__(self) -> int:
    return hash(id(self))
  def __eq__(self, __o: object) -> bool:
    return __o is self
  
  @staticmethod
  def _gchook(phase, info):
    """!
    @todo use a more sophisticated way of managing cache:
    1. do nothing when the garbage collector can free enough memory
    2. clear cache and spill in-mem storage to disk only when the garbage collector cannot free enough memory
    3. avoid spilling for in-mem storage if the reference count (available with sys.getrefcount()-1) too high (e.g., >1)
    """
    #AssetBase.get.cache_clear()
    pass
  
  @staticmethod
  def _get_tmp_backing_dir() -> tempfile.TemporaryDirectory:
    if AssetBase.backing_dir is None:
      AssetBase.backing_dir = tempfile.TemporaryDirectory(prefix="preppipe_asset")
    return AssetBase.backing_dir
  
  @staticmethod
  def _get_tmp_backing_path(suffix: str = "") -> str:
    backing_dir = AssetBase._get_tmp_backing_dir()
    fd, path = tempfile.mkstemp(dir=backing_dir,suffix=suffix)
    os.close(fd)
    return path
  
  @staticmethod
  def secure_overwrite(exportpath: str, write_callback: typing.Callable, open_mode : str = 'wb'):
    tmpfilepath = exportpath + ".tmp"
    parent_path = pathlib.Path(tmpfilepath).parent
    os.makedirs(parent_path, exist_ok=True)
    isOldExist = os.path.isfile(exportpath)
    with open(tmpfilepath, open_mode) as f:
      write_callback(f)
    if isOldExist:
      old_name = exportpath + ".old"
      os.rename(exportpath, old_name)
      os.rename(tmpfilepath, exportpath)
      os.remove(old_name)
    else:
      os.rename(tmpfilepath, exportpath)

gc.callbacks.append(AssetBase._gchook)

class BytesAsset(AssetBase):
  """!
  @~english @brief Base class for all unknown assets. The data is just a bytes array.
  @~chinese @brief 所有未知资源的基类。数据就是一个 bytes 数组。
  """
  def __init__(self, mimetype : str, *, snapshot: bytes = None, backing_store_path: str = "") -> None:
      super().__init__(mimetype, snapshot = snapshot, backing_store_path = backing_store_path)
  
  def get(self) -> bytes:
    return super().get()
  
  def _export(self, memory_data : typing.Any, mimetype : str) -> bytes:
    return memory_data
  
  def _load(self, snapshot : bytes, mimetype : str) -> typing.Any:
    return snapshot
  
  @staticmethod
  def create(src):
    if isinstance(src, bytes):
      return BytesAsset(snapshot=src)
    if isinstance(src, str):
      abs_path = os.path.abspath(src)
      if os.path.isfile(abs_path):
        return BytesAsset(backing_store_path=abs_path)
    raise RuntimeError("not an acceptable data: "+ str(src))

class AudioAsset(AssetBase):
  """!
  @~english @brief Base class for all audio assets
  @~chinese @brief 音频资源的基类
  @~
  
  <details open><summary>English(en)</summary>
  All audio assets use pydub.AudioSegment for manipulation-ready form.<br>
  This class takes care of import/export and format handling.<br>
  </details>
  
  <details open><summary>中文(zh)</summary>
  所有的音频资源都以 pydub.AudioSegment 表示，方便进行处理。<br>
  这个类提供导入、导出，以及文件格式的处理。<br>
  </details>
  """
  
  ##
  # @~english @brief Audio types whose MIME Type is exactly audio/xxx where xxx is file name extension
  # @~chinese @brief 所有 MIME 类型正好是 audio/xxx (xxx 是文件后缀名)的音频类型
  # 
  _mime_type_suffix_identity_set : typing.ClassVar[typing.Set[str]] = {
    "wav", "aac", "ogg", "m4a", "aiff", "flac"
  }
  
  ##
  # @~english @brief For audio types with different MIME subtype and file name extension, this bidict maps from MIME subtype to extension
  # @~chinese @brief 所有 MIME 子类型与文件后缀名不符的音频类型在这个 bidict 中可由 MIME 子类型转换为后缀名
  # 
  _mime_type_suffix_transform_dict : typing.ClassVar[bidict.bidict[str, str]] = {
    "mpeg" : "mp3"
  }
  
  @staticmethod
  def get_format_from_mimetype(mimetype : str) -> str:
    """!
    @~english @brief Convert a MIME Type string into pydub's \a format, which is also the file extension 
    @~chinese @brief 将 MIME 类型转化为 pydub 使用的 \a 格式，同时也是文件后缀名
    @~
    """
    parts = mimetype.split('/')
    assert len(parts) == 2 and parts[0] == 'audio'
    subtype = parts[1]
    if subtype in AudioAsset._mime_type_suffix_identity_set:
      return subtype
    if subtype in AudioAsset._mime_type_suffix_transform_dict:
      return AudioAsset._mime_type_suffix_transform_dict[subtype]
    raise NotImplementedError("Unrecognized audio mimetype "+ mimetype)
  
  @staticmethod
  def is_mimetype_supported(mimetype : str) -> bool:
    """!
    @~english @brief Check if a MIME Type is recognized
    @~chinese @brief 检查一个 MIME 类型是否可被识别
    @~
    """
    return (AudioAsset.get_format_from_mimetype(mimetype) is not None)
  
  @staticmethod
  def get_mimetype_from_format(format : str):
    format = format.lower()
    if format in AudioAsset._mime_type_suffix_identity_set:
      return "audio/" + format
    if format in AudioAsset._mime_type_suffix_transform_dict.inverse:
      return "audio/" + AudioAsset._mime_type_suffix_transform_dict.inverse[format]
    raise NotImplementedError("Unrecognized audio format "+ format)
  
  def __init__(self, mimetype : str, *, snapshot : bytes = None, backing_store_path : str = "") -> None:
    super().__init__(mimetype, snapshot=snapshot, backing_store_path=backing_store_path)
  
  def get(self) -> pydub.AudioSegment:
    return super().get()
  
  def _export(self, memory_data: pydub.AudioSegment, mimetype: str) -> bytes:
    buffer = io.BytesIO()
    memory_data.export(buffer, format = self.get_format_from_mimetype(mimetype))
    return buffer.read()
  
  def _load(self, snapshot : bytes, mimetype : str) -> typing.Any:
    buffer = io.BytesIO(snapshot)
    format = self.get_format_from_mimetype(mimetype)
    return pydub.AudioSegment.from_file(buffer, format=format)
  
  @staticmethod
  def create_from_record(mimetype : str, backing_store_path : str):
    return AudioAsset(mimetype, snapshot=None, backing_store_path = backing_store_path)
  
  @staticmethod
  def create_from_storage(backing_store_path : str):
    abs_path = os.path.abspath(backing_store_path)
    assert(os.path.isfile(abs_path))
    # get format from extension
    mimetype, encoding = mimetypes.guess_type(abs_path)
    if encoding is not None:
      raise RuntimeError("Unsupported encoding: " + encoding + " for file " + abs_path)
    assert AudioAsset.is_mimetype_supported(mimetype)
    return AudioAsset(mimetype, backing_store_path=abs_path)
  
  @staticmethod
  def create_from_bytes(mimetype : str, snapshot : bytes = None):
    return AudioAsset(mimetype, snapshot=snapshot)
    # buffer = io.BytesIO(snapshot)
    # audio_seg = pydub.AudioSegment.from_file(buffer, format=format)
    # obj = AudioAsset(format, audio_seg.duration_seconds, snapshot, "")
    # obj.cache_data(audio_seg)
    # return obj

class ImageAsset(AssetBase):
  """!
  @~english @brief Base class for all static, single-layer assets
  @~chinese @brief 所有静态、单图层图片资源的基类
  @~
  
  @todo add support for SVG
  
  <details open><summary>English(en)</summary>
  All image assets use PIL.Image for manipulation-ready form.<br>
  This class takes care of import/export and format handling.<br>
  </details>
  
  <details open><summary>中文(zh)</summary>
  所有的图片资源都以 PIL.Image 表示，方便进行处理。<br>
  这个类提供导入、导出，以及文件格式的处理。<br>
  </details>
  """
  
  ##
  # @~english @brief Image types whose MIME Type is exactly image/xxx where xxx is file name extension
  # @~chinese @brief 所有 MIME 类型正好是 image/xxx (xxx 是文件后缀名)的图片类型
  # 
  _mime_type_suffix_identity_set : typing.ClassVar[typing.Set[str]] = {
    "png", "bmp", "tiff", "dib", "gif", "pcx", "xbm"
  }
  
  ##
  # @~english @brief For image types with different MIME subtype and file name extension, this bidict maps from MIME subtype to extension
  # @~chinese @brief 所有 MIME 子类型与文件后缀名不符的图片类型在这个 bidict 中可由 MIME 子类型转换为后缀名
  # 
  _mime_type_suffix_transform_dict : typing.ClassVar[bidict.bidict[str, str]] = {
    # add SVG back after their support is ready
    # "svg+xml": "svg",
    "jepg": "jpg",
    "vnd-ms.dds": "dds",
    "vnd.microsoft.icon": "ico",
    "x-portable-pixmap": "ppm"
  }
  
  ##
  # @~english @brief For image types with MIME type not starting with "image", this bidict maps from full MIME type to extension
  # @~chinese @brief 所有 MIME 类型不以"image"开头的图片类型在这个 bidict 中可由完整的 MIME 类型转换为后缀名
  #
  _mime_type_full_dict : typing.ClassVar[bidict.bidict[str, str]] = {
    "application/postscript" : "eps"
  }
  
  @staticmethod
  def get_format_from_mimetype(mimetype : str) -> str:
    """!
    @~english @brief Convert a MIME Type string into pydub's \a format, which is also the file extension 
    @~chinese @brief 将 MIME 类型转化为 pydub 使用的 \a 格式，同时也是文件后缀名
    @~
    """
    parts = mimetype.split('/')
    assert len(parts) == 2
    subtype = parts[1]
    if parts[0] == 'image':
      if subtype in ImageAsset._mime_type_suffix_identity_set:
        return subtype
      if subtype in ImageAsset._mime_type_suffix_transform_dict:
        return ImageAsset._mime_type_suffix_transform_dict[subtype]
    elif mimetype in ImageAsset._mime_type_full_dict:
      return ImageAsset._mime_type_full_dict[mimetype]
    raise NotImplementedError("Unrecognized image mimetype "+ mimetype)
  
  @staticmethod
  def is_mimetype_supported(mimetype : str) -> bool:
    """!
    @~english @brief Check if a MIME Type is recognized
    @~chinese @brief 检查一个 MIME 类型是否可被识别
    @~
    """
    return (ImageAsset.get_format_from_mimetype(mimetype) is not None)
  
  @staticmethod
  def get_mimetype_from_format(format : str):
    format = format.lower()
    if format in ImageAsset._mime_type_suffix_identity_set:
      return "image/" + format
    if format in ImageAsset._mime_type_suffix_transform_dict.inverse:
      return "image/" + ImageAsset._mime_type_suffix_transform_dict.inverse[format]
    if format in ImageAsset._mime_type_full_dict.inverse:
      return ImageAsset._mime_type_full_dict.inverse[format]
    raise NotImplementedError("Unrecognized image format "+ format)
  
  def __init__(self, mimetype : str, *, snapshot : bytes = None, backing_store_path : str = "") -> None:
    super().__init__(mimetype, snapshot=snapshot, backing_store_path=backing_store_path)
  
  def get(self) -> PIL.Image:
    return super().get()
  
  def _export(self, memory_data : PIL.Image, mimetype : str) -> bytes:
    buffer = io.BytesIO()
    memory_data.save(buffer, format = self.get_format_from_mimetype(mimetype))
    return buffer.read()
  
  def _load(self, snapshot : bytes, mimetype : str) -> typing.Any:
    buffer = io.BytesIO(snapshot)
    return PIL.Image.open(buffer, format = self.get_format_from_mimetype(mimetype))
  
  
class TextAttribute(enum.Enum):
  # we only define TextAttribute without TextFragment because VNModel and InputModel permits different text fields
  # text attributes without associated data
  Bold = enum.auto()
  Italic = enum.auto()
  
  # text attributes with data
  Hierarchy = enum.auto() # data: int representing the "level" of text; 0: normal text; 1: title; 2: Header1; 3: Header2; ...
  Size = enum.auto() # data: int representing size change; 0 is no change, + means increase size, - means decrease size; see preppipe.util.FontSizeConverter for more details

  TextColor = enum.auto() # data: foreground color
  BackgroundColor = enum.auto() # data: background color (highlight color)
  FontConstraint = enum.auto() # RESERVED: we currently do not handle font families or font language tag. we will try to address this later on


class IRTypeObject:
  def __init__(self) -> None:
    super().__init__()
  
  def __str__(self) -> str:
    return type(self).__name__
  
class IRAttribute:
  def __init__(self) -> None:
    super().__init__()
  
  def __str__(self) -> str:
    return type(self).__name__
  
class IRValue:
  # may or may not be an SSA
  _attributes : typing.Dict[str, IRAttribute]
  
  def __init__(self) -> None:
    super().__init__()
    
  # support for using VNValue as key in dictionary / in set
  # no need to override in derived classes
  def __hash__(self) -> int:
    return hash(id(self))
  
  def __eq__(self, __o: object) -> bool:
    return __o is self
  
  def to_string(self, indent = 0) -> str:
    return type(self).__name__
  
  def __str__(self) -> str:
    return self.to_string(0)
  
  def get_type_object(self) -> IRTypeObject:
    raise NotImplementedError("IRValue not implementing get_type_object()!")

class IRBlock:
  _name : str
  _ops : typing.List[typing.Any]
  
  def __init__(self, name : str) -> None:
    # name should not have block prefix (something like '^')
    self._name = name
    self._ops = []
  
  @property
  def name(self):
    return self._name
  
  @name.setter
  def name(self, new_name : str):
    self._name = new_name

  def to_string(self, indent = 0) -> str:
    result = self.name + ":\n"
    for op in self._ops:
      result += "  "*(indent+1) + op.to_string(indent+1)+ "\n"
    return result
  
  def __str__(self) -> str:
    return self.to_string(0)
  
class IROp:
  _name : str
  _regions : typing.Dict[str, typing.List[IRBlock]]
  
  def to_string(self, indent = 0) -> str:
    result = self.name + ":\n"
    for region, blocks in self._regions.items():
      result += "  "*(indent+1) + region + ":\n"
      for b in blocks:
        result += "  "*(indent+2) + b.to_string(indent+2)
    return result
  
  def __str__(self) -> str:
    return self.to_string(0)

class MessageImportance(enum.Enum):
  Error = enum.auto()
  CriticalWarning = enum.auto()
  Warning = enum.auto()
  Info = enum.auto()

class MessageHandler:
  _instance = None
  
  @staticmethod
  def install_message_handler(handler):
    # subclass MessageHandler and call this function to install the handler
    assert isinstance(handler, MessageHandler)
    MessageHandler._instance = handler
  
  def message(self, importance : MessageImportance, msg : str, file : str = "", location: str = ""):
    locstring = ""
    if len(file) > 0 and len(location) > 0:
      locstring = file + ": " + location
    elif len(file) > 0:
      locstring = file
    elif len(location) > 0:
      locstring = location
    
    if len(locstring) > 0:
      locstring = locstring + ": "
    
    print("[{imp}] {loc}: {msg}".format(imp=str(importance), loc=locstring, msg=msg))
  
  @staticmethod
  def get():
    if MessageHandler._instance is None:
      MessageHandler._instance = MessageHandler()
    return MessageHandler._instance
  
  @staticmethod
  def info(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.Info, msg, file, location)
  
  @staticmethod
  def warning(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.Warning, msg, file, location)
  
  @staticmethod
  def critical_warning(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.CriticalWarning, msg, file, location)
  
  @staticmethod
  def error(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.Error, msg, file, location)
  