# 语涵编译器 (PrepPipe Compiler)

[English version available here.](README_en.md)

语涵编译器是一个（仍在开发中的）从富文本文档中生成视觉小说游戏工程文件的 Python 程序，目前支持以下导出形式：
  * [Ren'Py](https://www.renpy.org/) 工程目录
  * 纯文本发言信息，方便外部自定义工具读取。注：此为“阉割”后的版本，要有完整功能的话需要为本程序写 Python 插件。

目前支持的输入格式如下：
  * .odt (兼容 LibreOffice)
  * .docx (兼容 MS Office)
  * .md (兼容 Github Markdown)
  * .txt

语涵编译器本体（此仓库中的内容）是一个命令行程序，推荐使用[整合包](https://github.com/PrepPipe/preppipe-latest-all-in-one)。整合包中除了语涵编译器本体外也包含图形界面（[代码仓库在这](https://github.com/PrepPipe/preppipe_gui)）和其他的第三方依赖项。

由于文档不足，目前不推荐使用命令行，请尽可能使用图形界面。如果需要使用命令行，请以以下命令形式运行本程序：
```
python3 -m preppipe.pipeline_cmd <commands...>
```

文档在写了在写了。（新建文件夹）

QQ群：732421719
