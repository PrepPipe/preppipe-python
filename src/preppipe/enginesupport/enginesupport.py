# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from posixpath import basename
import typing
import PIL.Image
from enum import Enum
import re

from ..vnmodel import *

# ----------------------------------------------------------
# Engine Model (EM) (like LLVM's MIR)
# ----------------------------------------------------------

class EMInstruction:
  
  # abstract opcode data
  opcode : typing.Any
  
  # list of operands
  operand_list : typing.List[typing.Any] = []
  
  def __init__(self, opcode, operand_list : typing.List[typing.Any] = []) -> None :
    assert opcode is not None
    self.opcode = opcode
    if len(operand_list) == 0:
      self.operand_list = []
    else:
      self.operand_list = operand_list
  
  def set_operand_list(self, operand_list : typing.List[typing.Any]) -> None:
    self.operand_list = operand_list
  
  def add_operand(self, operand : typing.Any) -> None:
    self.operand_list.append(operand)
  
  def get_num_operands(self):
    return len(self.operand_list)
  
  def get_operand(self, index : int) -> typing.Any:
    return self.operand_list[index]

  def get_opcode(self) -> typing.Any:
    return self.opcode
  
  def get_operand_dict(self, arglist : typing.List[str]) -> typing.Dict[str, typing.Any]:
    assert(len(arglist) == len(self.operand_list))
    result : typing.Dict[str, typing.Any] = {}
    for i in range(0, len(self.operand_list)):
      result[arglist[i]] = self.operand_list[i]
    return result

class EMBasicBlock:
  
  label : str = ""
  instr_list : typing.List[EMInstruction] = []
  
  def __init__(self, label : str = "") -> None :
    self.label = label
    self.instr_list = []
  
  def add_instruction(self, instr : EMInstruction) -> EMInstruction:
    self.instr_list.append(instr)
    return instr
  
  def get_instruction_list(self) -> typing.List[EMInstruction]:
    return self.instr_list
  
  def get_label(self) -> str:
    return self.label

class EMFunction:
  """It is fine if left unused; not all engines support functions"""
  label : str = ""
  basicblock_list : typing.List[typing.Any] = []
  
  def __init__(self, label : str = "") -> None :
    self.label = label
    self.basicblock_list = []
  
  def add_basicblock(self, bb : typing.Any):
    self.basicblock_list.append(bb)
    return bb
  
  def get_label(self) -> str:
    return self.label

class EngineAssetLoweringDispatcher:
  engine : object = None # EngineSupport object
  def __init__(self, engine: object) -> None:
    self.engine = engine
  
  def visitVNImageAsset(self, image : VNImageAsset, obj : object):
    return self.engine.lowerVNImageAsset(obj, image)
  
  def visitVNLayeredImageAsset(self, image : VNLayeredImageAsset, obj : object):
    return self.engine.lowerVNLayeredImageAsset(obj, image)
  
  def visitVNAudioAsset(self, audio : VNAudioAsset, obj : object):
    return self.engine.lowerVNAudioAsset(obj, audio)

class EngineDataLabeler:
  """Base class and default implementation for identifier management in the engine
  
  The default pipeline assumes that we can use a single string to refer to anything that requires a label
  If this is not the case, this class should not be used; write backend-specific pass then
  
  This class is responsible for:
  1. determine what ID (for image, etc) is legal
    default implementation: all ID must satisfy [A-Za-z][A-Za-z0-9_]*
  2. sanitize an ID string (i.e., make a string valid for ID)
  3. create a unique label name from the VNValue.name
    default implementation:
      sanitize VNValue.name first
      if what's left is empty: "anon"
      if conflicting: add numeric suffix until no collision
  4. keep track of "conflict" relationships
      otherwise: 
  """
  pass

