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

# ----------------------------------------------------------
# Type system
# ----------------------------------------------------------

class VNValueType:
  """Base class of all types"""
  
  def validate(self, value: typing.Any) -> None:
    """Check whether the value conform to the typing requirement.
    
    Should be provided by all derived classes
    raise exception whenever validation fails; do nothing if everything good
    """
    pass
  
  def __eq__(self, other) -> bool:
    return (other is self) or type(self) == type(other)
  
  def is_convertible_to(self, target_type) -> bool:
    """return true of the value can be converted to the target type"""
    if isinstance(target_type, VNVoidType):
      return True
    return self.__eq__(target_type)
  
  def is_void_type(self):
    return isinstance(self, VNVoidType)
  def is_bool_type(self):
    return isinstance(self, VNBoolType)
  def is_integer_type(self):
    return isinstance(self, VNIntegerType)
  def is_string_type(self):
    return isinstance(self, VNStringType)
  def is_text_type(self):
    return isinstance(self, VNTextType)
  def is_image_type(self):
    return isinstance(self, VNImageType)
  def is_audio_type(self):
    return isinstance(self, VNAudioType)
  def is_video_type(self):
    return isinstance(self, VNVideoType)
  def is_sayer_type(self):
    return isinstance(self, VNSayerType)
  def is_basicblock_type(self):
    return isinstance(self, VNBasicBlockType)
  def is_function_type(self):
    return isinstance(self, VNFunctionType)

class VNVoidType(VNValueType):
  """No value type"""
  
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNVoidType.instance is None:
      VNVoidType.instance = VNVoidType()
    return VNVoidType.instance
  
  def validate(self, value: typing.Any) -> None:
    return

  
class VNVariableType(VNValueType):
  """Base class of variable types
  
  All types support ==, !=, <, <=, >, >= (all yielding boolean)
  All types support conversion to Text
  """
  def is_convertible_to(self, target_type) -> bool:
    if super().is_convertible_to(target_type):
      return True
    if isinstance(target_type, VNTextType):
      return True
    return False

class VNBoolType(VNVariableType):
  """Boolean type (true / false)
  
  Support !, ||, &&
  """
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNBoolType.instance is None:
      VNBoolType.instance = VNBoolType()
    return VNBoolType.instance

class VNIntegerType(VNVariableType):
  """Integer type; implementation dependent precision
  
  Support +, -, *, /, %, ^ (power)
  """
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNIntegerType.instance is None:
      VNIntegerType.instance = VNIntegerType()
    return VNIntegerType.instance
  
  def is_convertible_to(self, target_type) -> bool:
    if super().is_convertible_to(target_type):
      return True
    # in addition, we can convert to bool
    if isinstance(target_type, VNBoolType):
      return True
    return False

class VNStringType(VNVariableType):
  """UTF-8 String type.
  
  Support:
    + (concatenation)
    .length()
    .substr(pos, length)
    startswith
    endswith
  """
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNStringType.instance is None:
      VNStringType.instance = VNStringType()
    return VNStringType.instance

  def is_convertible_to(self, target_type) -> bool:
    if super().is_convertible_to(target_type):
      return True
    # in addition, we can convert to bool
    if isinstance(target_type, VNBoolType):
      return True
    return False

class VNFunctionType(VNValueType):
  """VNValueType for functions

  Functions can be call destinations, and entry point of external control flow
  Note that a single function in IR can have multiple entry basic blocks
    (e.g., when a function is a rewind entry and the current backgrounds, etc
    are specified in the caller)
  """
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNFunctionType.instance is None:
      VNFunctionType.instance = VNFunctionType()
    return VNFunctionType.instance

class VNBasicBlockType(VNValueType):
  """VNValueType for basic blocks
  
  Basic blocks can be destinations of branch and jump.
  """
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNBasicBlockType.instance is None:
      VNBasicBlockType.instance = VNBasicBlockType()
    return VNBasicBlockType.instance

class VNTextType(VNValueType):
  """Type for (runtime constant) displayable text (e.g., plot text, character name, etc)
  
  In VNModel: text = string + formatting attributes
  """
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNTextType.instance is None:
      VNTextType.instance = VNTextType()
    return VNTextType.instance

class VNImageType(VNValueType):
  """Type for (runtime constant) images (e.g., Background, CG, character sprite, etc)"""
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNImageType.instance is None:
      VNImageType.instance = VNImageType()
    return VNImageType.instance

class VNAudioType(VNValueType):
  """Type for (runtime constant) audio (e.g., voice, bgm, etc)"""
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNAudioType.instance is None:
      VNAudioType.instance = VNAudioType()
    return VNAudioType.instance

class VNVideoType(VNValueType):
  """Type for (runtime constant) videos"""
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNVideoType.instance is None:
      VNVideoType.instance = VNVideoType()
    return VNVideoType.instance

class VNSayerType(VNValueType):
  """Type for sayer info, sayer decl, and sayer update"""
  instance : typing.ClassVar[VNValueType] = None

  def get():
    if VNSayerType.instance is None:
      VNSayerType.instance = VNSayerType()
    return VNSayerType.instance

# ----------------------------------------------------------
# VNValue
# ----------------------------------------------------------

class VNUse:
  """Counterpart of llvm::Use
  
  Basically a struct that saves <user, operand index> pair
  NOTE: unlike LLVM which only use an unsigned number for operand index,
        we actually does not restrict what's the type of operand index,
        as long as:
          1. it is unique from the same user
          2. we can use the operand index to find the referenced value from the user
          3. we can compare (__eq__, __ne__) and hash (__hash__) the operand index
  """
  
  def __init__(self, user : object, operand_index : typing.Any) -> None:
    self.user = user
    self.operand_index = operand_index
  
  def get_user(self):
    return self.user
  
  def get_operand_index(self) -> typing.Any:
    return self.operand_index
  
  def __eq__(self, __o: object) -> bool:
    return self.user is __o.user and self.operand_index == __o.operand_index
  
  def __ne__(self, __o: object) -> bool:
    return not self.__eq__(__o)
  
  def __hash__(self) -> int:
    return hash((id(self.user), self.operand_index))

