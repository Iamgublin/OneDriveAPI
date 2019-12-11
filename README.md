OneDriveAPI
======================

## only tested in onedrive business


upload file
---------------------------
```
python3 ./upload.py
```


download file
--------------------------
```
python3 ./download.py onedrivepath
```
python3 ./download.py /Movie


change the download or upload filedir
-----------------------------------------
```
edit the value `rootdir` in upload.py and download.py
```


change appinfo
-----------------------------------------
```
edit the value `app_id` and `app_secret` in oauth_settings.yml
```

tips
-----------------------------------------
1.OneDrive code will rediect to `127.0.0.1`

2.retry time now is default 999999