from flask import Flask
from functions.aws import Aws
from functions.main import ConfigLoader
from functions.service import ServiceManager
app = Flask(__name__)

#get config

config = ConfigLoader().load_configurations()

running_process = {}

@app.route('/getconfig', methods=['GET'])
def get_config():
    return config