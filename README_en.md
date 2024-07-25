# PrepPipe Compiler

[简体中文版请点此处](README.md)

PrepPipe Compiler is a (work-in-progress) Python program that generates visual novel project files from rich-text input. We currently support the following formats out of the box:
  * [Ren'Py](https://www.renpy.org/) project files
  * Plain text dumps. This is intended for external programs / scripts. Note that the text dump does not support all features; you would need to implement a Python plugin for complete functionalities.

Currently, the program supports the following list of input formats:
  * .odt (compatible with LibreOffice)
  * .docx (compatible with MS Office)
  * .md (compatible with Github Markdown)
  * .txt

The compiler in this repo uses a command line interface (CLI). It is recommended that you try the [all-in-one package](https://github.com/PrepPipe/preppipe-latest-all-in-one), which in addition contains a GUI ([repo here](https://github.com/PrepPipe/preppipe_gui)) and third-party dependencies.

NOTE: at the time of writing, the GUI does not support English yet; we will add English support later.

If you want to use the CLI, you can run the program with:
```
python3 -m preppipe.pipeline_cmd <commands...>
```

We do not have user-oriented documentations yet; will add later...
