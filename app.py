import datetime
import threading

import colorlog
import pyufw as ufw
from flask import Flask, jsonify, request

from functions.aws import Aws
from functions.main import ConfigLoader
from functions.service import ServiceManager
from functions.task_manager import TaskManager

base_socks5_port = 50000
base_http_port = 60000

logger = colorlog.getLogger()
logger.setLevel(colorlog.INFO)
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - [%(levelname)s] - %(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            "DEBUG": "bold_green,bg_black",
            "INFO": "bold_green,bg_black",
            "WARNING": "bold_white,bg_red",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)
logger.addHandler(handler)
task = TaskManager()
app = Flask(__name__)
app_config = ConfigLoader()
app_config.load_api_config()
port = app_config.api_config.get("port")
if port is None:
    port = 5000

service = ServiceManager("")
service.reset_all()


def check_task_status(kwargs):
    config_name = kwargs.get("config_name")
    if task.profile.get(config_name) is None:
        task.register_profile(config_name)
    return task.profile[config_name]["status"]


def check_last_task(kwargs):
    config_name = kwargs.get("config_name")
    if task.profile.get(config_name) is None:
        print("Register profile")
        task.register_profile(config_name)
        return task.profile[config_name]["last_task"]
    else:
        if hasattr(task.profile[config_name], "task_start_time"):
            print("Check task start time")
            task_start_time = task.profile[config_name]["task_start_time"]
            task_start_time = datetime.datetime.strptime(
                task_start_time, task.timestamp_format
            )
            now = datetime.datetime.now()
            if (now - task_start_time).total_seconds() > 600:
                print("Timeout")
                task.profile[config_name]["status"] = "idle"
                task.profile[config_name]["last_task"]["status"] = "Timeout"
                task.profile[config_name]["task_start_time"] = None
                task.profile[config_name]["current_task"] = None
                task.profile[config_name]["last_task"]["end_time"] = now.strftime(
                    task.timestamp_format
                )
                return task.profile[config_name]["last_task"]
        return task.profile[config_name]["last_task"]


@app.route("/change_ip", methods=["GET"])
def get_start_process():
    apikey = request.args.get("apikey")
    config_name = request.args.get("config_name")
    config = ConfigLoader()
    if config.load_aws_config(config_name) is None:
        return jsonify({"message": "Config not found"})
    api_config = config.load_api_config()
    aws_config = config.load_aws_config(config_name)
    config_apikey = api_config.get("apikey")
    aws_apikey = aws_config.get("apikey")
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({"message": "Invalid API key"})
    user = aws_config.get("user")
    password = aws_config.get("pass")
    publicip = api_config.get("publicip")
    order = aws_config.get("order")
    socks5_port = base_socks5_port + int(order)
    http_port = base_http_port + int(order)
    if user and password:
        socks5_proxy = f"{publicip}:{socks5_port}:{user}:{password}"
        http_proxy = f"{publicip}:{http_port}:{user}:{password}"
    else:
        socks5_proxy = f"{publicip}:{socks5_port}"
        http_proxy = f"{publicip}:{http_port}"

    response = {
        "config_name": config_name,
        "region": aws_config.get("region"),
        "socks5_proxy": socks5_proxy,
        "http_proxy": http_proxy,
    }
    if not hasattr(task.profile, config_name):
        task.register_profile(config_name)
    if hasattr(task.profile[config_name], "last_task"):
        response["last_task"] = task.profile[config_name]["last_task"]
    if hasattr(task.profile[config_name], "current_task"):
        response["current_task"] = task.profile[config_name]["current_task"]
    task_type = "change_ip"
    kwargs = {"task_type": task_type, "config_name": config_name}
    # check aws login
    aws_login = Aws(config_name)
    if not aws_login.login():
        response["message"] = "AWS login failed"
        return jsonify(response)
    if check_task_status(kwargs) == "busy":
        response["status"] = "busy"
        response["message"] = "Process is busy"
        return jsonify(response)
    threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
    response["status"] = "busy"
    response["message"] = "Process started"
    return jsonify(response)


@app.route("/change_auth", methods=["GET"])
def get_change_auth():
    apikey = request.args.get("apikey")
    config_name = request.args.get("config_name")
    new_user = request.args.get("new_user")
    new_pass = request.args.get("new_pass")
    config = ConfigLoader()
    if config.load_aws_config(config_name) is None:
        return jsonify({"message": "Config not found"})
    api_config = config.load_api_config()
    aws_config = config.load_aws_config(config_name)
    config_apikey = api_config.get("apikey")
    aws_apikey = aws_config.get("apikey")
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({"message": "Invalid API key"})
    kwargs = {
        "task_type": "change_auth",
        "config_name": config_name,
        "new_user": new_user,
        "new_pass": new_pass,
    }
    try:
        threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
        return jsonify({"message": "Process started"})
    except Exception as e:
        return jsonify({"message": str(e)})


