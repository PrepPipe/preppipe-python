#!/usr/bin/env bash

# install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg
sudo python3 -m pip install odfpy pillow pydub numpy ghostscript editdistance bidict build twine pypinyin graphviz

# do a build to generate src/preppipe/_version.py
python3 -m build

# if for whatever reason the build fails, src/preppipe/_version.py can be created with the following content: (remove the comment)
#-------------------------------------------------------------------------------
# # coding: utf-8
# # file generated by setuptools_scm
# # don't change, don't track in version control
# __version__ = version = '0.0.1.post3'
# __version_tuple__ = version_tuple = (0, 0, 1)
#-------------------------------------------------------------------------------