class EngineSupport:
  """All engine support classes inherit this class, so that we can use reflection to query all supported engines
  
  This class should be a singleton; each backend would create a single instance of corresponding EngineSupport class
  When exporting the game project ("code generation" or CodeGen in complier context), we do the following:
  
  1. collection
    Create an EngineExport instance and collect all elementary parts of the project.
    Example "elementary parts" includes content (VNModel), external asset pack, GUI, configuration settings, etc
  
    This stage is mainly managed by user code that calls into EngineSupport functions, since only user knows what are available.
  
  2. labeling
    assign unique identifiers to VNValue references (e.g., image asset, functions) if they don't have one yet.
    Also export the asset into the project, doing conversion (e.g., jpg to png) if necessary
    
    This stage produces all necessary information for "binary compatibility", which means that the user can choose to export the source IR
    And use the label info to work on another part of the project compatible with this codegen results
  
    Starting from this stage, the backend code manages the whole process.
  
  3. lowering
    lower all VNModel Instructions to backend-specific instruction sequences.
    If some feature requires program instrumentation (e.g., collectibles implementation would instrument a "set flag" before the use),
      this is also a good place for that.
  
  4. post-lowering processing
    Some backends may want to do optimizations (e.g., simplifycfg), and they are perfectly fine
  
  5. export
    Write the data content to the directory.
  """
  
  engine_dict : typing.ClassVar[typing.Dict[str, object]] = {}
  engine_name : str = ""
  
  # --------------------------------------------------------
  # Interface functions for user code
  # --------------------------------------------------------
  
  def __init__(self, engine_name : str) -> None:
    EngineSupport.engine_dict[engine_name] = self
    self.engine_name = engine_name
    
  def get_engine_name(self):
    return self.engine_name
  
  def get_engine_list():
    return EngineSupport.engine_dict.keys()
  
  def get_engine(engine_name : str):
    return EngineSupport.engine_dict[engine_name]
  
  def start_export(self, project_dir : str):
    """Create an EngineExport object. Must be provided by backend
    
    Usually just create and return an EngineExport object
    """
    raise NotImplementedError()
  
  # --------------------------------------------------------
  # helper functions that backend can override
  #
  # The default pipeline will call these helper functions
  # --------------------------------------------------------
  
  def secure_overwrite(self, exportpath: str, write_callback, open_mode : str = 'wb'):
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
  
  # --------------------------------------------------------
  # functions for asset management
  # determines where we save asset files to, and any conversion we need to do
  
  # get list of formats supported by the engine. Return empty list if any format is supported
  # if we need conversion, default to use the first format in the list
  def get_supported_image_format_list(self) -> typing.List[str]:
    return []
  
  def get_supported_audio_format_list(self) -> typing.List[VNAudioFormat]:
    return []
  
  # Where to store an image for a paticular type
  # The image_name is expected to have correct suffix (i.e., we already did format conversion if needed)
  def get_background_image_path(self, project_dir, image_name : str) -> str:
    return os.path.join(project_dir, "images", "background", image_name)
  
  def get_sprite_image_path(self, project_dir, image_name : str) -> str:
    return os.path.join(project_dir, "images", "sprite", image_name)
  
  def get_side_image_path(self, project_dir, image_name : str) -> str:
    return os.path.join(project_dir, "images", "side_image", image_name)
  
  def get_foreground_item_image_path(self, project_dir, image_name : str) -> str:
    return os.path.join(project_dir, "images", "item", image_name)
  
  # where to store an audio for a paticular type. same assumptions (suffix already correct)
  def get_background_music_path(self, project_dir, audio_name : str) -> str:
    return os.path.join(project_dir, "audio", "bgm", audio_name)
  
  def get_sound_effect_path(self, project_dir, audio_name : str) -> str:
    return os.path.join(project_dir, "audio", "se", audio_name)
  
  def get_voice_path(self, project_dir, audio_name : str) -> str:
    return os.path.join(project_dir, "audio", "voice", audio_name)
  
  def _get_image_use_type(self, image:VNValue) -> str:
    """query all user to find what category (character sprite, side image, background, foreground item) does the image belongs to"""
    isSpriteUserFound = False # return string "sprite"
    isSideImageUserFound = False # return string "side"
    isBackgroundUserFound = False # return string "bg"
    isForegroundItemUserFound = False # return string "item"
    def updateFromUse(use: VNUse)->None:
      nonlocal isSpriteUserFound
      nonlocal isSideImageUserFound
      nonlocal isBackgroundUserFound
      nonlocal isForegroundItemUserFound
      user = use.get_user()
      if isinstance(user, VNSayerInfo):
        operand_index = use.get_operand_index()
        if isinstance(operand_index, tuple):
          key = operand_index[0]
          if key == VNSayerInfo.OperandType.CharacterSprite:
            isSpriteUserFound = True
          elif key == VNSayerInfo.OperandType.SideImage:
            isSideImageUserFound = True
      elif isinstance(user, VNUpdateBackgroundInst):
        isBackgroundUserFound = True
      elif isinstance(user, VNSelectionMatrixElement):
        matrix = user.get_parent()
        for use in matrix.get_uses():
          updateFromUse(use)
      else:
        # ignore unhandled uses
        pass
    
    for use in image.get_uses():
      updateFromUse(use)
    if isSpriteUserFound:
      return "sprite"
    if isSideImageUserFound:
      return "side"
    if isBackgroundUserFound:
      return "bg"
    return "item"
  
  def _get_audio_use_type(self, audio:VNValue) -> str:
    """return one of ["bgm", "voice", "se"] according to the use type"""
    isBGMUserFound = False
    isVoiceUserFound = False
    isSoundEffectUserFound = False
    def updateFromUse(use: VNUse)->None:
      nonlocal isBGMUserFound
      nonlocal isVoiceUserFound
      nonlocal isSoundEffectUserFound
      user = use.get_user()
      if isinstance(user, VNUpdateBGMInst):
        isBGMUserFound = True
      elif isinstance(user, VNSayInst):
        if use.get_operand_index() == VNSayInst.OperandType.Voice:
          isVoiceUserFound = True
      elif isinstance(user, VNSoundEffectInst):
        isSoundEffectUserFound = True
      elif isinstance(user, VNSelectionMatrixElement):
        matrix = user.get_parent()
        for use in matrix.get_uses():
          updateFromUse(use)
      else:
        # ignore unhandled uses
        pass
    for use in audio.get_uses():
      updateFromUse(use)
    if isBGMUserFound:
      return "bgm"
    if isVoiceUserFound:
      return "voice"
    return "se"
  
  def register_asset(self, obj: object, asset: VNValue, label, export_path : str, use_type : str):
    """Register an asset after it is saved. Default implementation assuming default EngineExport object, etc"""
    raise NotImplementedError()
  
  def lowerVNImageAsset(self, obj : object, image : VNImageAsset):
    supported_list = self.get_supported_image_format_list()
    imagedata = image.get_image()
    target_format = imagedata.format
    if not (len(supported_list) == 0 or imagedata.format in supported_list):
      # select the first format as the preferred
      target_format = supported_list[0]
    def saveimage(f):
      imagedata.save(f, format=target_format)
    
    # query all user to find what category (character sprite, side image, background, foreground item) does the image belongs to
    use_type = self._get_image_use_type(image)
    namespace_list = self.get_namespace_list(image, export_object=obj, image_use_type=use_type)
    basename = self.set_value_label(image, self.get_basename(image), obj, namespace_list)
    
    filename = basename + "." + str(target_format)
    project_dir = obj.get_project_directory()
    exportpath = ""
    if use_type == "sprite":
      exportpath = self.get_sprite_image_path(project_dir, filename)
    elif use_type == "side":
      exportpath = self.get_side_image_path(project_dir, filename)
    elif use_type == "bg":
      exportpath = self.get_background_image_path(project_dir, filename)
    elif use_type == "item":
      exportpath = self.get_foreground_item_image_path(project_dir, filename)
    else:
      raise NotImplementedError()
    self.secure_overwrite(exportpath, saveimage)
    self.register_asset(obj, image, basename, exportpath, use_type)
  
  def lowerVNLayeredImageAsset(self, obj : object, image : VNLayeredImageAsset):
    raise NotImplementedError()
  
  def lowerVNAudioAsset(self, obj : object, audio : VNAudioAsset):
    use_type = self._get_audio_use_type(audio)
    namespace_list = self.get_namespace_list(audio, export_object=obj, audio_use_type=use_type)
    basename = self.set_value_label(audio, self.get_basename(audio), obj, namespace_list)
    project_dir = obj.get_project_directory()
    exportpath = ""
    if use_type == "bgm":
      exportpath = self.get_background_music_path(project_dir, basename)
    elif use_type == "voice":
      exportpath = self.get_voice_path(project_dir, basename)
    elif use_type == "se":
      exportpath = self.get_sound_effect_path(project_dir, basename)
    exportpath = audio.save(exportpath, self.get_supported_audio_format_list())
    self.register_asset(obj, audio, basename, exportpath, use_type)

  # --------------------------------------------------------
  # functions for label management
  # we use the following model for determining name conflict:
  # 1. each VNValue can have one or more (string) tag, and each tag is a namespace
  # 2. each VNValue only has (at most) one unique label
  # 3. Our logic ensures that each label in each namespace maps to a unique VNValue
  # Example namespace tag include "file", "label", etc
  
  def get_basename(self, value : VNValue) -> str:
    # TODO update base_name after supporting backend label attributes
    return value.get_name()
  
  def get_reserved_name_set(self) -> typing.Set[str]:
    """What name should be avoided by all labels (e.g., reserved keywords)"""
    return {}
  
  def remove_illegal_characters_for_label(self, label : str, namespace_list : typing.List[str]) -> str:
    """Default implementation assumes that only alphanumeric characters and '_' can appear in a label. everything else are dropped"""
    result = re.sub(r'[^a-zA-Z0-9_]', '', label)
    if result.startswith('_'):
      result = result[1:]
    return result
  
  def get_namespace_list(self, value : VNValue, export_object : object, *args, **kwargs) -> typing.List[str]:
    """Return the list of namespaces that we need to avoid conflicts of
    
    This function is expected to use the type of value to make the judgement
    Overriding this function can also implement nested scope, e.g., having a per-function local label namespace for basicblocks
    
    Default implementation only distinguishes control flow names (label) and data flow names (file)
    """
    if isinstance(value, VNFunction) or isinstance(value, VNBasicBlock) or isinstance(value, VNInstruction):
      return ["label"]
    return ["data"]
  
  def get_unique_name(self, base_name, namespace_list : typing.List[str], name_map : typing.Dict[str, typing.Dict[str, VNValue]]) -> str:
    """Get a unique name that does not introduce naming conflict.
    
    The code assumes that adding _<number> suffix does not break the validity of the name.
    If the assumption does not hold, the backend needs to override this function
    """
    result = base_name
    number_suffix = 0
    reserved_names = self.get_reserved_name_set()
    
    def has_conflict(name : str, namespace_list : typing.List[str], name_map : typing.Dict[str, typing.Dict[str, VNValue]], reserved_names : typing.Set[str]) -> bool:
      for namespace in namespace_list:
        if namespace in name_map and name in name_map[namespace]:
          return True
      if name in reserved_names:
        return True
      return False
    
    while has_conflict(result, namespace_list, name_map, reserved_names):
      number_suffix += 1
      result = base_name + "_" + str(number_suffix)
    
    return result
  
  def set_value_label(self, value : VNValue, base_label : str, export_object, namespace_list : list = None) -> str:
    name_map = export_object.name_map
    element_map = export_object.element_map
    if namespace_list is None:
      namespace_list = self.get_namespace_list(value, export_object)
    base_label = self.remove_illegal_characters_for_label(base_label, namespace_list)
    if len(base_label) == 0:
      base_label = "anon"
    final_label = self.get_unique_name(base_label, namespace_list, name_map)
    for namespace in namespace_list:
      if namespace not in name_map:
        name_map[namespace] = {}
      name_map[namespace][final_label] = value
    element_map[value] = final_label
    return final_label
    


