import os
import signal
import sys
import tempfile
from subprocess import Popen, PIPE
from time import sleep
from typing import List

import pytest


def print_result(result: List[str]):
    for line in result:
        print(f"    {line}")


def preprocess(result):
    lines = [x.strip() for x in result.strip().split("\n")]
    return sorted(lines)


result_subhandled = """
Result: ['echo', 'math.add', 'system.listMethods', 'system.methodHelp', 'system.methodSignature', 'testing.getList']
Result: [1, 2, 3, 4, 'a', 'b', 'c', 'd']
Result: 8
Result: bite me
Shutting down reactor...
"""

result_web = """
Result: 8
Result: bite me
Shutting down reactor...
"""

result_web_auth = """
Unauthorized
Unauthorized
Result: 8
Result: bite me
Shutting down reactor...
"""



@pytest.mark.parametrize("client,server,expected_result", (
        ("tcp/client.py", "tcp/server.tac", "Result: 8"),
        ("tcp/client_subhandled.py", "tcp/server_subhandled.tac", result_subhandled),
        ("web/client.py", "web/server.tac", result_web,),
        ("webAuth/client.py", "webAuth/server.tac", result_web_auth),
))
def test_example(client, server, expected_result, tmpdir):
    examples_path = os.path.join(os.path.dirname(__file__), '../examples')

    temp_file_name = tmpdir.join("log.txt")
    pid_file_name = tmpdir.join("pid.txt")

    expected_result = preprocess(expected_result)
    print("Checking examples/%s against examples/%s ..." % (client, server))
    # start server
    command = f"twistd --pidfile {pid_file_name} -l {temp_file_name} -noy {os.path.join(examples_path, server)}"
    server_process = Popen(command, shell=True)
    pid = server_process.pid
    sleep(0.5)
    print("server started (pid=%d)" % pid)
    # run client
    command = "python %s" % os.path.join(examples_path, client)
    process = Popen(command, shell=True, stdout=PIPE)
    (stdout, stderr) = process.communicate()
    if stderr is not None:
        print("ERR", stderr)
    output = stdout.decode("utf-8")
    result = preprocess(output)
    print("client finished")
    # kill server
    os.kill(pid, signal.SIGTERM)
    sleep(0.5)
    os.kill(pid, signal.SIGKILL)
    # check results
    if result != expected_result:
        print("ERROR: expected '%s' but got '%s'" % (expected_result, result))
        print_result(expected_result)
        print("but got")
        print_result(result)
        print("-- log output:")
        with open(temp_file_name, 'r') as log_file:
            print(log_file.read())
        sys.exit(1)
