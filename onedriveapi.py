#!/usr/bin/env python3
import requests
import json
import yaml
import config
import os
import time
import threading
import urllib
import copy
from concurrent.futures import ThreadPoolExecutor

#https://docs.microsoft.com/en-us/onedrive/developer/rest-api/getting-started/graph-oauth?view=odsp-graph-online

url = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?response_type=code&client_id={client_id}&redirect_uri={domain}&scope=offline_access%20files.readwrite.all'

settings = {}
tokenstream = {}
downloadinfos = []
semlockdownload = ""
upload_thread_pool = []
download_thread_pool = []
semlockupload = ""
tokenjson = {}

upload_big_thread_pool = {}

#" * : < > ? \ / |均为特殊字符  上传时需要替换
def replacespecialcharactor(remotepath):
    remotepath = remotepath.replace("*","_")
    remotepath = remotepath.replace("\"","_")
    remotepath = remotepath.replace("<","_")
    remotepath = remotepath.replace(">","_")
    remotepath = remotepath.replace(":","_")
    remotepath = remotepath.replace("?","_")
    remotepath = remotepath.replace("|","_")
    return remotepath


#上传成功时删除文件
def deletefile(filepath):
    try:
        os.remove(filepath)  # 删除文件
    except Exception as e:
        print("remove file error %s" % e.__str__)

class MulThreadDownload(threading.Thread):
    def __init__(self, url, startpos, endpos, f):
        super(MulThreadDownload, self).__init__()
        self.url = url
        self.startpos = startpos
        self.endpos = endpos
        self.fd = f

    def download(self):
        global semlockdownload
        # print("start thread:%s at %s" % (self.getName(), time.time()))
        headers = {"Range": "bytes=%s-%s" % (self.startpos, self.endpos)}
        trytimes = 0
        while True:
            try:
                res = requests.get(self.url, headers=headers, timeout=100)
                break
            except Exception as e:
                if trytimes > 9999:
                    print("download error,try next")
                    trytimes += 1
                    time.sleep(20)

        # res.text 是将get获取的byte类型数据自动编码，是str类型， res.content是原始的byte类型数据
        # 所以下面是直接write(res.content)
        self.fd.seek(self.startpos)
        self.fd.write(res.content)
        semlockdownload.release()
        # print("stop thread:%s at %s" % (self.getName(), time.time()))
        self.fd.close()

    def run(self):
        self.download()


class MulThreadUpload(threading.Thread):
    def __init__(self, remotePath, filename, target_filename):
        super(MulThreadUpload, self).__init__()
        self.remotePath = remotePath
        self.filename = filename
        self.target_filename = target_filename

    def upload(self):
        global tokenjson
        global semlockupload

        ret = False
        trytime = 0

        while True:
            if self.remotePath == "None":
                self.remotePath = "/"
            url = config.app_url + \
                '/v1.0/me/drive/items/root:{}/{}:/content'.format(urllib.parse.quote(self.remotePath), urllib.parse.quote(self.filename))

            while True:
                headers = {
                    'Authorization':
                    'bearer {}'.format(tokenjson["access_token"]),
                    'Content-Type': 'application/octet-stream',
                }
                try:
                    pull_res = requests.put(url,
                                            headers=headers,
                                            data=open(self.target_filename, 'rb'),
                                            timeout=30)
                    break
                except Exception as e:
                    if (trytime > 99999):
                        return False
                    print("putfilesmall connect error try next")
                    print(e.__str__)
                    time.sleep(20)
                    trytime = trytime + 1
                    continue

            pull_res = json.loads(pull_res.text)
            if 'error' in pull_res.keys():
                if (trytime > 99999):
                    break
                print("putfilesmall ret error %s" % pull_res)
                reacquireToken()
                trytime = trytime + 1
            else:
                ret = True
                break

        semlockupload.release()
        if ret is True:
            deletefile(self.target_filename)
        return ret

    def run(self):
        self.upload()

