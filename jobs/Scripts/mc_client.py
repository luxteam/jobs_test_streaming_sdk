import argparse
import os
import psutil
import json
import platform
from datetime import datetime
from shutil import copyfile, move, which
import sys
from pyffmpeg import FFmpeg
import traceback
from time import sleep, time
import socket
from instance_state import SecondClientInstanceState
from utils import *
from mc_actions import *
from analyzeLogs import analyze_logs

ROOT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_PATH)
from jobs_launcher.core.config import *
from jobs_launcher.core.system_info import get_gpu


# mapping of commands and their implementations
ACTIONS_MAPPING = {
    "make_screen": MakeScreen,
    "sleep_and_screen": SleepAndScreen,
    "record_metrcis": RecordMetrics,
    "record_video": RecordVideo,
    "finish": Finish
}


def get_audio_device_name():
    try:
        ff = FFmpeg()
        ffmpeg_exe = ff.get_ffmpeg_bin()

        # list all existing audio devices
        ffmpeg_command = "{} -list_devices true -f dshow -i dummy".format(ffmpeg_exe)

        ffmpeg_process = psutil.Popen(ffmpeg_command, stdout=PIPE, stderr=STDOUT, shell=True)

        audio_device = None

        for line in ffmpeg_process.stdout:
            line = line.decode("utf8")
            if "Stereo Mix" in line:
                audio_device = line.split("\"")[1]
                break
        else:
            raise Exception("Audio device wasn't found")

        main_logger.info("Found audio device: {}".format(audio_device))

        return audio_device
    except Exception as e:
        main_logger.error("Can't get audio device name. Use default name instead")
        main_logger.error(str(e))
        main_logger.error("Traceback:\n{}".format(traceback.format_exc()))

        return "Stereo Mix (Realtek High Definition Audio)"


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
    keys = case["second_client_keys"]

    return "{keys} -connectionurl {transport_protocol}://{ip_address}:1235".format(
        keys=keys,
        transport_protocol=case["transport_protocol"],
        ip_address=args.ip_address
    )


def prepare_empty_reports(args, current_conf):
    main_logger.info('Create empty report files')

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
            test_case_report['render_device'] = args.server_gpu_name

            if case['status'] == 'skipped':
                prepared_keys = prepare_keys(args, case)

                keys_description = "Second client keys: {}".format(prepared_keys)
                test_case_report["script_info"] = case["script_info"]
                test_case_report["script_info"].append(keys_description)
            else:
                test_case_report["script_info"] = case["script_info"]
                
            test_case_report['test_group'] = args.test_group
            test_case_report['tool'] = 'StreamingSDK'
            test_case_report['render_time'] = 0.0
            test_case_report['execution_time'] = 0.0
            test_case_report['transport_protocol'] = case['transport_protocol'].upper()
            test_case_report['tool_path'] = args.tool
            test_case_report['date_time'] = datetime.now().strftime(
                '%m/%d/%Y %H:%M:%S')
            test_case_report[SCREENS_PATH_KEY] = os.path.join(args.output, "Color", case["case"])
            test_case_report["second_client_configuration"] = get_gpu() + " " + platform.system()
            test_case_report["message"] = []

            if case['status'] == 'skipped':
                test_case_report['test_status'] = 'skipped'
                test_case_report['group_timeout_exceeded'] = False
            else:
                test_case_report['test_status'] = 'error'

            case_path = os.path.join(args.output, case['case'] + CASE_REPORT_SUFFIX)

            with open(case_path, "w") as f:
                f.write(json.dumps([test_case_report], indent=4))

    with open(os.path.join(args.output, "test_cases.json"), "w+") as f:
        json.dump(cases, f, indent=4)


def save_results(args, case, cases, execution_time = 0.0, test_case_status = "", error_messages = []):
    with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "r") as file:
        test_case_report = json.loads(file.read())[0]
        test_case_report["test_status"] = test_case_status
        test_case_report["execution_time"] = execution_time
        test_case_report["log"] = os.path.join("tool_logs", case["case"] + "_second_client.log")
        test_case_report["testing_start"] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        test_case_report["message"] = test_case_report["message"] + list(error_messages)
        test_case_report["keys"] = case["prepared_keys"]

        if test_case_report["test_status"] == "passed" or test_case_report["test_status"] == "error":
            test_case_report["group_timeout_exceeded"] = False

        video_path = os.path.join("Color", case["case"] + "second_win_client.mp4")

        if os.path.exists(os.path.join(args.output, video_path)):
            test_case_report[VIDEO_KEY] = video_path

        # save keys from scripts in script_info
        test_case_report["script_info"] = case["script_info"]

        if "used_memory" in case:
            test_case_report["used_memory_second_client"] = case["used_memory"]

    with open(os.path.join(args.output, case["case"] + CASE_REPORT_SUFFIX), "w") as file:
        json.dump([test_case_report], file, indent=4)

    if test_case_status:
       case["status"] = test_case_status

    with open(os.path.join(args.output, "test_cases.json"), "w") as file:
        json.dump(cases, file, indent=4)


