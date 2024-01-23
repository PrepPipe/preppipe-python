import os
import unittest
import typing
import tempfile
import shutil
import preppipe
import preppipe.pipeline_cmd
import preppipe.pipeline
from . import util
import warnings

class TestZHDocsRenPyExport(unittest.TestCase):
  LANGMODE : typing.ClassVar[list[str]] = ["zh_cn", "zh_hk"]

  @classmethod
  def setUpClass(cls):
      # 解决错误 ResourceWarning: Enable tracemalloc to get the object allocation traceback
      warnings.simplefilter('ignore', ResourceWarning)

  def test_zh_docs(self):
    basedir = os.path.dirname(os.path.realpath(__file__))
    assetdir = os.path.join(basedir, "assets")
    dirname = os.path.join(basedir, "zh")
    self.maxDiff = None
    with tempfile.TemporaryDirectory() as project_dir:
      # print("TestZHDocsRenPyExport.test_zh_docs(): export directory at "+ project_dir)
      for file in os.listdir(dirname):
        filebase, ext = os.path.splitext(file)
        def handle_input(input_flag : str):
          # 给每个语言模式都测试一下
          testpath = os.path.join(project_dir, filebase)
          for lang in self.LANGMODE:
            shutil.rmtree(testpath, ignore_errors=True)
            args = ["--language", lang,
                    # "-v",
                    "--searchpath", assetdir,
                    input_flag, os.path.join(dirname, file),
                    "--cmdsyntax", "--vnparse", "--vncodegen",
                    "--vn-blocksorting", "--vn-entryinference", "--vn-longsaysplitting",
                    "--renpy-codegen",
                    "--renpy-export", testpath]
            preppipe.pipeline.pipeline_main(args)
            strdump = util.collectDirectoryDataAsText(testpath, excludepattern="preppipert.rpy")
            # print(strdump)
            # 如有需要就输出
            util.copyTestDirIfRequested(testpath, "TestZHDocsRenPyExport.test_zh_docs")
            # 再取已保存的内容
            # 如果我们还没保存内容，那么这是第一次运行，只记录
            expected_content = ""
            filerootbase = filebase.split('_')[0]
            expected_path = os.path.join(dirname, filerootbase + '_' + lang +".txt")
            if os.path.exists(expected_path):
              with open(expected_path, "r", encoding="utf-8") as f:
                expected_content = f.read()
            else:
              with open(expected_path, "w", encoding="utf-8") as f:
                f.write(strdump)
              expected_content = strdump
            self.assertListEqual(expected_content.splitlines(), strdump.splitlines())
        if ext == ".odt":
          # 找到了个样例
          handle_input("--odf")
        elif ext == ".docx":
          if filebase not in ("zh2", "demo"):
            # 暂时把这两个去掉；docx 和 odt 对匿名图片的默认命名不一样，比较的时候总把这些不一致当作错误
            handle_input("--docx")
        elif ext == ".txt" and filebase.split('_')[-1] in ("utf8", "gb2312"):
          handle_input("--txt")
        elif ext == ".md":
          handle_input("--md")

if __name__ == '__main__':
  unittest.main()