#如果是大文件等待下载完毕再返回，否则立即返回
def down_file(url, filepathdir, filename, filesize):
    global semlockdownload
    global download_thread_pool

    if len(download_thread_pool) > 50:
        for i in download_thread_pool:
            i.join()
        download_thread_pool.clear()

    # 获取文件的大小和文件名
    filefullpath = filepathdir + filename
    print("down_file download:%s" % filefullpath)

    if not os.path.exists(filepathdir):
        # 如果不存在则创建目录
        os.makedirs(filepathdir)

    # 线程数
    threadnum = 0

    #文件大于1MB时.每10MB都分配一个线程
    sizemb = filesize//1024//1024
    if(sizemb == 0):
        threadnum = 1
    else:
        threadnum = sizemb // 10

    if (threadnum == 0):
        threadnum = 1

    #只有一个线程时，直接一次性下载完整文件
    step = filesize // threadnum

    mtd_list = []
    start = 0
    end = -1

    # 请空并生成文件
    tempf = open(filefullpath, 'w')
    tempf.close()
    # rb+ ，二进制打开，可任意位置读写
    with open(filefullpath, 'rb+') as f:
        fileno = f.fileno()
        # 如果文件大小为11字节，那就是获取文件0-10的位置的数据。如果end = 10，说明数据已经获取完了。
        while end < filesize - 1:
            semlockdownload.acquire()
            start = end + 1
            end = start + step - 1
            if end > filesize:
                end = filesize
            # print("start:%s, end:%s"%(start,end))
            # 复制文件句柄
            dup = os.dup(fileno)
            # print(dup)
            # 打开文件
            fd = os.fdopen(dup, 'rb+', -1)
            #print(fd)
            t = MulThreadDownload(url, start, end, fd)
            t.start()

            if(threadnum == 1):
                download_thread_pool.append(t)
                break
            else:
                mtd_list.append(t)

        for i in mtd_list:
            i.join()
    return True  # 完成单个文件下载


def reacquireToken():
    global settings
    global tokenjson
    redirect_url = "http://localhost/"
    ReFreshData = 'client_id={client_id}&redirect_uri={redirect_uri}&client_secret={client_secret}&refresh_token={refresh_token}&grant_type=refresh_token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = ReFreshData.format(client_id=settings["app_id"],
                              redirect_uri=redirect_url,
                              client_secret=settings["app_secret"],
                              refresh_token=tokenjson["refresh_token"])
    url = config.BaseAuthUrl + '/common/oauth2/v2.0/token'

    while True:
        try:
            res = requests.post(url, data=data, headers=headers,timeout=100)
            break
        except Exception as e:
            print("reacquireToken error try next")
            print(e.__str__)
            time.sleep(20)

    refreshtokenjson = json.loads(res.text)

    savetokenjson(refreshtokenjson)
    tokenjson = refreshtokenjson


#code获取以后执行一次就行，否则会报错
def redeemcode(code):
    global settings
    global tokenjson
    url = config.BaseAuthUrl + '/common/oauth2/v2.0/token'
    redirect_url = "http://localhost/"
    AuthData = 'client_id={client_id}&redirect_uri={redirect_uri}&client_secret={client_secret}&code={code}&grant_type=authorization_code'
    data = AuthData.format(client_id=settings["app_id"],
                           redirect_uri=redirect_url,
                           client_secret=settings["app_secret"],
                           code=code)
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'ISV|CuteOne|CuteOne/1.0'
    }
    res = requests.post(url, data=data, headers=headers)
    if (res.status_code == 400):
        print("redeemcode error")
        return None

    tokenjson = json.loads(res.text)

    savetokenjson(tokenjson)
    return tokenjson


def CreateUploadSession(fileName, remotePath):
    global tokenjson

    if remotePath == "None":
        remotePath = "/"
    url = config.app_url + \
        '/v1.0/me/drive/root:{}/{}:/createUploadSession'.format(
            urllib.parse.quote(remotePath), urllib.parse.quote(fileName))
    headers = {
        'Authorization': 'bearer {}'.format(tokenjson["access_token"]),
        'Content-Type': 'application/json'
    }
    data = {
        "item": {
            "@microsoft.graph.conflictBehavior": "fail",
        }
    }
    while True:
        try:
            pull_res = requests.post(url, headers=headers, data=json.dumps(data),timeout=100)
            if pull_res.status_code == 409:                                  #文件已经存在
                return False
            else:
                pull_res = json.loads(pull_res.text)
                if 'error' in pull_res.keys():
                    print("[%s] %s" % (fileName, pull_res))
                    #针对过多请求的情况，尝试休息一下
                    time.sleep(10)
                    reacquireToken()
                    pull_res = CreateUploadSession(fileName, remotePath)
                    return pull_res
                else:
                    return pull_res
        except Exception as e:
            print("CreateUploadSession error try next")
            print(e.__str__)
            time.sleep(20)


def putfilesmall(target_filename, fileName, remotePath, maxwait=50):
    global upload_thread_pool

    if len(upload_thread_pool) > maxwait:
        for i in upload_thread_pool:
            i.join()
        upload_thread_pool.clear()

    semlockupload.acquire()
    t = MulThreadUpload(remotePath,fileName,target_filename)
    t.start()
    upload_thread_pool.append(t)

    return True


def _file_seek(target_filename, fileName, startlength, length):
    startlength = int(startlength) if startlength == "0" else startlength
    with open(target_filename, 'rb') as f:
        f.seek(int(startlength))
        content = f.read(length)
    return content


