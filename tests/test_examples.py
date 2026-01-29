import os
import signal
import sys
import tempfile
from pathlib import Path
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
    examples_path = Path(__file__).parent.parent / 'examples'

    temp_file_name = tmpdir.join("log.txt")
    pid_file_name = tmpdir.join("pid.txt")

    expected_result = preprocess(expected_result)
    print("Checking examples/%s against examples/%s ..." % (client, server))
    # start server - use list form to avoid shell quoting issues
    server_cmd = [
        "twistd",
        "--pidfile", str(pid_file_name),
        "-l", str(temp_file_name),
        "-noy", str(examples_path / server)
    ]
    print(f"Starting server with command: {' '.join(server_cmd)}")
    server_process = Popen(server_cmd, stdout=PIPE, stderr=PIPE)
    sleep(0.5)

    result = None
    try:
        # run client - use sys.executable to ensure we're in the same Python environment
        client_cmd = [sys.executable, str(examples_path / client)]
        process = Popen(client_cmd, stdout=PIPE)
        (stdout, stderr) = process.communicate()
        if stderr is not None:
            print("ERR", stderr)
        output = stdout.decode("utf-8")
        result = preprocess(output)
    finally:
        # kill server
        try:
            with open(pid_file_name, 'r') as pid_file:
                pid = int(pid_file.read())
                os.kill(pid, signal.SIGTERM)
        except FileNotFoundError:
            # If pid file doesn't exist, try to kill the shell process
            # and capture any server errors
            if server_process.poll() is None:
                server_process.terminate()
                server_process.wait(timeout=5)
            else:
                # Server already exited, check for errors
                stdout, stderr = server_process.communicate()
                if stderr:
                    print(f"Server stderr: {stderr.decode('utf-8')}")
                if stdout:
                    print(f"Server stdout: {stdout.decode('utf-8')}")

    assert result == expected_result
