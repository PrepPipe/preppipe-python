#!/usr/bin/env bash

# install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg
sudo python3 -m pip install odfpy pillow pydub numpy ghostscript editdistance bidict build twine

# do a build to generate src/preppipe/_version.py
python3 -m build