def _uploadPart(target_filename,
                fileName,
                filesize,
                length,
                offset,
                uploadUrl='',
                trytime=99999999):
    length = int(length) if int(offset) + \
        int(length) < filesize else filesize - int(offset)
    endpos = int(offset) + length - 1 if int(offset) + \
        length < filesize else filesize - 1
    data = _file_seek(target_filename, fileName, offset, length)
    headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Length': str(length),
        'Content-Range': 'bytes {}-{}/{}'.format(offset, endpos, filesize)
    }
    times = 0
    while True:
        while True:
            try:
                pull_res = requests.put(uploadUrl, headers=headers, data=data, timeout=500)
                break
            except Exception as e:
                if (times > trytime):
                    break
                print("[%s] putfilebig connect error try next" % (target_filename))
                print(e.__str__)
                time.sleep(20)
                times = times + 1
        # pull_res = json.loads(pull_res.text)
        if pull_res.status_code == 202:
            pull_res = json.loads(pull_res.text)
            offset = pull_res['nextExpectedRanges'][0].split('-')[0]
            return {"code": 2, "offset": offset}
        elif pull_res.status_code == 201:
            #上传完毕
            return {"code": 0}
        else:
            print("[%s] putfilebig connect error code:%d" % (target_filename, pull_res.status_code))
            print(pull_res.text)
            time.sleep(20)
            times = times + 1


def putfilebig(target_filename, fileName, remotePath):
    crsession = CreateUploadSession(fileName, remotePath)
    filesize = os.path.getsize(target_filename)
    # 遇到Memory Error时，调整一下这里的length大小，避免爆内存
    length = 200 * 1024 * 1024
    offset = 0
    status = ""
    if crsession:
        while (status == ""):
            res = _uploadPart(target_filename, fileName, filesize,
                              length, offset, crsession['uploadUrl'])
            if res["code"] == 2:
                offset = res['offset']
            else:
                status = 0

    deletefile(target_filename)
    print("upload %s success" % target_filename)
    return True

#多线程wrapper
def putfilebigMultiple(target_filename, fileName, remotePath):
    global upload_big_thread_pool

    ret = upload_big_thread_pool.submit(
        putfilebig, target_filename, fileName, remotePath)

    return True


def upProcess(localpath, fileName, remotePath="None"):
    print("upload %s" % localpath)
    filesize = os.path.getsize(localpath)
    #if filesize > 4194304:
    # 这里暂时不使用微软的上传小文件API，这个API在网络不稳定的时候，容易导致突然断线，导致上传的内容不完整
    #先用多线程上传
    #return putfilebig(localpath, fileName, remotePath)
    #TODO:避免流量过大造成链接被阻止 https://docs.microsoft.com/en-us/sharepoint/dev/general-development/how-to-avoid-getting-throttled-or-blocked-in-sharepoint-online
    return putfilebigMultiple(localpath, fileName, remotePath)
    #else:
    #    return putfilesmall(localpath, fileName, remotePath)


def get_one_file_list(path=''):
    global tokenjson

    times=0
    trytime=999999999

    if path:
        BaseUrl = config.app_url + '/v1.0/me/drive/root:{}:/children?expand=thumbnails'.format(urllib.parse.quote(path))
    else:
        BaseUrl = config.app_url + '/v1.0/me/drive/root/children?expand=thumbnails'
    headers = {'Authorization': 'Bearer {}'.format(tokenjson["access_token"])}
    while True:
        try:
            get_res = requests.get(BaseUrl, headers=headers, timeout=30)
            break
        except Exception as e:
            if (times > trytime):
                break
            print("get_one_file_list error try next")
            print(e.__str__)
            time.sleep(20)
            times = times + 1

    get_res = json.loads(get_res.text)
    if 'error' in get_res.keys():
        print("get_one_file_list error %s" % get_res)
        reacquireToken()
        return get_one_file_list(path)
    else:
        if 'value' in get_res.keys():
            result = get_res['value']
            if '@odata.nextLink' in get_res.keys():
                pageres = get_one_file_list_page(get_res["@odata.nextLink"])
                result += pageres
            return {'code': True, 'msg': '获取成功', 'data': result}
        else:
            print("get_one_file_list value is None")
            return None


def get_one_file_list_page(url, total=[]):
    global tokenjson

    headers = {'Authorization': 'Bearer {}'.format(tokenjson["access_token"])}
    get_res = requests.get(url, headers=headers, timeout=30)
    get_res = json.loads(get_res.text)
    if 'value' in get_res.keys():
        total += get_res['value']
        if '@odata.nextLink' in get_res.keys():
            get_one_file_list_page(get_res["@odata.nextLink"], total)
        return total


def task_write(data):
    global downloadinfos
    dic = {
        "id": data["id"],
        "parentReference": data["parentReference"]["id"],
        "name": data["name"],
        "file": data["file"]["mimeType"],
        "path": data["parentReference"]["path"].replace("/drive/root:", ""),
        "is_file": 1,
        "file_size": data["size"]
    }
    threading.Lock()
    print("append downloadinfos path:%s filesize:%s" % (dic["path"]+ '/' + dic["name"],dic["file_size"]))
    downloadinfos.append(dic)
    threading.RLock()


