#!/usr/bin/env python3

import preppipe
import preppipe._version
import datetime

def generate_versionfile():
  # The version string must be a 4-number string separated by dots, so we need a conversion here
  versionstr = preppipe._version.__version__.replace("post", "")
  version_number_tuple = tuple([int(s) for s in versionstr.split(".")])
  year = datetime.datetime.now().year
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
        StringStruct(u'FileDescription', u'PrepPipe Compiler Command Line Interface'),
        StringStruct(u'FileVersion', u'{versionstr}'),
        StringStruct(u'InternalName', u'PrepPipe CLI'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {year} PrepPipe Contributors.'),
        StringStruct(u'OriginalFilename', u'preppipe_cli.exe'),
        StringStruct(u'ProductName', u'PrepPipe Compiler'),
        StringStruct(u'ProductVersion', u'{versionstr}')]
      ),
      StringTable(
        u'080404B0',
        [StringStruct(u'CompanyName', u'语涵计划'),
        StringStruct(u'FileDescription', u'语涵编译器命令行'),
        StringStruct(u'FileVersion', u'{versionstr}'),
        StringStruct(u'InternalName', u'PrepPipe CLI'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {year} 语涵计划贡献者'),
        StringStruct(u'OriginalFilename', u'preppipe_cli.exe'),
        StringStruct(u'ProductName', u'语涵编译器'),
        StringStruct(u'ProductVersion', u'{versionstr}')]
      ),
      StringTable(
        u'040404B0',
        [StringStruct(u'CompanyName', u'語涵計劃'),
        StringStruct(u'FileDescription', u'語涵編譯器命令行'),
        StringStruct(u'FileVersion', u'{versionstr}'),
        StringStruct(u'InternalName', u'PrepPipe CLI'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {year} 語涵計劃貢獻者'),
        StringStruct(u'OriginalFilename', u'preppipe_cli.exe'),
        StringStruct(u'ProductName', u'語涵編譯器'),
        StringStruct(u'ProductVersion', u'{versionstr}')]
      ),
    ]),
    VarFileInfo([VarStruct(u'Translation', [0x0804, 1200, 0x0404, 1200, 0x409, 1252])])
  ]
)
"""
  with open("versionfile.txt", "w", encoding="utf-8") as f:
    f.write(versionfile_content)

  # print the content for debugging
  # the environment may not support non-ascii characters, so we need to escape them
  verfile_lines = versionfile_content.splitlines()
  verfile_lines_converted = [u.encode("unicode_escape").decode("utf-8") for u in verfile_lines]
  versionfile_print = '\n'.join(verfile_lines_converted)
  print(versionfile_print)

if __name__== "__main__":
  generate_versionfile()