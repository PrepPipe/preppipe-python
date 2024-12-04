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

## 开发环境设置

如果您想构建一个开发环境，您需要安装以下 Python 依赖项。推荐在一个 `venv` 中操作。
  * 构建需要 `build twine`
  * 运行时需要的包在 [setup.cfg](setup.cfg) 的 `options.install_requires` 和 `options.extras_require` 下
  * 部分依赖（比如 llist）可能需要您拥有 C/C++ 编译环境，如果安装依赖时报错请按照提示操作。

语涵编译器在运行时需要使用 `ffmpeg` 进行音视频的格式转换。请确保程序能在运行时找到它，比如把路径加到 `PATH` 中。

要在 Python 中使用 `import preppipe` 等的话，请确保本仓库里的 `src` 目录在 `PYTHONPATH` 中，比如：(假设这个 `preppipe` 仓库在 `/path/to/preppipe`)
```
export PYTHONPATH=/path/to/preppipe/src
```

另外我们推荐执行以下操作来注入设置。目前这能使 `git` 更好地显示中文路径（部分素材有用到）。
```
git config --local include.path $PWD/gitconfig
```
