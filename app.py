from flask import render_template
from flask import Flask, render_template, request

import adbTools as adb

app = Flask(__name__)


@app.route('/index.html')
def index():
    return render_template('index.html')


# 检测是否安装
@app.route('/checkInstall', methods=['GET'])
def checkInstall():
    packageName = request.args.get("packageName")
    return adb.check_install(packageName)


# 获取设备列表
@app.route("/getDevices")
def getDevices():
    deviceList = adb.get_device_list()
    return deviceList


@app.route("/runTest", methods=['GET'])
def startRun():
    deviceName = request.args.get("deviceName")
    packageName = request.args.get("packageName")
    times = request.args.get("times")

    if (adb.check_device_is_working(deviceName)):
        return {"code": 999, "errmsg": "设备正在使用中，请稍后再试", "result": "设备正在使用中，请稍后再试"}
    else:
        adb.start_fast_bot_test(deviceName, packageName, times)
        return {"code": 200, "errmsg": "让子弹飞一会", "result": "运行成功，结束后会钉钉通知，请关注"}


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8090)
