#!/usr/bin/env python3

import os
import io
import pathlib
import typing
import PIL.Image
import pydub
import pathlib
import enum
from enum import Enum
import preppipe.commontypes

# IR design requirement:
# 1. all control and dataflow dependence must be available in the "main" part, without involving attributes
# 2. options that can affect VN gameplay but not content delivery (e.g., transitions like fade/dissolve/...) are attributes
# 3. Interfacing with the rest of pipeline:
#     - Backends can choose not to implement all functionalities in the IR. Some features are just impossible to implement.
#     - Frontends can choose not to use all functionalities here.
#     - IR transform / analysis must support all functionalities, including attributes. These code are expected to be part of preppipe and maintained in-tree.

class VNValueType(Enum):
  Void = 0 # reserved
  
  # asset types
  Text = 1 # rich text; can have colors, styles, etc
  Image = 2
  Audio = 3
  Video = 4
  Screen = 5 # blackbox displayable
  
  # control flow target types
  Label = 6 # local control transfer target
  Function = 7 # "global" control transfer target
  
  # data types
  Integer = 8
  String = 9 # plain text; just a string in programming language context

class VNSourceLoc:
  """VNSourceLoc encodes the source location of any VNValue
  
  All source locations are at least precise to files
  """
  
  file : str = ""
  filetype: preppipe.commontypes.FileType
  
  def __init__(self, src_file : str, src_filetype : preppipe.commontypes.FileType) -> None:
    self.file = src_file
    self.filetype = src_filetype

# for all text position: all lines and columns start at 1; 0 is an invalid value

class VNSourceLoc_TextPosition(VNSourceLoc):
  """(Point) source location for Text and Document files"""

  line : int = 0
  column : int = 0
  
  def __init__(self, src_file : str, src_filetype : preppipe.commontypes.FileType, src_line : int, src_column: int) -> None:
    super().__init__(src_file, src_filetype)
    self.line = src_line
    self.column = src_column

class VNSourceLoc_TextRange(VNSourceLoc):
  """(Range) source location for Text and Document files. Both ends are closed interval (i.e., [start, end])"""
  start_line : int = 0
  start_column : int = 0
  end_line: int = 0
  end_column : int = 0
  
  def __init__(self, src_file : str, src_filetype : preppipe.commontypes.FileType, start_line : int, start_column: int, end_line : int, end_column : int) -> None:
    super().__init__(src_file, src_filetype)
    self.start_line = start_line
    self.start_column = start_column
    self.end_line = end_line
    self.end_column = end_column

class VNValue:
  """VNValue is (almost) the common base class of everything in VNModel. It resembles llvm::User
  
  This class does the following:
  1. maintain the use-def chain
  2. keep the metadata (including VNSourceLoc)
  
  Note that unlike llvm IR, we distinguish "whether some thing is const or not" with runtime property instead of types.
  This should reduce number of types we need to handle when we don't care whether the value is const or not.
  
  In VNModel, something is constant means "given the configuration settings (language, resolution, etc), the value can be determined at compile time"
  Which means constants can depend on configuration inputs
  """
  name : str = "" # name of the value
  value_type : VNValueType # type of the value
  
  srcloc : VNSourceLoc = None # source location of this value
  metadata : typing.Dict[str, object] = {} # should be dict of str -> VNAttribute
  
  use_list :    typing.List[object] = [] # should be list of VNValues
  md_use_list : typing.List[object] = [] # should be list of VNAttribute
  
  def __init__(self, ty : VNValueType) -> None:
    self.name = ""
    self.value_type = ty
    self.srcloc = None
    self.metadata = {}
    self.use_list = []
    self.md_use_list = []
  
  def set_source_location(self, source_location : VNSourceLoc):
    self.srcloc = source_location
  
  def set_name(self, name : str):
    self.name = name
  
  def get_name(self) -> str:
    return self.name
  
  def has_name(self) -> bool:
    return len(self.name) > 0
  
  def is_constant(self):
    return False

  def get_type(self) -> VNValueType:
    return self.value_type

