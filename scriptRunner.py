import subprocess, shlex
import os

# user should trigger
# user should query by name to get status
# user should query by name to get script's output
# user should be able to submit shell script by name


class ScriptRunner:
    def __init__(self, script_path, arguments=""):
        self.script_path = script_path
        self.args = arguments
        self.stdout_file = os.path.dirname(script_path) + "/stdout.txt"
        self.stderr_file = os.path.dirname(script_path) + "/stderr.txt"
        self.master_dir_name = "ScriptExecutorService"

    def run_script(self):
        concatenated_string = self.script_path + " " + self.args
        args = shlex.split(concatenated_string)
        print(args)
        fout = open(self.stdout_file, 'w+')
        ferr = open(self.stderr_file, 'w+')
        proc = subprocess.Popen(args, stdout=fout, stderr=ferr)
        proc.communicate()
        proc.wait()
        return proc.returncode

    @staticmethod
    def get_script_output(script_path):
        # read from stdout and show
        stdout_file = script_path + "/stdout.txt"
        with open(stdout_file, "r") as f:
            return f.read().replace('\n', '')

    @staticmethod
    def get_script_err(script_path):
        stderr_file = script_path + "/stderr.txt"
        with open(stderr_file, "r") as f:
            return f.read().replace('\n', '')




