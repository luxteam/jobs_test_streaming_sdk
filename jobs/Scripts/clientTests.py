import socket
import sys
import os
from time import sleep
import traceback
import json
from instance_state import ClientInstanceState
from actions import ClientActionException
from client_actions import *
import psutil
from utils import *
from subprocess import PIPE, STDOUT
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from jobs_launcher.core.config import *


# mapping of commands and their implementations
ACTIONS_MAPPING = {
    "execute_cmd": ExecuteCMD,
    "check_window": CheckWindow,
    "check_game": CheckWindow,
    "press_keys_server": PressKeysServer,
    "abort": Abort,
    "retry": Retry,
    "next_case": NextCase,
    "click_server": ClickServer,
    "start_test_actions_client": StartTestActionsClient,
    "start_test_actions_server": StartTestActionsServer,
    "make_screen": MakeScreen,
    "record_video": RecordVideo,
    "move": Move,
    "click": Click,
    "sleep": DoSleep,
    "parse_keys": PressKeys,
    "sleep_and_screen": SleepAndScreen,
    "skip_if_done": SkipIfDone
}


# Client controls test case execution. 
# It inits communication, decides to do next case, retry or restart at all the current case.
# Client reads list of actions and executes them one by one.
# It sends actions which must be executed on server to it.
# Also client does screenshots and records video.
def start_client_side_tests(args, case, process, script_path, last_log_line, audio_device_name, current_try):
    output_path = os.path.join(args.output, "Color")

    screen_path = os.path.join(output_path, case["case"])
    if not os.path.exists(screen_path):
        os.makedirs(screen_path)

    archive_path = os.path.join(args.output, "gpuview")
    if not os.path.exists(archive_path):
        os.makedirs(archive_path)

    archive_name = case["case"]

    # default launching of client and server (order doesn't matter)
    if "start_first" not in case or (case["start_first"] != "client" and case["start_first"] != "server"):
        if start_streaming is not None and process is None:
            should_collect_traces = (args.collect_traces == "BeforeTests")
            process = start_streaming(args.execution_type, script_path, not should_collect_traces)

            if should_collect_traces:
                collect_traces(archive_path, archive_name + "_client.zip")

    game_name = args.game_name

    # start client before server
    if "start_first" in case and case["start_first"] == "client":
        if start_streaming is not None and process is None:
            should_collect_traces = (args.collect_traces == "BeforeTests")
            process = start_streaming(args.execution_type, script_path, not should_collect_traces)

            if should_collect_traces:
                collect_traces(archive_path, archive_name + "_client.zip")
            else:
                sleep(10)

    response = None

    # Connect to server to sync autotests
    while True:
        try:
            sock = socket.socket()
            sock.connect((args.ip_address, int(args.communication_port)))
            sock.send("ready".encode("utf-8"))
            response = sock.recv(1024).decode("utf-8")
            break
        except Exception:
            main_logger.info("Could not connect to server. Try it again")

    params = {}

    try:
        # create state object
        instance_state = ClientInstanceState()

        # Client init communication:
        # 1.  Client sent ready to server
        # 2.  Server check that Streaming SDK process is alive and sent result (ready/fail)
        #     3.1 Server sent ready: Client check that Streaming SDK process is alive.
        #         3.1.1 Streaming SDK client is alive: start do actions
        #         3.1.2 Streaming SDK client isn't alive: client sent retry to server to init retry of the current test case
        #     3.2 Server sent fail: client sent retry to server to init retry of the current test case

        if response == "ready":

            # start server before client
            if "start_first" in case and case["start_first"] == "server":
                if start_streaming is not None and process is None:
                    should_collect_traces = (args.collect_traces == "BeforeTests")
                    process = start_streaming(args.execution_type, script_path, not should_collect_traces)

                    if should_collect_traces:
                        collect_traces(archive_path, archive_name + "_client.zip")

            if not is_workable_condition(process):
                instance_state.non_workable_client = True
                raise Exception("Client has non-workable state")

            # get list of actions for the current game / benchmark
            actions_key = "{}_actions".format(game_name.lower())
            if actions_key in case:
                actions = case[actions_key]
            else:
                # use default list of actions if some specific list of actions doesn't exist
                with open(os.path.abspath(args.common_actions_path), "r", encoding="utf-8") as common_actions_file:
                    actions = json.load(common_actions_file)[actions_key]

            # build params dict with all necessary variables for test actions
            params["output_path"] = output_path
            params["screen_path"] = screen_path
            params["archive_path"] = archive_path
            params["current_image_num"] = 1
            params["current_try"] = current_try
            params["audio_device_name"] = audio_device_name
            params["args"] = args
            params["case"] = case
            params["game_name"] = game_name

            # execute actions one by one
            for action in actions:
                # skip some actions if it's necessary (e.g. actions to open a game / benchmark)
                if instance_state.commands_to_skip > 0:
                    instance_state.commands_to_skip -= 1
                    continue

                main_logger.info("Current action: {}".format(action))
                main_logger.info("Current state:\n{}".format(instance_state.format_current_state()))

                # split action to command and arguments
                parts = action.split(" ", 1)
                command = parts[0]
                if len(parts) > 1:
                    arguments_line = parts[1]
                else:
                    arguments_line = None

                params["action_line"] = action
                params["command"] = command
                params["arguments_line"] = arguments_line

                # find necessary command and execute it
                if command in ACTIONS_MAPPING:
                    command_object = ACTIONS_MAPPING[command](sock, params, instance_state, main_logger)
                    command_object.do_action()
                else:
                    raise ClientActionException("Unknown client command: {}".format(command))

                main_logger.info("Finish action execution\n\n\n")

            # say server to start next case
            command_object = NextCase(sock, params, instance_state, main_logger)
            command_object.do_action()

            process = close_streaming_process(args.execution_type, case, process)
            last_log_line = save_logs(args, case, last_log_line, current_try)

            with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "r") as file:
                json_content = json.load(file)[0]

            json_content["test_status"] = "passed"

            # execute iperf if it's necessary
            command_object = IPerf(sock, params, instance_state, main_logger)
            command_object.do_action()

            if "iperf_executed" in params and params["iperf_executed"]:
                logs_path = "tool_logs"
                json_content["iperf_result"] = os.path.join(logs_path, case["case"] + "_iperf.log")

            with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "w") as file:
                json.dump([json_content], file, indent=4)

        elif response == "fail":
            instance_state.non_workable_server = True
            raise Exception("Server has non-workable state")
        else:
            raise Exception("Unknown server answer: {}".format(response))
    except Exception as e:
        instance_state.prev_action_done = False
        main_logger.error("Fatal error. Case will be aborted: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        raise e
    finally:
        if not instance_state.prev_action_done:
            # client or server Streaming SDK instance isn't alive. Retry the current case
            if instance_state.non_workable_client or instance_state.non_workable_server:
                command_object = Retry(sock, params, instance_state, main_logger)
                command_object.do_action()
            else:
                # some case failed on client at all during execution. Sent signal to server and retry
                instance_state.is_aborted_client = True
                command_object = Abort(sock, params, instance_state, main_logger)
                command_object.do_action()
        elif instance_state.is_aborted_server:
            # some case failed on server at all during execution. Server doesn't require to receive signal
            pass

        sock.close()

        return process, last_log_line