class VNAttribute(VNValue):
  """VNAttribute is the base class of (doppable) attributes that can be attached to anything in IR"""
  
  # static variable for attribute name in VNValue metadata dict
  attr_name : typing.ClassVar[str] = ""
  
  def __init__(self, ty : VNValueType = VNValueType.Void) -> None:
    super().__init__(ty)
  
  def is_constant(self):
    pass

class VNLanguageDependentValue(VNValue):
  """Base class for any VNValue that can have different actual data in different languages"""
  
  def __init__(self, ty : VNValueType):
    super().__init__(ty)

### classes for text data

class VNTextAttribute(Enum):
  # text attributes without associated data
  Bold = 0
  Italic = 1
  
  # text attributes with data
  Size = 2 # data: int representing size change; 0 is no change, + means increase size, - means decrease size
  TextColor = 3 # data: foreground color
  BackgroundColor = 4 # data: background color (highlight color)
  RubyText = 5 # data: string that should be displayed above the text
  KeywordReference = 6 # This fragment references a keyword. data: reference to keyword entry

class VNTextFragment(VNValue):
  """text element with the same appearance. lanugage dependence should be handled by IR tree parents.
  This can be a variable reference or a literal, for example
  """
  attributes : typing.Dict[VNTextAttribute, typing.Any] = {}
  
  def __init__(self, attributes : typing.Dict[VNTextAttribute, typing.Any] = {}) -> None:
    super().__init__(VNValueType.Text)
    self.attributes = attributes
  
  def is_constant(self):
    pass

class VNTextLiteralFragment(VNTextFragment):
  """literal text element"""
  
  text : str = ""
  attributes : typing.Dict[VNTextAttribute, typing.Any] = {}
  
  def __init__(self, text : str = "", attributes : typing.Dict[VNTextAttribute, typing.Any] = {}) -> None:
    super().__init__(attributes)
    self.text = text
    self.attributes = attributes
  
  def is_constant(self):
    return True
  
  def get_text(self) -> str:
    return self.text
  
  def get_attributes(self) -> typing.Dict[VNTextAttribute, typing.Any]:
    return self.attributes

class VNTextBlock(VNLanguageDependentValue):
  """Class that represent a block of text, possibly with different data for different languages and with variable references"""
  
  fragmentMap : typing.Dict[str, typing.List[VNTextFragment]] = {}
  
  def __init__(self, text: typing.Any):
    super().__init__(VNValueType.Text)
    if isinstance(text, dict):
      for k in text.keys():
        assert isinstance(k, str)
      self.fragmentMap = text
    elif isinstance(text, VNTextFragment):
      self.fragmentMap = {"": text}
    elif isinstance(text, str):
      self.fragmentMap = {"": VNTextLiteralFragment(text)}
    else:
      raise RuntimeError("Unhandled text type")
    
  def get_fragment_list(self, language : str) -> typing.List[VNTextFragment]:
    return self.fragmentMap[language]

class VNCharacterIdentity(VNValue):
  """Identity of an abstract sayer. Similar to the name operand of Renpy's Character()
  
  We use a dedicated class so that we can attach additional metadata for analysis
  This is considered a global constant. No say command can directly reference sayer identity
  The name of the character identity is recommended to be alphanumeric, but is not mandatory
  """
  
  def __init__(self, name : str) -> None:
    super().__init__(VNValueType.Void)
    self.set_name(name)
  
  

