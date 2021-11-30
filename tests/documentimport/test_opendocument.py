#!/usr/bin/env python3

import os
import unittest
import preppipe.documentimport.opendocument

class TestOpenDocumentImport(unittest.TestCase):
  def helper_load(name):
    filename = os.path.dirname(os.path.realpath(__file__)) + "/" + name
    filedata = open(filename, "rb")
    docmodel = preppipe.documentimport.opendocument.import_odf(filedata, filename)
    filedata.close()
    return docmodel
  
  def test_load_puretext(self):
    docmodel = TestOpenDocumentImport.helper_load("opendocument_puretext.odt")
    expected_str = """Test1

_This_ is a **TEST**!!!This 
This is <#c9211e>Another</#c9211e> <B#ffff00>Test e</B#ffff00>
Centralized text


"""
    self.assertEqual(docmodel.__str__(), expected_str)

  def test_load_withimage(self):
    docmodel = TestOpenDocumentImport.helper_load("opendocument_withimage.odt")
    docstrDump = docmodel.__str__()
    print("test_load_withimage:")
    print(docstrDump)
    expected_str = """<#0 PNG(1920, 1080) MD5: 41bb8fddfc2cd80c0592bd8df4b44b2a>

TextBoxTextBox2Test1

SecondParagraph

_This_ is a **TEST**!!! <#1 PNG(400, 600) MD5: 9bddaca0b360e80374249fa3c685e5be>This
This is <#c9211e>Another</#c9211e> <B#ffff00>Test e</B#ffff00>
Centralized text


"""
    self.assertEqual(docstrDump, expected_str)

if __name__ == '__main__':
  unittest.main()