class VNValue:
  """VNValue is (almost) the common base class of everything in VNModel. It resembles llvm::User
  
  This class does the following:
  1. maintain the use-def chain
  2. keep the metadata (including source location)
  
  Note that unlike llvm IR, we distinguish "whether some thing is const or not" with runtime property instead of types.
  This should reduce number of types we need to handle when we don't care whether the value is const or not.
  
  In VNModel, something is constant means "given the configuration settings (language, resolution, etc), the value can be determined at compile time"
  Which means constants can depend on configuration inputs
  """
  
  name : str = "" # name of the value, should be unique within the type. No restriction on character set
  value_type : VNValueType = None # type of the value
  
  attribute_map : typing.Dict[str, object] = {} # should be dict of str -> VNAttribute
  
  metadata : typing.List[typing.Any] = [] # something not affecting analysis and code generation in general
  
  uses : typing.Set[VNUse] = {}
  
  def __init__(self, ty : VNValueType) -> None:
    self.name = ""
    self.value_type = ty
    self.attribute_map = {}
    self.metadata = []
    self.uses = set()
  
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
  
  def get_attribute(self, attrType):
    key = attrType.get_attr_name()
    if key in self.attribute_map:
      return self.attribute_map[key]
    return None
  
  def set_attribute(self, attr) -> bool:
    key = attr.get_attr_name()
    if key in self.attribute_map:
      return False
    self.attribute_map[key] = attr
    return True
  
  def get_metadata(self) -> typing.List[typing.Any]:
    return self.metadata
  
  def add_use(self, use: VNUse) -> None:
    self.uses.add(use)
  
  def remove_use(self, use: VNUse) -> None:
    self.uses.remove(use)
  
  def get_uses(self):
    return self.uses
  
  def update_operand(self, operand_index : typing.Any, old_target : object, new_target : object) -> None:
    """def-use list manipulation. Should be called by child to update def-use list"""
    use = VNUse(self, operand_index)
    if not (old_target is None):
      assert isinstance(old_target, VNValue)
      old_target.remove_use(use)
    if not (new_target is None):
      assert isinstance(new_target, VNValue)
      new_target.add_use(use)
    # done
  
  def initialize_operand(self, operand_index : typing.Any, target : object) -> None:
    """Helper method for initialization (no old use value)"""
    self.update_operand(operand_index, None, target)
  
  def initialize_single_operand(self, target: object) -> None:
    """Helper method for initialization, when self only use one operand"""
    self.update_operand(None, None, target)
  
  def get_operand(self, operand_index : typing.Any):
    """Return the operand at given index
    
    Should be provided by derived class if they take operands
    """
    raise NotImplementedError("get_operand() unimplemented on " + str(type(self)))
  
  # support for using VNValue as key in dictionary / in set
  # no need to override in derived classes
  def __hash__(self) -> int:
    return hash(id(self))
  
  def __eq__(self, __o: object) -> bool:
    return __o is self
  
  # support for visitor pattern
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    raise NotImplementedError("visit() not implemented on " + str(type(self)))

# ----------------------------------------------------------
# VNAttribute
# ----------------------------------------------------------

class VNAttribute(VNValue):
  """VNAttribute is the base class of attributes that can be attached to anything in IR"""
  
  # static variable for attribute name in VNValue attribute dict
  attr_name : typing.ClassVar[str] = ""
  
  parent : VNValue = None # parent VNValue of this attribute
  
  def __init__(self, parent : VNValue) -> None:
    super().__init__(VNVoidType.get())
    self.parent = parent
  
  def get_attr_name() -> str:
    return VNAttribute.attr_name

  def set_parent(self, parent : VNValue) -> None:
    self.parent = parent

  def get_parent(self) -> None:
    return self.parent

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNAttribute(self, *args, **kwargs)
  
# ----------------------------------------------------------
# VNSelectionMatrix
# ----------------------------------------------------------

class VNSelectionMatrixElement(VNValue):
  """Individual element in a selection matrix
  
  This inherits from VNValue to keep track of def-use chain
  This class expects no user. This should just be inside the body of a selection matrix
  """
  key : tuple = None
  value : VNValue = None
  parent: object = None # VNSelectionMatrix
  
  def __init__(self, key: tuple, value : VNValue) -> None:
    super().__init__(value.get_type())
    self.key = key
    self.value = value
    self.parent = None
    self.initialize_single_operand(value)
  
  def get_operand(self, operand_index: typing.Any) -> VNValue:
    assert operand_index is None
    return self.get_value()
  
  def set_parent(self, parent : object) -> None:
    self.parent = parent
  
  def get_parent(self):
    return self.parent
  
  def get_key(self):
    return self.key
  
  def get_value(self) -> VNValue:
    return self.value
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSelectionMatrixElement(self, *args, **kwargs)

class VNSelectionMatrixKeyType(Enum):
  LANGUAGE = 0  # key is string
  SAYER = 1 # key is sayer identifier (used for e.g., selecting different voice for multiple candidate sayer saying the same thing)

