from flask import Flask, request, jsonify, Response
from functions.task_manager import TaskManager
from functions.main import ConfigLoader
from functions.service import ServiceManager
import threading
import colorlog
logger = colorlog.getLogger()
logger.setLevel(colorlog.INFO)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt=None,
    reset=True,
    log_colors={
		'DEBUG':    'bold_green,bg_black',
		'INFO':     'bold_white,bg_white',
		'WARNING':  'bold_white,bg_red',
		'ERROR':    'red',
		'CRITICAL': 'red,bg_white',
	},))
logger.addHandler(handler)
task = TaskManager()
app = Flask(__name__)
app_config = ConfigLoader()
app_config.load_api_config()
port = app_config.api_config.get('port')
if port == None:
    port = 5000

service = ServiceManager('')
service.reset_all()

def check_task_status(kwargs):
    config_name = kwargs.get('config_name')
    if task.profile.get(config_name) == None:
        task.register_profile(config_name)
    return task.profile[config_name]['status']

@app.route('/change_ip', methods=['GET'])
def get_start_process():
    apikey = request.args.get('apikey')
    print(f'apikey: {apikey}')
    config_name = request.args.get('config_name')
    config = ConfigLoader()
    if config.load_aws_config(config_name) == None:
        return jsonify({'message': 'Config not found'})
    api_config = config.load_api_config()
    aws_config = config.load_aws_config(config_name)
    config_apikey = api_config.get('apikey')
    aws_apikey = aws_config.get('apikey')
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({'message': 'Invalid API key'})
    user = aws_config.get('user')
    password = aws_config.get('pass')
    publicip = api_config.get('publicip')
    order = aws_config.get('order')
    if user and password:
        socks5_proxy = f'{publicip}:5000{order}:{user}:{password}'
    else:
        socks5_proxy = f'{publicip}:5000{order}'
    response = {
    'config_name': config_name,
    'region': aws_config.get('region'),
    'socks5_proxy': socks5_proxy,
    'last_task': task.profile[config_name]['last_task']
    }
    if hasattr(task.profile[config_name], 'current_task'):
        response['current_task'] = task.profile[config_name]['current_task']
    task_type = 'change_ip'
    kwargs = {
    'task_type': task_type,
    'config_name': config_name
    }
    if check_task_status(kwargs) == 'busy':
        response['status'] = 'busy'
        response['message'] = 'Process is busy'
        return jsonify(response)
    threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
    response['status'] = 'busy'
    response['message'] = 'Process started'
    return jsonify(response)

@app.route('/change_region', methods=['GET'])
def get_change_region():
    apikey = request.args.get('apikey')
    new_region = request.args.get('new_region')
    print(f'apikey: {apikey}')
    config_name = request.args.get('config_name')
    config = ConfigLoader()
    if config.load_aws_config(config_name) == None:
        return jsonify({'message': 'Config not found'})
    api_config = config.load_api_config()
    aws_config = config.load_aws_config(config_name)
    old_region = aws_config.get('region')
    config_apikey = api_config.get('apikey')
    aws_apikey = aws_config.get('apikey')
    if apikey != config_apikey:
        if apikey != aws_apikey:
            return jsonify({'message': 'Invalid API key'})
    task_type = 'change_region'
    new_region = request.args.get('new_region')
    kwargs = {
    'task_type': task_type,
    'config_name': config_name,
    'new_region': new_region
    }
    response = {
    'config_name': config_name,
    'old_region': old_region,
    'new_region': new_region,
    'last_task': task.profile[config_name]['last_task']
    }
    if hasattr(task.profile[config_name], 'current_task'):
        response['current_task'] = task.profile[config_name]['current_task']
    
    if old_region == new_region:
        response['message'] = 'New region is the same as the old region'
        return jsonify(response)
    if check_task_status(kwargs) == 'busy':
        response['message'] = 'Process is busy'
        return jsonify(response)
    threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
    response['message'] = 'Process started'
    return jsonify(response)

@app.route('/getTask', methods=['GET'])
def get_task():
    apikey = request.args.get('apikey')
    config = ConfigLoader()
    api_config = config.load_api_config()
    config_apikey = api_config.get('apikey')
    if apikey != config_apikey:
        return jsonify({'message': 'Invalid API key'})
    return jsonify(task.profile)


if __name__ == '__main__':
    app.run(port=port, host='0.0.0.0', debug=False)