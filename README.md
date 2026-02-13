# 语涵编译器 PrepPipe Compiler

语涵编译器是一个（仍在开发中的）视觉小说开发工具，使用更符合自然语言（比如中文）书写习惯的剧本格式，提供更低成本更快速的 Demo 构建功能，帮助视觉小说开发者实现“小步快跑”的开发流程。

PrepPipe Compiler is a (work-in-progress) visual novel development tool which allows you to use a script format closer to natural language (e.g., English) writing and create demos with minimum cost and effort, enabling visual novel development with a smaller feedback loop (effort to outcome).

此工具读取以下内容：
* 剧本 (docx/odt 文档，Markdown, 纯文本 TXT)
* （可选）资源素材（背景，立绘，音乐等）

此工具可以产出：
* 游戏引擎工程文件（脚本和转换/生成的资源素材）
* 数据、报告（改进中）

What you need to feed into the tool:
* Story scripts (docx/odt documents, markdown, plain text)
* (Optional) assets (backgrounds, character sprites, music, etc)

What you can get from the tool:
* Game engine project files (scripts and converted/generated assets)
* Statistics & Reports (WIP)

本程序已以抢先体验模式上架至 [Steam](https://store.steampowered.com/app/2961200/)。

We have released the program as Early Access on [Steam](https://store.steampowered.com/app/2961200/).

### 文档 Documentation

该项目的文档由 [preppipe-docs 仓库](https://github.com/PrepPipe/preppipe-docs) 管理，[文档页面可由此打开。](https://preppipe.github.io/preppipe-docs/) 打包的程序内也会附带相同的文档。

The documentation is managed in the [preppipe-docs repo](https://github.com/PrepPipe/preppipe-docs). [You can open the page here.](https://preppipe.github.io/preppipe-docs/) The same documentation is also included in the release packages.

### 素材资源 Assets

该项目的资源（背景、角色立绘等）存放在 [preppipe-assets 仓库](https://github.com/PrepPipe/preppipe-assets) 中。为方便从镜像获取，该仓库需要您手动下载。推荐将其置于仓库下 `assets` 目录中（或者使用 symlink）以使用 `build_assets.py`.

All assets (e.g., backgrounds and character sprites) are stored in the [preppipe-assets repo](https://github.com/PrepPipe/preppipe-assets). To simplify accessing this repo from a mirror, currently you will need to manually download / clone this repo. We recommend to put it at `assets` to enable use of `build_assets.py`.

### 下载与运行 Download and Run

目前我们只提供 64 位 Windows 系统的程序包，支持 Windows 10/11，不支持更早的 Windows 版本。其他系统如有需要的话请联系我们。打包好的程序可在 Github 的 release 页面获取，比如 [最新的开发中版本](https://github.com/PrepPipe/preppipe-python/releases/tag/latest-develop) 。用户请下载带 `full` 后缀的包 (`preppipe-windows-x64-full.7z`)，该包除了程序本体外还包含了第三方依赖（[ffmpeg](https://ffmpeg.org/)） 和程序文档。下载解压后请双击 `preppipe.exe` 以运行图形界面 (GUI)。

Currently we only provide prebuilt packages for 64-bit Windows system, supporting Windows 10/11 but not earlier versions of Windows. Please contact us if prebuilt packages for other platforms are desired. The packages are available from the release page on GitHub. For example, in [the latest develop build](https://github.com/PrepPipe/preppipe-python/releases/tag/latest-develop). End users please download packages with `full` suffix (`preppipe-windows-x64-full.7z`) which bundles third-party dependencies ([ffmpeg](https://ffmpeg.org/)) and documentations in addition to the program executables. Once it is downloaded and unzipped, please double-lick `preppipe.exe` to launch the graphical user interface (GUI).

### 论文 Publications

COG 2024: ["PrepPipe: Prototyping Compiler for Attainable Visual Novel Development"](http://doi.org/10.1109/CoG60054.2024.10645615)

[PDF 可从此处下载 | PDF Available here](https://www.researchgate.net/publication/383516971_PrepPipe_Prototyping_Compiler_for_Attainable_Visual_Novel_Development)

### 联系方式 Contact us

中文用户请加 QQ 群：732421719，或者关注 [B站：远行的泥土](https://space.bilibili.com/2132259509)

English users please use the [Github Discussions page](https://github.com/PrepPipe/preppipe-python/discussions) or the issue page on Github.

## 开发环境设置

目前运行本程序需要至少 Python 3.10 版本。需要开发的话请使用最低版本(3.10.x)，以免在其他使用最低版本的环境出错。

如果您想构建一个开发环境，您需要安装以下 Python 依赖项。推荐在一个 `venv` 中操作。
  * 构建需要 `build twine`
  * 运行时需要的包在 [setup.cfg](setup.cfg) 的 `options.install_requires` 和 `options.extras_require` 下
  * 部分依赖可能需要您拥有 C/C++ 编译环境，如果安装依赖时报错请按照提示操作。

（注：如果你使用 VSCode, 您可以在 `.vscode/settings.json` 中将 `"python.defaultInterpreterPath"` 指向 `venv` 中的 Python 解释器）

语涵编译器在运行时需要使用 `ffmpeg` 进行音视频的格式转换。请确保程序能在运行时找到它，比如把路径加到 `PATH` 中。

调试 Ren'Py 引擎整合相关的功能时，请将 [Ren'Py SDK](https://renpy.org/latest.html) 下载并解压到仓库根目录下 `renpy-sdk` 目录中。`renpy-sdk` 已在 `.gitignore` 中。注意，解压 Ren'Py 提供下载的压缩包时，解压的路径会带上 Ren'Py 的版本号 （比如 `renpy-8.5.2-sdk`）,请将该版本号从目录名称中删除。语涵编译器的发布包也会将 Ren'Py SDK 解压后置于 `renpy-sdk` 目录下。

开发时请确保本仓库里的 `src` 目录在 `PYTHONPATH` 中，比如：(假设这个 `preppipe` 仓库在 `/path/to/preppipe`)
```
export PYTHONPATH=/path/to/preppipe/src
```

这样 `import preppipe` 才不会报错。如果您使用 VSCode, 您可以在仓库根目录下创建 `.env` 文件并加入以下内容：
```
PYTHONPATH=/path/to/preppipe/src
```

并在 `.vscode/settings.json` 中加入如下值来自动设置 `PYTHONPATH`
```
"python.envFile": "${workspaceFolder}/.env"
```

另外我们推荐执行以下操作来注入设置。目前这能使 `git` 更好地显示中文路径（部分素材有用到）。
```
git config --local include.path $PWD/gitconfig
```

## 更新后所需操作

本仓库有部分内容需要由程序生成，该步骤需要在(1)刚 `git clone` 完仓库时，或(2)相应的部分有改动时手动执行。CI 中每次构建完整的发布包都会执行这些操作。

需要手动执行的有：（请在上述开发环境配置完毕后执行）
* 资源文件处理。请在获取[资源仓](#素材资源-assets)后，在仓库根目录下运行 `python3 ./build_assets.py` 以生成 `src/preppipe/assets/_install` 下的内容。该操作需要在资源列表更新时或任意资源类型保存的的内部数据结构改变时重新进行。
* GUI 中 PySide6 `.ui` 文件编译。请在 `src/preppipe_gui_pyside6/forms` 目录下将所有诸如 `xxx.ui` 的文件使用命令 `pyside6-uic xxx.ui generated/ui_xxx.py` 编译成 `.py`。如果您使用 Linux，您可以直接用该目录下的 `Makefile`。其他环境下可使用同目录下的 `makeall.py`。该操作需要在任意 .ui 文件更改后重新执行。

## GUI启动

在完成上述配置后，于项目根目录`python ci/preppipe_gui_entry.py`启动即可。

## 对于windows用户

在配置过程中，您可能碰到安装`editdistance`时报错的问题，请参考#[本地安装](https://www.jianshu.com/p/f1ca375f5fd1)解决。
另外，如果提示找不到`pyaudioop`，可以通用`pip install audioop-lts`解决。