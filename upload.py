#!/usr/bin/env python3
import os
import onedriveapi

def findfile(root_path, file_list, dir_list):
    #获取该目录下所有的文件名称和目录名称
    dir_or_files = os.listdir(root_path)
    for dir_file in dir_or_files:
        #获取目录或者文件的路径
        dir_file_path = os.path.join(root_path, dir_file)
        #判断该路径为文件还是路径
        if os.path.isdir(dir_file_path):
            dir_list.append(dir_file_path)
            #递归获取所有文件和目录的路径
            findfile(dir_file_path, file_list, dir_list)
        else:
            tmp = {}
            res = root_path.split(rootpath)
            tmp["filepath"] = dir_file_path
            tmp["filename"] = dir_file
            tmp["absolutepath"] = res[1].replace('\\', '/')
            file_list.append(tmp)


tokenjson = onedriveapi.init()
if tokenjson is None:
    exit()
    
file_list = []
dir_list = []
rootpath = "d:\\test"
findfile(rootpath, file_list, dir_list)
for item in file_list:
    remotepath = "/upload" + item["absolutepath"]
    ret = onedriveapi.upProcess(item["filepath"], item["filename"], remotepath)
    try:
        if (ret is True):
            os.remove(item["filepath"])  # 删除文件
    except Exception as e:
        print("remove file error %s" % e.__str__)

dir_list.reverse()
for item in dir_list:
    try:
        os.rmdir(item)
    except Exception as e:
        pass