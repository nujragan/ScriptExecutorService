from flask import *
from celery import Celery
from scriptRunner import ScriptRunner
import os
from time import sleep
from werkzeug.utils import secure_filename

application = Flask(__name__)
application.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
application.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
application.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
application.config['UPLOAD_EXTENSIONS'] = ['.sh', '.csh']
application.config['TASKS_INFO_FILE_NAME'] = "tasks_info.txt"
application.config['SCRIPT_STATUS_FILE_NAME'] = ".script_status.txt"

path = "/tmp/ScriptExecutorService/"
UPLOAD_FOLDER = os.path.join(path)
application.secret_key = "Top secret key!"

if not os.path.isdir(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)

application.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

celery = Celery(application.name, broker=application.config['CELERY_BROKER_URL'],
                backend=application.config['CELERY_RESULT_BACKEND'])
celery.conf.update(application.config)


@application.route("/welcome")
def hello():
    return jsonify({'hello': 'world'})


@application.route('/SubmitScript')
def index():
    return render_template('index.html')


def change_file_to_be_executable(filePath):
    os.chmod(filePath, 0o755)


@application.route('/SubmitScript', methods=['POST'])
def upload_file():
    uploaded_file = request.files['file']
    filename = uploaded_file.filename
    if filename != '':
        file_name, file_ext = os.path.splitext(filename)[0], os.path.splitext(filename)[1]
        if file_ext not in current_app.config['UPLOAD_EXTENSIONS']:
            abort(400, "Only scripts ending with .sh and .csh are accepted")
        full_upload_folder_name = os.path.join(application.config['UPLOAD_FOLDER'], secure_filename(file_name))
        if not os.path.isdir(full_upload_folder_name):
            os.mkdir(full_upload_folder_name)
        else:
            abort(400, "Script with same name is already uploaded. Please use different name")
        file_path = os.path.join(full_upload_folder_name, secure_filename(filename))
        uploaded_file.save(file_path)
        change_file_to_be_executable(file_path)
    return redirect(url_for('index'))


@celery.task(name="app.run_script_bg", bind=True)
def run_script_bg(self, script_path, arguments):
    self.update_state(state='PROGRESS')
    sr = ScriptRunner(script_path, arguments)
    exit_code = sr.run_script()
    if exit_code == 0:
        self.update_state(state='SUCCESS')
    else:
        with open(os.path.dirname(script_path) + "/" + application.config['SCRIPT_STATUS_FILE_NAME'], 'a') as f:
            stderr = ScriptRunner.get_script_err(os.path.dirname(script_path))
            f.write("%s:::%s:::%s\n" % (self.request.id, exit_code, stderr))
        self.update_state(
            state='FAILURE'
        )
    return exit_code


def store_task_id_under_scripts_folder(task_id, script_path_dir):
    task_id_file = script_path_dir + "/" + application.config['TASKS_INFO_FILE_NAME']
    f = open(task_id_file, "a")
    f.write(task_id + "\n")
    f.close()


@application.route("/trigger", methods=["POST"])
def run_script():
    """
    post-data: {"scriptName":"a_b_c.sh","arguments": ""}
    :return: {"scriptName":"a_b_c.sh","arguments": ""}
    """
    scriptName = request.json['scriptName']
    args = request.json['arguments']
    script_basename = scriptName.split(".")[0]
    script_path_components = [application.config['UPLOAD_FOLDER'], script_basename, scriptName]
    script_path_dir = os.path.join(application.config['UPLOAD_FOLDER'], script_basename)
    actual_script_path = os.path.join('', *script_path_components)
    if os.path.exists(actual_script_path):
        task = run_script_bg.apply_async(args=[actual_script_path, args])
        sleep(1)
        store_task_id_under_scripts_folder(task.id, script_path_dir)
        return "Successfully Triggered script: %s with args: %s" % (scriptName, args) , 202
    else:
        abort(400, "%s : not present in the server to trigger. Please submit the script first before triggering" %scriptName)


# @application.route("/listAllAvailableScripts/", methods=["GET"])
# def getAllScripts():
#     return jsonify([x[1] for x in os.walk(application.config['UPLOAD_FOLDER'])])


@application.route("/getStdOut/<scriptName>", methods=["GET"])
def get_std_out(scriptName):
    script_basename = scriptName.split(".")[0]
    script_path_dir = os.path.join(application.config['UPLOAD_FOLDER'], script_basename)
    return jsonify(ScriptRunner.get_script_output(script_path_dir))


@application.route("/getStdErr/<scriptName>", methods=["GET"])
def get_std_err(scriptName):
    script_basename = scriptName.split(".")[0]
    script_path_dir = os.path.join(application.config['UPLOAD_FOLDER'], script_basename)
    return jsonify(ScriptRunner.get_script_err(script_path_dir))


def get_task_id_from_scriptName(script_path_dir):
    task_id_file = script_path_dir + "/" + application.config['TASKS_INFO_FILE_NAME']
    if os.path.exists(task_id_file):
        with open(task_id_file) as f:
            content = f.readlines()
        return [x.strip() for x in content]


@application.route('/ScriptStatus/<scriptName>', methods=['GET'])
def get_script_status(scriptName):
    script_basename = scriptName.split(".")[0]
    script_path_dir = os.path.join(application.config['UPLOAD_FOLDER'], script_basename)
    taskIDs = get_task_id_from_scriptName(script_path_dir)
    response = {}
    if taskIDs:
        task_id = taskIDs[-1]
        task = run_script_bg.AsyncResult(task_id)
        if task.state == 'PROGRESS':
            response[task.id] = {
                'scriptStatus': "Running",
            }
        elif task.state != 'FAILURE':
            std_out = ScriptRunner.get_script_output(script_path_dir)
            response[task.id] = {
                'scriptStatus': task.state,
                'exitStatus': 0,
                'stdout': str(std_out)
            }
        else:
            exception_file = script_path_dir + "/" + application.config['SCRIPT_STATUS_FILE_NAME']
            if os.path.exists(exception_file):
                with open(exception_file) as f:
                    content = f.readlines()
                    for x in content:
                        if task_id in x.strip():
                            exitStatus = x.strip().split(':::')[1]
                            stderr = x.strip().split(':::')[2]
                            response[task.id] = {
                                'scriptStatus': 'FAILURE',
                                'exitCode': exitStatus,
                                'stderr': str(stderr)
                            }

    return jsonify(response)


if __name__ == '__main__':
    application.run()