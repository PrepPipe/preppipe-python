# 该脚本生成 preppipe-docs 仓中所有需要由本仓库生成的文档
import tempfile
import yaml
import os
import preppipe
import preppipe.language
import preppipe.pipeline
import preppipe.pipeline_cmd

MKDOCS_OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../docs_mkdocs"))

LANG_DICT = {
  "zh_cn" : "zh",
  "zh_hk" : "zh-Hant",
  "en" : "en",
}
ASSET_LISTING_INFO : dict[str, str | dict[str, str]] = {
  "base_path" : f"{MKDOCS_OUT_PATH}/docs/",
  "base_path_ref" : "/",
  "common_export_path" : "generated/common/assetlistings",
}
ASSET_LISTING_INFO["language_specific_docs"] = {lang : prefix + "/generated/script/assets.md" for lang, prefix in LANG_DICT.items()}

def main():
  print(f"Writing docs to: {MKDOCS_OUT_PATH}")
  os.makedirs(MKDOCS_OUT_PATH, exist_ok=True)

  # 前端命令文档
  print("Generating command docs...")
  for lang, prefix in LANG_DICT.items():
    preppipe.language.Translatable.language_update_preferred_langs([lang])
    cmddocs_path = os.path.join(MKDOCS_OUT_PATH, "docs", prefix, "script")
    os.makedirs(cmddocs_path, exist_ok=True)
    preppipe.pipeline.invoke_tool_main("cmddocs", [
      "--namespace=vn",
      f"--markdown={cmddocs_path}/cmddocs.md",
    ])

  # 资源列表
  print("Generating asset listing...")
  ymlfile = tempfile.NamedTemporaryFile(mode="w", delete=False)
  yaml.dump(ASSET_LISTING_INFO, ymlfile)
  ymlfile.close()
  preppipe.pipeline.invoke_tool_main("assetmanager", [
    "--export-docs", ymlfile.name,
  ])
  os.remove(ymlfile.name)

if __name__ == "__main__":
  main()
