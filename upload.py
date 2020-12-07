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
            #远程目录和文件名去掉非法字符
            tmp["filename"] = onedriveapi.replacespecialcharactor(dir_file)
            tmp["absolutepath"] = onedriveapi.replacespecialcharactor(res[1].replace('\\', '/'))

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

onedriveapi.uninit()


dir_list.reverse()
for item in dir_list:
    try:
        os.rmdir(item)
    except Exception as e:
        pass