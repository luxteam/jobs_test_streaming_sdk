import argparse
import os
import subprocess
import psutil
import json
import platform
from datetime import datetime
from shutil import copyfile, move
import sys
from utils import *
from subprocess import PIPE, STDOUT
from threading import Thread
import copy
import traceback
import time
import win32api
from instance_state import AndroidInstanceState
from android_actions import *
from analyzeLogs import analyze_logs

ROOT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_PATH)
from jobs_launcher.core.config import *
from jobs_launcher.core.system_info import get_gpu


# some games should be rebooted sometimes
REBOOTING_GAMES = {"valorant": {"time_to_reboot": 3000, "delay": 120}, "lol": {"time_to_reboot": 3000}}


# mapping of commands and their implementations
ACTIONS_MAPPING = {
    "open_game": OpenGame,
    "click": Click,
    "sleep": DoSleep,
    "press_keys": PressKeys,
    "make_screen": MakeScreen,
    "sleep_and_screen": SleepAndScreen,
    "record_video": RecordVideo,
    "start_actions": StartActions
}


def hide_emulator(args):
    window = win32gui.FindWindow(None, "Android Emulator - Pixel:5554")
    make_window_minimized(window)


def copy_test_cases(args):
    try:
        copyfile(os.path.realpath(os.path.join(os.path.dirname(
            __file__), '..', 'Tests', args.test_group, 'test_cases.json')),
            os.path.realpath(os.path.join(os.path.abspath(
                args.output), 'test_cases.json')))

        cases = json.load(open(os.path.realpath(
            os.path.join(os.path.abspath(args.output), 'test_cases.json'))))

        with open(os.path.join(os.path.abspath(args.output), "test_cases.json"), "r") as json_file:
            cases = json.load(json_file)

        if os.path.exists(args.test_cases) and args.test_cases:
            with open(args.test_cases) as file:
                test_cases = json.load(file)['groups'][args.test_group]
                if test_cases:
                    necessary_cases = [
                        item for item in cases if item['case'] in test_cases]
                    cases = necessary_cases

            with open(os.path.join(args.output, 'test_cases.json'), "w+") as file:
                json.dump(duplicated_cases, file, indent=4)
    except Exception as e:
        main_logger.error('Can\'t load test_cases.json')
        main_logger.error(str(e))
        exit(-1)


def prepare_keys(args, case):
    prepared_keys = case["server_keys"]
    # TODO remove hardcoded values
    prepared_keys = prepared_keys.replace("<resolution>", "1920,1080")


