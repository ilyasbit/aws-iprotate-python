from flask import Flask, request, jsonify, Response
import functions.task_manager
import functions.api
import functions.run
import threading
import time


config_name = 'aws1'
task_type = 'change_ip'
task = functions.task_manager.TaskManager()

app = Flask(__name__)

def check_task_status(config_name, task_type):
    if task.profile.get(config_name) == None:
        task.register_profile(config_name)
    return task.profile[config_name]['status']


@app.route('/change_ip', methods=['GET'])
def get_start_process():
    kwargs = {
    'task_type': 'change_ip',
    'config_name': request.args.get('config_name')
    }
    if check_task_status(config_name, task_type) == 'busy':
        return 'Process is busy'
    threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
    return 'Process started'
if __name__ == '__main__':
    app.run()

@app.route('/change_region', methods=['GET'])
def get_change_region():
    kwargs = {
    'task_type': 'change_region',
    'config_name': request.args.get('config_name'),
    'new_region': request.args.get('new_region')
}

    task_type = 'change_region'
    config_name = request.args.get('config_name')
    new_region = request.args.get('new_region')
    if check_task_status(config_name, task_type) == 'busy':
        return 'Process is busy'
    threading.Thread(target=task.set_start_task, kwargs=kwargs).start()
    return 'Process started'

@app.route('/getTask', methods=['GET'])
def get_task():
    return jsonify(task.profile)