class VNSayerInfo(VNValue):
  """Information of an abstract sayer. Very similar to RenPy's Character()
  
  All information about the sayer are accessible here, including:
    - character sprite image
    - side image
    - "name" field content
    - "name" field location
    - text field location
  The information necessary is highly engine-specific but we try to unify common ones
  
  VNSayerInfo is considered (global) constant; if a say instruction directly reference the sayer info, no sprite will be shown
  If character sprite is desired, use SayerDecl and SayerUpdate
  
  Each sayer have one identity (VNCharacterIdentity) to link the different appearance of the same person together
  Each sayer is like one "version" of the person
  """
  
  # identity: the identity of sayer.
  # Each "sayer" person should have one unique identity, like a name.
  # A single identity (e.g., a person) can map to more than one sayer instance (e.g., the person with cloth A and with cloth B)
  # the VNModel use this to track persons for analysis
  identity : VNCharacterIdentity = None
  
  # what's put in the "name" field in gameplay
  # we always use VNTextBlock even if only the default language is used
  name_text : VNTextBlock = None
  
  # default text style for the text
  # we may want all texts from a sayer to have the same color, for example.
  # the text content in style_text is not important. However, if it is not empty, IR will use its content for demo.
  style_text : VNTextFragment = None
  
  # tags for all "groups" the sayer is in (e.g., male, female, student, teacher, ...)
  # Tags may be time-invariant or not; it is per-sayer, instead of per-identity
  group : typing.List[str] = []
  
  # what character sprite to use for each state (e.g., face expression) of the sayer
  # if the sayer info is referenced directly, character sprite will not be shown
  # use sayer decl and sayer update for using character sprite
  character_sprite_dict = {} # <label> -> VNValue : Image
  
  # side image is usually displayed at the left side of the text box
  # this is per-text and will be shown when sayer info is directly referenced in the say instruction
  # however, the state change can only be done with sayer decl and sayer update, so only the default one will be used
  side_image_dict = {} # <label> -> VNValue : Image
  
  # default state for querying images, etc
  default_state : str = ""
  
  def __init__(self, identity : VNCharacterIdentity = None) -> None:
    super().__init__(VNValueType.Void)
    self.identity = identity
    self.name_text = None
    self.style_text = None
    self.group = []
    self.character_sprite_dict = {}
    self.side_image_dict = {}
    self.default_state = ""
  
  def get_identity(self) -> str :
    return self.identity
  
  def set_identity(self, identity : VNCharacterIdentity) -> None:
    self.identity = identity
  
  def get_name_text(self) -> VNTextBlock:
    return self.name_text
  
  def set_name_text(self, name_text : VNTextBlock) -> None:
    self.name_text = name_text
  
  def get_style_text(self) -> VNTextFragment:
    return self.style_text
  
  def set_style_text(self, style_text: VNTextFragment) -> None:
    self.style_text = style_text
  
  def get_character_sprite(self, state : str) -> VNValue:
    return self.character_sprite_dict.get(state)
  
  def set_character_sprite(self, state : str, sprite : VNValue) -> VNValue:
    self.character_sprite_dict[state] = sprite
    return sprite
  
  def get_side_image(self, state : str) -> VNValue:
    return self.side_image_dict.get(state)
  
  def set_side_image(self, state : str, image : VNValue) -> VNValue:
    self.side_image_dict[state] = image
    return image
  
  def get_default_side_image(self) -> VNValue:
    return self.side_image_dict.get(self.default_state)
  
  def get_default_state(self) -> str:
    return self.default_state

  def set_default_state(self, state : str) -> str:
    self.default_state = state
    return state

### classes for image

# all image type data should contain the following info:
# 1. the size (width, height) of the image, in pixels. Should be included in the image metadata
# 2. (optional) the scale factor, which is either a pair of integers (dividend / divisor) or a float; default to 1.
#   The size should be multiplied with this scale factor when loading/displaying the image.
#   If you want to shrink an image, the scale factor should be < 1. If you want to zoom it, use scale factor > 1.
# 3. The truncation policy. If the Image cannot be scaled to a given aspect ratio, how to deal with that.

class VNAspectRatioAdjustmentPolicy(Enum):
  Distort = 0 # distort the image horizontally or vertically to make it fit
  KeepHeight = 1 # keep the height and possibly truncating the two edges on left and right side
  KeepWidth = 2 # keep the width and possibly truncating the top and bottom part of the image