def execute_tests(args, current_conf):
    rc = 0

    with open(os.path.join(os.path.abspath(args.output), "test_cases.json"), "r") as json_file:
        cases = json.load(json_file)

    tests_left = len(cases)

    tool_path = args.tool

    tool_path = os.path.abspath(tool_path)

    audio_device_name = get_audio_device_name()

    process = None
    # copy log from last log line (it's actual for groups without restarting of client / server)
    last_log_line = None

    more_tests = True
    previous_test_case = None
    current_try = 0

    while tests_left > 0:
        try:
            # Connect to server to sync autotests
            while True:
                try:
                    sock = socket.socket()
                    sock.connect((args.ip_address, int(args.communication_port)))
                    sock.send("second_client".encode("utf-8"))
                    response = sock.recv(1024).decode("utf-8")
                    break
                except Exception:
                    main_logger.info("Could not connect to server. Try it again")
                    sleep(1)

            # find test case
            with open(os.path.join(os.path.abspath(args.output), "test_cases.json"), "r") as json_file:
                cases = json.load(json_file)

            case = None

            for current_case in cases:
                if current_case["case"] == response:
                    case = current_case
                    break
            else:
                raise Exception("Could not find test case with name '{}'".format(response))

            if case == previous_test_case:
                current_try += 1
            else:
                previous_test_case = case
                current_try = 0

            prepared_keys = prepare_keys(args, case)
            execution_script = "{tool} {keys}".format(tool=tool_path, keys=prepared_keys)

            case["prepared_keys"] = prepared_keys

            keys_description = "Second client keys: {}".format(prepared_keys)
            case["script_info"].append(keys_description)

            script_path = os.path.join(args.output, "{}.bat".format(case["case"]))

            with open(script_path, "w") as f:
                f.write(execution_script)

            output_path = os.path.join(args.output, "Color")

            screen_path = os.path.join(output_path, case["case"])
            if not os.path.exists(screen_path):
                os.makedirs(screen_path)

            instance_state = SecondClientInstanceState()

            # build params dict with all necessary variables for test actions
            params = {}
            params["output_path"] = output_path
            params["screen_path"] = screen_path
            params["current_image_num"] = 1
            params["current_try"] = current_try
            params["args"] = args
            params["case"] = case
            params["client_type"] = "second_client"

            case_start_time = time.time()
            process = start_streaming("client", script_path, not should_collect_traces)

            # while client doesn't sent 'next_case' command server waits next command
            while not instance_state.finish_command_received:
                try:
                    request = sock.recv(1024).decode("utf-8")
                except Exception as e:
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

                params["action_line"] = request
                params["command"] = command
                params["arguments_line"] = arguments_line

                # find necessary command and execute it
                if command in ACTIONS_MAPPING:
                    command_object = ACTIONS_MAPPING[command](connection, params, instance_state, main_logger)
                    command_object.do_action()
                else:
                    raise ServerActionException("Unknown client command: {}".format(command))

                main_logger.info("Finish action execution\n\n\n")

            process = close_streaming_process("client", case, process)

            with open(os.path.join(args.output, "test_cases.json"), "w+") as f:
                json.dump(cases, f, indent=4)

            process = close_streaming_process("client", case, process)
            last_log_line = save_logs(args, case, last_log_line, current_try)
            execution_time = time.time() - case_start_time
            save_results(args, case, cases, execution_time = execution_time, test_case_status = "passed", error_messages = [])

        except Exception as e:
            main_logger.error("Fatal error: {}".format(str(e)))
            main_logger.error("Traceback: {}".format(traceback.format_exc()))
            last_log_line = save_logs(args, case, last_log_line, current_try)
            execution_time = time.time() - case_start_time
            save_results(args, case, cases, execution_time = execution_time, test_case_status = "error", error_messages = [])

        finally:
            tests_left -= 1

    return 0


def createArgsParser():
    parser = argparse.ArgumentParser()

    parser.add_argument("--tool", required=True, metavar="<path>")
    parser.add_argument("--output", required=True, metavar="<dir>")
    parser.add_argument("--test_group", required=True)
    parser.add_argument("--test_cases", required=True)
    parser.add_argument('--ip_address', required=True)
    parser.add_argument('--communication_port', required=True)
    parser.add_argument('--server_gpu_name', required=True)
    parser.add_argument('--server_os_name', required=True)
    parser.add_argument('--screen_resolution', required=True)
    parser.add_argument('--track_used_memory', required=False, default=False)

    return parser


if __name__ == '__main__':
    main_logger.info('Main script start working...')

    args = createArgsParser().parse_args()

    try:
        os.makedirs(args.output)

        if not os.path.exists(os.path.join(args.output, "Color")):
            os.makedirs(os.path.join(args.output, "Color"))
        if not os.path.exists(os.path.join(args.output, "tool_logs")):
            os.makedirs(os.path.join(args.output, "tool_logs"))

        # use OS name and GPU name from server (to skip and merge cases correctly)
        render_device = args.server_gpu_name
        system_pl = args.server_os_name
        current_conf = set(system_pl) if not render_device else {system_pl, render_device}
        main_logger.info("Detected GPUs: {}".format(render_device))
        main_logger.info("PC conf: {}".format(current_conf))
        main_logger.info("Creating predefined errors json...")

        copy_test_cases(args)
        prepare_empty_reports(args, current_conf)
        exit(execute_tests(args, current_conf))
    except Exception as e:
        main_logger.error("Failed during script execution. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))
        exit(-1)
