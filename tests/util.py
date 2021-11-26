#!/usr/bin/env python3

import os
import hashlib
import shutil

def collectDirectoryDataAsText(path : str) -> str:
  """Dump all contents in a directory as a single string to ease comparison"""
  result = []
  rootpath = os.path.abspath(path)
  for root, subdirs, files in os.walk(rootpath):
    subdirs.sort()
    for file in files:
      filePath = os.path.join(root, file)
      printPath = os.path.relpath(filePath, rootpath)
      result.append(printPath + ":")
      with open(filePath, "rb") as f:
        bin = f.read();
        isString = True
        try:
          fileString = bin.decode("utf-8")
        except:
          isString = False
        if isString:
          result.append(fileString)
        else:
          result.append("<Binary file; MD5=" + str(hashlib.md5(bin)) + ">")
  return "\n".join(result)
    
def copyTestDirIfRequested(srcdir: str, testname: str) -> None:
  """Sometimes we want to preserve the temporary files from tests (for manual inspection and testing)
  To preserve the output file, the unittest should be invoked with the following two environment variables set:
    - PREPPIPE_TEST_EXPORT_WRITE_DIR: the directory where the files will be copied to
    - PREPPIPE_TEST_EXPORT_TEST_NAME: the test name who can write to this directory
  """
  enabledExportTest = os.environ.get("PREPPIPE_TEST_EXPORT_TEST_NAME")
  if enabledExportTest == testname:
    # do the copy
    copyDest = os.environ.get("PREPPIPE_TEST_EXPORT_WRITE_DIR")
    if copyDest is None:
      raise RuntimeError("PREPPIPE_TEST_EXPORT_WRITE_DIR not specified")
    print("Copying " + srcdir + " to " + copyDest)
    shutil.copytree(srcdir, copyDest, dirs_exist_ok=True)
