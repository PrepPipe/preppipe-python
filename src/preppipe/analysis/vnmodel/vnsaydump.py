# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
import dataclasses
import collections
import os

from ...vnmodel import *
from ...pipeline import TransformBase, IODecl, BackendDecl, TransformArgumentGroup
from ...language import TranslationDomain

TR_vn_saydump = TranslationDomain("vn_saydump")

@dataclasses.dataclass
class _VNSayDumpSettings:
  comment_fmtstr : str = "#{comment}"
  narrator_say_fmtstr : str = "{content}"
  sayer_noexpr_fmtstr : str = "{sayer}:{content}"
  sayer_withexpr_fmtstr : str = "{sayer}({expression}):{content}"
  expr_separator : str = ','
  text_escape_dict : dict[str, str] = dataclasses.field(default_factory=dict)
  text_escape_chars : str = ':：'
  text_escape_prefix : str = '\\'
  ctrl_return_fmtstr : str = ""
  ctrl_tailcall_fmtstr : str = "# TailCall: {callee}"
  ctrl_call_fmtstr : str = "# Call: {callee}"
  ctrl_ending_fmtstr : str = "# Ending: {ending}"
  ctrl_jump_fmtstr : str = "# Jump: {dest}"
  jump_dest_separatpr : str = ','
  scene_switch_fmtstr : str = "# Scene : {scene}"

@dataclasses.dataclass
class _SayDump_BlockState:
  characterstates : dict[VNCharacterSymbol, str] = dataclasses.field(default_factory=dict) # 由立绘猜测的角色状态

  def clone(self):
    return _SayDump_BlockState(characterstates=self.characterstates.copy())

