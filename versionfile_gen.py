#!/usr/bin/env python3

import pyinstaller_versionfile
import preppipe
import preppipe._version
import datetime

def generate_versionfile():
  # The version string must be a 4-number string separated by dots, so we need a conversion here
  versionstr = preppipe._version.__version__.replace("post", "")
  year = datetime.datetime.now().year

  # the library does not support single/duble quotes in the strings; just avoid them
  pyinstaller_versionfile.create_versionfile(
    output_file="versionfile.txt",
    version=versionstr,
    company_name="PrepPipe",
    file_description="PrepPipe Compiler Command Line Interface (CLI) Executable",
    internal_name="PrepPipe",
    legal_copyright="Copyright (c) " + str(year) + " PrepPipe Contributors.",
    original_filename="preppipe_cli.exe",
    product_name="PrepPipe Compiler",
    translations=[0x0409, 1200, 0x0804, 1200, 0x0404, 1200]
  )

  # print the content for debugging
  with open("versionfile.txt", "r", encoding="utf-8") as f:
    content = f.read()
    print(content)

if __name__== "__main__":
  generate_versionfile()