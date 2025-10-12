# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import json
import os
from ..pipeline import *
from ..irbase import *
from ..inputmodel import *

# pylint: disable=pointless-string-statement
'''
样例输出：假设素材保存到 <assetdir> 下

{
  "files": [
    {
      "name": "测试1", // 去掉路径与拓展名之后的名称，这个会决定后面生成的文件名、对象名等
      "path": "test/path/测试1.docx", // 原路径，用于调试
      "body": <BodyScope> // 下面举例
    }
  ],
  "embedded": [ // 内嵌素材列表，所有支持的内嵌素材都会列在这
    {
      "parent": "test/path/测试1.docx",
      "srcref": "1.png", // 素材在文档内的路径， docx 与 odt 会使用不同的路径
      "extracted": "anon_1.png", // 素材在 assetdir 中的相对位置位置 (<assetdir>/anon_1.png)
      "size": [800, 600], // 图片大小
      "bbox": [0, 0, 800, 600], // 对于所有图片，我们都先打开一次，分析一下 bbox （即哪部分不是空白的），这样后续处理时不用再打开图片
    }
  ],
}

<BodyScope>: [ // 代表一个文件或是一个内嵌的域
  [ // 每个段落都是一个 array, 对应原来 InputModel 的 Block
    {
      "type": "text", // 文本，可能带有格式信息
      "content": "你好",
      "format": { // 可选，没有的话就是默认黑色字体，无加粗倾斜等效果
        "bold": true
      }
    },
    {
      "type": "text",
      "content": ",",
    },
    {
      "type": "text",
      "content": "世界！",
      "format": {
        "italic": true
      }
    }
  ],
  [ // 第二个段落
    {
      "type": "assetref", // 表示内嵌资源（现在应该只有图片）
      "ref": "1.png", // 引用上面内嵌的 1.png
    }
  ],
  [ // 第三个段落
    {
      "type": "centered", // 纯文本居中时生成，不包含格式信息（颜色、加粗等）。对应当前 InputModel 中的 SpecialBlock (reason=centered)
      "content": "图一：ABCD" // 单行或多行文本，\n 连接，最后一行没有 \n
    }
  ],
  [
    {
      "type": "codeblock", // 代码块，纯文本有段落背景色时生成。对应当前 InputModel 中的 SpecialBlock (reason=backgroundcolor)
      "content": "ABCDEFG" // 单行或多行文本，\n 连接，最后一行没有 \n
    }
  ],
  [
    {
      "type": "list", // 列表
      "items": [
        <BodyScope>, // 第一项，如果有下一级列表的话也包含在这里
        ... // 后续每一项都有一个独立的 BodyScope
      ]
    }
  ]
]
'''