class VNSelectionMatrix(VNValue):
  """Template that selects one from a matrix of candidates
  
  Note that this selection matrix is intended for selection based on configurations
  (i.e., language, sayer, etc); it is not for user-specified variables
  """
  key_list : typing.List[VNSelectionMatrixKeyType] = None
  value_dict : typing.Dict[tuple, VNSelectionMatrixElement] = {}
  
  def __init__(self, ty: VNValueType, key_list : typing.List[VNSelectionMatrixKeyType]) -> None:
    super().__init__(ty)
    assert len(key_list) > 0
    self.key_list = key_list.copy()
    self.value_dict = {}
  
  def get_key_list(self) -> typing.List[VNSelectionMatrixKeyType]:
    return self.key_list
  
  def add_candidate(self, keys : tuple, value : VNValue) -> bool:
    assert len(keys) == len(self.key_list)
    assert value.get_type() == self.get_type()
    if keys in self.value_dict:
      return False
    element = VNSelectionMatrixElement(keys, value)
    element.set_parent(self)
    self.value_dict[keys] = element
    return True

  def get_candidate(self, keys: tuple) -> VNSelectionMatrixElement:
    assert len(keys) == len(self.key_list)
    if keys in self.value_dict:
      return self.value_dict[keys]
    return None
  
  def get_value_dict(self):
    return self.value_dict;
  
  # we can iterate over all VNSelectionMatrixElement by "for e in matrix"
  def __iter__(self):
    return iter(self.value_dict.values())
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSelectionMatrix(self, *args, **kwargs)

# ----------------------------------------------------------
# Literal types
# ----------------------------------------------------------

# we may have many many strings and it may be more efficient to directly use python str instead of string literal object
# however, we use the convention that: if the content can be accessed by user (e.g., display, or search keyword),
# wrap the string into a string literal object

class VNBooleanLiteral(VNValue):
  value : bool = False
  
  def __init__(self, value : bool) -> None:
    super().__init__(VNBoolType.get())
    self.value = value
  
  def get_value(self) -> bool:
    return self.value
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNBooleanLiteral(self, *args, **kwargs)

class VNIntegerLiteral(VNValue):
  value : int = 0
  
  def __init__(self, value : int) -> None:
    super().__init__(VNIntegerType.get())
    self.value = value
  
  def get_value(self) -> int:
    return self.value
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNIntegerLiteral(self, *args, **kwargs)
  
class VNStringLiteral(VNValue):
  value : str = ""
  
  def __init__(self, value : str) -> None:
    super().__init__(VNStringType.get())
    self.value = value
  
  def get_value(self) -> str:
    return self.value

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNStringLiteral(self, *args, **kwargs)
  
# ----------------------------------------------------------
# Variables
# ----------------------------------------------------------
class VNVariableStorageDuration(Enum):
  """Enum for variable storage durations
  
  Temporary values (e.g., load) does not have storage and
    therefore no storage duration
  """
  Persistent = 0 # the variable is global (like a per-user value)
  Save = enum.auto() # the variable is per-save-file
  External = enum.auto() # the variable is managed by external code

class VNVariable(VNValue):
  """Class for all variables
  
  Although it is called "variable", we should really call it "memory"..
  """
  initializer : VNValue = None
  
  def __init__(self, ty: VNValueType, initializer : VNValue = None) -> None:
    super().__init__(ty)
    if initializer is not None:
      assert initializer.get_type() == ty
    self.initializer = initializer
  
  def get_initializer(self) -> VNValue:
    return self.initializer
  
  def set_initializer(self, initializer : VNValue) -> None:
    if initializer is not None:
      assert initializer.get_type() == self.get_type()
    self.initializer = initializer

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNVariable(self, *args, **kwargs)

# ----------------------------------------------------------
# classes for text data
# ----------------------------------------------------------

class VNTextAttribute(Enum):
  """Enum for commonly supported text formatting attributes.
  
  Additional attributes can be implemented as VNAttribute on entries
  """
  
  # text attributes without associated data
  Bold = 0
  Italic = 1
  
  # text attributes with data
  Size = 2 # data: int representing size change; 0 is no change, + means increase size, - means decrease size
  TextColor = 3 # data: foreground color
  BackgroundColor = 4 # data: background color (highlight color)

class RubyTextAttribute(VNAttribute):
  """Mark a text fragment as having ruby text"""
  text : VNStringLiteral = None
  
  attr_name : typing.ClassVar[str] = "ruby_text"
  
  def get_attr_name() -> str:
    return VNAttribute.attr_name
  
  def __init__(self, parent: VNValue, text : VNStringLiteral) -> None:
    assert isinstance(parent, VNTextFragment)
    super().__init__(parent)
    self.text = text
    self.initialize_single_operand(text)
  
  def get_text(self) -> VNStringLiteral:
    return self.text
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_text()

class VNTextFragment(VNValue):
  """text element with the same appearance. lanugage dependence should be handled by IR tree parents.
  
  The text can be a variable reference (VNVariable), a literal (VNStringLiteral), or a temporary variable (e.g., concatenation of strings)
  """
  styles : typing.Dict[VNTextAttribute, typing.Any] = {} # text formatting attributes
  text : VNValue = None
  
  def __init__(self, text : VNValue, styles : typing.Dict[VNTextAttribute, typing.Any] = {}) -> None:
    super().__init__(VNTextType.get())
    assert text.get_type().is_string_type()
    self.styles = styles.copy()
    self.text = text
    self.initialize_single_operand(text)
  
  def get_text(self):
    return self.text
  
  def get_styles(self):
    return self.styles

  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.text

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNTextFragment(self, *args, **kwargs)

class VNTextBlock(VNValue):
  """Class that represent a block of text, and they can have different formatting attributes, etc """
  
  fragments : typing.List[VNTextFragment] = []
  
  def __init__(self, text: typing.Any):
    super().__init__(VNTextType.get())
    self.fragments = []
    if isinstance(text, list):
      self.fragments = text.copy()
    elif isinstance(text, VNTextFragment):
      self.fragments = [text]
    elif isinstance(text, str):
      self.fragments = [VNTextFragment(VNStringLiteral(text),{})]
    else:
      raise RuntimeError("Unhandled text type")
    for i in range(0, len(self.fragments)):
      self.initialize_operand(i, self.fragments[i])
    
  def get_fragment_list(self) -> typing.List[VNTextFragment]:
    return self.fragments
  
  def get_operand(self, operand_index: typing.Any):
    assert isinstance(operand_index, int)
    return self.fragments[operand_index]

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNTextBlock(self, *args, **kwargs)

