# https://github.com/pyinstaller/pyinstaller/issues/3843
from PyInstaller.utils.hooks import collect_data_files

collected_data = collect_data_files('cairosvg')
datas = []
for item_path, dest in collected_data:
  datas.append((item_path, "."))