def _get_blocks_list(f : VNFunction, setting : _VNSayDumpSettings, char_state_dict : dict[Value, dict[VNCharacterSymbol, str]], char_sideimage_state_dict : dict[Value, dict[VNCharacterSymbol, str]]) -> list[tuple[str, list[str]]]:
  # 将每个基本块的内容做成一个 list[str]，把函数内所有基本块的内容并成一个大的 list，再返回
  # 为了保证每个块都有一个名字，我们在这先把所有块的名字确定了
  blocknames : dict[Block, str] = {}
  anon_index = 0
  for b in f.body.blocks:
    if len(b.name) > 0:
      blocknames[b] = b.name
    else:
      blocknames[b] = 'anon_' + str(anon_index)
      anon_index += 1

  def escape_str(s : str) -> str:
    result = ''
    for ch in s:
      if ch in setting.text_escape_dict:
        # 使用字典进行转义
        result += setting.text_escape_dict[ch]
      elif ch in setting.text_escape_chars:
        # 使用转义字符进行转义
        result += setting.text_escape_prefix + ch
      else:
        result += ch
    return result

  # 开始走遍整个函数
  entryblock = f.get_entry_block()
  entrystate = _SayDump_BlockState()
  blockdict : dict[Block, _SayDump_BlockState] = {entryblock: entrystate}
  visitedblocks : set[Block] = set()
  worklist = collections.deque()
  worklist.append(entryblock)
  visitedblocks.add(entryblock)
  blocks : list[tuple[str, list[str]]] = []
  while len(worklist) > 0:
    curblock = worklist.popleft()
    curstate = blockdict[curblock]
    blocktext : list[str] = []
    blocks.append((blocknames[curblock], blocktext))
    def handle_op (op : Operation):
      if isinstance(op, MetadataOp):
        if isinstance(op, CommentOp):
          comment = op.comment.get_string()
          result = setting.comment_fmtstr.format(comment=comment)
          blocktext.append(result)
        elif isinstance(op, ErrorOp):
          text = op.error_code + ': ' + op.error_message.get_string()
          result = setting.comment_fmtstr.format(comment=text)
          blocktext.append(result)
      elif isinstance(op, VNInstruction):
        if isinstance(op, (VNCreateInst, VNModifyInst)):
          # 有可能是角色上场或立绘改变
          if op.device.get().get_std_device_kind() == VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
            if content := op.content.try_get_value():
              if content in char_state_dict:
                for ch, state in char_state_dict[content].items():
                  curstate.characterstates[ch] = state
        elif isinstance(op, VNSceneSwitchInstructionGroup):
          if scene := op.dest_scene.try_get_value():
            result = setting.scene_switch_fmtstr.format(scene=scene.name)
            blocktext.append(result)
          for childop in op.body.body:
            handle_op(childop)
        elif isinstance(op, VNSayInstructionGroup):
          expr = None
          who = None
          what = ''
          specified_sayers = [u.value for u in op.sayer.operanduses()]
          def collect_as_textstr(operand : OpOperand) -> str:
            contentlist = []
            for u in operand.operanduses():
              v = u.value
              if isinstance(v, (StringLiteral, TextFragmentLiteral)):
                contentlist.append(v.get_string())
              else:
                contentlist.append(str(v))
            return ''.join(contentlist)
          for child in op.body.body:
            if isinstance(child, VNPutInst):
              match child.device.get().get_std_device_kind():
                case VNStandardDeviceKind.O_SAY_TEXT_TEXT:
                  what = collect_as_textstr(child.content)
                case VNStandardDeviceKind.O_SAY_NAME_TEXT:
                  who = collect_as_textstr(child.content)
                case VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY:
                  curvalue = child.content.get()
                  if curvalue in char_sideimage_state_dict:
                    for ch, state in char_sideimage_state_dict[curvalue].items():
                      if ch in specified_sayers:
                        expr = state
                        break
                case _:
                  pass
          # 尝试从立绘中获取状态信息
          if who is not None and len(specified_sayers) == 1:
            sayer = specified_sayers[0]
            if sayer in curstate.characterstates:
              expr = curstate.characterstates[sayer]
          # 开始输出
          what = escape_str(what)
          if who is not None:
            who = escape_str(who)
            if expr is None:
              result = setting.sayer_noexpr_fmtstr.format(sayer=who, content=what)
            else:
              exprstr = setting.expr_separator.join(expr.split(','))
              result = setting.sayer_withexpr_fmtstr.format(sayer=who, content=what, expression=exprstr)
          else:
            result = setting.narrator_say_fmtstr.format(content=what)
          blocktext.append(result)
        elif isinstance(op, VNTerminatorInstBase):
          if isinstance(op, VNLocalTransferInstBase):
            target_list = []
            for u in op.target_list.operanduses():
              target = u.value
              assert isinstance(target, Block)
              targetname = blocknames[target]
              target_list.append(targetname)
              if target not in blockdict:
                blockdict[target] = curstate.clone()
              if target not in visitedblocks:
                visitedblocks.add(target)
                worklist.append(target)
            deststr = setting.jump_dest_separatpr.join(target_list)
            result = setting.ctrl_jump_fmtstr.format(dest=deststr)
            blocktext.append(result)
          elif isinstance(op, VNTailCallInst):
            target = op.target.get().name
            result = setting.ctrl_tailcall_fmtstr.format(callee=target)
            blocktext.append(result)
          elif isinstance(op, VNReturnInst):
            blocktext.append(setting.ctrl_return_fmtstr)
          elif isinstance(op, VNEndingInst):
            result = setting.ctrl_ending_fmtstr.format(ending=op.ending.get().get_string())
            blocktext.append(result)
        elif isinstance(op, VNCallInst):
          # 要放在 TailCall 处理之后，免得把 TailCall 的情况也在这处理了
          target = op.target.get().name
          result = setting.ctrl_call_fmtstr.format(callee=target)
          blocktext.append(result)
    for op in curblock.body:
      handle_op(op)
  return blocks

_TR_vn_saydump_name = TR_vn_saydump.tr("name_prefix",
  en="vn-saydump: ",
  zh_cn="发言导出：",
  zh_hk="發言導出：",
)

_TR_vn_saydump_dump_outside_outputdir = TR_vn_saydump.tr("dump_outside_outputdir",
  en="Export directory \"{realpath}\" outside output directory \"{outputdir}\" and will be skipped. Please check if the file names or the namespace path may be misunderstood.",
  zh_cn="要导出的目录 \"{realpath}\" 不在指定的输出目录中： \"{outputdir}\"。该导出将不会进行。请检查文件名和命名空间路径是否会引起歧义。",
  zh_hk="要導出的目錄 \"{realpath}\" 不在指定的輸出目錄中： \"{outputdir}\"。該導出將不會進行。請檢查文件名和命名空間路徑是否會引起歧義。",
)

