from subprocess import run
import requests
import json
import os
import time

# 钉钉机器人Url
ding_ding_hook_url = ""

# 实际dir名称应该是 ERRORDIR+deviceName
error_dir = "pandaLog_"


# 消息打印
def log(msg):
    print(msg)


# 检查设备是否使用中
def check_device_is_working(device_name):
    file_name = "{fileName}.lock".format(fileName=device_name)
    return os.path.exists(file_name)


# 获取设备列表 返回格式 {"设备名称":"true(使用中)"}
def get_device_list():
    adb_commond = run('adb devices', capture_output=True)

    log(adb_commond)

    output_string = adb_commond.stdout.decode('UTF-8').strip()

    # 存储已连接的设备
    devices_data = {}

    # 用于标记跳过第一行
    is_first_line = True

    # 遍历设备列表，检查设备使用状况
    for line in output_string.splitlines():

        if not is_first_line:

            device_name = line.replace("device", "").strip()
            # 检查设备是否正在使用中
            is_working = check_device_is_working(device_name)

            devices_data[device_name] = is_working

        else:

            is_first_line = False

    return devices_data


# 检查apk是否安装
def check_install(package_name):
    devices = get_device_list()
    print(devices)
    # 存储最后检查的结果
    result_list = {}

    for device in devices.keys():
        # 检查是否有指定的安装包
        adb_commond = "adb -s {deviceName} shell pm list packages {packageName}".format(deviceName=device,
                                                                                        packageName=package_name)
        log(adb_commond)
        adb_out_put = run(adb_commond, capture_output=True)

        result = adb_out_put.stdout.decode('UTF-8').strip()
        # 检查是否有结果输出
        result_list[device] = len(result) > 0

    return result_list


# 初始化导入配置
def initConfig(device_name):
    adb_commond_list = {"adb -s {deviceName} push fastbot-thirdpart.jar /sdcard".format(deviceName=device_name),
                        "adb -s {deviceName} push framework.jar /sdcard".format(deviceName=device_name),
                        "adb -s {deviceName} push monkeyq.jar /sdcard".format(deviceName=device_name),
                        "adb -s {deviceName} push libs\.  /data/local/tmp/".format(deviceName=device_name), }

    for cmd in adb_commond_list:
        run(cmd)


# 开始运行
def start_fast_bot_test(devices_name, package_name, duration):
    try:
        initConfig(devices_name)

        # # 创建一个临时文件，标记设备正在使用中
        create_lock_file(devices_name)

        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # 一个随机数据 用于区分不同的文件夹
        tag = str(int(time.time()))

        # 错误日志存放目录
        dir_name = error_dir + devices_name + "_" + tag

        adb_commond = "adb -s {devices} shell CLASSPATH=/sdcard/monkeyq.jar:/sdcard/framework.jar:/sdcard/fastbot-thirdpart.jar  exec app_process /system/bin com.android.commands.monkey.Monkey -p {packageName} --agent reuseq --running-minutes {duration} --throttle 800 --bugreport --output-directory /sdcard/{errorLogFileDir}".format(
            devices=devices_name, packageName=package_name, duration=duration, errorLogFileDir=dir_name
        )

        log(adb_commond)

        run(adb_commond)

        # 检查是否有crash产生
        exception = has_exception(devices_name, dir_name)

        # 检查是否有crash问题
        crash_data = ""
        if exception["Crash"]:
            crash_data = get_crash_data_v2(devices_name, dir_name)

        statistics = show_log_detail(devices_name, dir_name + "/max.activity.statistics.log")
        statistics_json = json.loads(statistics)

        # 页面覆盖率
        coverage = statistics_json["Coverage"]

        # 已测试的页面
        test_activity = statistics_json["TestedActivity"]

        end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        result_data = {"覆盖率": str(coverage) + "%", "已测试页面": test_activity, "Crash": exception["Crash"],
                       "ANR": exception["ANR"], "OOM": exception["OOM"],
                       "Crash日志": crash_data, "日志目录": dir_name, "开始时间": start_time, "结束时间": end_time}

        log(result_data)

        # 发送钉钉消息通知
        post_to_ding_ding(devices_name, package_name, duration, result_data)

        delete_lock_file(devices_name)

    except Exception as e:
        log(e)
        delete_lock_file(devices_name)
        post_error(devices_name)


def get_last_line(log_data):
    lines = log_data.splitlines()

    # 取最后一行数据
    last_line = lines[len(lines) - 1]

    return last_line


# 检查运行过程中是否出现crash
def has_exception(device_name, dir_name):
    adb_commond = "adb -s {deviceName} shell ls  sdcard/{dirName}".format(deviceName=device_name, dirName=dir_name)
    output = run(adb_commond, capture_output=True).stdout.decode('UTF-8')
    lines = output.splitlines()

    has_crash = False
    has_oom = False
    has_anr = False

    for line in lines:

        if "app_crash" in line or "Crash" in line:
            has_crash = True
        if "oom" in line:
            has_oom = True
        if "anr" in line or "Anr" in line:
            has_anr = True

    return {"Crash": has_crash, "OOM": has_oom, "ANR": has_anr}