# ----------------------------------------------------------
# character and sayer
# ----------------------------------------------------------

class VNCharacterIdentity(VNValue):
  """Identity of an abstract sayer. Similar to the name operand of Renpy's Character()
  
  We use a dedicated class so that we can attach additional metadata for analysis
  This is considered a global constant. No say command can directly reference sayer identity
  The name of the character identity is recommended to be alphanumeric, but is not mandatory
  """
  
  def __init__(self, name : str) -> None:
    super().__init__(VNVoidType.get())
    self.set_name(name)
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNCharacterIdentity(self, *args, **kwargs)
  

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
  
  class OperandType(Enum):
    """Operand index for sayer info"""
    Identity = 0
    NameText = enum.auto()
    StyleText = enum.auto()
    CharacterSprite = enum.auto() # we will also attach a label in the operand index
    SideImage = enum.auto()
  
  # identity: the identity of sayer.
  # Each "sayer" person should have one unique identity, like a name.
  # A single identity (e.g., a person) can map to more than one sayer instance (e.g., the person with cloth A and with cloth B)
  # the VNModel use this to track persons for analysis
  identity : VNCharacterIdentity = None
  
  # what's put in the "name" field in gameplay
  # should have text type
  name_text : VNValue
  
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
  # this is per-text and will be shown when sayer info is directly referenced in the say instruction, if possible
  side_image_dict = {} # <label> -> VNValue : Image
  
  # default state for querying images, etc
  default_state : str = ""
  
  def __init__(self, identity : VNCharacterIdentity = None) -> None:
    super().__init__(VNSayerType.get())
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
    self.update_operand(VNSayerInfo.OperandType.Identity, self.identity, identity)
    self.identity = identity
  
  def get_name_text(self) -> VNValue:
    return self.name_text
  
  def set_name_text(self, name_text : VNValue) -> None:
    self.update_operand(VNSayerInfo.OperandType.NameText, self.name_text, name_text)
    self.name_text = name_text
  
  def get_style_text(self) -> VNTextFragment:
    return self.style_text
  
  def set_style_text(self, style_text: VNTextFragment) -> None:
    self.update_operand(VNSayerInfo.OperandType.StyleText, self.style_text, style_text)
    self.style_text = style_text
  
  def get_character_sprite(self, state : str) -> VNValue:
    return self.character_sprite_dict.get(state)
  
  def set_character_sprite(self, state : str, sprite : VNValue) -> VNValue:
    self.update_operand((VNSayerInfo.OperandType.CharacterSprite, state), self.character_sprite_dict.get(state), sprite)
    self.character_sprite_dict[state] = sprite
    return sprite
  
  def get_side_image(self, state : str) -> VNValue:
    return self.side_image_dict.get(state)
  
  def set_side_image(self, state : str, image : VNValue) -> VNValue:
    self.update_operand((VNSayerInfo.OperandType.SideImage, state), self.side_image_dict.get(state), image)
    self.side_image_dict[state] = image
    return image
  
  def get_default_side_image(self) -> VNValue:
    return self.side_image_dict.get(self.default_state)
  
  def get_default_state(self) -> str:
    return self.default_state

  def set_default_state(self, state : str) -> str:
    self.default_state = state
    return state
  
  # make sure we can call sayer.get_sayer_info() when handling VNSayInst,
  # no matter which class (SayerInfo, SayerDecl, SayerUpdate) it is referencing
  def get_sayer_info(self):
    return self

  def get_operand(self, operand_index: typing.Any):
    if isinstance(operand_index, tuple):
      key = operand_index[0]
      state = operand_index[1]
      assert isinstance(key, VNSayerInfo.OperandType) and isinstance(state, str)
      if key == VNSayerInfo.OperandType.CharacterSprite:
        return self.get_character_sprite(state)
      elif key == VNSayerInfo.OperandType.SideImage:
        return self.get_side_image(state)
      else:
        raise NotImplementedError("Unexpected operand index key")
    else:
      assert isinstance(operand_index, VNSayerInfo.OperandType)
      if operand_index == VNSayerInfo.OperandType.Identity:
        return self.get_identity()
      elif operand_index == VNSayerInfo.OperandType.NameText:
        return self.get_name_text()
      elif operand_index == VNSayerInfo.OperandType.StyleText:
        return self.get_style_text()
      else:
        raise NotImplementedError("Unexpected operand index key")
      
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSayerInfo(self, *args, **kwargs)

class VNSayerInfoReference(VNValue):
  """Reference to VNSayerInfo with a state label"""
  sayer : VNSayerInfo = None
  state : str = ""
  
  def __init__(self, sayer : VNSayerInfo, state : str) -> None:
    super().__init__(VNSayerType.get())
    self.sayer = sayer
    self.state = state
    self.initialize_single_operand(sayer)
  
  def get_sayer_state(self) -> str:
    return self.state
  
  def get_sayer_info(self) -> VNSayerInfo:
    return self.sayer
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_sayer_info()

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSayerInfoReference(self, *args, **kwargs)