class EngineExport:
  """Base class for representing a (currently in process) project export. Counterpart of LLVM's MIR.
  
  Each backend should create a derived class from this base class and implement all required functions
  """
  
  engine : EngineSupport = None # EngineSupport object
  vnmodel : VNModel = None # model object
  project_dir : str = ""
  options : dict = {}
  
  def __init__(self, engine, project_dir) -> None:
    self.engine = engine
    self.project_dir = project_dir
    self.options = {}
    self.vnmodel = None
  
  def get_project_directory(self):
    return self.project_dir
  
  def set_option(self, key, value):
    """User should call this function to set options"""
    self.options[key] = value
  
  def get_option(self, key, default_value = None):
    return self.options.get(key, default_value)
  
  def add(self, module : typing.Any) -> None:
    """user should call this function to add components of game project"""
    if isinstance(module, VNModel):
      self.add_vnmodel(module)
      return
    raise NotImplementedError()
  
  def add_vnmodel(self, vnmodel : VNModel) -> None:
    if self.vnmodel is None:
      self.vnmodel = vnmodel
      return
    raise RuntimeError("more than one VNModel added")
  
  def _get_asset_lowering_dispatcher(self):
    return EngineAssetLoweringDispatcher(self.engine)
  
  def _default_preparation(self):
    """Backend can call this function to label functions, basic blocks, and lower assets"""
    # step 1: label all functions and basic blocks, and characters and sayers
    self.name_map : typing.Dict[str, typing.Dict[str, VNValue]] = {} # namespace -> [label -> VNValue]
    self.element_map : typing.Dict[VNValue, str] = {} # VNValue -> label
    
    # label all functions first
    for function in self.vnmodel.get_function_list():
      base_name = self.engine.get_basename(function)
      self.engine.set_value_label(function, base_name, self)
    # then all basic blocks
    # if a backend has local scope (e.g., renpy), we can create one namespace for each function (since now functions have unique labels)
    for function in self.vnmodel.get_function_list():
      for bb in function.get_basicblock_list():
        self.engine.set_value_label(bb, self.engine.get_basename(bb), self)
    
    # label character identity
    for identity in self.vnmodel.get_character_list():
      base_name = self.engine.get_basename(identity)
      self.engine.set_value_label(identity, base_name, self)
    # then all sayers
    for sayer in self.vnmodel.get_sayer_list():
      base_name = self.engine.get_basename(sayer)
      self.engine.set_value_label(sayer, base_name, self)
    
    # step 2: export all assets, including those unused by the current vnmodel (they may be needed by external code)
    # (if we want to drop unused assets, this should be done in IR)
    dispatcher = self._get_asset_lowering_dispatcher()
    for asset in self.vnmodel.get_asset_list():
      asset.visit(dispatcher, self)
    # done
  
  def do_export(self)-> typing.Any:
    """Call this function after all components are added. Return (backend-defined) warnings / errors
    
    All backends should provide their own driver implementation"""
    raise NotImplementedError()
      
  

