from flask import Flask, request, jsonify, Response
from functions.aws import Aws
from functions.main import ConfigLoader
from functions.service import ServiceManager
from functions.api import TaskManager
import threading


app = Flask(__name__)
task = TaskManager()

def start_task(profile, process_type):
    task.run(profile, process_type)

@app.route('/start-process', methods=['GET'])
def start_process():
    if task.status == 'idle':
        profile = request.args.get('profile')
        process_type = request.args.get('process_type')
        threading.Thread(target=start_task, args=(profile, process_type)).start()
        return jsonify({'message': 'Process started'}), 200
    else:
        return jsonify({'message': 'Process still running'}), 304

if __name__ == '__main__':
    app.run()

#get config

config = ConfigLoader().load_configurations()

running_process = {}

@app.route('/getconfig', methods=['GET'])
def get_config():
    return config