# ----------------------------------------------------------
# classes for image
# ----------------------------------------------------------

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
  """Base image or "image literal". Images with transparent borders are automatically compressed away (and only the non-empty part is stored)
  
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
    super().__init__(VNImageType.get())
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
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNImageAsset(self, *args, **kwargs)
  
class VNLayeredImageAsset(VNValue):
  """Layered image that can have multiple variants, in a model similar to RenPy's layeredimage
  
  Each reference to the final image would require a reference AND a list of attributes
  For simplicity, we just use a simplified model that:
  1. there are a bunch of layers, from the bottom to the top
  2. each layer is at most one image, without any transform or effect, etc
  The size of the layered image is determined by the size of the first (bottom) layer. If this is not what you want, add a transparent layer with desired size.
  We rely on letting VNImageAsset able to auto-crop to avoid dealing with layers having different sizes
  Later on we may also support more fancy use on layered images, like treating each layer as a "part" and have a tooltip or click action, etc (for showing block diagram, etc)
  
  Operand index is a tuple with:
    operand_index[0]: int the layer index
    operand_index[1]: str the layer option name
  """
  layers : typing.List[typing.Tuple[str, typing.Dict[str, VNImageAsset]]] = [] # layer hierarchy
  layer_option_dict : typing.Dict[str, int] = {} # map from layer options to the layer index (i.e., "wink" -> (index for "eye" layer))
  
  def __init__(self) -> None:
    super().__init__(VNImageType.get())
    self.layers = []
    self.layer_option_dict = {}
  
  def add_layer(self, layer_name : str, option_dict : typing.Dict[str, VNImageAsset]):
    """Add a new layer to this image asset"""
    for curname, curdict in self.layers.items():
      assert curname != layer_name
    
    layer_tuple = (layer_name, option_dict.copy())
    layer_index = len(self.layers)
    self.layers.append(layer_tuple)
    
    for option, image_layer in option_dict.items():
      assert option not in self.layer_option_dict
      self.layer_option_dict[option] = layer_index
      self.update_operand((layer_index, option), None, image_layer)
      
  def get_operand(self, operand_index: typing.Any):
    layer_index = operand_index[0]
    option = operand_index[1]
    assert isinstance(layer_index, int) and isinstance(option, str)
    return self.layers[layer_index][1][option]
  
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
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNLayeredImageAsset(self, *args, **kwargs)

class VNLayeredImageReference(VNValue):
  """Reference to a layered image with a set of states"""
  source : VNLayeredImageAsset = None
  attr_list : typing.List[str] = []
  
  def __init__(self, source : VNLayeredImageAsset, attr_list : typing.List[str]) -> None:
    super().__init__(VNImageType.get())
    self.source = source
    self.attr_list = attr_list.copy()
    self.initialize_single_operand(source)
  
  def get_source_layered_image(self):
    return self.source
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_source_layered_image()
  
  def get_image_stack(self):
    return self.source.get_image_stack(self.attr_list)
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNLayeredImageReference(self, *args, **kwargs)

# ----------------------------------------------------------
# classes for audio
# ----------------------------------------------------------

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
      raise NotImplementedError("Unrecognized audio extension "+ ext)
  
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
    raise NotImplementedError("Unexpected audio format")

class VNAudioAsset(VNValue):
  """Base audio. We may also transparently drop silenced parts under the hood
  
  (Or may not...)
  """
  audio : pydub.AudioSegment = None
  audio_data : bytes = None
  audio_format : VNAudioFormat = VNAudioFormat.INVALID
  
  
  def __init__(self, audio : typing.Any, format : VNAudioFormat = VNAudioFormat.INVALID) -> None:
    super().__init__(VNAudioType.get())
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
      raise NotImplementedError("Unhandled audio data type")
  
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
        self.audio.export(f, format = chosen_format)
      os.rename(tmppath, path)
    # done
    return path
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNAudioAsset(self, *args, **kwargs)

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
  
  parent : object # VNBasicBlock
  
  def __init__(self, ty : VNValueType) -> None:
    # make sure it has the same signature as VNValue.__init__ to avoid headache when using multiple inheritance
    super().__init__(ty)
    self.parent = None

  def get_parent(self):
    return self.parent

  def is_terminator(self) -> bool:
    return False
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNInstruction(self, *args, **kwargs)

class VNTerminatorInstruction(VNInstruction):
  def __init__(self) -> None:
    super().__init__(VNVoidType.get())
  
  def is_terminator(self) -> bool:
    return True
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNTerminatorInstruction(self, *args, **kwargs)

class VNReturnInst(VNTerminatorInstruction):
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNReturnInst(self, *args, **kwargs)

class VNCallInst(VNInstruction):
  """Call a function. We does not support function parameters.
  
  All contexts (foreground / background image, sprites, etc) in the current function context becomes undefined afterwards
  If later code requires use of the context, there will be updateXXX instructions to recover them
  """
  callee: object # VNFunction
  
  def __init__(self, callee : object) -> None:
    super().__init__(VNVoidType.get())
    self.callee = callee
    self.initialize_single_operand(callee)
  
  def set_callee(self, callee : object) -> None:
    self.update_operand(None, self.callee, callee)
    self.callee = callee
  
  def get_callee_name(self):
    return self.callee.get_name()
  
  def get_callee(self):
    return self.callee
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_callee()
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNCallInst(self, *args, **kwargs)

class VNTailCall(VNAttribute):
  """If this attribute is present on a call, the subsequent instructions must be a return
  
  This is a hint that no state saving (for sprites, etc) is required for a call
  
  UPDATE: Unimplemented
  """
  pass

class VNDestroy(VNAttribute):
  """This attribute represents that an instruction destroyed a context state without explicitly referencing it in operands (probably a call)
  
  UPDATE: Unimplemented
  """
  pass

class VNUnreachableInst(VNTerminatorInstruction):
  """Warn the use if any of the following happens:
  1. An unreachable instruction is actually statically reachable
  2. A basic block without unreachable terminator is found statically unreachable
  """
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNUnreachableInst(self, *args, **kwargs)

class VNExitInst(VNTerminatorInstruction):
  """Exit this execution, possibly with an exit code (default to 0)"""
  
  exit_code : VNValue = None
  
  def __init__(self, exit_code : VNValue = None) -> None:
    super().__init__()
    self.exit_code = None
    if exit_code is None:
      exit_code = VNIntegerLiteral(0)
    self.set_exit_code(exit_code)
  
  def set_exit_code(self, exit_code : VNValue) -> None:
    assert exit_code is not None
    assert exit_code.get_type().is_integer_type()
    self.update_operand(None, self.exit_code, exit_code)
  
  def get_exit_code(self) -> VNValue:
    return self.exit_code
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_exit_code()
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNExitInst(self, *args, **kwargs)

class VNJumpInst(VNTerminatorInstruction):
  """Unconditional branch.
  
  Destination must be basic block within the same function
  """
  successor : object = None # VNBasicBlock
  
  def __init__(self, successor) -> None:
    super().__init__()
    self.successor = successor
    self.initialize_single_operand(successor)
  
  def get_successor(self) -> None:
    return self.successor
  
  def set_successor(self, successor):
    self.update_operand(None, self.successor, successor)
    self.successor = successor
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_successor()
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNJumpInst(self, *args, **kwargs)

class VNBranchInst(VNTerminatorInstruction):
  """Conditional branch"""

  condition : VNValue = None
  true_successor : object = None # VNBasicBlock
  false_successor : object = None # VNBasicBlock
  
  class OperandType(Enum):
    Condition = 0
    TrueSuccessor = 1
    FalseSuccessor = 2
  
  def __init__(self, condition : VNValue, true_successor, false_successor) -> None:
    super().__init__()
    assert(condition.get_type().is_convertible_to(VNBoolType.get()))
    self.condition = condition
    self.true_successor = true_successor
    self.false_successor = false_successor
    self.initialize_operand(VNBranchInst.OperandType.Condition, condition)
    self.initialize_operand(VNBranchInst.OperandType.TrueSuccessor, true_successor)
    self.initialize_operand(VNBranchInst.OperandType.FalseSuccessor, false_successor)
  
  def get_condition(self):
    return self.condition
  
  def get_true_successor(self):
    return self.true_successor
  
  def get_false_successor(self):
    return self.false_successor
  
  def get_operand(self, operand_index: typing.Any):
    assert isinstance(operand_index, VNBranchInst.OperandType)
    if operand_index == VNBranchInst.OperandType.Condition:
      return self.get_condition()
    elif operand_index == VNBranchInst.OperandType.TrueSuccessor:
      return self.get_true_successor()
    elif operand_index == VNBranchInst.OperandType.FalseSuccessor:
      return self.get_false_successor()
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNBranchInst(self, *args, **kwargs)

class VNChoiceOption(VNValue):
  """One possible option for a VNChoiceInst
  
  Each candidate option will have one VNChoiceOption
  Currently only text options are available. Later on we may enable selection based on images
  """
  text : VNValue # must be available; text being displayed for the option
  value : VNValue
  
  class OperandType(Enum):
    Text : 0
    Value : 1
  
  def __init__(self, value : VNValue, text : VNValue) -> None:
    super().__init__(value.get_type())
    self.text = text
    self.value = value
    self.initialize_operand(VNChoiceOption.OperandType.Text, text)
    self.initialize_operand(VNChoiceOption.OperandType.Value, value)
  
  def get_text(self):
    return self.text
  
  def get_value(self):
    return self.value
  
  def get_operand(self, operand_index: typing.Any):
    if operand_index == VNChoiceOption.OperandType.Text:
      return self.get_text()
    elif operand_index == VNChoiceOption.OperandType.Value:
      return self.get_value()
    else:
      raise NotImplementedError()
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNChoiceOption(self, *args, **kwargs)
  
class VNChoiceInst(VNInstruction):
  """Let the user to select one option from >=1 candidates"""
  
  options : typing.List[VNChoiceOption]
  
  def __init__(self, ty : VNValueType, options : typing.List[VNChoiceOption] = []) -> None:
    super().__init__(ty)
    self.options = options.copy()
    for i in range(0, len(self.options)):
      assert self.options[i].get_type() == self.get_type()
      self.initialize_operand(i, self.options[i])
  
  def add_option(self, option : VNChoiceOption):
    assert option.get_type() == self.get_type()
    index = len(self.options)
    self.options.append(option)
    self.initialize_operand(index, option)
  
  def get_option_list(self):
    return self.options
  
  def get_operand(self, operand_index: typing.Any):
    return self.options[operand_index]
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNChoiceInst(self, *args, **kwargs)

class VNSayerDeclInst(VNInstruction):
  """Declares a new sayer, most importantly it can create the sprite
  
  If we want to (1) have a character sprite, or (2) use more than default state for a sayer,
  then we need to use sayer decl and sayer update
  
  If we have a character sprite, we disable the side image by default, otherwise the side image will be used if available. To override this, add an VNSayerSideImageUse attribute
  """
  
  sayer_base : VNSayerInfo = None # the constant sayer info
  
  current_state : str = ""
  
  def __init__(self, sayer_base : VNSayerInfo) -> None:
    super().__init__(VNSayerType.get())
    self.sayer_base = sayer_base
    self.current_state = sayer_base.get_default_state()
    self.initialize_single_operand(sayer_base)
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_sayer_info()
  
  def get_sayer_info(self):
    return self.sayer_base
  
  def set_sayer_state(self, state : str) -> None:
    self.current_state = state
  
  def get_sayer_state(self) -> str :
    return self.current_state
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSayerDeclInst(self, *args, **kwargs)
  

class VNSayerSideImageUse(VNAttribute):
  """Specify whether the side image should be used, if available."""
  
  attr_name : typing.ClassVar[str] = "SideImageUse"
  
  enable : bool = True
  
  def __init__(self, parent : VNValue, enable : bool = True):
    super().__init__(parent)
    self.enable = enable
  
  def get_enabled(self) -> bool:
    return self.enable

class VNSayerUpdateInst(VNInstruction):
  """Modify an existing sayer, including hiding the sprite / "destructing" the sayer"""
  
  sayer_base : VNSayerInfo = None # the constant sayer info
  
  sayer_last : VNValue = None # VNSayerDeclInstr, VNSayerUpdateInstr, etc
  
  current_state : str = ""
  
  class OperandType(Enum):
    SayerBase = 0
    SayerLast = 1
  
  def __init__(self, prev) -> None:
    super().__init__(VNSayerType.get())
    self.sayer_last = prev
    self.sayer_base = prev.get_sayer_info()
    self.current_state = prev.get_sayer_state()
    self.initialize_operand(VNSayerUpdateInst.OperandType.SayerBase, self.sayer_base)
    self.initialize_operand(VNSayerUpdateInst.OperandType.SayerLast, self.sayer_last)
    
  def get_operand(self, operand_index: typing.Any):
    assert isinstance(operand_index, VNSayerUpdateInst.OperandType)
    if operand_index == VNSayerUpdateInst.OperandType.SayerBase:
      return self.get_sayer_info()
    elif operand_index == VNSayerUpdateInst.OperandType.SayerLast:
      return self.get_prev()
    else:
      raise NotImplementedError("Unexpected operand index type")
  
  def get_sayer_info(self) -> VNSayerInfo:
    return self.sayer_base
  
  def get_prev(self):
    return self.sayer_last
  
  def set_sayer_state(self, state : str) -> None:
    self.current_state = state
  
  def get_sayer_state(self) -> str :
    return self.current_state
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSayerUpdateInst(self, *args, **kwargs)

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
  text : VNValue
  voice : VNValue
  
  class OperandType(Enum):
    Sayer = 0
    Text = 1
    Voice = 2
  
  def __init__(self, sayer : VNValue, text : VNValue, voice : VNValue = None) -> None:
    super().__init__(VNTextType.get())
    self.sayer = sayer
    self.text = text
    self.voice = voice
    self.initialize_operand(VNSayInst.OperandType.Sayer,  sayer)
    self.initialize_operand(VNSayInst.OperandType.Text,   text)
    self.initialize_operand(VNSayInst.OperandType.Voice,  voice)
  
  def get_sayer(self) -> VNValue:
    return self.sayer
  
  def get_text(self) -> VNValue:
    return self.text
  
  def get_voice(self) -> VNValue:
    return self.voice

  def get_operand(self, operand_index: typing.Any):
    assert isinstance(operand_index, VNSayInst.OperandType)
    if operand_index == VNSayInst.OperandType.Sayer:
      return self.get_sayer()
    elif operand_index == VNSayInst.OperandType.Text:
      return self.get_text()
    elif operand_index == VNSayInst.OperandType.Voice:
      return self.get_voice()
    else:
      raise NotImplementedError("Unexpected operand type")
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSayInst(self, *args, **kwargs)

class VNUpdateContextInstruction(VNInstruction):
  """Base class for updating any exclusive context"""
  def __init__(self):
    super().__init__(VNVoidType.get())
  

class VNUpdateBackgroundInst(VNUpdateContextInstruction):
  """Update background image (or maybe a Screen)"""
  
  background : VNValue = None
  
  def __init__(self, background : VNValue):
    super().__init__()
    self.background = background
    self.initialize_single_operand(background)
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_background()

  def get_background(self):
    return self.background
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNUpdateBackgroundInst(self, *args, **kwargs)

class VNUpdateBGMInst(VNUpdateContextInstruction):
  """Update the background music (can be a list for circulation)
  When without any attributes, we default to "loop all"
  Later on we may support attributes to set it to random loop, etc
  """
  
  bgm_list : typing.List[VNValue] = []
  
  def __init__(self, bgm):
    super().__init__()
    if isinstance(bgm, list):
      self.bgm_list = bgm.copy()
    else:
      self.bgm_list = [bgm]
    
    # validation
    for entry in self.bgm_list:
      assert isinstance(entry, VNValue)
      assert entry.get_type().is_audio_type()
    
    for i in range(0, len(self.bgm_list)):
      self.initialize_operand(i, self.bgm_list[i])
  
  def get_operand(self, operand_index: typing.Any):
    assert isinstance(operand_index, int)
    return self.bgm_list[operand_index]
  
  def get_bgm_list(self) -> typing.List[VNValue]:
    return self.bgm_list
  
  def get_first_bgm(self) -> VNValue:
    return self.bgm_list[0]
  
  def size(self) -> int:
    return len(self.bgm_list)
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNUpdateBGMInst(self, *args, **kwargs)

class VNSoundEffectInst(VNInstruction):
  """play a (one-shot) sound effect"""
  
  sound : VNValue = None
  
  def __init__(self, sound):
    super().__init__(VNVoidType.get())
    self.sound = sound
    assert sound.get_type().is_audio_type()
    self.initialize_single_operand(sound)

  def get_sound(self):
    return self.sound
  
  def get_operand(self, operand_index: typing.Any):
    assert operand_index is None
    return self.get_sound()

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNSoundEffectInst(self, *args, **kwargs)

class VNBasicBlock(VNValue):
  
  parent : object # VNFunction
  instr_list : typing.List[VNInstruction] = []
  
  def __init__(self, name : str = "") -> None:
    super().__init__(VNBasicBlockType.get())
    self.instr_list = []
    self.set_name(name)
    self.parent = None
  
  def get_parent(self):
    return self.parent
  
  def get_instruction_list(self):
    return self.instr_list
  
  def get_terminator(self):
    return self.instr_list[-1]
  
  def add_instruction(self, instr : VNInstruction) -> VNInstruction:
    self.instr_list.append(instr)
    instr.parent = self
    return instr
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNBasicBlock(self, *args, **kwargs)

class VNFunction(VNValue):
  
  # we use the VNValue.name as the (identifier) name that can be looked up
  
  basicblock_list : typing.List[VNBasicBlock] = []
  
  # a short, numerical name like 1.2 for chapter 1, section 2
  numerical_name : str = ""
  
  # a long, rich text name for display
  full_name : VNTextBlock = None
  
  def __init__(self, name : str = "") -> None:
    super().__init__(VNFunctionType.get())
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
    bb.parent = self
    return bb
  
  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNFunction(self, *args, **kwargs)

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
    super().__init__(VNVoidType.get())
    self.set_name(name)
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
  
  def get_asset_list(self):
    return self.asset_dict.values()
  
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
    2. ***REMOVED***
      
    """
    pass

  def visit(self, callee : object, *args, **kwargs) -> typing.Any:
    return callee.visitVNModel(self, *args, **kwargs)

