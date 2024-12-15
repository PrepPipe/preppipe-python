# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import io

from .ast import *
from ..enginecommon.export import *

# pylint: disable=invalid-name
class WebGalExportVisitor(BackendASTVisitorBase):
  dest : io.TextIOBase
  def __init__(self, dest : io.TextIOBase) -> None:
    super().__init__()
    self.dest = dest

  WEBGAL_STR_ESCAPE_DICT : typing.ClassVar[dict[str, str]] = {
    '"' : r'\"',
    "'" : r"\'",
    ";" : r"\;",
    #'\n' : r"\n",
    #'%' : r"\%",
    #'[' : r"[[",
    #'{' : r"{{",
  }

  @staticmethod
  def escapestr(s : str) -> str:
    s = s.replace('\\', r"\\")
    for k, v in WebGalExportVisitor.WEBGAL_STR_ESCAPE_DICT.items():
      s = s.replace(k, v)
    return s

  def walk_body(self, b : Block):
    for op in b.body:
      if isinstance(op, BackendASTNodeBase):
        op.accept(self)
      elif isinstance(op, ErrorOp):
        code : str = op.error_code
        msg : str = op.error_message.get_string()
        fullmsg = msg + ' (' + code + ')'
        self.dest.write(self.tr_error.get() + ":" + self.escapestr(fullmsg) + "\n")
      elif isinstance(op, MetadataOp):
        if isinstance(op, CommentOp):
          content = op.comment.get_string()
        else:
          content = str(op)
        for s in content.split('\n'):
          self.dest.write('; ' + s + '\n')
      else:
        raise NotImplementedError("TODO")

  def visitWebGalCommentNode(self, node : WebGalCommentNode):
    if content := node.content.try_get_value():
      self.dest.write('; ' + content.get_string() + '\n')

  def visitWebGalASMNode(self, node : WebGalASMNode):
    if content := node.content.try_get_value():
      self.dest.write(content.get_string() + '\n')

  def add_common_flags(self, result : list[str], node : WebGalNode):
    if node.get_flag_next():
      result.append('-next')
    if when := node.when.try_get_value():
      result.append('-when=' + when.get_string())

  def test(self, flag : OpOperand[BoolLiteral]) -> bool:
    if v := flag.try_get_value():
      return v.value
    return False

  def get_str_or_none(self, s : OpOperand[StringLiteral]) -> str:
    if v := s.try_get_value():
      return v.get_string()
    return 'none'

  def visitWebGalSayNode(self, node : WebGalSayNode):
    saystr = node.sayer.get().get_string() + ':' + '|'.join([s.get_string() for s in node.content.get().value])
    result = [saystr]
    if voice := node.voice.try_get_value():
      result.append('-' + voice.get_string())
      if voice_volume := node.voice_volume.try_get_value():
        result.append('-volume=' + str(voice_volume.value))
    if self.test(node.flag_notend):
      result.append('-notend')
    if self.test(node.flag_concat):
      result.append('-concat')
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalIntroNode(self, node : WebGalIntroNode):
    result = ['intro:' + '|'.join([s.get_string() for s in node.content.get().value])]
    if self.test(node.flag_hold):
      result.append('-hold')
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalSetTextboxNode(self, node : WebGalSetTextboxNode):
    if self.test(node.on):
      cmdstr = 'setTextbox:on'
    else:
      cmdstr = 'setTextbox:hide'
    result = [cmdstr]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalEndNode(self, node : WebGalEndNode):
    result = ['end']
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalChangeBGNode(self, node : WebGalChangeBGNode):
    result = ['changeBg:' + self.get_str_or_none(node.bg)]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalChangeFigureNode(self, node : WebGalChangeFigureNode):
    result = ['changeFigure:' + self.get_str_or_none(node.figure)]
    if id_str := node.id_str.try_get_value():
      result.append('-id=' + id_str.get_string())
    if position := node.position.try_get_value():
      result.append('-' + position.get_string())
    if transform := node.transform.try_get_value():
      result.append('-transform=' + transform.get_string())
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalMiniAvatarNode(self, node : WebGalMiniAvatarNode):
    result = ['miniAvatar:' + self.get_str_or_none(node.avatar)]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalUnlockCGNode(self, node : WebGalUnlockCGNode):
    result = ['unlockCg:' + self.get_str_or_none(node.cg)]
    if namestr := node.namestr.try_get_value():
      result.append('-name=' + namestr.get_string())
    if series := node.series.try_get_value():
      result.append('-series=' + str(series.value))
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalBGMNode(self, node : WebGalBGMNode):
    result = ['bgm:' + self.get_str_or_none(node.bgm)]
    if volume := node.volume.try_get_value():
      result.append('-volume=' + str(volume.value))
    if enter := node.enter.try_get_value():
      result.append('-enter=' + str(enter.value))
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalPlayEffectNode(self, node : WebGalPlayEffectNode):
    result = ['playEffect:' + self.get_str_or_none(node.effect)]
    if id_str := node.id_str.try_get_value():
      result.append('-id=' + id_str.get_string())
    if volume := node.volume.try_get_value():
      result.append('-volume=' + str(volume.value))
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalUnlockBGMNode(self, node : WebGalUnlockBGMNode):
    result = ['unlockBgm:' + self.get_str_or_none(node.bgm)]
    if namestr := node.namestr.try_get_value():
      result.append('-name=' + namestr.get_string())
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalPlayVideoNode(self, node : WebGalPlayVideoNode):
    result = ['playVideo:' + self.get_str_or_none(node.video)]
    if self.test(node.flag_skipoff):
      result.append('-skipOff')
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalChangeSceneNode(self, node : WebGalChangeSceneNode):
    result = ['changeScene:' + node.scene.get().get_string()]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalCallSceneNode(self, node : WebGalCallSceneNode):
    result = ['callScene:' + node.scene.get().get_string()]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalChooseBranchNode(self, node : WebGalChooseBranchNode):
    condition_str = ''
    if condition_show := node.condition_show.try_get_value():
      condition_str += '(' + condition_show.get_string() + ')'
    if condition_clickable := node.condition_clickable.try_get_value():
      condition_str += '[' + condition_clickable.get_string() + ']'
    if len(condition_str) > 0:
      self.dest.write(condition_str + '->')
    self.dest.write(node.text.get().get_string() + ':' + node.destination.get().get_string())

  def visitWebGalChooseNode(self, node : WebGalChooseNode):
    self.dest.write('choose:')
    is_first = True
    for branch in node.choices.body:
      if not is_first:
        self.dest.write('|')
      else:
        is_first = False
      if isinstance(branch, WebGalChooseBranchNode):
        self.visitWebGalChooseBranchNode(branch)
      else:
        raise PPInternalError("Invalid node in WebGalChooseNode")
    result = []
    self.add_common_flags(result, node)
    if len(result) > 0:
      self.dest.write(' ' + ' '.join(result))
    self.dest.write(';\n')

  def visitWebGalLabelNode(self, node : WebGalLabelNode):
    result = ['label:' + node.label.get().get_string()]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalJumpLabelNode(self, node : WebGalJumpLabelNode):
    result = ['jumpLabel:' + node.label.get().get_string()]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalSetVarNode(self, node : WebGalSetVarNode):
    result = ['setVar:' + node.varname.get().get_string() + '=' + node.expr.get().get_string()]
    if self.test(node.flag_global):
      result.append('-global')
    if when := node.when.try_get_value():
      result.append('-when=' + when.get_string())
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalGetUserInputNode(self, node : WebGalGetUserInputNode):
    result = ['getUserInput:' + node.varname.get().get_string()]
    if title := node.title.try_get_value():
      result.append('-title=' + title.get_string())
    if buttontext := node.buttontext.try_get_value():
      result.append('-buttonText=' + buttontext.get_string())
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalSetAnimationNode(self, node : WebGalSetAnimationNode):
    result = ['setAnimation:' + node.animation.get().get_string()]
    if target := node.target.try_get_value():
      result.append('-target=' + target.get_string())
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalSetTransitionNode(self, node : WebGalSetTransitionNode):
    result = ['setTransition:']
    if target := node.target.try_get_value():
      result.append('-target=' + target.get_string())
    if enter := node.enter.try_get_value():
      result.append('-enter=' + enter.get_string())
    if exit := node.exit.try_get_value():
      result.append('-exit=' + exit.get_string())
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalPixiInitNode(self, node : WebGalPixiInitNode):
    result = ['pixiInit']
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def visitWebGalPixiPerformNode(self, node : WebGalPixiPerformNode):
    result = ['pixiPerform:' + node.effect.get().get_string()]
    self.add_common_flags(result, node)
    self.dest.write(' '.join(result) + ';\n')

  def start_visit(self, file : WebGalScriptFileOp):
    self.walk_body(file.body)

def export_webgal(m : WebGalModel, out_path : str, template_dir : str = '') -> None:
  assert isinstance(m, WebGalModel)
  os.makedirs(out_path, exist_ok=True)
  # step 1: copy the template directory and the runtime
  if len(template_dir) > 0:
    shutil.copytree(template_dir, out_path, dirs_exist_ok=True)

  # step 2: start walking all script files
  # apply the default transform to make output nicer
  for script in m.scripts():
    scriptpath = os.path.join(out_path, script.name)
    parentdir = os.path.dirname(scriptpath)
    os.makedirs(parentdir, exist_ok=True)
    with open(scriptpath, 'w', encoding="utf-8") as f:
      exporter = WebGalExportVisitor(f)
      exporter.start_visit(script)

  export_assets_and_cacheable(m, out_path=out_path)
  # done for now
