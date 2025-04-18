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

我们正在尝试将本程序上架至 [Steam](https://store.steampowered.com/app/2961200/)，敬请期待。

We are working towards releasing the program on [Steam](https://store.steampowered.com/app/2961200/).

### 文档 Documentation

该项目的文档由 [preppipe-docs 仓库](https://github.com/PrepPipe/preppipe-docs) 管理，[文档页面可由此打开。](https://preppipe.github.io/preppipe-docs/) 打包的程序内也会附带相同的文档。

The documentation is managed in the [preppipe-docs repo](https://github.com/PrepPipe/preppipe-docs). [You can open the page here.](https://preppipe.github.io/preppipe-docs/) The same documentation is also included in the release packages.

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

目前本程序需要至少 Python 3.10 版本。

如果您想构建一个开发环境，您需要安装以下 Python 依赖项。推荐在一个 `venv` 中操作。
  * 构建需要 `build twine`
  * 运行时需要的包在 [setup.cfg](setup.cfg) 的 `options.install_requires` 和 `options.extras_require` 下
  * 部分依赖（比如 llist）可能需要您拥有 C/C++ 编译环境，如果安装依赖时报错请按照提示操作。

（注：如果你使用 VSCode, 您可以在 `.vscode/settings.json` 中将 `"python.defaultInterpreterPath"` 指向 `venv` 中的 Python 解释器）

语涵编译器在运行时需要使用 `ffmpeg` 进行音视频的格式转换。请确保程序能在运行时找到它，比如把路径加到 `PATH` 中。

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
