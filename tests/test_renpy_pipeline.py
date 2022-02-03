#!/usr/bin/env python3

import os
import unittest
import tempfile
import preppipe.deprecated.documentmodel
import preppipe
import preppipe.deprecated.documentimport.opendocument
import preppipe.deprecated.vnimport.document
import preppipe.deprecated.vnexport.renpy
from . import util

class TestRenPyPipeline(unittest.TestCase):
  def test_odf_import(self):
    filename = os.path.dirname(os.path.realpath(__file__)) + "/renpy_pipeline_odf.odt"
    filedata = open(filename, "rb")
    docmodel = preppipe.deprecated.documentimport.opendocument.import_odf(filedata, filename)
    filedata.close()
    vnmodel = preppipe.deprecated.vnimport.document.get_visual_novel_model_from_document(docmodel)
    with tempfile.TemporaryDirectory() as project_dir:
      print("TestRenPyPipeline.test_odf_import(): export directory at "+ project_dir)
      preppipe.deprecated.vnexport.renpy.export_renpy(vnmodel, project_dir)
      print(util.collectDirectoryDataAsText(project_dir))
      util.copyTestDirIfRequested(project_dir, "TestRenPyPipeline.test_odf_import")
    # self.assertEqual(docmodel.__str__(), expected_str)

if __name__ == '__main__':
  unittest.main()
