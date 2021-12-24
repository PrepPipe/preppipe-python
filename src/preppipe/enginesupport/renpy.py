#!/usr/bin/env python3

from io import UnsupportedOperation
from warnings import warn
import os, sys
import typing
import re
import PIL.Image
import pathlib
from enum import Enum
import enum
from collections import deque
import preppipe.commontypes

from preppipe.vnmodel import *

from preppipe.enginesupport.enginesupport import *

# in VSCode: move the mouse to the left of "#region" to collapse it
# reference: https://www.renpy.org/doc/html/reserved.html
_renpy_reserved_names = {
#region
  # keywords from python
  'ArithmeticError',
  'AssertionError',
  'AttributeError',
  'BaseException',
  'BufferError',
  'BytesWarning',
  'DeprecationWarning',
  'EOFError',
  'Ellipsis',
  'EnvironmentError',
  'Exception',
  'False',
  'FloatingPointError',
  'FutureWarning',
  'GeneratorExit',
  'IOError',
  'ImportError',
  'ImportWarning',
  'IndentationError',
  'IndexError',
  'KeyError',
  'KeyboardInterrupt',
  'LookupError',
  'MemoryError',
  'NameError',
  'None',
  'NoneType',
  'NotImplemented',
  'NotImplementedError',
  'OSError',
  'OverflowError',
  'PPP',
  'PendingDeprecationWarning',
  'ReferenceError',
  'RuntimeError',
  'RuntimeWarning',
  'StandardError',
  'StopIteration',
  'SyntaxError',
  'SyntaxWarning',
  'SystemError',
  'SystemExit',
  'TabError',
  'True',
  'TypeError',
  'UnboundLocalError',
  'UnicodeDecodeError',
  'UnicodeEncodeError',
  'UnicodeError',
  'UnicodeTranslateError',
  'UnicodeWarning',
  'UserWarning',
  'ValueError',
  'Warning',
  'ZeroDivisionError',
  'abs',
  'all',
  'any',
  'apply',
  'basestring',
  'bin',
  'bool',
  'buffer',
  'bytearray',
  'bytes',
  'callable',
  'chr',
  'classmethod',
  'cmp',
  'coerce',
  'compile',
  'complex',
  'copyright',
  'credits',
  'delattr',
  'dict',
  'dir',
  'divmod',
  'enumerate',
  'eval',
  'execfile',
  'exit',
  'file',
  'filter',
  'float',
  'format',
  'frozenset',
  'getattr',
  'globals',
  'hasattr',
  'hash',
  'help',
  'hex',
  'id',
  'input',
  'int',
  'intern',
  'isinstance',
  'issubclass',
  'iter',
  'len',
  'license',
  'list',
  'locals',
  'long',
  'map',
  'max',
  'memoryview',
  'min',
  'next',
  'object',
  'oct',
  'open',
  'ord',
  'pow',
  'print',
  'property',
  'quit',
  'range',
  'raw_input',
  'reduce',
  'reload',
  'repr',
  'reversed',
  'round',
  'set',
  'setattr',
  'slice',
  'sorted',
  'staticmethod',
  'str',
  'sum',
  'super',
  'tuple',
  'type',
  'unichr',
  'unicode',
  'vars',
  'xrange',
  'zip',
  # keywords from RenPy
  'ADVCharacter',
  'ADVSpeaker',
  'Action',
  'AddToSet',
  'Alpha',
  'AlphaBlend',
  'AlphaDissolve',
  'AlphaMask',
  'AnimatedValue',
  'Animation',
  'At',
  'Attribute',
  'AudioData',
  'AudioPositionValue',
  'Bar',
  'BarValue',
  'Borders',
  'BrightnessMatrix',
  'Button',
  'Call',
  'Character',
  'Color',
  'ColorMatrix',
  'ColorizeMatrix',
  'ComposeTransition',
  'Composite',
  'Condition',
  'ConditionGroup',
  'ConditionSwitch',
  'Confirm',
  'ContrastMatrix',
  'Crop',
  'CropMove',
  'DictEquality',
  'DictInputValue',
  'DictValue',
  'DisableAllInputValues',
  'Dissolve',
  'Drag',
  'DragGroup',
  'DynamicCharacter',
  'DynamicDisplayable',
  'DynamicImage',
  'EndReplay',
  'FactorZoom',
  'Fade',
  'FieldEquality',
  'FieldInputValue',
  'FieldValue',
  'FileAction',
  'FileCurrentPage',
  'FileCurrentScreenshot',
  'FileDelete',
  'FileJson',
  'FileLoad',
  'FileLoadable',
  'FileNewest',
  'FilePage',
  'FilePageName',
  'FilePageNameInputValue',
  'FilePageNext',
  'FilePagePrevious',
  'FileSave',
  'FileSaveName',
  'FileScreenshot',
  'FileSlotName',
  'FileTakeScreenshot',
  'FileTime',
  'FileUsedSlots',
  'Fixed',
  'Flatten',
  'FontGroup',
  'Frame',
  'Function',
  'Gallery',
  'GamepadCalibrate',
  'GamepadExists',
  'GetCharacterVolume',
  'GetTooltip',
  'Grid',
  'HBox',
  'Help',
  'Hide',
  'HideInterface',
  'HueMatrix',
  'IdentityMatrix',
  'If',
  'Image',
  'ImageButton',
  'ImageDissolve',
  'ImageReference',
  'Input',
  'InputValue',
  'InvertMatrix',
  'InvertSelected',
  'Jump',
  'Language',
  'LayeredImage',
  'LayeredImageProxy',
  'Live2D',
  'LiveComposite',
  'LiveCrop',
  'LiveTile',
  'MainMenu',
  'Matrix',
  'MixerValue',
  'Model',
  'Motion',
  'MouseDisplayable',
  'MouseMove',
  'Move',
  'MoveFactory',
  'MoveIn',
  'MoveOut',
  'MoveTransition',
  'Movie',
  'MultiPersistent',
  'MultipleTransition',
  'MusicRoom',
  'NVLCharacter',
  'NVLSpeaker',
  'NoRollback',
  'Notify',
  'Null',
  'NullAction',
  'OffsetMatrix',
  'OldMoveTransition',
  'OpacityMatrix',
  'OpenURL',
  'PY2',
  'Pan',
  'ParameterizedText',
  'Particles',
  'Pause',
  'PauseAudio',
  'Pixellate',
  'Placeholder',
  'Play',
  'PlayCharacterVoice',
  'Position',
  'Preference',
  'PushMove',
  'Queue',
  'QueueEvent',
  'QuickLoad',
  'QuickSave',
  'Quit',
  'RemoveFromSet',
  'Replay',
  'RestartStatement',
  'Return',
  'Revolve',
  'RevolveInOut',
  'RollForward',
  'Rollback',
  'RollbackToIdentifier',
  'RotateMatrix',
  'RotoZoom',
  'RoundRect',
  'SaturationMatrix',
  'ScaleMatrix',
  'ScreenVariableInputValue',
  'ScreenVariableValue',
  'Screenshot',
  'Scroll',
  'SelectedIf',
  'SensitiveIf',
  'SepiaMatrix',
  'Set',
  'SetCharacterVolume',
  'SetDict',
  'SetField',
  'SetLocalVariable',
  'SetMixer',
  'SetMute',
  'SetScreenVariable',
  'SetVariable',
  'SetVoiceMute',
  'Show',
  'ShowMenu',
  'ShowTransient',
  'ShowingSwitch',
  'SideImage',
  'SizeZoom',
  'Skip',
  'SnowBlossom',
  'Solid',
  'Speaker',
  'SplineMotion',
  'Sprite',
  'SpriteManager',
  'Start',
  'StaticValue',
  'Stop',
  'Style',
  'StylePreference',
  'SubTransition',
  'Swing',
  'Text',
  'TextButton',
  'Tile',
  'TintMatrix',
  'ToggleDict',
  'ToggleField',
  'ToggleLocalVariable',
  'ToggleMute',
  'ToggleScreen',
  'ToggleScreenVariable',
  'ToggleSetMembership',
  'ToggleVariable',
  'ToggleVoiceMute',
  'Tooltip',
  'Transform',
  'TransformMatrix',
  'VBox',
  'VariableInputValue',
  'VariableValue',
  'Viewport',
  'VoiceInfo',
  'VoiceReplay',
  'Window',
  'With',
  'XScrollValue',
  'YScrollValue',
  'Zoom',
  'ZoomInOut',
  'absolute',
  'absolute_import',
  'achievement',
  'adv',
  'alt',
  'anim',
  'audio',
  'bchr',
  'blinds',
  'bord',
  'build',
  'center',
  'centered',
  'color',
  'config',
  'default',
  'default_transition',
  'define',
  'director',
  'dissolve',
  'division',
  'ease',
  'easeinbottom',
  'easeinleft',
  'easeinright',
  'easeintop',
  'easeoutbottom',
  'easeoutleft',
  'easeoutright',
  'easeouttop',
  'extend',
  'fade',
  'gui',
  'hpunch',
  'hyperlink_function',
  'hyperlink_sensitive',
  'hyperlink_styler',
  'iap',
  'icon',
  'im',
  'irisin',
  'irisout',
  'layeredimage',
  'layout',
  'left',
  'library',
  'main_menu',
  'menu',
  'mouse_visible',
  'move',
  'moveinbottom',
  'moveinleft',
  'moveinright',
  'moveintop',
  'moveoutbottom',
  'moveoutleft',
  'moveoutright',
  'moveouttop',
  'name_only',
  'narrator',
  'nvl',
  'nvl_clear',
  'nvl_clear_next',
  'nvl_erase',
  'nvl_hide',
  'nvl_list',
  'nvl_menu',
  'nvl_narrator',
  'nvl_show',
  'nvl_show_core',
  'nvl_variant',
  'nvl_window',
  'offscreenleft',
  'offscreenright',
  'os',
  'persistent',
  'pixellate',
  'predict_menu',
  'predict_say',
  'preferences',
  'print_function',
  'pushdown',
  'pushleft',
  'pushright',
  'pushup',
  'pygame_sdl2',
  'pystr',
  'python_dict',
  'python_list',
  'python_object',
  'python_set',
  'renpy',
  'reset',
  'right',
  'save_name',
  'say',
  'shaderdoc',
  'slideawaydown',
  'slideawayleft',
  'slideawayright',
  'slideawayup',
  'slidedown',
  'slideleft',
  'slideright',
  'slideup',
  'squares',
  'store',
  'style',
  'suppress_overlay',
  'sv',
  'swing',
  'sys',
  'theme',
  'tobytes',
  'toggle_skipping',
  'top',
  'topleft',
  'topright',
  'truecenter',
  'ui',
  'unicode_literals',
  'updater',
  'vcentered',
  'voice',
  'voice_can_replay',
  'voice_replay',
  'voice_sustain',
  'vpunch',
  'wipedown',
  'wipeleft',
  'wiperight',
  'wipeup',
  'with_statement',
  'zoomin',
  'zoominout',
  'zoomout',
  # special labels (https://www.renpy.org/doc/html/label.html#special-labels)
  'start',
  'quit',
  'after_load',
  'splashscreen',
  'before_main_menu',
  'main_menu',
  'after_warp',
  'hide_windows',
  # dummy one
  ''
#endregion
}

