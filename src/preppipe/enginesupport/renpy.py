# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

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

from ..vnmodel import *
from .enginesupport import *

class RenpyExport(EngineExport):
  image_decl : typing.Dict[VNValue, str] # value -> export path
  audio_decl : typing.Dict[VNValue, str] # value -> export path
  function_list : typing.List[EMFunction]
  init_block : EMBasicBlock
  
  def __init__(self, engine, project_dir) -> None:
    super().__init__(engine, project_dir)
    self.image_decl = {}
    self.audio_decl = {}
    self.function_list = []
    self.init_block = None
  
  def do_export(self)-> typing.Any:
    return self.engine.export_pipeline(self)

class RenpySupport(EngineSupport):
  class _Opcode(Enum):
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
  instance = None

  def __init__(self) -> None:
    super().__init__("renpy")

  def get():
    if RenpySupport.instance is None:
      RenpySupport.instance = RenpySupport()
    return RenpySupport.instance
  
  def initialize():
    RenpySupport.get()
  
  def start_export(self, project_dir: str) -> RenpyExport:
    return RenpyExport(self, project_dir)
  
  def get_reserved_name_set(self) -> typing.Set[str]:
    return RenpySupport._renpy_reserved_names
  
  def get_supported_image_format_list(self) -> typing.List[str]:
    return ['PNG', 'JPEG', 'WEBP']
  
  def get_supported_audio_format_list(self) -> typing.List[VNAudioFormat]:
    return [VNAudioFormat.OGG, VNAudioFormat.MP3, VNAudioFormat.WAV]
  
  def register_asset(self, obj: RenpyExport, asset: VNValue, label : str, export_path : str, use_type : str):
    # for each image asset registered, we create an Image statement declaring it
    # we don't declare audios; just reference them by full path
    obj.element_map[asset] = label
    export_path = os.path.relpath(export_path, obj.get_project_directory())
    ty = asset.get_type()
    if ty.is_image_type():
      obj.image_decl[asset] = export_path
      if use_type == "bg":
        obj.init_block.add_instruction(EMInstruction(RenpySupport._Opcode.RO_Image, [["bg", label], export_path]))
      return
    if ty.is_audio_type():
      obj.audio_decl[asset] = export_path
      return
    raise NotImplementedError()
  
  def get_namespace_list(self, value: VNValue, export_object : RenpyExport, *args, **kwargs) -> typing.List[str]:
    ty = value.get_type()
    if ty.is_function_type():
      return ["function"]
    if ty.is_basicblock_type():
      assert isinstance(value, VNBasicBlock)
      return ["bb_" + export_object.element_map[value.get_parent()]]
    if ty.is_audio_type():
      return ["audio_"+ kwargs["audio_use_type"]]
    if ty.is_image_type():
      return ["image_"+kwargs["image_use_type"]]
    if ty.is_sayer_type() or isinstance(value, VNCharacterIdentity):
      return ["sayer"]
    return ["misc"]
  
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
  
  def _get_sanitized_say_text_str(text : VNValue, attributes : typing.Dict[VNTextAttribute, typing.Any]) -> str:
    """Render the text block into a string for Renpy's say command. if attributes is not None, this will be used as the basis"""
    if isinstance(text, VNTextFragment):
      # make sure actual_attr is not None
      actual_attr = {}
      if attributes is not None:
        actual_attr = attributes
      
      cur_style = text.get_styles()
      if len(cur_style) > 0:
        actual_attr = {**actual_attr, **cur_style}
      
      showText = text.get_text()
      curText = ""
      if isinstance(showText, VNStringLiteral):
        curText = RenpySupport._sanitize(showText.get_value())
      else:
        raise NotImplementedError()
      
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
        # we should have executed one of these branches
        raise RuntimeError("Unknown text attribute")
      ruby = text.get_attribute(RubyTextAttribute)
      if ruby is not None:
        assert isinstance(ruby, RubyTextAttribute)
        curText = "{rb}" + curText + "{/rb}{rt}" + RenpySupport._sanitize(ruby.get_text()) + "{/rt}"
      return curText
    elif isinstance(text, VNTextBlock):
      curText = ""
      for piece in text.get_fragment_list():
        curText += RenpySupport._get_sanitized_say_text_str(piece, attributes)
      return curText
    elif isinstance(text, list):
      curText = ""
      for piece in text:
        curText += RenpySupport._get_sanitized_say_text_str(piece, attributes)
      return curText
    else:
      raise RuntimeError("Unexpected text type")
  
  class EMBuilder(VNModelVisitor):
    """Build EM"""
    obj : RenpyExport
    
    def __init__(self, obj : RenpyExport) -> None:
      super().__init__(True)
      self.obj = obj
    
    # entry point
    def build(self):
      model = self.obj.vnmodel
      for func in model.get_function_list():
        cur_func = EMFunction(self.obj.element_map[func])
        self.obj.function_list.append(cur_func)
        for bb in func.get_basicblock_list():
          cur_block = EMBasicBlock(self.obj.element_map[bb])
          cur_func.add_basicblock(cur_block)
          for inst in bb.get_instruction_list():
            ret = inst.visit(self, function=cur_func, basicblock=cur_block)
            if isinstance(ret, EMInstruction):
              cur_block.add_instruction(ret)
            elif isinstance(ret, list):
              for inst in ret:
                if inst is not None:
                  cur_block.add_instruction(inst)
      # done
      return
    
    # helper
    def resolve_sprite_use(self, value : VNValue, sayer_tag : str) -> typing.List[str]:
      assert value.get_type().is_image_type()
      if isinstance(value, VNImageAsset):
        image_label = self.obj.element_map[value]
        result = [sayer_tag, image_label]
        self.obj.init_block.add_instruction(EMInstruction(RenpySupport._Opcode.RO_Image, [result, self.obj.image_decl[value]]))
        return result
      # not handling layered image reference yet
      raise NotImplementedError()
    
    def resolve_audio_use(self, value : VNValue) -> str:
      return self.obj.audio_decl[value]
    
    # instruction handling
    def visitVNSayerDeclInst(self, value: VNSayerDeclInst, *args, **kwargs):
      sayer = value.get_sayer_info()
      sayer_tag = self.obj.element_map[sayer]
      sprite = sayer.get_character_sprite(value.get_sayer_state())
      return EMInstruction(RenpySupport._Opcode.RO_Show, [self.resolve_sprite_use(sprite, sayer_tag)])
    
    def visitVNSayerUpdateInst(self, value: VNSayerUpdateInst, *args, **kwargs):
      sayer = value.get_sayer_info()
      sprite = sayer.get_character_sprite(value.get_sayer_state())
      return EMInstruction(RenpySupport._Opcode.RO_Show, [self.resolve_sprite_use(sprite)])
    
    def visitVNSayInst(self, value: VNSayInst, *args, **kwargs):
      sayer = value.get_sayer()
      text = value.get_text()
      voice = value.get_voice()
      voice_inst = None
      if voice is not None:
        voice_inst = EMInstruction(RenpySupport._Opcode.RO_Voice, ['"' + self.resolve_audio_use(voice) + '"'])
      sayer_operand = None
      text_attr = None
      if sayer is not None:
        sayer_info = sayer.get_sayer_info()
        assert isinstance(sayer_info, VNSayerInfo)
        style_text = sayer_info.get_style_text()
        if style_text is not None:
          text_attr = style_text.get_styles()
        sayer_operand = self.obj.element_map[sayer_info]
      text_operand = RenpySupport._get_sanitized_say_text_str(text, text_attr)
      say_inst = EMInstruction(RenpySupport._Opcode.RO_Say, [sayer_operand, text_operand])
      return [voice_inst, say_inst]
    
    def visitVNReturnInst(self, value: VNReturnInst, *args, **kwargs):
      return EMInstruction(RenpySupport._Opcode.RO_Return)
    
    def visitVNCallInst(self, value: VNCallInst, *args, **kwargs):
      callee_label = self.obj.element_map[value.get_callee()]
      return EMInstruction(RenpySupport._Opcode.RO_Call, [callee_label])
    
    def visitVNUpdateBGMInst(self, value: VNUpdateBGMInst, *args, **kwargs):
      bgm_reference_list = []
      for bgm in value.get_bgm_list():
        bgm_reference_list.append('"' + self.resolve_audio_use(bgm) + '"')
      return EMInstruction(RenpySupport._Opcode.RO_PlayMusic, [bgm_reference_list])
    
    def visitVNUpdateBackgroundInst(self, value: VNUpdateBackgroundInst, *args, **kwargs):
      bg = self.obj.element_map[value.get_background()]
      return EMInstruction(RenpySupport._Opcode.RO_Show, [['bg', bg]])

  class EMExpander(VNModelVisitor):
    obj : RenpyExport
    
    def _get_cmd_str(instr : EMInstruction) -> str:
      single_operand_instr_dict = {
        RenpySupport._Opcode.RO_Scene: "scene",
        RenpySupport._Opcode.RO_Show: "show",
        RenpySupport._Opcode.RO_PlayMusic: "play music",
        RenpySupport._Opcode.RO_Hide: "hide",
        RenpySupport._Opcode.RO_Voice: "voice",
        RenpySupport._Opcode.RO_Jump: "jump",
        RenpySupport._Opcode.RO_Call: "call"
      }
      no_operand_instr_dict = {
        RenpySupport._Opcode.RO_Return: "return"
      }
      # no operand case
      if instr.get_opcode() in no_operand_instr_dict:
        return no_operand_instr_dict[instr.get_opcode()]
      
      # single operand case
      if instr.get_opcode() in single_operand_instr_dict:
        operand = instr.get_operand(0)
        instr_str = single_operand_instr_dict[instr.get_opcode()]
        if isinstance(operand, str):
          return instr_str + " " + operand
        elif isinstance(operand, list):
          return instr_str + " " + " ".join(operand)
        else:
          raise NotImplementedError()  
      
      # other
      if instr.get_opcode() == RenpySupport._Opcode.RO_Character:
        return "define {sayer_label} = Character({sayer_nametext}, voice_tag={character_label})".format(
          **instr.get_operand_dict([
            "character_label",
            "sayer_label",
            "sayer_nametext"
        ]))
      
      if instr.get_opcode() == RenpySupport._Opcode.RO_Say:
        sayer = instr.get_operand(0)
        sayer_prefix = ""
        if sayer is not None:
          sayer_prefix = sayer + " "
        return sayer_prefix + '"' + instr.get_operand(1) + '"'
      
      if instr.get_opcode() == RenpySupport._Opcode.RO_Image:
        tag_list = instr.get_operand(0)
        refpath = instr.get_operand(1)
        return "image " + " ".join(tag_list) + " = \"" + refpath + '"'
      
      raise RuntimeError("Unsupported instruction type:" + str(instr))
  
    def __init__(self, obj : RenpyExport) -> None:
      super().__init__(True)
      self.obj = obj
    
    def write_basic_block(self, f, bb : EMBasicBlock, indent: int, write_label : bool = True):
      if write_label:
        # note the dot before the label
        f.write("label ." + bb.get_label() + ":\n")
      for inst in bb.get_instruction_list():
        f.write(" "*indent)
        command = RenpySupport.EMExpander._get_cmd_str(inst)
        f.write(command)
        f.write("\n")
    
    def write(self, f, indent: int, entry_function : VNFunction):
      # lower init block first
      self.write_basic_block(f, self.obj.init_block, 0, False)
      f.write("\n")
      # jump to entry function if it is specified
      if entry_function is not None:
        f.write("label start:\n" + " "*indent + "jump " + self.obj.element_map[entry_function] + "\n")
      # write all functions
      for func in self.obj.function_list:
        # there is no dot before the label
        # each function just jumps to the entry block
        f.write("label " + func.get_label() + ":\n" + " "*indent + "jump ." + func.basicblock_list[0].get_label() + "\n")
        for bb in func.basicblock_list:
          self.write_basic_block(f, bb, indent, True)
      # done
      f.write("\n")
  
  def export_pipeline(self, obj : RenpyExport):
    rootscript = obj.get_option("rootscript", "script.rpy")
    entryfunction = obj.get_option("entryfunction", None)
    indent = obj.get_option("indent", 4)
    if entryfunction is not None:
      entryfunction = obj.vnmodel.get_function(entryfunction)
    
    obj.init_block = EMBasicBlock()
    obj._default_preparation()
    # declare all sayers
    for sayer in obj.vnmodel.get_sayer_list():
      instr = EMInstruction(RenpySupport._Opcode.RO_Character)
      character = sayer.get_identity()
      character_label = obj.element_map[character]
      # character label, sayer label, sayer name text
      instr.add_operand('"' + character_label + '"')
      instr.add_operand(obj.element_map[sayer]) # sayer label should not be quoted
      nametext = "None"
      name_text = sayer.get_name_text()
      if name_text is not None:
        nametext = '"' + RenpySupport._get_sanitized_say_text_str(name_text, {}) + '"'
      instr.add_operand(nametext)
      if sayer.get_default_side_image() is not None:
        # side_image = sayer.get_default_side_image()
        # side_image_expr = materialize_image(side_image)
        # TODO support side image
        pass
      obj.init_block.add_instruction(instr)
    
    # lower all functions and instructions
    builder = RenpySupport.EMBuilder(obj)
    builder.build()
    
    # write all code to export
    expander = RenpySupport.EMExpander(obj)
    self.secure_overwrite(os.path.join(obj.get_project_directory(), rootscript), lambda f : expander.write(f, indent, entryfunction), 'w')
    return

# global scope (executed when imported)
RenpySupport.initialize()
