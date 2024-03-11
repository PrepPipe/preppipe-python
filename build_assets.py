#!/usr/bin/env python3

import os
import preppipe
import preppipe.pipeline_cmd
import preppipe.pipeline

def main():
  srcpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
  os.environ["PREPPIPE_TOOL"] = "assetmanager"
  preppipe.pipeline.pipeline_main(["--build", srcpath])
  preppipe.pipeline.pipeline_main(["--dump-json"])

if __name__ == "__main__":
  main()
