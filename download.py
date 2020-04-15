#!/usr/bin/env python3
import onedriveapi
import os
import sys

def is_need_sync(localfilepath, remotesize):
    if (not os.path.exists(localfilepath)):
        return True

    localsize = os.path.getsize(localfilepath)
    if (localsize != remotesize):
        return True

    return False


def download_folder(path, need_sync):
    res = onedriveapi.task_getlist(path)

    for item in res:
        if item["is_file"]:
            #如果添加了同步参数，验证下是否需要同步
            if (need_sync is True) and not is_need_sync(
                    rootdir + item["path"] + '/' + item["name"],
                    item["file_size"]):
                print("sync:file %s is NOT need sync" % rootdir + item["path"] + '/' +
                      item["name"])
                continue
            elif need_sync is True:
                print("sync:file %s is need sync" % (rootdir + item["path"] + '/' +
                                                     item["name"]))

            # 拉取下载地址
            down_info = onedriveapi.pull_dirve_file(item["id"])
            if down_info is None:
                assert (False)

            # 下载文件
            down_result = onedriveapi.down_file(down_info["url"],
                                                rootdir + item["path"] + '/',
                                                item["name"],
                                                item["file_size"])

def download_file(path):
    item = onedriveapi.getfiledownloadurl(path)
    
    # 下载文件
    down_result = onedriveapi.down_file(item["url"],
                                                rootdir + item["path"] + '/',
                                                item["name"],
                                                item["file_size"])


need_sync = False
print("%d" % len(sys.argv))
if len(sys.argv) == 3 and sys.argv[2] == '-s':
    need_sync = True

rootdir = "d:\\test"

tokenjson = onedriveapi.init()
if (tokenjson is None):
    exit()

if(onedriveapi.isurlfile(sys.argv[1])):
    download_file(sys.argv[1])
else:
    download_folder(sys.argv[1],need_sync)