class VNImageAsset(VNValue):
  """Base image. Images with transparent borders are automatically compressed away (and only the non-empty part is stored)
  
  Reference to this image only needs a reference to this VNImageAsset
  """
  
  # image data that goes to storage
  # may undergo transparent extension before the user is querying the actual data
  base_image : PIL.Image = None
  
  class AutoCropInfo:
    """We are doing auto-crop on the original image.
    
    The original image is cropped from <canvas_size> to the size of base_image
    To reconstruct the original image, after filling the <canvas_size> with <background_color>,
    we need to copy the <base_image> to the canvas so that the top-left corner is at <base_pos> (start at 0)
    """
    # None of these values can be None
    canvas_size : typing.Tuple[int, int] = None # (width, height)
    background_color : preppipe.commontypes.Color = None # background color to fill
    base_pos : typing.Tuple[int, int] = None # (xmin, ymin)
  
  autocrop : AutoCropInfo = None # not none if we are doing autocrop
  
  def __init__(self, image) -> None:
    super().__init__(VNValueType.Image)
    self.base_image = image # should be PIL Image
    self.autocrop = None
  
  def get_image(self):
    """All image-like value should support get_image() that returns the final image without additional transforms"""
    # get the final image
    if self.autocrop is None:
      return self.base_image
    
    image = PIL.Image.new(self.base_image.mode, self.autocrop.canvas_size, self.autocrop.background_color)
    image.paste(self.base_image, self.autocrop.base_pos)
    return image
  
  def get_base_image(self):
    return self.base_image
  
  def get_autocrop_info(self):
    return self.autocrop
  
class VNLayeredImageAsset(VNValue):
  """Layered image that can have multiple variants, in a model similar to RenPy's layeredimage
  
  Each reference to the final image would require a reference AND a list of attributes
  For simplicity, we just use a simplified model that:
  1. there are a bunch of layers, from the bottom to the top
  2. each layer is at most one image, without any transform or effect, etc
  The size of the layered image is determined by the size of the first (bottom) layer. If this is not what you want, add a transparent layer with desired size.
  We rely on letting VNImageAsset able to auto-crop to avoid dealing with layers having different sizes
  Later on we may also support more fancy use on layered images, like treating each layer as a "part" and have a tooltip or click action, etc (for showing block diagram, etc)
  """
  layers : typing.List[typing.Tuple[str, typing.Dict[str, VNImageAsset]]] = [] # layer hierarchy
  layer_option_dict : typing.Dict[str, int] = {} # map from layer options to the layer index (i.e., "wink" -> (index for "eye" layer))
  
  def __init__(self) -> None:
    super().__init__(VNValueType.Image)
    self.layers = []
    self.layer_option_dict = {}
  
  def add_layer(self, layer_name : str, option_dict : typing.Dict[str, VNImageAsset]):
    """Add a new layer to this image asset"""
    for curname, curdict in self.layers.items():
      assert curname != layer_name
    
    layer_tuple = (layer_name, option_dict)
    layer_index = len(self.layers)
    self.layers.append(layer_tuple)
    
    for option in option_dict.keys():
      assert option not in self.layer_option_dict
      self.layer_option_dict[option] = layer_index
  
  def get_image_stack(self, attr_list : typing.List[str]) -> typing.List[VNImageAsset]:
    result = [None] * len(self.layers)
    
    # load the default values
    for layer_index in range(0, len(self.layers)):
      layer_dict = self.layers[layer_index][1]
      if "" in layer_dict:
        result[layer_index] = layer_dict[""]
    
    # override from the arguments
    for option in attr_list:
      layer_index = self.layer_option_dict[option]
      layer_dict = self.layers[layer_index][1]
      result[layer_index] = layer_dict[option]
    
    # drop None image layers
    return list(filter(None, result))

class VNImageReference(VNValue):
  """A (derived) image value that can have crops, etc"""
  # TODO
  pass

### classes for audio
class VNAudioFormat(Enum):
  INVALID = 0
  WAV = enum.auto()
  MP3 = enum.auto()
  AAC = enum.auto()
  OGG = enum.auto()
  M4A = enum.auto()
  AIFF = enum.auto()
  FLAC = enum.auto()
  
  def from_ext(ext : str):
    if ext.startswith('.'):
      ext = ext[1:]
    ext = ext.lower()
    if ext == "wav":
      return VNAudioFormat.WAV
    elif ext == "mp3":
      return VNAudioFormat.MP3
    elif ext == "aac":
      return VNAudioFormat.AAC
    elif ext == "ogg":
      return VNAudioFormat.OGG
    elif ext == "m4a":
      return VNAudioFormat.M4A
    elif ext == "aiff":
      return VNAudioFormat.AIFF
    elif ext == "flac":
      return VNAudioFormat.FLAC
    else:
      raise RuntimeError("Unrecognized audio extension "+ ext)
  
  def to_string(format):
    if format == VNAudioFormat.WAV:
      return "wav"
    if format == VNAudioFormat.MP3:
      return "mp3"
    if format == VNAudioFormat.AAC:
      return "aac"
    if format == VNAudioFormat.OGG:
      return "ogg"
    if format == VNAudioFormat.M4A:
      return "m4a"
    if format == VNAudioFormat.AIFF:
      return "aiff"
    if format == VNAudioFormat.FLAC:
      return "flac"
    raise RuntimeError("Unexpected audio format")