def task_getlist(path=''):
    global tokenjson
    global downloadinfos
    res = get_one_file_list(path)
    thread_list = []  # 线程存放列表
    for i in res["data"]:
        if "folder" in i.keys():
            dic = {
                "id": i["id"],
                "parentReference": i["parentReference"]["id"],
                "name": i["name"],
                "file": "folder",
                "path": i["parentReference"]["path"].replace("/drive/root:", ""),
                "is_file": 0
            }
            threading.Lock()
            downloadinfos.append(dic)
            threading.RLock()
            t = threading.Thread(target=task_getlist,
                                    args=(
                                         "/" + path + "/" + i["name"],
                                     ))
            thread_list.append(t)
        else:
            t = threading.Thread(target=task_write, args=(i,))
            thread_list.append(t)
    for t in thread_list:
        t.start()
    for t in thread_list:
        t.join()

    return downloadinfos


def pull_dirve_file(file_id, trytimemax=10000):
    global tokenjson

    BaseUrl = config.app_url + 'v1.0/me/drive/items/' + file_id
    headers = {'Authorization': 'Bearer {}'.format(tokenjson["access_token"])}
    try:
        trytime = 0
        while True:
            try:
                get_res = requests.get(BaseUrl, headers=headers, timeout=30)
                break
            except Exception as e:
                if (trytime > trytimemax):
                    return None
                print("get drive file failed, try again")
                trytime = trytime + 1
                time.sleep(20)
        get_res = json.loads(get_res.text)
        if 'error' in get_res.keys():
            reacquireToken()
            return pull_dirve_file(file_id)
        else:
            if '@microsoft.graph.downloadUrl' in get_res.keys():
                return {
                    "name": get_res["name"],
                    "url": get_res["@microsoft.graph.downloadUrl"]
                }
            else:
                return pull_dirve_file(file_id)
    except Exception as e:
        return None


def savetokenjson(tokenjson):
    global tokenstream
    tokenstream.seek(0)
    tokenstream.truncate()
    yaml.safe_dump(tokenjson, tokenstream)


def init():
    global settings
    global tokenstream
    global tokenjson
    global semlockupload
    global semlockdownload
    global upload_big_thread_pool

    # Load the oauth_settings.yml file
    stream = open('oauth_settings.yml', 'r')
    passredeem = False
    try:
        tokenstream = open('keyjson.yml', 'r+')
        passredeem = True
    except FileNotFoundError:
        tokenstream = open('keyjson.yml', "w")

    settings = yaml.load(stream, yaml.SafeLoader)

    if (not passredeem):
        urluse = url.format(client_id=settings["app_id"],
                            domain="http://localhost/")
        print(urluse)
        code = input("code>")

    if (passredeem):
        tokenjson = yaml.load(tokenstream)
    else:
        tokenjson = redeemcode(code)

    if tokenjson == None:
        exit()

    #10个线程下载
    semlockupload = threading.BoundedSemaphore(10)

    # 信号量，同时只允许10个线程运行
    semlockdownload = threading.BoundedSemaphore(10)

    #上传线程池
    upload_big_thread_pool = ThreadPoolExecutor(max_workers=10)

    return tokenjson

def uninit():
    global upload_thread_pool
    global download_thread_pool

    #等待所有上传线程结束
    for i in upload_thread_pool:
        i.join()

    for i in download_thread_pool:
        i.join()

    #等待线程池执行完毕
    upload_big_thread_pool.shutdown(wait=True)

def getfiledownloadurl(urlpath):
    global tokenjson
    
    BaseUrl = config.app_url + 'v1.0/me/drive/root:/' + urlpath
    headers = {'Authorization': 'Bearer {}'.format(tokenjson["access_token"])}
    try:
        trytime = 0
        while True:
            try:
                get_res = requests.get(BaseUrl, headers=headers, timeout=30)
                break
            except Exception as e:
                print("get drive file failed, try again")
                trytime = trytime + 1
                time.sleep(20)
        get_res = json.loads(get_res.text)
        if 'error' in get_res.keys():
            reacquireToken()
            return getfiledownloadurl(urlpath)
        else:
            if '@microsoft.graph.downloadUrl' in get_res.keys():
                return {
                    "name": get_res["name"],
                    "url": get_res["@microsoft.graph.downloadUrl"],
                    "file_size": get_res["size"],
                    "path": get_res["parentReference"]["path"].replace("/drive/root:", "")
                }
            else:
                return None
    except Exception as e:
        return None

def isurlfile(urlpath):
    if getfiledownloadurl(urlpath) is None:
        return False
    else:
        return True