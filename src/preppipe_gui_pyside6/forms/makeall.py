# Use this instead of the Makefile if there is no make

import glob, os, subprocess, pathlib

os.makedirs("generated", exist_ok=True)

for ui in glob.glob("*.ui"):
  out = f"generated/ui_{pathlib.Path(ui).stem}.py"
  commands = ["pyside6-uic", ui, "-o", out]
  print(' '.join(commands))
  subprocess.run(commands, check=True)