def prepare_empty_reports(args):
    main_logger.info('Create empty report files')

    render_device = get_gpu()
    platform_name = platform.system() + " with Android real device"
    current_conf = set(platform_name) if not render_device else {platform_name, render_device}
    main_logger.info("Detected GPUs: {}".format(render_device))
    main_logger.info("PC conf: {}".format(current_conf))
    main_logger.info("Creating predefined errors json...")

    resolution_width = win32api.GetSystemMetrics(0)
    resolution_height = win32api.GetSystemMetrics(1)

    with open(os.path.join(os.path.abspath(args.output), "test_cases.json"), "r") as json_file:
        cases = json.load(json_file)

    for case in cases:
        if is_case_skipped(case, current_conf):
            case['status'] = 'skipped'

        if case['status'] != 'done' and case['status'] != 'error':
            if case["status"] == 'inprogress':
                case['status'] = 'active'

            test_case_report = {}
            test_case_report['test_case'] = case['case']
            test_case_report['render_device'] = render_device

            if case['status'] == 'skipped':
                prepared_keys = prepare_keys(args, case)

                keys_description = "Server keys: {}".format(prepared_keys)
                case["script_info"].append(keys_description)
            else:
                test_case_report['script_info'] = case['script_info']

            test_case_report['test_group'] = args.test_group
            test_case_report['tool'] = 'StreamingSDK'
            test_case_report['render_time'] = 0.0
            test_case_report['execution_time'] = 0.0
            test_case_report['keys'] = case['server_keys']
            test_case_report['transport_protocol'] = case['transport_protocol'].upper()
            test_case_report['server_tool_path'] = args.server_tool
            test_case_report['client_tool_path'] = args.client_tool
            test_case_report['date_time'] = datetime.now().strftime(
                '%m/%d/%Y %H:%M:%S')
            test_case_report[SCREENS_PATH_KEY] = os.path.join(args.output, "Color", case["case"])
            test_case_report["number_of_tries"] = 0
            test_case_report["server_configuration"] = render_device + " " + platform_name
            test_case_report["message"] = []

            script_info = []

            # ignore client keys (they aren't used in Android autotests)
            for i in range(len(test_case_report["script_info"])):
                if "Client keys" not in test_case_report["script_info"][i]:
                    # ignore line with client keys (they aren't used by Android autotests)
                    script_info.append(test_case_report["script_info"][i])

            test_case_report["script_info"] = script_info

            if case['status'] == 'skipped':
                test_case_report['test_status'] = 'skipped'
                test_case_report['group_timeout_exceeded'] = False
            else:
                test_case_report['test_status'] = 'error'

            case_path = os.path.join(args.output, case['case'] + CASE_REPORT_SUFFIX)

            if os.path.exists(case_path):
                with open(case_path) as f:
                    case_json = json.load(f)[0]
                    test_case_report["number_of_tries"] = case_json["number_of_tries"]

            with open(case_path, "w") as f:
                f.write(json.dumps([test_case_report], indent=4))

    with open(os.path.join(args.output, "test_cases.json"), "w+") as f:
        json.dump(cases, f, indent=4)


def save_results(args, case, cases, execution_time = 0.0, test_case_status = "", error_messages = []):
    with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "r") as file:
        test_case_report = json.loads(file.read())[0]

        test_case_report["test_status"] = test_case_status

        test_case_report["execution_time"] = execution_time

        test_case_report["server_log"] = os.path.join("tool_logs", case["case"] + "_server.log")
        test_case_report["client_log"] = os.path.join("tool_logs", case["case"] + "_client.log")

        test_case_report["testing_start"] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        test_case_report["number_of_tries"] += 1

        test_case_report["message"] = test_case_report["message"] + list(error_messages)

        if test_case_report["test_status"] == "passed" or test_case_report["test_status"] == "error":
            test_case_report["group_timeout_exceeded"] = False

        video_path = os.path.join("Color", case["case"] + ".mp4")

        if os.path.exists(os.path.join(args.output, video_path)):
            test_case_report[VIDEO_KEY] = video_path

        # save keys from scripts in script_info
        test_case_report["script_info"] = case["script_info"]

    with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "w") as file:
        json.dump([test_case_report], file, indent=4)

    if test_case_status:
       case["status"] = test_case_status

    with open(os.path.join(args.output, "test_cases.json"), "w") as file:
        json.dump(cases, file, indent=4)


def prepare_android_emulator(args):
    #execute_adb_command("adb uninstall com.amd.remotegameclient")
    #execute_adb_command("adb install {}".format(os.path.abspath(args.client_tool)))
    #execute_adb_command("adb shell pm grant com.amd.remotegameclient android.permission.RECORD_AUDIO")
    pass