def vn_say_dump(m : VNModel, setting : _VNSayDumpSettings, outputdir : str):
  # 我们首先扫描所有的角色信息，构建角色状态表（什么立绘对应什么角色状态）
  # 由于每个立绘可能有多个角色同时使用，我们假设所有这些角色的状态都会改变
  outputdir = os.path.realpath(outputdir)
  char_state_dict : dict[Value, dict[VNCharacterSymbol, str]] = {}
  char_sideimage_state_dict : dict[Value, dict[VNCharacterSymbol, str]] = {}
  for ns in m.namespace:
    for ch in ns.characters:
      for s in ch.sprites:
        if s.get_value() in char_state_dict:
          curdict = char_state_dict[s.get_value()]
        else:
          curdict = {}
          char_state_dict[s.get_value()] = curdict
        curdict[ch] = s.name
      for s in ch.sideimages:
        if s.get_value() in char_sideimage_state_dict:
          curdict = char_sideimage_state_dict[s.get_value()]
        else:
          curdict = {}
          char_sideimage_state_dict[s.get_value()] = curdict
        curdict[ch] = s.name
  for ns in m.namespace:
    for f in ns.functions:
      dname = os.path.join(ns.name, f.name)[1:] # [1:]把命名空间开头的 '/'给去掉
      realpath = os.path.realpath(os.path.join(outputdir, dname))
      # 检查 realpath 是否在 outputdir 下，如果不在的话报错并跳过
      if os.path.commonprefix([realpath, outputdir]) != outputdir:
        print(_TR_vn_saydump_name.get() + _TR_vn_saydump_dump_outside_outputdir.format(realpath=realpath, outputdir=outputdir))
        continue
      result = _get_blocks_list(f, setting, char_state_dict, char_sideimage_state_dict)
      if len(result) == 0:
        continue
      parentdir = os.path.dirname(realpath)
      os.makedirs(parentdir, exist_ok=True)
      if len(result) == 1:
        # 我们只生成一个文件
        blockname, lines = result[0]
        with open(realpath + '.txt', "w", encoding='utf-8') as f:
          f.write('\n'.join(lines) + '\n')
      else:
        # 我们生成一个目录
        os.makedirs(realpath, exist_ok=True)
        blockindex = 1
        for blockname, lines in result:
          fname = os.path.join(realpath, str(blockindex) + '_' + blockname + '.txt')
          blockindex += 1
          with open(fname, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

@TransformArgumentGroup('vn-saydump', "Options for Dumping say contents")
@BackendDecl('vn-saydump', input_decl=VNModel, output_decl=IODecl("Dump directory", nargs=1))
class VNSayDumpPass(TransformBase):
  setting : typing.ClassVar[_VNSayDumpSettings] = _VNSayDumpSettings()

  setting_gamecreator : typing.ClassVar[_VNSayDumpSettings] = _VNSayDumpSettings(
    comment_fmtstr = "//{comment}",
    sayer_withexpr_fmtstr = "{sayer}:{content}", # GameCreator 表情等用的是另一套编号机制，暂时都不导出
    text_escape_chars = ':：',
    ctrl_tailcall_fmtstr = "// TailCall: {callee}",
    ctrl_call_fmtstr= "// Call: {callee}",
    ctrl_ending_fmtstr = "// Ending: {ending}",
    ctrl_jump_fmtstr = "// Jump: {dest}",
    scene_switch_fmtstr = "// Scene: {scene}",
  )

  setting_presets_dict : typing.ClassVar[dict[str, _VNSayDumpSettings]] = {
    "gamecreator" : setting_gamecreator,
  }

  @staticmethod
  def install_arguments(argument_group : argparse._ArgumentGroup):
    argument_group.add_argument("--vnsaydump-preset", nargs=1, type=str, default='')

  _tr_unknown_preset = TR_vn_saydump.tr("unknown_preset",
    en="Preset \"{preset}\" does not exist. Presets registered: ",
    zh_cn="预设 \"{preset}\" 不存在。已注册的预设有： ",
    zh_hk="預設 \"{preset}\" 不存在。已註冊的預設有： ",
  )

  @staticmethod
  def handle_arguments(args : argparse.Namespace):
    if preset := args.vnsaydump_preset:
      preset_name = preset[0]
      if len(preset_name) > 0:
        if preset_name in VNSayDumpPass.setting_presets_dict:
          VNSayDumpPass.setting = VNSayDumpPass.setting_presets_dict[preset_name]
        else:
          raise RuntimeError(VNSayDumpPass._tr_unknown_preset.format(preset=preset_name)+ str(list(VNSayDumpPass.setting_presets_dict.keys())))

  _tr_invalid_path = TR_vn_saydump.tr("invalid_path",
    en="Export path should be a valid directory is instead of a file: ",
    zh_cn="导出目录应是一个有效的目录而不是个文件： ",
    zh_hk="導出目錄應是一個有效的目錄而不是個文件： ",
    )

  def run(self) -> None:
    assert len(self.inputs) == 1
    out_path = self.output
    if os.path.exists(out_path):
      if not os.path.isdir(out_path):
        raise RuntimeError(VNSayDumpPass._tr_invalid_path.get() + out_path)
    vn_say_dump(self.inputs[0], self.setting, out_path)