class VNAudioAsset(VNValue):
  """Base audio. We may also transparently drop silenced parts under the hood
  
  (Or may not...)
  """
  audio : pydub.AudioSegment = None
  audio_data : bytes = None
  audio_format : VNAudioFormat = VNAudioFormat.INVALID
  
  
  def __init__(self, audio : typing.Any, format : VNAudioFormat = VNAudioFormat.INVALID) -> None:
    super().__init__(VNValueType.Audio)
    if isinstance(audio, bytes):
      # already loaded data
      assert format != VNAudioFormat.INVALID
      self.audio_format = format
      self.audio_data = audio
    elif isinstance(audio, pydub.AudioSegment):
      # again, already loaded data
      assert format != VNAudioFormat.INVALID
      self.audio_format = format
      self.audio = audio
    elif isinstance(audio, str):
      # we are provided a file name
      basepath, ext = os.path.splitext(audio)
      self.audio_format = VNAudioFormat.from_ext(ext)
      # make sure parent directory exist
      with open(audio, "rb") as f:
        self.audio_data = f.read();
    else:
      raise RuntimeError("Unhandled audio data type")
  
  def get_audio(self) -> pydub.AudioSegment:
    return self.audio
  
  def save(self, basepath_noextension : str, acceptable_formats : typing.List[VNAudioFormat] = []) -> str:
    """Save the audio to the specified path. return the final path with extension.
    
    acceptable_formats should be the list of formats that we can directly save. if it is empty, all formats are considered acceptable.
    """
    # ensure there is no extension
    basepath_noextension = os.path.splitext(basepath_noextension)[0]
    path = ""
    if len(acceptable_formats) == 0 or self.audio_format in acceptable_formats:
      # we can save without conversion
      extension = VNAudioFormat.to_string(self.audio_format)
      path = basepath_noextension + "." + extension
      if self.audio_data is None:
        assert self.audio is not None
        buffer = io.BytesIO()
        self.audio.export(buffer, format = extension)
        self.audio_data = buffer.read()
      assert self.audio_data is not None
      tmppath = path + ".tmp"
      # make sure parent directory exists
      parent_path = pathlib.Path(tmppath).parent
      os.makedirs(parent_path, exist_ok=True)
      with open(tmppath, "wb") as f:
        f.write(self.audio_data)
      os.rename(tmppath, path)
    else:
      chosen_format = VNAudioFormat.to_string(acceptable_formats[0])
      if self.audio is None:
        assert self.audio_data is not None
        buffer = io.BytesIO(self.audio_data)
        self.audio = pydub.AudioSegment.from_file(buffer)
      path = basepath_noextension + "." + chosen_format
      tmppath = path + ".tmp"
      parent_path = pathlib.Path(tmppath).parent
      os.makedirs(parent_path, exist_ok=True)
      with open(tmppath, "wb") as f:
        self.audio.export(tmppath, format = chosen_format)
      os.rename(tmppath, path)
    # done
    return path

### classes for "code"

# We use the same model of "Function -> BasicBlock -> Instruction" from LLVM, now with different semantics:
# "Function" is still called "Function". It is the smallest unit for code reuse and "major" control flow transfer. Nothing below Section has globally visible name.
# "BasicBlock" is still called "BasicBlock". It is the smallest unit for control flow transfer. BasicBlocks end with a terminator instruction, like LLVM.
# "Instruction" is basically the same as instructions from LLVM.