def execute_tests(args):
    render_device = get_gpu()
    platform_name = platform.system() + " with Android real device"
    current_conf = set(platform_name) if not render_device else {platform_name, render_device}

    rc = 0

    with open(os.path.join(os.path.abspath(args.output), "test_cases.json"), "r") as json_file:
        cases = json.load(json_file)

    resolution_width = win32api.GetSystemMetrics(0)
    resolution_height = win32api.GetSystemMetrics(1)

    process = None
    client_closed = True
    processes = {}

    # copy log from last log line
    last_log_line_server = None
    last_log_line_client = None

    # first time video recording can be unstable, do it before tests
    execute_adb_command("adb shell screenrecord --time-limit=10 /sdcard/video.mp4")

    for case in [x for x in cases if not is_case_skipped(x, current_conf)]:

        case_start_time = time.time()

        current_try = 0

        main_logger.info("Start test case {}. Try: {}".format(case["case"], current_try))

        while current_try < args.retries:
            error_messages = set()

            try:
                instance_state = AndroidInstanceState()

                # copy settings.json to update transport protocol using by server instance
                settings_json_path = os.path.join(os.getenv("APPDATA"), "..", "Local", "AMD", "RemoteGameServer", "settings", "settings.json")

                copyfile(
                    os.path.realpath(
                        os.path.join(os.path.dirname(__file__),
                        "..",
                        "Configs",
                        "settings_{}.json".format(case["transport_protocol"].upper()))
                    ), 
                    settings_json_path
                )

                with open(settings_json_path, "r") as file:
                    settings_json_content = json.load(file)

                main_logger.info("Network in settings.json ({}): {}".format(case["case"], settings_json_content["Headset"]["Network"]))
                main_logger.info("Datagram size in settings.json ({}): {}".format(case["case"], settings_json_content["Headset"]["DatagramSize"]))

                prepared_keys = prepare_keys(args, case)

                server_execution_script = "{tool} {keys}".format(tool=args.server_tool, keys=prepared_keys)

                server_script_path = os.path.join(args.output, "{}.bat".format(case["case"]))
       
                with open(server_script_path, "w") as f:
                    f.write(server_execution_script)

                keys_description = "Server keys: {}".format(prepared_keys)
                case["script_info"].append(keys_description)

                case["prepared_keys"] = prepared_keys

                params = {}

                output_path = os.path.join(args.output, "Color")

                screen_path = os.path.join(output_path, case["case"])
                if not os.path.exists(screen_path):
                    os.makedirs(screen_path)

                params["output_path"] = output_path
                params["screen_path"] = screen_path
                params["current_image_num"] = 1
                params["current_try"] = current_try
                params["args"] = args
                params["case"] = case
                params["game_name"] = args.game_name.lower()

                # get list of actions for the current game / benchmark
                actions_key = "{}_actions_android".format(args.game_name.lower())
                if actions_key in case:
                    actions = case[actions_key]
                else:
                    # use default list of actions if some specific list of actions doesn't exist
                    with open(os.path.abspath(args.common_actions_path), "r", encoding="utf-8") as common_actions_file:
                        actions = json.load(common_actions_file)[actions_key]

                # execute actions one by one
                for action in actions:
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
                        command_object = ACTIONS_MAPPING[command](None, params, instance_state, main_logger)
                        command_object.do_action()
                    else:
                        raise ClientActionException("Unknown client command: {}".format(command))

                    # check that connection is still alive
                    if command == "open_game":
                        # start server first
                        if "start_first" in case and case["start_first"] == "server":
                            if process is None:
                                main_logger.info("Start Streaming SDK server instance")
                                process = start_streaming("server", server_script_path)
                                sleep(10)

                        if client_closed:
                            execute_adb_command("adb logcat -c")
                            execute_adb_command("adb shell am start -n com.amd.remotegameclient/.MainActivity")

                        if "start_first" in case and case["start_first"] == "client":
                            sleep(10)

                        # start server after client
                        if "start_first" not in case or case["start_first"] == "client":
                            main_logger.info("Start Streaming SDK server instance")
                            process = start_streaming("server", server_script_path)

                    main_logger.info("Finish action execution\n\n\n")

                execution_time = time.time() - case_start_time
                save_results(args, case, cases, execution_time = execution_time, test_case_status = "passed", error_messages = [])

                break
            except Exception as e:
                execution_time = time.time() - case_start_time
                save_results(args, case, cases, execution_time = execution_time, test_case_status = "failed", error_messages = error_messages)
                close_game_process(args.game_name.lower())
                main_logger.error("Failed to execute test case (try #{}): {}".format(current_try, str(e)))
                main_logger.error("Traceback: {}".format(traceback.format_exc()))
            finally:
                # close Streaming SDK android app
                client_closed = close_android_app(case)
                # close Streaming SDK server instance
                process = close_streaming_process("server", case, process)
                last_log_line_server = save_logs(args, case, last_log_line_server, current_try)
                last_log_line_client = save_android_log(args, case, last_log_line_client, current_try)

                try:
                    with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "r") as file:
                        json_content = json.load(file)[0]

                    json_content["test_status"] = "passed"
                    analyze_logs(args.output, json_content, case, execution_type = "android")

                    with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "w") as file:
                        json.dump([json_content], file, indent=4)
                except Exception as e:
                    main_logger.error("Failed to analyze_logs (try #{}): {}".format(current_try, str(e)))
                    main_logger.error("Traceback: {}".format(traceback.format_exc()))

                # restart game if it's required
                global REBOOTING_GAMES
                
                with open(os.path.join(ROOT_PATH, "state.py"), "r") as json_file:
                    state = json.load(json_file)

                if state["restart_time"] == 0:
                    state["restart_time"] = time.time()
                    main_logger.info("Reboot time was set")
                else:
                    main_logger.info("Time left from the latest restart of game: {}".format(time.time() - state["restart_time"]))
                    if args.game_name.lower() in REBOOTING_GAMES and (time.time() - state["restart_time"]) > REBOOTING_GAMES[args.game_name.lower()]["time_to_reboot"]:
                        close_game(args.game_name.lower())
                        close_game_process(args.game_name.lower())

                        # sleep a bit if it's required (some games can open same lobby if restart game immediately)
                        if "delay" in REBOOTING_GAMES[args.game_name.lower()]:
                            sleep(REBOOTING_GAMES[args.game_name.lower()]["delay"])

                        state["restart_time"] = time.time()

                with open(os.path.join(ROOT_PATH, "state.py"), "w+") as json_file:
                    json.dump(state, json_file, indent=4)

                current_try += 1

                if ("keep_server" in case and case["keep_server"]) or ("keep_client" in case and case["keep_client"]):
                    sleep(30)
        else:
            main_logger.error("Failed to execute case '{}' at all".format(case["case"]))
            rc = -1
            execution_time = time.time() - case_start_time
            save_results(args, case, cases, execution_time = execution_time, test_case_status = "error", error_messages = error_messages)

    return rc


def createArgsParser():
    parser = argparse.ArgumentParser()

    parser.add_argument("--client_tool", required=True, metavar="<path>")
    parser.add_argument("--server_tool", required=True, metavar="<path>")
    parser.add_argument("--output", required=True, metavar="<dir>")
    parser.add_argument("--test_group", required=True)
    parser.add_argument("--test_cases", required=True)
    parser.add_argument("--retries", required=False, default=2, type=int)
    parser.add_argument('--game_name', required=True)
    parser.add_argument('--common_actions_path', required=True)

    return parser


if __name__ == '__main__':
    main_logger.info('simpleRender start working...')

    args = createArgsParser().parse_args()

    try:
        os.makedirs(args.output)

        if not os.path.exists(os.path.join(args.output, "Color")):
            os.makedirs(os.path.join(args.output, "Color"))
        if not os.path.exists(os.path.join(args.output, "tool_logs")):
            os.makedirs(os.path.join(args.output, "tool_logs"))

        hide_emulator(args)
        copy_test_cases(args)
        prepare_empty_reports(args)
        prepare_android_emulator(args)
        exit(execute_tests(args))
    except Exception as e:
        main_logger.error("Failed during script execution. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))
        exit(-1)
