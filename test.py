import os
import uuid

g = os.walk("pandaLog_fbfcdf5d")

dirName = ""

for path, dir_list, file_list in g:
    for dir_name in dir_list:
        dirName = dir_name

name = "pandaLog_fbfcdf5d" + "/" + dir_name + "/" + dir_name+".log"

print(name)

data = ""
with open(name, "r", encoding="utf-8") as f:
    data = f.read()

print(data)