# besides the concepts borrowed from LLVM, there are additional constructs unique to VN:
# Exclusive Contexts (e.g., BGM, Background, etc) are updated with UpdateContext (base class) Instructions; logically treated as writing to global variables
# Non-exclusive elements (e.g., sprite, foreground item, etc) are created with CreateElement and modified with ModifyElement (base class) instructions, and destroyed with DeleteElement instruction.
# Text wait/continue/sprite highlighting ... are implemented as attributes on text instruction
class VNInstruction(VNValue):
  """Base class for all instructions in VNModel"""
  
  def __init__(self, ty : VNValueType) -> None:
    # make sure it has the same signature as VNValue.__init__ to avoid headache when using multiple inheritance
    super().__init__(ty)

  def is_terminator(self) -> bool:
    return False

class VNReturnInst(VNInstruction):
  
  def __init__(self) -> None:
    super().__init__(VNValueType.Void)
  
  def is_terminator(self) -> bool:
    return True

class VNCallInst(VNInstruction):
  """Call a function. We does not support function parameters.
  
  All contexts (foreground / background image, sprites, etc) in the current function context becomes undefined afterwards
  If later code requires use of the context, there will be updateXXX instructions to recover them
  """
  callee_name : str = "" # the name of the function being called
  callee_ref : object # VNFunction
  
  def __init__(self, callee_name : str) -> None:
    super().__init__(VNValueType.Function)
    self.callee_name = callee_name
    self.callee_ref = None
  
  def set_callee(self, callee_ref : object) -> None:
    """Bind the callee ref to a function. Should be called during construction of the VNModel"""
    assert callee_ref.get_name() == self.callee_name
    self.callee_ref = callee_ref
  
  def get_callee_name(self):
    return self.callee_name
  
  def get_callee(self):
    return self.callee_ref

class VNTailCall(VNAttribute):
  """If this attribute is present on a call, the subsequent instructions must be a return
  
  This is a hint that no state saving (for sprites, etc) is required for a call
  """
  pass

class VNDestroy(VNAttribute):
  """This attribute represents that an instruction destroyed a context state without explicitly referencing it in operands (probably a call)"""
  pass

class VNUnreachableInst(VNInstruction):
  """Warn the use if any of the following happens:
  1. An unreachable instruction is actually statically reachable
  2. A basic block without unreachable terminator is found statically unreachable
  """
  def __init__(self) -> None:
    super().__init__(VNValueType.Void)
  
  def is_terminator(self) -> bool:
    return True

class VNExitInst(VNInstruction):
  """Exit this model, possibly with an exit code (default to 0)"""
  
  exit_code : VNValue = None
  
  def __init__(self, exit_code : VNValue = None) -> None:
    super().__init__(VNValueType.Integer)
    self.exit_code = exit_code
  
  def is_terminator(self) -> bool:
    return True

class VNBranchInst(VNInstruction):
  """Conditional and unconditional branch. branch destinations must be basic blocks inside the same function"""

  condition : VNValue = None
  true_successor : object = None # VNBasicBlock
  false_successor : object = None # VNBasicBlock

  def __init__(self, *, unconditional_successor = None, condition = None, true_successor = None, false_successor = None) -> None:
    """Please specify one of the set of arguments:
    
    For an unconditional branch:
      unconditional_successor: the successor basic block
    
    For a conditional branch:
      condition: the branch condition
      true_successor: the successor basic block if condition is true
      false_successor: the successor basic block if condition is false
    """
    super().__init__(VNValueType.Void)
    if unconditional_successor is not None:
      assert condition is None
      assert true_successor is None
      assert false_successor is None
      self.condition = None
      self.true_successor = unconditional_successor
      self.false_successor = unconditional_successor
    else:
      assert condition is not None
      assert true_successor is not None
      assert false_successor is not None
      self.condition = condition
      self.true_successor = true_successor
      self.false_successor = false_successor
  
  def is_terminator(self) -> bool:
    return True