# helper functions

def _get_label_name(name : str, type_prefix : str, scope_prefix: str, name_dict : typing.Dict[str, typing.Any], prefix : str = "") -> str:
  # get the base name
  base_label = re.sub(r'[^a-zA-Z0-9_]', '', name.replace(" ", "_"))
  
  # ensure the name does not start with number or underscore, or is not empty
  if len(base_label) > 0:
    frontchar = base_label[0]
    if frontchar == '_' or frontchar.isnumeric():
      base_label = type_prefix + "_" + base_label
  else:
    # we have no alphanumetic characters
    base_label = type_prefix + "_anon"
  
  # make sure it is unique
  # we may have duplicates
  
  # try to add scope prefix to resolve this
  if prefix + base_label in name_dict and len(scope_prefix) > 0:
    base_label = scope_prefix + "_" + base_label
  
  # now add the prefix; we no longer add prefix to base label
  if len(prefix) > 0:
    base_label = prefix + base_label
  
  # if not working, add a numeric suffix
  numeric_suffix = 0
  result = base_label
  while result in name_dict:
    numeric_suffix += 1
    result = base_label + '_' + str(numeric_suffix)
  
  # done
  return result

def label_branch_targets(model : VNModel, reserved_set : typing.Set[str] = [], include_basicblock : bool = True) -> typing.Dict[VNValue, str]:
  """Assign all functions (and optionally basic blocks) with a label that is:
  1. alphanumeric, non-empty
  2. does not start with underscore '_'
  3. unique across all functions and basic blocks
  
  We may need this labeling even when functions already has no duplicated label so avoid sanitization issue or reserved keywords
  """
  name_dict = {} # label -> element (used internally)
  elem_dict = {} # element -> label (for returning)
  
  # add all reserved keywords to name_dict
  for reserved in reserved_set:
    assert isinstance(reserved, str)
    name_dict[reserved] = None
  
  # actual work
  for func in model.get_function_list():
    func_label = _get_label_name(func.get_name(), "control_label", "", name_dict)
    name_dict[func_label] = func
    elem_dict[func] = func_label
    if include_basicblock:
      for bb in func.get_basicblock_list():
        bbname = bb.get_name()
        if len(bbname) == 0 and bb is func.get_entry_block():
          bbname = "entry"
        bb_label = _get_label_name(bbname, "control_label", func_label, name_dict)
        name_dict[bb_label] = bb
        elem_dict[bb] = bb_label
  
  return elem_dict

