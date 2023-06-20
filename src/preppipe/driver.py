# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import sys

from .inputmodel import Context
from .frontend.opendocument import parse_odf
from .frontend.commandsyntaxparser import perform_command_parse_transform

def _testmain():
  if len(sys.argv) < 2 or len(sys.argv[1]) == 0:
    print("please specify the input file!")
    sys.exit(1)
  ctx = Context()
  filepath = sys.argv[1]
  doc = parse_odf(ctx, filepath)
  perform_command_parse_transform(doc)
  doc.view()

if __name__ == "__main__":
  _testmain()