def _export_inputs(inputs : list[IMDocumentOp], assetdir : str, jsonpath : str):
  print("Exporting input documents to", jsonpath, "with assets in", assetdir) # 只为调试
  json_files = []
  json_embedded = []

  def process_asset(assetdata: AssetData, parentpath: str)->str:
    #处理内嵌素材，返回srcref
    if isinstance(assetdata,ImageAssetData):
      srcref=assetdata._loc.get_file_path()
      extracted=os.path.basename(srcref)
      with PIL.Image.open(assetdata.backing_store_path) as f:
        bbox=f.getbbox()
        size=f.size
        f.save(os.path.join(assetdir,extracted))
      json_embedded.append({
        "parent":parentpath,
        "srcref":srcref,
        "extracted":extracted,
        "size":size,
        "bbox":bbox
      })
      return srcref
    raise NotImplementedError(type(assetdata).__name__)
    return ""

  def process_text_fragment(v:TextFragmentLiteral):
    format_dict = {}
    for attr,value in v.style.value:
      match attr:
        case TextAttribute.Bold:
          if value:
            format_dict["bold"]=True
        case TextAttribute.Italic:
          if value:
            format_dict["italic"]=True
        case TextAttribute.TextColor:
          format_dict["color"]=str(value)
        # case TextAttribute.BackgroundColor:
        #   format_dict["backgroundcolor"]=str(value)
    
    text_item = {"type": "text", "content": v.content.value}
    if format_dict:
      text_item["format"] = format_dict
    return text_item

  def process_block(block: Block,parentpath:str):
    block_ops = list(block.body)
    if len(block_ops) == 1:
      op = block_ops[0]
      if isinstance(op, IMSpecialBlockOp):
        reason = op.get_attr(IMSpecialBlockOp.ATTR_REASON)
        content_list = []
        for i in range(op.content.get_num_operands()):
          v = op.content.get(i)
          if isinstance(v, StringLiteral):
            content_list.append(v.get_string())
        content_str = "\n".join(content_list)
        
        if reason == IMSpecialBlockOp.ATTR_REASON_CENTERED:
          return [{"type": "centered", "content": content_str}]
        elif reason == IMSpecialBlockOp.ATTR_REASON_BG_HIGHLIGHT:
          return [{"type": "codeblock", "content": content_str}]
        else:
          raise NotImplementedError(f"Unsupported special block reason: {reason}")
      
      elif isinstance(op, IMListOp):
        items = []
        for i in range(op.get_num_items()):
          region = op.get_item(i + 1)
          body_scope = []
          for sub_block in region.blocks:
            body_scope.append(process_block(sub_block, parentpath))
          items.append(body_scope)
        return [{"type": "list", "items": items}]
      
      elif isinstance(op, IMTableOp):
        raise NotImplementedError("Table export not implemented")
    
    # 处理普通文本块
    paragraph = []
    for op in block_ops:
      if not isinstance(op, IMElementOp):
        continue
      for i in range(op.content.get_num_operands()):
        v = op.content.get(i)
        if isinstance(v, StringLiteral):
          paragraph.append({"type": "text", "content": v.get_string()})
        elif isinstance(v, TextFragmentLiteral):
          paragraph.append(process_text_fragment(v))
        elif isinstance(v, AssetData):
          paragraph.append({"type": "assetref", "ref": process_asset(v, parentpath)})
        else:
          raise NotImplementedError(f"Unsupported value type: {type(v)}")
    return paragraph

  for doc in inputs:
    doc_body = []
    parentpath = doc.location.get_file_path()
    for block in doc.body.blocks:
      doc_body.append(process_block(block, parentpath))
    
    doc_entry = {
      "name": doc.name,
      "path": parentpath,
      "body": doc_body
    }
    json_files.append(doc_entry)
  
  json_result = {
    "files": json_files,
    "embedded": json_embedded
  }
  with open(jsonpath, 'w', encoding='utf-8') as f:
    json.dump(json_result, f, ensure_ascii=False, indent=2)



@TransformArgumentGroup('input-export', "Options for Input Export")
@BackendDecl('input-export', input_decl=IMDocumentOp, output_decl=IODecl(description='<json path>', nargs=1))
class _InputExport(TransformBase):
  _asset_dir : typing.ClassVar[str] = ""

  @staticmethod
  def install_arguments(argument_group : argparse._ArgumentGroup):
    argument_group.add_argument("--input-export-assetdir", nargs=1, type=str, default='')

  @staticmethod
  def handle_arguments(args : argparse.Namespace): # pylint: disable=protected-access
    _InputExport._asset_dir = args.input_export_assetdir
    if isinstance(_InputExport._asset_dir, list):
      assert len(_InputExport._asset_dir) == 1
      _InputExport._asset_dir = _InputExport._asset_dir[0]
    assert isinstance(_InputExport._asset_dir, str)
    if len(_InputExport._asset_dir) > 0 and not os.path.isdir(_InputExport._asset_dir):
      if os.path.exists(_InputExport._asset_dir):
        raise RuntimeError('--input-export-assetdir: assetdir "' + _InputExport._asset_dir + '" exists but is not a directory')
      else:
        os.makedirs(_InputExport._asset_dir)

  def run(self) -> None:
    assetdir = _InputExport._asset_dir
    if len(assetdir) == 0:
      assetdir = os.path.dirname(self.output)
    _export_inputs(self.inputs, assetdir, self.output) # type: ignore