# ----------------------------------------------------------
# common helper
# ----------------------------------------------------------

class VNModelVisitor:
  default_ignore : bool
  def __init__(self, default_ignore : bool) -> None:
    self.default_ignore = default_ignore
  def default_handler(self):
    if self.default_ignore:
      pass
    else:
      raise NotImplementedError()
  # can fold in VSCode
  #region
  def visitVNAttribute(self, value : VNAttribute, *args, **kwargs) :
    self.default_handler()

  def visitVNSelectionMatrixElement(self, value : VNSelectionMatrixElement, *args, **kwargs) :
    self.default_handler()

  def visitVNSelectionMatrix(self, value : VNSelectionMatrix, *args, **kwargs) :
    self.default_handler()

  def visitVNBooleanLiteral(self, value : VNBooleanLiteral, *args, **kwargs) :
    self.default_handler()

  def visitVNIntegerLiteral(self, value : VNIntegerLiteral, *args, **kwargs) :
    self.default_handler()

  def visitVNStringLiteral(self, value : VNStringLiteral, *args, **kwargs) :
    self.default_handler()

  def visitVNVariable(self, value : VNVariable, *args, **kwargs) :
    self.default_handler()

  def visitVNTextFragment(self, value : VNTextFragment, *args, **kwargs) :
    self.default_handler()

  def visitVNTextBlock(self, value : VNTextBlock, *args, **kwargs) :
    self.default_handler()

  def visitVNCharacterIdentity(self, value : VNCharacterIdentity, *args, **kwargs) :
    self.default_handler()

  def visitVNSayerInfo(self, value : VNSayerInfo, *args, **kwargs) :
    self.default_handler()

  def visitVNSayerInfoReference(self, value : VNSayerInfoReference, *args, **kwargs) :
    self.default_handler()

  def visitVNImageAsset(self, value : VNImageAsset, *args, **kwargs) :
    self.default_handler()

  def visitVNLayeredImageAsset(self, value : VNLayeredImageAsset, *args, **kwargs) :
    self.default_handler()

  def visitVNLayeredImageReference(self, value : VNLayeredImageReference, *args, **kwargs) :
    self.default_handler()

  def visitVNAudioAsset(self, value : VNAudioAsset, *args, **kwargs) :
    self.default_handler()

  def visitVNInstruction(self, value : VNInstruction, *args, **kwargs) :
    self.default_handler()

  def visitVNTerminatorInstruction(self, value : VNTerminatorInstruction, *args, **kwargs) :
    self.default_handler()

  def visitVNReturnInst(self, value : VNReturnInst, *args, **kwargs) :
    self.default_handler()

  def visitVNCallInst(self, value : VNCallInst, *args, **kwargs) :
    self.default_handler()

  def visitVNUnreachableInst(self, value : VNUnreachableInst, *args, **kwargs) :
    self.default_handler()

  def visitVNExitInst(self, value : VNExitInst, *args, **kwargs) :
    self.default_handler()

  def visitVNJumpInst(self, value : VNJumpInst, *args, **kwargs) :
    self.default_handler()

  def visitVNBranchInst(self, value : VNBranchInst, *args, **kwargs) :
    self.default_handler()

  def visitVNChoiceOption(self, value : VNChoiceOption, *args, **kwargs) :
    self.default_handler()

  def visitVNChoiceInst(self, value : VNChoiceInst, *args, **kwargs) :
    self.default_handler()

  def visitVNSayerDeclInst(self, value : VNSayerDeclInst, *args, **kwargs) :
    self.default_handler()

  def visitVNSayerUpdateInst(self, value : VNSayerUpdateInst, *args, **kwargs) :
    self.default_handler()

  def visitVNSayInst(self, value : VNSayInst, *args, **kwargs) :
    self.default_handler()

  def visitVNUpdateBackgroundInst(self, value : VNUpdateBackgroundInst, *args, **kwargs) :
    self.default_handler()

  def visitVNUpdateBGMInst(self, value : VNUpdateBGMInst, *args, **kwargs) :
    self.default_handler()

  def visitVNSoundEffectInst(self, value : VNSoundEffectInst, *args, **kwargs) :
    self.default_handler()

  def visitVNBasicBlock(self, value : VNBasicBlock, *args, **kwargs) :
    self.default_handler()

  def visitVNFunction(self, value : VNFunction, *args, **kwargs) :
    self.default_handler()

  def visitVNModel(self, value : VNModel, *args, **kwargs) :
    self.default_handler()
  #endregion

# ----------------------------------------------------------
# common VNAttribute
# ----------------------------------------------------------

# TODO source location is not on top priority and we will revisit them later

class VNSourceLoc(VNAttribute):
  """VNSourceLoc encodes the source location of any VNValue
  
  All source locations are at least precise to files
  """
  
  attr_name : typing.ClassVar[str] = "source_loc"
  
  file : str = ""
  filetype: preppipe.commontypes.FileType
  
  def get_attr_name() -> str:
    return VNSourceLoc.attr_name
  
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