@app.route("/change_region", methods=["GET"])
def get_change_region():
    # base_socks5_port = 50000
    apikey = request.args.get("apikey")
    new_region = request.args.get("new_region")
    if new_region is None:
        return jsonify({"message": "New region is not provided"})
    config_name = request.args.get("config_name")
    config = ConfigLoader()
    if config.load_aws_config(config_name) is None:
        return jsonify({"message": "Config not found"})
    api_config = config.load_api_config()
    aws_config = config.load_aws_config(config_name)
    old_region = aws_config.get("region")
    config_apikey = api_config.get("apikey")
    aws_apikey = aws_config.get("apikey")
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({"message": "Invalid API key"})
    task_type = "change_region"
    new_region = request.args.get("new_region")
    kwargs = {
        "task_type": task_type,
        "config_name": config_name,
        "new_region": new_region,
    }
    response = {
        "config_name": config_name,
        "old_region": old_region,
        "new_region": new_region,
        "last_task": task.profile[config_name]["last_task"],
    }
    if hasattr(task.profile[config_name], "current_task"):
        response["current_task"] = task.profile[config_name]["current_task"]

    if old_region == new_region:
        response["message"] = "New region is the same as the old region"
        return jsonify(response)
    if check_task_status(kwargs) == "busy":
        response["message"] = "Process is busy"
        return jsonify(response)
    threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
    response["message"] = "Process started"
    return jsonify(response)


@app.route("/get_available_region", methods=["GET"])
def get_available_region():
    apikey = request.args.get("apikey")
    config_name = request.args.get("config_name")
    config = ConfigLoader()
    if config.load_aws_config(config_name) is None:
        return jsonify({"message": "Config not found"})
    api_config = config.load_api_config()
    aws_config = config.load_aws_config(config_name)
    config_apikey = api_config.get("apikey")
    aws_apikey = aws_config.get("apikey")
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({"message": "Invalid API key"})
    aws = Aws(config_name)
    aws.login()
    regions = aws.get_all_regions()
    return jsonify(regions)


@app.route("/get_config", methods=["GET"])
def get_config_detail():
    apikey = request.args.get("apikey")
    config_name = request.args.get("config_name")
    config = ConfigLoader()
    if config.load_aws_config(config_name) is None:
        return jsonify({"message": "Config not found"})
    api_config = config.load_api_config()
    publicip = api_config.get("publicip")
    aws_config = config.load_aws_config(config_name)
    config_apikey = api_config.get("apikey")
    aws_apikey = aws_config.get("apikey")
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({"message": "Invalid API key"})
    aws = Aws(config_name)
    response = {}
    response["available_region"] = aws.get_all_regions()
    profile_task = task.profile.get(config_name)
    current_task = profile_task.get("current_task") or None
    last_task = profile_task.get("last_task") or None
    status = profile_task.get("status") or "idle"
    response.update(aws_config)
    user = aws_config.get("user")
    password = aws_config.get("pass")
    order = aws_config.get("order")
    socks5_port = base_socks5_port + int(order)
    http_port = base_http_port + int(order)
    if user and password:
        socks5_proxy = f"{publicip}:{socks5_port}:{user}:{password}"
        http_proxy = f"{publicip}:{http_port}:{user}:{password}"
    else:
        socks5_proxy = f"{publicip}:{socks5_port}"
        http_proxy = f"{publicip}:{http_port}"

    response["current_task"] = current_task
    response["last_task"] = last_task
    response["status"] = status
    response["socks5_proxy"] = socks5_proxy
    response["http_proxy"] = http_proxy
    return jsonify(response)


@app.route("/change_whitelist", methods=["GET"])
def change_whitelist():
    apikey = request.args.get("apikey")
    config_name = request.args.get("config_name")
    new_whitelist = request.args.get("new_whitelist")
    config = ConfigLoader()
    if config.load_aws_config(config_name) is None:
        return jsonify({"message": "Config not found"})
    api_config = config.load_api_config()
    aws_config = config.load_aws_config(config_name)
    config_apikey = api_config.get("apikey")
    aws_apikey = aws_config.get("apikey")
    kwargs = {
        "task_type": "change_whitelist",
        "config_name": config_name,
        "new_whitelist": new_whitelist,
    }
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({"message": "Invalid API key"})
    try:
        threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
        return jsonify({"message": "Process started"})
    except Exception as e:
        return jsonify({"message": str(e)})


@app.route("/get_task", methods=["GET"])
def get_task():
    apikey = request.args.get("apikey")
    config = ConfigLoader()
    api_config = config.load_api_config()
    config_apikey = api_config.get("apikey")
    if apikey != config_apikey:
        return jsonify({"message": "Invalid API key"})
    return jsonify(task.profile)


if __name__ == "__main__":
    ufw.enable()
    ufw.default(incoming="allow", outgoing="allow", routed="allow")
    app.run(port=port, host="0.0.0.0", debug=False)
