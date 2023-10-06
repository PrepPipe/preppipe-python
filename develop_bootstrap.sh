#!/usr/bin/env bash

# install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg
# dependendies for building
sudo python3 -m pip install build twine
# dependencies for preppipe
sudo python3 -m pip install llist odfpy python-docx chardet marko pillow pydub numpy ghostscript editdistance bidict pypinyin graphviz
sudo python3 -m pip install antlr4-python3-runtime>=4.10

# do a build to generate src/preppipe/_version.py
python3 -m build

# To create pyinstaller package, run:
# pyinstaller --collect-data preppipe -F preppipe_cli.py
# (Add --paths <venv>/lib/python3.10/site-packages/ if using virtual environment)
# (Add --icon=preppipe.ico to include the icon if on Windows or Mac)

# if for whatever reason the build fails, src/preppipe/_version.py can be created with the following content: (remove the comment)
#-------------------------------------------------------------------------------
# # coding: utf-8
# # file generated by setuptools_scm
# # don't change, don't track in version control
# __version__ = version = '0.0.1.post3'
# __version_tuple__ = version_tuple = (0, 0, 1)
#-------------------------------------------------------------------------------
