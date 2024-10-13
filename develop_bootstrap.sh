#!/usr/bin/env bash

# install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg
# dependendies for building
sudo python3 -m pip install build twine
# dependencies for preppipe
sudo python3 -m pip install llist odfpy python-docx chardet marko pyyaml pillow pydub numpy scipy matplotlib opencv-python ghostscript editdistance bidict pypinyin graphviz
sudo python3 -m pip install antlr4-python3-runtime>=4.10

# Following steps are optional but recommended

# add the gitconfig
git config --local include.path $PWD/gitconfig

# do a build to generate src/preppipe/_version.py
python3 -m build