class _RenpyInstrOpcode(Enum):
  RIO_Invalid = 0
  
  # TaggedName ::= <Tag> [<Attr>]*
  
  # metadata
  RO_Character = enum.auto()   # define <Op#1 sayer_label> = Character(<Op#2 name_text>, voice_tag=<Op#0 character_label>, <*op>...)
  
  # scene play
  RO_Scene = enum.auto()       # scene <TaggedName>
  RO_Show = enum.auto()        # show <TaggedName> [at left|right|center|truecenter]
  RO_Hide = enum.auto()        # hide <Tag>
  RO_With = enum.auto()        # with dissolve|fade|None
  RO_PlayMusic = enum.auto()   # play music "<music_filename>"
  RO_Voice = enum.auto()       # voice "<voice_filename>"
  
  RO_Pause = enum.auto()       # pause <time_s>
  
  RO_Image = enum.auto()       # image <ImageDef : id> = "<image_filename>" (global scope only)
  RO_Say = enum.auto()         # ["<SayerName>" / <SayerDef>] "<Text>"
  
  # control flow
  RO_Return = enum.auto()      # return
  RO_Menu = enum.auto()        # menu:\n [\t"<choice_text>"\n\t\tjump <dest>\n]+ (choice: +1 indent, jump: +2 indent)
  RO_Jump = enum.auto()        # jump <dest>
  RO_Call = enum.auto()        # call <dest>