def label_basicblocks(func : VNFunction, reserved_set : typing.Set[str] = []) -> typing.Dict[VNBasicBlock, str]:
  """Assign labels to basic blocks with the same criteria as label_branch_targets:
  
  1. alphanumeric, non-empty
  2. does not start with underscore '_'
  3. unique
  """
  name_dict = {} # label -> element (used internally)
  elem_dict = {} # element -> label (for returning)
  
  # add all reserved keywords to name_dict
  for reserved in reserved_set:
    assert isinstance(reserved, str)
    name_dict[reserved]= None
    
  for bb in func.get_basicblock_list():
    bbname = bb.get_name()
    if len(bbname) == 0 and bb is func.get_entry_block():
      bbname = "entry"
    bb_label = _get_label_name(bbname, "label", "", name_dict, ".")
    name_dict[bb_label] = bb
    elem_dict[bb] = bb_label
  
  return elem_dict

def label_sayer_identity(model : VNModel, reserved_set : typing.Set[str] = []) -> typing.Dict[str, str]:
  """make sure all characters and sayers have (alphanumeric) labels"""
  name_dict = {}
  elem_dict = {}
  for reserved in reserved_set:
    assert isinstance(reserved, str)
    name_dict[reserved] = None
  for character in model.get_character_list():
    name = _get_label_name(character.get_name(), "character", "", name_dict)
    name_dict[name] = character
    elem_dict[character] = name
  for sayer in model.get_sayer_list():
    character = sayer.get_identity()
    character_label = elem_dict[character]
    name = _get_label_name(character_label + sayer.get_name(), "sayer", "", name_dict)
    name_dict[name] = sayer
    elem_dict[sayer] = name
  return elem_dict
  