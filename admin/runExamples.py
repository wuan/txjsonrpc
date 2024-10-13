#!/usr/bin/env python
from __future__ import print_function
import os
import sys
import tempfile
from subprocess import Popen, PIPE
from time import sleep
from typing import List

if __name__ == '__main__':

    examples = [
        ("tcp/client.py", "tcp/server.tac"),
        ("tcp/client_subhandled.py", "tcp/server_subhandled.tac"),
        ("web/client.py", "web/server.tac"),
        ("webAuth/client.py", "webAuth/server.tac"),
        ]


    expectedResults = [
        "Result: 8",
        """
        Result: ['echo', 'math.add', 'system.listMethods', 'system.methodHelp', 'system.methodSignature', 'testing.getList']
        Result: [1, 2, 3, 4, 'a', 'b', 'c', 'd']
        Result: 8
        Result: bite me
        Shutting down reactor...
        """,
        """
        Result: 8
        Result: bite me
        Shutting down reactor...
        """,
        """
        Unauthorized
        Unauthorized
        Result: 8
        Result: bite me
        Shutting down reactor...
        """,
        ]


    def print_result(result: List[str]):
        for line in result:
            print(f"    {line}")

    def preprocess(result):
        lines = [x.strip() for x in result.strip().split("\n")]
        return sorted(lines)


    for example, expectedResult in zip(examples, expectedResults):
        client, server = example
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=True) as temp_file:
                temp_file_name = temp_file.name

                expectedResult = preprocess(expectedResult)
                print("Checking examples/%s against examples/%s ..." % (client, server))
                # start server
                command = f"twistd -l {temp_file_name} -noy {os.path.join('examples', server)}"
                server_process = Popen(command, shell=True)
                pid = server_process.pid
                sleep(0.5)
                # run client
                command = "python %s" % os.path.join("examples", client)
                process = Popen(command, shell=True, stdout=PIPE)
                (stdout, stderr) = process.communicate()
                if stderr is not None:
                    print("ERR", stderr)
                output = stdout.decode("utf-8")
                result = preprocess(output)
                # kill server
                os.kill(pid, 15)
                # check results
                if result != expectedResult:
                    print("ERROR: expected '%s' but got '%s'" % (expectedResult, result))
                    print_result(expectedResult)
                    print("but got")
                    print_result(result)
                    print("-- log output:")
                    with open(temp_file_name, 'r') as log_file:
                        print(log_file.read())
                    sys.exit(1)
        except Exception as e:
            print(f"failed in example: client {client}, server {server}")
            raise e