class VNSayerDeclInstr(VNInstruction):
  """Declares a new sayer, most importantly it can create the sprite
  
  If we want to (1) have a character sprite, or (2) use more than default state for a sayer,
  then we need to use sayer decl and sayer update
  
  If we have a character sprite, we disable the side image by default, otherwise the side image will be used if available. To override this, add an VNSayerSideImageUse attribute
  """
  
  sayer_base : VNSayerInfo = None # the constant sayer info
  
  current_state : str = ""
  
  def __init__(self, sayer_base : VNSayerInfo) -> None:
    super().__init__(VNValueType.Void)
    self.sayer_base = sayer_base
    current_state = sayer_base.get_default_state()
  
  def get_sayer_info(self):
    return self.sayer_base
  
  def set_sayer_state(self, state : str) -> None:
    self.current_state = state
  
  def get_sayer_state(self) -> str :
    return self.current_state
  

class VNSayerSideImageUse(VNAttribute):
  """Specify whether the side image should be used, if available."""
  
  attr_name : typing.ClassVar[str] = "SideImageUse"
  
  enable : bool = True
  
  def __init__(self, enable : bool = True):
    self.enable = enable
  
  def get_enabled(self) -> bool:
    return self.enable

class VNSayerUpdateInstr(VNInstruction):
  """Modify an existing sayer, including hiding the sprite / "destructing" the sayer"""
  
  sayer_base : VNSayerInfo = None # the constant sayer info
  
  sayer_last : object = None # VNSayerDeclInstr, VNSayerUpdateInstr, etc
  
  current_state : str = ""
  
  def __init__(self, prev) -> None:
    super().__init__(VNValueType.Void)
    self.sayer_last = prev
    self.sayer_base = prev.get_sayer_info()
    self.current_state = prev.get_sayer_state()
  
  def get_sayer_info(self) -> VNSayerInfo:
    return self.sayer_base
  
  def get_prev(self):
    return self.sayer_last
  
  def set_sayer_state(self, state : str) -> None:
    self.current_state = state
  
  def get_sayer_state(self) -> str :
    return self.current_state

class VNSayInst(VNInstruction):
  """Display text instruction
  Each instruction can have:
    the text to say
    the sayer (can be None)
  The return value of the text instruction is the text being displayed
  The state of the sayer (expressions like sad, happy, etc) are on the sayer instead of text
  Whether we wait/continue/... is implemented in attributes:
    [wait]: wait for click after text rolled over
    [continue(Text)]: continue from the text in the specified text source (e.g., a previous VNSayInst)
  """
  sayer : VNValue
  text : VNTextBlock
  voice : VNValue
  
  def __init__(self, sayer : VNValue, text : VNTextBlock, voice : VNValue = None) -> None:
    super().__init__(VNValueType.Text)
    self.sayer = sayer
    self.text = text
    self.voice = voice
  
  def get_sayer(self) -> VNValue:
    return self.sayer
  
  def get_text(self) -> VNTextBlock:
    return self.text
  
  def get_voice(self) -> VNValue:
    return self.voice

class VNUpdateContext(VNInstruction):
  """Base class for updating any exclusive context"""
  def __init__(self):
    super().__init__(VNValueType.Void)
  

class VNUpdateBackground(VNUpdateContext):
  """Update background image (or maybe a Screen)"""
  
  background : VNValue = None
  
  def __init__(self, background : VNValue):
    super().__init__()
    assert background.get_type() in [VNValueType.Image, VNValueType.Screen]
    self.background = background

  def get_background(self):
    return self.background

class VNUpdateBGMInstr(VNUpdateContext):
  """Update the background music (can be a list for circulation)
  When without any attributes, we default to "loop all"
  Later on we may support attributes to set it to random loop, etc
  """
  
  bgm_list : typing.List[VNValue] = []
  
  def __init__(self, bgm):
    super().__init__()
    if isinstance(bgm, list):
      self.bgm_list = bgm
    else:
      self.bgm_list = [bgm]
    
    # validation
    for entry in self.bgm_list:
      assert isinstance(entry, VNValue)
      assert entry.get_type() == VNValueType.Audio
  
  def get_bgm_list(self) -> typing.List[VNValue]:
    return self.bgm_list
  
  def get_first_bgm(self) -> VNValue:
    return self.bgm_list[0]
  
  def size(self) -> int:
    return len(self.bgm_list)

