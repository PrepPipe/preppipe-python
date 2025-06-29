#!/usr/bin/env python3

import os
import argparse
import preppipe
import preppipe.pipeline_cmd
import preppipe.pipeline

def main():
  parser = argparse.ArgumentParser(description="Asset Building helper")
  parser.add_argument("--export-built-embedded", metavar="<dir>", default=None, help="Copy the embedded assets to the specified directory")
  args = parser.parse_args()

  srcpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
  os.environ["PREPPIPE_TOOL"] = "assetmanager"
  assetmanager_args = [
    "--build-embedded", srcpath,
    "--dump-json"
  ]
  if args.export_built_embedded:
    assetmanager_args += ["--export-built-embedded", args.export_built_embedded]
  preppipe.pipeline.pipeline_main(assetmanager_args)

if __name__ == "__main__":
  main()
