import os
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
def test_example(client, server, expected_result):
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        temp_file_name = temp_file.name

        expected_result = preprocess(expected_result)
        print("Checking examples/%s against examples/%s ..." % (client, server))
        # start server
        command = f"twistd -l {temp_file_name} -noy {os.path.join('../examples', server)}"
        server_process = Popen(command, shell=True)
        pid = server_process.pid
        sleep(0.5)
        # run client
        command = "python %s" % os.path.join("../examples", client)
        process = Popen(command, shell=True, stdout=PIPE)
        (stdout, stderr) = process.communicate()
        if stderr is not None:
            print("ERR", stderr)
        output = stdout.decode("utf-8")
        result = preprocess(output)
        # kill server
        os.kill(pid, 15)
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
