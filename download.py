#!/usr/bin/env python3
import onedriveapi
import os
import sys

rootdir = "d:\\test"

tokenjson = onedriveapi.init()
if (tokenjson is None):
    exit()

res = onedriveapi.task_getlist(sys.argv[1])

for item in res:
    if item["is_file"]:
        # 拉取下载地址
        down_info = onedriveapi.pull_dirve_file(item["id"])
        if down_info is None:
            assert (False)

        # 下载文件
        down_result = onedriveapi.down_file(down_info["url"],
                                            rootdir + item["path"] + '/',
                                            down_info["name"],
                                            item["file_size"])
