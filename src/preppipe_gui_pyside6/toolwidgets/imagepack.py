from ..toolwidgetinterface import *
from PySide6.QtWidgets import *
from preppipe.assets.assetmanager import *
from preppipe.util.imagepack import *

TR_gui_tool_imagepack = TranslationDomain("gui_tool_imagepack")

class ImagePackBackgroundTool(ToolWidgetInterface):
  @classmethod
  def getToolInfo(cls, packid : str | None = None) -> ToolWidgetInfo:
    if packid is None:
      return ToolWidgetInfo(
        idstr="imagepack_background",
        name = ImagePackDocsDumper._tr_heading_background,
      )
    descriptor = ImagePack.get_descriptor_by_id(packid)
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError(f"Unexpected descriptor type {type(descriptor)}")
    return ToolWidgetInfo(
      idstr="imagepack_background",
      name = descriptor.topref,
      data={"packid": packid},
    )

  @classmethod
  def getChildTools(cls, packid : str | None = None) -> list[type[ToolWidgetInterface] | ToolWidgetInfo] | None:
    if packid is not None:
      return None
    result = []
    for descriptor in ImagePack.MANIFEST.values():
      if not isinstance(descriptor, ImagePackDescriptor):
        raise PPInternalError(f"Unexpected descriptor type {type(descriptor)}")
      if descriptor.packtype != ImagePackDescriptor.ImagePackType.BACKGROUND:
        continue
      result.append((ImagePackBackgroundTool, {"packid": descriptor.pack_id}))
    return result