# 格式化日志数据
def format_log_data(log_data):
    # 已测试覆盖的activity列表
    app_activity_list = []
    # 覆盖率
    coverage = ""
    # 是否查找到已覆盖的activity标签
    is_find_target_tag = False

    # log(str(log_data))

    splitlines = log_data.splitlines()

    for line in splitlines:
        if is_find_target_tag:
            position = line.rindex('.')
            app_activity_list.append(line[position + 1:])
        else:
            if "Explored app activities" in line:
                is_find_target_tag = True
                pass

    # 移除最后一行数据
    if len(app_activity_list) > 0:
        app_activity_list.pop(len(app_activity_list) - 1)

    return {"覆盖页面": app_activity_list}


# 创建临时文件，标记设备正在使用中
def create_lock_file(device_name):
    file_name = "{fileName}.lock".format(fileName=device_name)
    lock_file = open(file_name, 'w')
    lock_file.close()


# 删除临时文件
def delete_lock_file(device_name):
    file_name = "{fileName}.lock".format(fileName=device_name)
    os.remove(os.getcwd() + '\\' + file_name)


def get_crash_data_v2(devices_name, dir_name):
    # parent_path = download_crash_log_only(devices_name, "sdcard/pandaLog_fbfcdf5d_1637031702/", False) 测试

    parent_path = download_crash_log_v2(devices_name, dir_name, False)

    result_path = download_crash_log_v2(devices_name, parent_path, True)

    return show_log_detail(devices_name, result_path)


# 获取log文件详细内容
def show_log_detail(devices_name, path):
    adb_commond = "adb -s {deviceName} shell cat sdcard/{path}".format(deviceName=devices_name, path=path)

    return run(adb_commond, capture_output=True).stdout.decode('UTF-8')


# 只下载crash日志文件
def download_crash_log_v2(devices_name, dir_name, ingone_log):
    adb_commond = "adb -s {deviceName} shell ls  sdcard/{dirName} ".format(deviceName=devices_name,
                                                                           dirName=dir_name)
    log(adb_commond)

    adb_output = run(adb_commond, capture_output=True).stdout.decode('UTF-8')

    data_list = adb_output.splitlines()

    crash_log_dir_path = ""

    for line in data_list:
        if line in "No such file or directory":
            pass
        elif (".log" in line or ".txt" in line) and ingone_log == False:
            pass
        else:
            crash_log_dir_path = dir_name + "/" + line

    return crash_log_dir_path


# 获取crash的log日志文件名称
def get_crash_file_name(dir_name):
    g = os.walk(dir_name)

    child_dir = ""

    # 获取指定文件夹下面的子文件中的log日志文件
    for path, dir_list, file_list in g:
        for dir in dir_list:
            child_dir = dir

    return dir_name + "/" + child_dir + "/" + child_dir + ".log"


# 获取crash数据
def get_crash_data(dir_name, device_name):
    adb_commond = "adb -s {deviceName} pull /sdcard/{errorLogDirName}/".format(
        deviceName=device_name, errorLogDirName=dir_name)

    print(adb_commond)

    # 下载crash文件
    output_string = run(adb_commond, capture_output=True)

    crash_file = get_crash_file_name(dir_name)

    log(crash_file)

    # 读取文件内容
    data = ""
    with open(crash_file, "r", encoding="utf-8") as f:
        data = f.read()

    return data


def post_error(device_name):
    params = {"测试状态": "设备 {device_name} 运行失败，请检查设置".format(device_name=device_name)}
    data = {"text": {"content": params}, "msgtype": "text"}

    headers = {'Content-Type': 'application/json'}

    r = requests.post(ding_ding_hook_url, headers=headers, data=json.dumps(data))

    print(r.text)


# 发送钉钉消息
def post_to_ding_ding(device_name, package_name, duration, result):
    # text 格式
    params = {"测试设备": device_name, "包名": package_name, "测试时长": str(duration) + " 分钟",
              "测试结果": result}
    data = {"text": {"content": params}, "msgtype": "text"}

    # Markdown 格式
    # markdown = "# 测试设备 \n{deviceName} \n # 测试时长 \n {time} 分钟 \n # 页面覆盖率 \n {coverage}".format(
    #     deviceName=deviceName, time=time, coverage=testResult['coverage']
    # )
    # data = {"msgtype": "markdown", "markdown": {"title": packageName, "text": markdown}}

    headers = {'Content-Type': 'application/json'}
    r = requests.post(ding_ding_hook_url, headers=headers, data=json.dumps(data))

    print(r.text)