class VNSoundEffect(VNInstruction):
  """play a (one-shot) sound effect"""
  
  sound : VNValue = None
  
  def __init__(self, sound):
    super().__init__(VNValueType.Audio)
    self.sound = sound
    assert isinstance(sound,VNValue)
    assert sound.get_type() == VNValueType.Audio
  

class VNBasicBlock(VNValue):
  
  instr_list : typing.List[VNInstruction] = []
  
  def __init__(self, name : str = "") -> None:
    super().__init__(VNValueType.Label)
    self.instr_list = []
    self.set_name(name)
  
  def get_instruction_list(self):
    return self.instr_list
  
  def get_terminator(self):
    return self.instr_list[-1]
  
  def add_instruction(self, instr : VNInstruction) -> VNInstruction:
    self.instr_list.append(instr)
    return instr

class VNFunction(VNValue):
  
  # we use the VNValue.name as the (identifier) name that can be looked up
  
  basicblock_list : typing.List[VNBasicBlock] = []
  
  # a short, numerical name like 1.2 for chapter 1, section 2
  numerical_name : str = ""
  
  # a long, rich text name for display
  full_name : VNTextBlock = None
  
  def __init__(self, name : str = "") -> None:
    super().__init__(VNValueType.Function)
    self.basicblock_list = []
    self.numerical_name = ""
    self.full_name = None
    self.set_name(name)
  
  def get_basicblock_list(self):
    return self.basicblock_list
    
  def get_entry_block(self):
    return self.basicblock_list[0]
  
  def add_basicblock(self, bb : VNBasicBlock) -> VNBasicBlock:
    self.basicblock_list.append(bb)
    return bb

# assets
class VNAsset(VNValue):
  
  data : bytes = None # the actual data
  
  def __init__(self, ty : VNValueType) -> None:
    super().__init__(ty)
    

class VNModel(VNValue):
  # we use list to preserve the declaration order
  character_list : typing.List[VNCharacterIdentity] = []
  sayer_list : typing.List[VNSayerInfo] = []
  
  function_dict : typing.Dict[str, VNFunction] = {}
  
  
  entry : str = "start"
  
  # assets are unordered
  asset_dict : typing.Dict[str, VNValue] = {} # values should be asset type
  
  def __init__(self, name : str = "", entry : str = "start") -> None:
    super().__init__(name)
    self.entry = entry
    self.character_list = []
    self.sayer_list = []
    self.function_dict = {}
  
  def set_entry_function(self, entry : str) -> None:
    self.entry = entry
  
  def add_asset(self, asset : VNValue) -> VNValue:
    assert asset.get_name() not in self.asset_dict
    self.asset_dict[asset.get_name()] = asset
    return asset
  
  def get_asset(self, asset_name : str):
    return self.asset_dict[asset_name]
  
  def validate(self) -> None:
    """Validate the model; raise exception if any problems found"""
    pass
  
  def add_function(self, func : VNFunction) -> VNFunction:
    assert func.get_name() not in self.function_dict
    self.function_dict[func.get_name()] = func
    return func
  
  def get_function(self, name : str) -> VNFunction:
    return self.function_dict[name]
  
  def get_function_list(self):
    return self.function_dict.values()
  
  def get_sayer_list(self):
    return self.sayer_list
  
  def get_character_list(self):
    return self.character_list
  
  def add_character(self, character : VNCharacterIdentity) -> VNCharacterIdentity:
    self.character_list.append(character)
    return character
  
  def add_sayer(self, sayer : VNSayerInfo) -> VNSayerInfo:
    self.sayer_list.append(sayer)
    return sayer
  
  def empty(self) -> bool :
    return len(self.function_dict) == 0
  
  def finalize(self) -> None:
    """Called after the construction is done
    
    This function does the following things:
    1. Validation (TODO)
    2. Update all name reference to object reference
      e.g., for VNCallInst: add reference to callee function
      
    """
    for func in self.function_dict.values():
      for bb in func.get_basicblock_list():
        for instr in bb.get_instruction_list():
          if isinstance(instr, VNCallInst):
            callee_name = instr.get_callee_name()
            callee = self.get_function(callee_name)
            instr.set_callee(callee)
    # done
    