class RenpySupport(EngineSupport):
  def _get_cmd_str(instr : EMInstruction) -> str:
    single_operand_instr_dict = {
      _RenpyInstrOpcode.RO_Scene: "scene",
      _RenpyInstrOpcode.RO_Show: "show",
      _RenpyInstrOpcode.RO_Hide: "hide",
      _RenpyInstrOpcode.RO_PlayMusic: "play music",
      _RenpyInstrOpcode.RO_Voice: "voice",
      _RenpyInstrOpcode.RO_Jump: "jump",
      _RenpyInstrOpcode.RO_Call: "call"
    }
    no_operand_instr_dict = {
      _RenpyInstrOpcode.RO_Return: "return"
    }
    # no operand case
    if instr.get_opcode() in no_operand_instr_dict:
      return no_operand_instr_dict[instr.get_opcode()]
    
    # single operand case
    if instr.get_opcode() in single_operand_instr_dict:
      operand = instr.get_operand(0)
      assert isinstance(operand, str)
      return single_operand_instr_dict[instr.get_opcode()] + " " + operand
    
    # other
    if instr.get_opcode() == _RenpyInstrOpcode.RO_Character:
      return "define {sayer_label} = Character({sayer_nametext}, voice_tag={character_label})".format(
        **instr.get_operand_dict([
          "character_label",
          "sayer_label",
          "sayer_nametext"
      ]))
    
    if instr.get_opcode() == _RenpyInstrOpcode.RO_Say:
      sayer = instr.get_operand(0)
      sayer_prefix = ""
      if sayer is not None:
        sayer_prefix = sayer + " "
      return sayer_prefix + '"' + instr.get_operand(1) + '"'
    
    if instr.get_opcode() == _RenpyInstrOpcode.RO_Image:
      refpath = instr.get_operand(0)
      tag_list = instr.get_operand(1)
      return "image " + " ".join(tag_list) + " = \"" + refpath + '"'
    
    raise RuntimeError("Unsupported instruction type:" + str(instr))
    
  def _sanitize(text: str) -> str:
    result = ""
    for ch in text:
      if ch == '[':
        result += "[["
      elif ch == '{':
        result += "{{"
      elif ch == '"':
        result += "\\\""
      elif ch == "'":
        result += "\\\'"
      elif ch == "\\":
        result += "\\\\"
      else:
        result += ch
    return result
  
  def _get_label_name(name : str) -> str:
    result = re.sub(r'[^a-zA-Z0-9_]', '', name)
    if result.startswith('_'):
      result = result[1:]
    if len(result) == 0:
      result = "anon"
    return result
  
  def _get_unique_name(base_name : str, unique_dict : typing.Dict[str, typing.Any]) -> str :
    result = base_name
    number_suffix = 0
    while result in unique_dict or result in _renpy_reserved_names:
      number_suffix += 1
      result = base_name + "_" + str(number_suffix)
    return result
  
  def _get_pil_image_extension(image) -> str:
    return str(image.format)
  
  def _get_sanitized_say_text_str(text : VNValue, attributes : typing.Dict[VNTextAttribute, typing.Any]) -> str:
    """Render the text block into a string for Renpy's say command. if attributes is not None, this will be used as the basis"""
    if isinstance(text, VNTextLiteralFragment):
      # make sure actual_attr is not None
      actual_attr = attributes
      if attributes is None:
        actual_attr = text.get_attributes()
      if actual_attr is None:
        actual_attr = {}
      if len(text.get_attributes()) > 0:
        if len(attributes) == 0:
          actual_attr = text.get_attributes()
        else:
          actual_attr = {**attributes, **text.get_attributes()}
      curText = RenpySupport._sanitize(text.get_text())
      for attr, value in actual_attr.items():
        if attr == VNTextAttribute.Bold:
          curText = "{b}" + curText + "{/b}"
          continue
        if attr == VNTextAttribute.Italic:
          curText = "{i}" + curText + "{/i}"
          continue
        if attr == VNTextAttribute.Size:
          # we will support it, but not now
          raise RuntimeError("Size attribute not supported yet")
        if attr == VNTextAttribute.TextColor:
          curText = "{color=" + value.getString() + "}" + curText + "{/color}"
          continue
        if attr == VNTextAttribute.BackgroundColor:
          # do nothing (unsupported)
          continue
        if attr == VNTextAttribute.RubyText:
          curText = "{rb}" + curText + "{/rb}{rt}" + value + "{/rt}"
          continue
        if attr == VNTextAttribute.KeywordReference:
          # we will support it, but not now
          raise RuntimeError("Keyword reference attribute not supported yet")
        # we should have executed one of these branches
        raise RuntimeError("Unknown text attribute")
      return curText
    elif isinstance(text, list):
      curText = ""
      for piece in text:
        curText += RenpySupport._get_sanitized_say_text_str(piece, attributes)
      return curText
    else:
      raise RuntimeError("Unexpected text type")
  
  def export(vnmodel : VNModel, game_dir : str, **kwarg) -> None:
    """Export the visual novel model into a Renpy project game directory (should be the <project>/game directory)
    
    We will create files under these directories inside game_dir:
      ./scripts/: all game scripts go there; the entrypoint defaults to "start"
      ./audio/: all audio assets go there; we will use the following subdirectories:
        ./audio/bgm: all background musics go there
        ./audio/voice: all voice go there
        ./audio/se: all sound effects go there
      ./images/: all image assets go there:
        ./images/background: all background image goes there
        ./images/sprite: all other (non-background) images
    
    Config can have following keys:
      "rootscript": str, specify the path (relative from game_dir) of the root script.
        defaults to overwrite the "script.rpy" from RenPy project template
      "entryfunction": str, specify the entry function name of root script entry point
        defaults to "start"
        If this is explicitly set to None, we will not create a start label
      "indent": int, specify how many whitespace do we prepend for each line
    """
    
    
    
    
    rootscript = kwarg.get("rootscript", "script.rpy")
    entryfunction = kwarg.get("entryfunction", "start")
    indent = kwarg.get("indent", 4)
    
    rootscript_name = os.path.join(game_dir, rootscript)
    rootscript_tmpname = rootscript_name + ".tmp"
    
    # assert os.path.dirname(game_dir) == "game"
    assert not vnmodel.empty()
    
    
    emitted_warning_set : typing.Set[str] = {}
    def warn_once(wname : str, text : str) -> None:
      nonlocal emitted_warning_set
      if wname in emitted_warning_set:
        return
      emitted_warning_set.add(wname);
      warn(wname + ": " + text)
    
    # step 1: lowering
    # convert the VNModel to Renpy specific constructs
    
    # control flow lowering: we create one label for each (function x basic block), and leave the start label to directly branch to the entry function
    initBlock = EMBasicBlock("init")
    
    # since renpy does not have functions, we flatten all functions into basic blocks
    function_label_dict = label_branch_targets(vnmodel, _renpy_reserved_names)
    
    character_dict = label_sayer_identity(vnmodel, _renpy_reserved_names)
    assert set(function_label_dict.values()).isdisjoint(character_dict.values())
    
    image_dict = {} # "<tag>" -> { "<label_name>" -> "<ref_path>" }
    materialized_images = {} # VNValue -> "<ref_path>"
    def materialize_image(image : VNValue, image_tag : str) -> str:
      """write the image into the corresponding directory and store the reference"""
      
      nonlocal image_dict
      nonlocal materialized_images
      
      # early exit if we already materialized it
      if image in materialized_images:
        return materialized_images[image]
      
      # this is a new image and let's handle it
      if isinstance(image, VNImageAsset):
        imagedata = image.get_image()
        if image_tag not in image_dict:
          image_dict[image_tag] = {}
        
        subdict = image_dict[image_tag]
        base_name = RenpySupport._get_unique_name(RenpySupport._get_label_name(image.get_name()), subdict)
        exportpath = ""
        if imagedata.format not in ['WEBP', 'PNG', 'JPEG']:
          # we need to save the image in another format (just always png for now)
          exportpath = os.path.join(game_dir, "images", image_tag, base_name + ".png")
          tmpfilepath = exportpath + ".tmp"
          parent_path = pathlib.Path(tmpfilepath).parent
          os.makedirs(parent_path, exist_ok=True)
          with open(tmpfilepath, 'wb') as f:
            imagedata.save(f, format = 'PNG')
          os.rename(tmpfilepath, exportpath)
        else:
          # just use the current format
          exportpath = os.path.join(game_dir, "images", image_tag, base_name + "." + RenpySupport._get_pil_image_extension(imagedata))
          tmpfilepath = exportpath + ".tmp"
          parent_path = pathlib.Path(tmpfilepath).parent
          os.makedirs(parent_path, exist_ok=True)
          with open(tmpfilepath, 'wb') as f:
            imagedata.save(f, format = imagedata.format)
          os.rename(tmpfilepath, exportpath)
        # now the image file is exported to exportpath
        refpath = os.path.relpath(exportpath, game_dir)
        materialized_images[image] = refpath
        subdict[base_name] = refpath
        return refpath
      else:
        raise RuntimeError("Unsupported image type")
    
    def declare_image(refpath : str, tag_list : typing.List[str]) -> None:
      decl = EMInstruction(_RenpyInstrOpcode.RO_Image, [refpath, tag_list])
      initBlock.add_instruction(decl)
    
    sprite_image_dict = {} # tuple<sprite image, character_label> -> result list
    character_label_dict = {} # character_label -> {second_label -> sprite image}
    def materialize_character_sprite(sprite_image: VNValue, character_label: str) -> typing.List[str]:
      """make sure the sprite image is materalized
      
      also create an Image instruction that declares this image
      """
      # for simplicity, we only use at most one attribute
      # search in cache first
      key_tuple = (sprite_image, character_label)
      if key_tuple in sprite_image_dict:
        return sprite_image_dict[key_tuple]
      
      # first, make sure the image is materialized
      image = materialize_image(sprite_image, "sprite")
      # we expect image to be a ref_path to the image file
      # create a label for that image
      basename_withext = os.path.basename(image)
      basename = os.path.splitext(basename_withext)[0]
      second_label = basename
      # crop the character_label if present
      if second_label.startswith(character_label):
        second_label = second_label[len(character_label):]
      if second_label.startswith("_"):
        second_label = second_label[1:]
      if len(second_label) > 0 and second_label[0].isnumeric():
        second_label = "sprite_" + second_label
      
      # ensure second_label is unique
      if character_label not in character_label_dict:
        character_label_dict[character_label] = {}
      
      label_dict = character_label_dict[character_label]
      number_suffix = 0
      base_second_label = second_label
      while second_label in label_dict:
        number_suffix += 1
        second_label = base_second_label + "_" + str(number_suffix)
      label_dict[second_label] = sprite_image
      result = [character_label, second_label]
      sprite_image_dict[key_tuple] = result
      declare_image(image, result)
      return result
    
    materialized_background_image = {} # background image -> tag list ("bg", xxxx)
    background_image_dict = {} # second label -> image
    def materialize_background_image(image : VNValue) -> typing.List[str]:
      if image in materialized_background_image:
        return materialized_background_image[image]
      
      # make sure it is materialized first
      refpath = materialize_image(image, "bg")
      
      # generate a name for the background
      basename_withext = os.path.basename(refpath)
      basename = os.path.splitext(basename_withext)[0]
      result = ["bg", basename]
      declare_image(refpath, result)
      return result
    
    materialized_audio = {} # VNValue -> <ref_path>
    def materialize_audio(audio : VNValue, audio_tag : str) -> str:
      # supported formats: https://www.renpy.org/doc/html/audio.html
      assert audio_tag in ["bgm", "voice", "se"]
      nonlocal materialized_audio
      if audio in materialized_audio:
        return materialized_audio[audio]
      if isinstance(audio, VNAudioAsset):
        base_name = RenpySupport._get_unique_name(RenpySupport._get_label_name(audio.get_name()), materialized_audio)
        exportpath = os.path.join(game_dir, "audio", audio_tag, base_name)
        abspath = audio.save(exportpath, [VNAudioFormat.OGG, VNAudioFormat.MP3, VNAudioFormat.WAV])
        return os.path.relpath(abspath, start = game_dir)
      else:
        raise RuntimeError("Unhandled audio type")
    
    def quote(text : str) -> str:
      return '"' + text + '"'
    
    class ActiveSayerInfo:
      # the information we maintained for each sayer
      
      character: str = ""
      side_image : str = ""
      
      def __init__(self, character_sprite, side_image):
        # we expect the character_sprite to be the list for the sprite image (e.g., ["Alice", "happy"])
        # we only need the first part for hiding the character, etc
        self.character = character_sprite[0]
        self.side_image = side_image
    
    # add declaration of all sayers
    for sayer in vnmodel.get_sayer_list():
      instr = EMInstruction(_RenpyInstrOpcode.RO_Character)
      character = sayer.get_identity()
      # character label, sayer label, sayer name text
      instr.add_operand(quote(character_dict[character]))
      instr.add_operand(character_dict[sayer]) # sayer label should not be quoted
      nametext = "None"
      if sayer.get_name_text() is not None:
        nametext = quote(RenpySupport._get_sanitized_say_text_str(sayer.get_name_text().get_fragment_list(""), {}))
      instr.add_operand(nametext)
      if sayer.get_default_side_image() is not None:
        # side_image = sayer.get_default_side_image()
        # side_image_expr = materialize_image(side_image)
        # TODO support side image
        pass
      initBlock.add_instruction(instr)
    
    rpybb_list : typing.List[EMBasicBlock] = []
    
    for func in vnmodel.get_function_list():
      func_label = function_label_dict[func]
      
      # we traverse along the control flow edges to visit the function
      # because we haven't implemented branch yet, this is not used for now
      traversed_bb_set = {}
      bb_worklist = deque()
      
      bb_worklist.append(func.get_entry_block())
      
      bb_map : typing.Dict[VNBasicBlock, EMBasicBlock] = {}
      
      # we use the function label as the entry block name
      # all the rest of blocks use local label
      bb_name_map = label_basicblocks(func, {"entry"})
      bb_name_map[func.get_entry_block()] = func_label
      
      # sayerdecl/sayerupdate/sayerphi (SSA node) -> ActiveSayerInfo
      sayer_dict = {}
      
      def handle_sayer_update(instr):
        nonlocal sayer_dict
        nonlocal character_dict
        nonlocal rpybb
        sayerinfo = instr.get_sayer_info()
        sayerstate = instr.get_sayer_state()
        character = sayerinfo.get_identity()
        # character_label = character_dict[character]
        sayer_label = character_dict[sayerinfo]
        # we try to access the side image and character_sprite
        # if any of them is available, we materialize the image (export to output directory) and record that
        # if we have the sprite, we insert a show command
        character_sprite = sayerinfo.get_character_sprite(sayerstate)
        character_sprite_expr = None
        if character_sprite is not None:
          character_sprite_expr = materialize_character_sprite(character_sprite, sayer_label)
          showinstr = EMInstruction(_RenpyInstrOpcode.RO_Show)
          operand = character_sprite_expr
          if isinstance(character_sprite_expr, list):
            operand = " ".join(character_sprite_expr)
          showinstr.set_operand_list([operand])
          rpybb.add_instruction(showinstr)
        # we don't handle side image here
        # side_image = sayerinfo.get_side_image(sayerstate)
        # side_image_expr = None
        # if side_image is not None:
        #   side_image_expr = materialize_image(side_image)
        sayerinfo_tosave = ActiveSayerInfo(character_sprite_expr, None)
        sayer_dict[instr] = sayerinfo_tosave
      
      while len(bb_worklist) > 0:
        bb = bb_worklist.popleft()
        bb_label = bb_name_map[bb]
        rpybb = EMBasicBlock(bb_label)
        bb_map[bb] = rpybb
        rpybb_list.append(rpybb)
        
        for instr in bb.get_instruction_list():
          if isinstance(instr, VNUpdateBackground):
            background = instr.get_background()
            background_expr = materialize_background_image(background)
            operand = background_expr
            if isinstance(background_expr, list):
              operand = " ".join(background_expr)
            sceneinstr = EMInstruction(_RenpyInstrOpcode.RO_Scene)
            sceneinstr.set_operand_list([operand])
            rpybb.add_instruction(sceneinstr)
          elif isinstance(instr, VNSayerDeclInstr):
            handle_sayer_update(instr)
          elif isinstance(instr, VNSayerUpdateInstr):
            handle_sayer_update(instr)
          elif isinstance(instr, VNUpdateBGMInstr):
            bgm = instr.get_first_bgm()
            bgm_expr = materialize_audio(bgm, "bgm")
            bgminstr = EMInstruction(_RenpyInstrOpcode.RO_PlayMusic)
            bgminstr.add_operand(quote(bgm_expr))
            rpybb.add_instruction(bgminstr)
          elif isinstance(instr, VNSayInst):
            voice = instr.get_voice()
            if voice is not None:
              voice_expr = materialize_audio(voice, "voice")
              voiceinstr = EMInstruction(_RenpyInstrOpcode.RO_Voice)
              voiceinstr.add_operand(quote(voice_expr))
              rpybb.add_instruction(voiceinstr)
            # TODO we currently don't support multiple languages yet
            # TODO make use of attributes from sayer
            sayer = instr.get_sayer()
            # as long as we have a narrator, the sayer is not none
            sayer_operand = None
            if sayer is not None:
              # add the sayer label operand
              sayerinfo = sayer
              if not isinstance(sayerinfo, VNSayerInfo):
                # sayer decl or update
                sayerinfo = sayer.get_sayer_info()
              sayer_operand = character_dict[sayerinfo]
            
            # TODO support default text style
            text_frag_list = instr.get_text().get_fragment_list("")
            text_str = RenpySupport._get_sanitized_say_text_str(text_frag_list, {})
            sayinstr = EMInstruction(_RenpyInstrOpcode.RO_Say)
            sayinstr.set_operand_list([sayer_operand, text_str])
            rpybb.add_instruction(sayinstr)
          elif isinstance(instr, VNReturnInst):
            rpybb.add_instruction(EMInstruction(_RenpyInstrOpcode.RO_Return))
          elif isinstance(instr, VNCallInst):
            rpybb.add_instruction(EMInstruction(_RenpyInstrOpcode.RO_Call, [function_label_dict[instr.get_callee()]]))
          else:
            raise RuntimeError("Unsupported VNInstruction type: " + str(type(instr)))
    # OK, abstract model done
    # TODO check & opt
    # codegen
    def write_block(dest, bb : EMBasicBlock, indent: int, write_label : bool = True) -> None:
      if write_label:
        s.write("label " + bb.get_label() + ":\n")
      for instr in bb.get_instruction_list():
        s.write(" "*indent)
        command = RenpySupport._get_cmd_str(instr)
        s.write(command)
        s.write("\n")
    
    entryname = ""
    if entryfunction is not None:
      entryname = function_label_dict[vnmodel.get_function(entryfunction)]
    
    parent_path = pathlib.Path(rootscript_tmpname).parent
    os.makedirs(parent_path, exist_ok=True)
    with open(rootscript_tmpname, "w") as s:
      # step 1: write init block
      write_block(s, initBlock, 0, False)
      s.write("\n")
      # step 2: write all function blocks
      for bb in rpybb_list:
        write_block(s, bb, indent)
        s.write("\n")
      # step 3: write a branch to entry
      if len(entryname) > 0:
        s.write("label start:\n" + " "*indent + "jump " + entryname + "\n")
      # done!
    os.rename(rootscript_tmpname, rootscript_name)
  