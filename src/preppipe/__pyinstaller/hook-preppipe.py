# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('preppipe', excludes=['__pyinstaller'])
