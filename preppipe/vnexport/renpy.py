#!/usr/bin/env python3

from io import UnsupportedOperation
from warnings import warn
import os, sys, typing
import preppipe.visualnovelmodel as visualnovelmodel

def renpy_sanitize(text: str) -> str:
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

# We will create files under these directories inside project_dir:
#   ./scripts/: all game scripts go there; the entrypoint defaults to "start"
#   ./audio/: all audio assets go there; we will use the following subdirectories:
#     ./audio/bgm: all background musics go there
#     ./audio/voice: all voice go there
#     ./audio/se: all sound effects go there
#   ./images/: all image assets go there:
#     ./images/bg: all background image goes there
#     ./images/sprite: all other (non-background) images

def export_renpy(vnmodel : visualnovelmodel.VisualNovelModel, project_dir : str, **kwarg) -> None:
  """Export the visual novel model into a Renpy Project directory
  Config can have following keys:
    "rootscript": str, specify the path (relative from project_dir) of the root script.
      defaults to overwrite the "script.rpy" from RenPy project template
    "startpoint": str, specify the label name of root script entry point
      defaults to "start"
    "endpoint": str, specify a label for the script to jump to at the end
      defaults to None, in which case the RenPy script will end with "return"
      if the script already has a terminating jump or return, this value is not used
    "indent": int, specify how many whitespace do we prepend for each line
  """
  rootscript = kwarg.get("rootscript", "script.rpy")
  startpoint = kwarg.get("startpoint", "start")
  endpoint = kwarg.get("endpoint", None)
  indent = kwarg.get("indent", 4)
  
  warned_text_background_color_unsupported = False
  
  def warn_text_background_color_unsupported():
    nonlocal warned_text_background_color_unsupported
    if warned_text_background_color_unsupported:
      return
    warn("RenPy export does not support text background color")
    warned_text_background_color_unsupported = True
  
  isRequireInsertingEndpoint = True
  
  with open(os.path.join(project_dir, rootscript), "w") as s:
    # TODO collect all contexts and define the corresponding variables
    # for now we simply dump all elements
    s.write("label " + startpoint + ":\n")
    for b in vnmodel.block_list:
      command_queue = []
      pending_text = ""
      for e in b.element_list:
        if isinstance(e, visualnovelmodel.VNSayTextElement):
          curText = renpy_sanitize(e.text);
          if e.bold():
            curText = "{b}" + curText + "{/b}"
          if e.italic():
            curText = "{i}" + curText + "{/i}"
          if e.has_nonzero_sizelevel():
            raise UnsupportedOperation("Text size level not supported yet!")
          if e.has_text_color():
            curText = "{color=" + e.text_color().getString() + "}" + curText + "{/color}"
          if e.has_background_color():
            warn_text_background_color_unsupported()
          if e.has_ruby_text():
            curText = "{rb}" + curText + "{/rb}{rt}" + e.ruby_text() + "{/rt}"
          pending_text += curText
        elif isinstance(e, visualnovelmodel.VNClearElement):
          if len(pending_text) > 0:
            s.write(" "*indent)
            s.write("\"")
            s.write(pending_text)
            s.write("\"\n")
            pending_text = ""
        else:
          # unrecognized structure
          pass
    if isRequireInsertingEndpoint:
      s.write(" "*indent)
      if endpoint is None:
        s.write("return\n")
      else:
        s.write("jump " + endpoint + "\n")
    s.write("\n")
  # done
