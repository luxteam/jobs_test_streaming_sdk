import socket
import sys
import os
import json
from time import sleep, time
import psutil
from subprocess import PIPE
import traceback
import win32gui
import win32api
import shlex
import pyautogui
import pydirectinput
from utils import *
from threading import Thread
from instance_state import ServerInstanceState
from server_actions import *
from android_actions import MakeScreen, SleepAndScreen, RecordVideo
from analyzeLogs import analyze_logs

ROOT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_PATH)
from jobs_launcher.core.config import *

pyautogui.FAILSAFE = False

GAMES_WITH_TIMEOUTS = ['apexlegends']

# some games should be rebooted sometimes
REBOOTING_GAMES = {"valorant": {"time_to_reboot": 3000, "delay": 120}, "lol": {"time_to_reboot": 3000, "delay": 240}}


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
    "start_test_actions_server": DoTestActions,
    "gpuview": GPUView,
    "record_metrics": RecordMetrics,
    "make_screen": MakeScreen,
    "sleep_and_screen": SleepAndScreen,
    "record_video": RecordVideo
}


ANDROID_ACTIONS = ["make_screen", "sleep_and_screen", "record_video"]


# Server receives commands from client and executes them
# Server doesn't decide to retry case or do next test case. Exception: fail on server side which generates abort on server side
def start_server_side_tests(args, case, process, android_client_closed, script_path, last_log_line, last_log_line_android, current_try):
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
                collect_traces(archive_path, archive_name + "_server.zip")

    # TODO: make single parameter to configure launching order
    # start android client before server
    if "android_start" in case and case["android_start"] == "before_server":
        if android_client_closed:
            multiconnection_start_android(args.test_group)

    # start server before client
    if "start_first" in case and case["start_first"] == "server":
        if start_streaming is not None and process is None:
            should_collect_traces = (args.collect_traces == "BeforeTests")
            process = start_streaming(args.execution_type, script_path, not should_collect_traces)

            if should_collect_traces:
                collect_traces(archive_path, archive_name + "_server.zip")
            else:
                sleep(10)

    # configure socket
    sock = socket.socket()
    sock.bind(("", int(args.communication_port)))
    # max one connection
    sock.listen(1)
    connection, address = sock.accept()

    request = connection.recv(1024).decode("utf-8")

    game_name = args.game_name.lower()

    global GAMES_WITH_TIMEOUTS

    # some games can kick by AFK reason
    # press space before each test case to prevent it
    if game_name in GAMES_WITH_TIMEOUTS:
        pydirectinput.press("space")

    params = {}
    processes = {}

    try:
        # create state object
        instance_state = ServerInstanceState()

        # server waits ready from client
        if request == "ready":

            # start client before server
            if "start_first" in case and case["start_first"] == "client":
                if start_streaming is not None and process is None:
                    should_collect_traces = (args.collect_traces == "BeforeTests")
                    process = start_streaming(args.execution_type, script_path, not should_collect_traces)

                    if should_collect_traces:
                        collect_traces(archive_path, archive_name + "_server.zip")

            # TODO: make single parameter to configure launching order
            # start android client after server or default behaviour
            if ("android_start" in case and case["android_start"] == "before_server") or "android_start" not in case:
                multiconnection_start_android(args.test_group)

            if is_workable_condition(process):
                connection.send("ready".encode("utf-8"))
            else:
                connection.send("fail".encode("utf-8"))

            # non-blocking usage
            connection.setblocking(False)

            # build params dict with all necessary variables for test actions
            params["output_path"] = output_path
            params["screen_path"] = screen_path
            params["archive_path"] = archive_path
            params["current_image_num"] = 1
            params["current_try"] = current_try
            params["args"] = args
            params["case"] = case
            params["game_name"] = game_name
            params["processes"] = processes
            params["client_type"] = "android"

            test_action_command = DoTestActions(sock, params, instance_state, main_logger)
            test_action_command.parse()

            # while client doesn't sent 'next_case' command server waits next command
            while instance_state.wait_next_command:
                try:
                    request = connection.recv(1024).decode("utf-8")
                except Exception as e:
                    # execute test actions if it's requested by client and new command doesn't received
                    if instance_state.executing_test_actions:
                        test_action_command.execute()
                    else:
                        sleep(1)
                    continue

                main_logger.info("Received action: {}".format(request))
                main_logger.info("Current state:\n{}".format(instance_state.format_current_state()))

                # split action to command and arguments
                parts = request.split(" ", 1)
                command = parts[0]
                if len(parts) > 1:
                    arguments_line = parts[1]
                else:
                    arguments_line = None

                if command != "gpuview" and command != "record_metrics" and command not in ANDROID_ACTIONS :
                    # if new command received server must stop to execute test actions execution. Exception: gpuview and record_metrics commands
                    instance_state.executing_test_actions = False

                params["action_line"] = request
                params["command"] = command
                params["arguments_line"] = arguments_line

                # find necessary command and execute it
                if command in ACTIONS_MAPPING:
                    # if client requests to start doing test actions server must answer immediately and starts to execute them
                    if command == "start_test_actions_server":
                        connection.send("done".encode("utf-8"))
                        instance_state.executing_test_actions = True
                        continue

                    command_object = ACTIONS_MAPPING[command](connection, params, instance_state, main_logger)
                    command_object.do_action()
                else:
                    raise ServerActionException("Unknown server command: {}".format(command))

                main_logger.info("Finish action execution\n\n\n")

            process = close_streaming_process(args.execution_type, case, process)

            if args.test_group == "Multiconnection":
                # close Streaming SDK android app
                android_client_closed = close_android_app(case, True)
                last_log_line_android = save_android_log(args, case, None, current_try, log_name_postfix="_android")

            last_log_line = save_logs(args, case, last_log_line, current_try)

            with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "r") as file:
                json_content = json.load(file)[0]

            json_content["test_status"] = "passed"
            analyze_logs(args.output, json_content, case)

            # execute iperf if it's necessary
            params["json_content"] = json_content
            command_object = IPerf(connection, params, instance_state, main_logger)
            command_object.do_action()

            with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "w") as file:
                json.dump([json_content], file, indent=4)

        else:
            raise Exception("Unknown client request: {}".format(request))
    except Exception as e:
        # Unexpected exception. Generate abort status on server side
        main_logger.error("Fatal error. Case will be aborted:".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        if not instance_state.is_aborted:
            connection.send("abort".encode("utf-8"))

        raise e
    finally:
        connection.close()

        # restart game if it's required
        global REBOOTING_GAMES
        
        with open(os.path.join(ROOT_PATH, "state.py"), "r") as json_file:
            state = json.load(json_file)

        if state["restart_time"] == 0:
            state["restart_time"] = time()
            main_logger.info("Reboot time was set")
        else:
            main_logger.info("Time left from the latest restart of game: {}".format(time() - state["restart_time"]))
            if args.game_name.lower() in REBOOTING_GAMES and (time() - state["restart_time"]) > REBOOTING_GAMES[args.game_name.lower()]["time_to_reboot"]:
                close_game(game_name.lower())
                result = close_processes(processes, main_logger)
                main_logger.info("Processes were closed with status: {}".format(result))

                # sleep a bit if it's required (some games can open same lobby if restart game immediately)
                if "delay" in REBOOTING_GAMES[args.game_name.lower()]:
                    sleep(REBOOTING_GAMES[args.game_name.lower()]["delay"])

                state["restart_time"] = time()
                
        with open(os.path.join(ROOT_PATH, "state.py"), "w+") as json_file:
            json.dump(state, json_file, indent=4)

        return process, last_log_line
