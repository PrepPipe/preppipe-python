#!/usr/bin/env python3

import sys
import argparse
import datetime
import preppipe
import preppipe.language

def generate_versionfile(versionfile_filename: str, executable_filename : str, is_cli_only : bool = True):
  # The version string must be a 4-number string separated by dots, so we need a conversion here
  versionstr = preppipe.__version__.replace("post", ".")
  version_number_list = [int(s) for s in versionstr.split(".")]
  while len(version_number_list) < 4:
    version_number_list.append(0)
  version_number_tuple = tuple(version_number_list)
  versionstr = ".".join([str(s) for s in version_number_tuple])
  year = datetime.datetime.now().year

  internalname = "PrepPipe CLI"
  file_description_dict = {
    "en" : "PrepPipe Compiler Command Line Interface",
    "zh_cn": "语涵编译器命令行",
    "zh_hk": "語涵編譯器命令行"
  }
  if not is_cli_only:
    internalname = "PrepPipe"
    keys = list(file_description_dict.keys())
    for key in keys:
      result = preppipe.language.Translatable.tr_program_name.lookup_candidate(key)
      if result is None:
        raise RuntimeError(f"Cannot find the program name for language {key}")
      file_description_dict[key] = result

  versionfile_content = f"""# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx

VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0. Must always contain 4 elements.
    filevers={version_number_tuple},
    prodvers={version_number_tuple},
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'PrepPipe Project'),
        StringStruct(u'FileDescription', u'{file_description_dict["en"]}'),
        StringStruct(u'FileVersion', u'{versionstr}'),
        StringStruct(u'InternalName', u'{internalname}'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {year} PrepPipe Contributors.'),
        StringStruct(u'OriginalFilename', u'{executable_filename}'),
        StringStruct(u'ProductName', u'PrepPipe Compiler'),
        StringStruct(u'ProductVersion', u'{versionstr}')]
      ),
      StringTable(
        u'080404B0',
        [StringStruct(u'CompanyName', u'语涵计划'),
        StringStruct(u'FileDescription', u'{file_description_dict["zh_cn"]}'),
        StringStruct(u'FileVersion', u'{versionstr}'),
        StringStruct(u'InternalName', u'{internalname}'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {year} 语涵计划贡献者'),
        StringStruct(u'OriginalFilename', u'{executable_filename}'),
        StringStruct(u'ProductName', u'语涵编译器'),
        StringStruct(u'ProductVersion', u'{versionstr}')]
      ),
      StringTable(
        u'040404B0',
        [StringStruct(u'CompanyName', u'語涵計劃'),
        StringStruct(u'FileDescription', u'{file_description_dict["zh_hk"]}'),
        StringStruct(u'FileVersion', u'{versionstr}'),
        StringStruct(u'InternalName', u'{internalname}'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {year} 語涵計劃貢獻者'),
        StringStruct(u'OriginalFilename', u'{executable_filename}'),
        StringStruct(u'ProductName', u'語涵編譯器'),
        StringStruct(u'ProductVersion', u'{versionstr}')]
      ),
    ]),
    VarFileInfo([VarStruct(u'Translation', [0x0804, 1200, 0x0404, 1200, 0x409, 1252])])
  ]
)
"""
  with open(versionfile_filename, "w", encoding="utf-8") as f:
    f.write(versionfile_content)

  # print the content for debugging
  # the environment may not support non-ascii characters, so we need to escape them
  verfile_lines = versionfile_content.splitlines()
  verfile_lines_converted = [u.encode("unicode_escape").decode("utf-8") for u in verfile_lines]
  versionfile_print = '\n'.join(verfile_lines_converted)
  print(versionfile_print)

if __name__== "__main__":
  # versionfile_gen.py <versionfile> <executable_filename> [--cli]
  parser = argparse.ArgumentParser(description='Generate version file for Windows executable')
  parser.add_argument('versionfile', type=str, help='Output version file', default="versionfile.txt")
  parser.add_argument('executable_filename', type=str, help='Executable filename', default="preppipe.exe")
  parser.add_argument('--cli', action='store_true', help='CLI only')
  args = parser.parse_args()
  is_cli_only = args.cli
  generate_versionfile(args.versionfile, args.executable_filename, is_cli_only)
