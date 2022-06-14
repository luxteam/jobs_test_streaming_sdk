import argparse
import os
import subprocess
import psutil
import json
import platform
from datetime import datetime
from shutil import copyfile, move, which
import sys
from utils import *
from clientTests import start_client_side_tests
from serverTests import start_server_side_tests
from queue import Queue
from subprocess import PIPE, STDOUT
from threading import Thread
from pyffmpeg import FFmpeg
import copy
import traceback
import time
import win32api

ROOT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_PATH)
from jobs_launcher.core.config import *
from jobs_launcher.core.system_info import get_gpu


# process of Streaming SDK client / server
PROCESS = None
# Multiconnection: save state of android client
android_client_closed = True
MC_CONFIG = get_mc_config()


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
                json.dump(cases, file, indent=4)
    except Exception as e:
        main_logger.error('Can\'t load test_cases.json')
        main_logger.error(str(e))
        exit(-1)


def calculate_status(status_in_json, execution_status):
    test_statuses = (status_in_json, execution_status)
    statuses = ("skipped", "error", "failed", "passed")

    for status in statuses:
        if status in test_statuses:
            return status


def prepare_keys(args, case):
    keys = case["server_keys"] if args.execution_type == "server" else case["client_keys"]

    if args.execution_type == "server":
        # replace 'x' in resolution by ',' (1920x1080 -> 1920,1080)
        # place the current screen resolution in keys of the server instance
        return keys.replace("<resolution>", args.screen_resolution.replace("x", ","))
    else:
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

                if args.execution_type == "server":
                    keys_description = "Server keys: {}".format(prepared_keys)
                    test_case_report["script_info"] = []
                    test_case_report["script_info"].append(keys_description)

                elif args.execution_type == "client":
                    keys_description = "Client keys: {}".format(prepared_keys)
                    test_case_report['script_info'] = case['script_info']
                    test_case_report["script_info"].append(keys_description)
            else:
                test_case_report['script_info'] = case['script_info']
                
            test_case_report['test_group'] = args.test_group
            test_case_report['tool'] = 'StreamingSDK'
            test_case_report['render_time'] = 0.0
            test_case_report['execution_time'] = 0.0
            test_case_report['execution_type'] = args.execution_type
            test_case_report['transport_protocol'] = case['transport_protocol'].upper()
            test_case_report['tool_path'] = args.server_tool if args.execution_type == 'server' else args.client_tool
            test_case_report['date_time'] = datetime.now().strftime(
                '%m/%d/%Y %H:%M:%S')
            if 'jira_issue' in case:
                test_case_report['jira_issue'] = case['jira_issue']
            min_latency_key = 'min_{}_latency'.format(args.execution_type)
            test_case_report[min_latency_key] = -0.0
            max_latency_key = 'max_{}_latency'.format(args.execution_type)
            test_case_report[max_latency_key] = -0.0
            median_latency_key = 'median_{}_latency'.format(args.execution_type)
            test_case_report[median_latency_key] = -0.0
            test_case_report[SCREENS_PATH_KEY] = os.path.join(args.output, "Color", case["case"])
            test_case_report["number_of_tries"] = 0
            test_case_report["client_configuration"] = get_gpu() + " " + platform.system()
            if args.server_gpu_name == "none" and args.server_os_name == "none":
                test_case_report["server_configuration"] = get_gpu() + " " + platform.system()
            else:
                test_case_report["server_configuration"] = args.server_gpu_name + " " + args.server_os_name
            test_case_report["message"] = []

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

        test_case_report["test_status"] = calculate_status(test_case_report["test_status"], test_case_status)

        test_case_report["execution_time"] = execution_time

        test_case_report["server_log"] = os.path.join("tool_logs", case["case"] + "_server.log")
        test_case_report["client_log"] = os.path.join("tool_logs", case["case"] + "_client.log")

        if args.test_group in MC_CONFIG["android_client"]:
            test_case_report["android_log"] = os.path.join("tool_logs", case["case"] + "_android.log")

        if args.collect_traces == "AfterTests" or args.collect_traces == "BeforeTests":
            if args.execution_type == "server":
                test_case_report["server_trace_archive"] = os.path.join("gpuview", case["case"] + "_server.zip")
            else:
                test_case_report["client_trace_archive"] = os.path.join("gpuview", case["case"] + "_client.zip")

        test_case_report["testing_start"] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        test_case_report["number_of_tries"] += 1

        test_case_report["message"] = test_case_report["message"] + list(error_messages)

        test_case_report["keys"] = case["prepared_keys"]

        if test_case_report["test_status"] == "passed" or test_case_report["test_status"] == "error":
            test_case_report["group_timeout_exceeded"] = False

        if args.execution_type == "server":
            video_path = os.path.join("Color", case["case"] + "android.mp4")
        else:
            video_path = os.path.join("Color", case["case"] + "win_client.mp4")

        if os.path.exists(os.path.join(args.output, video_path)):
            test_case_report[VIDEO_KEY] = video_path

        # save keys from scripts in script_info
        test_case_report["script_info"] = case["script_info"]

        if "used_memory" in case:
            used_memory_key = 'used_memory_{}'.format(args.execution_type)
            test_case_report[used_memory_key] = case["used_memory"]

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

    tool_path = args.server_tool if args.execution_type == "server" else args.client_tool

    tool_path = os.path.abspath(tool_path)

    if args.execution_type == "client":
        # name of Stereo mix device can be different on different machines
        audio_device_name = get_audio_device_name()
    else:
        audio_device_name = None

    # copy log from last log line (it's actual for groups without restarting of client / server)
    last_log_line = None

    if (args.test_group in MC_CONFIG["android_client"]) and args.execution_type == "server":
        # first time video recording on Android device can be unstable, do it before tests
        execute_adb_command("adb shell screenrecord --time-limit=10 /sdcard/video.mp4")

    for case in [x for x in cases if not is_case_skipped(x, current_conf)]:

        case["game_name"] = args.game_name

        case_start_time = time.time()

        # take tool keys based on type of the instance (server/client)
        keys = case["server_keys"] if args.execution_type == "server" else case["client_keys"]

        current_try = 0

        main_logger.info("Start test case {}. Try: {}".format(case["case"], current_try))

        while current_try < args.retries:
            global PROCESS, android_client_closed

            error_messages = set()

            try:
                if args.execution_type == "server":
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

                    if case["case"].find('STR_CFG') != -1 or case["case"].find('STR_CFR') != -1:
                        copyfile(
                            os.path.realpath(
                                os.path.join(os.path.dirname(__file__),
                                "..",
                                "Configs",
                                "{}.json".format(case["case"]))
                            ),
                            settings_json_path
                        )

                    with open(settings_json_path, "r") as file:
                        settings_json_content = json.load(file)

                    main_logger.info("Network in settings.json ({}): {}".format(case["case"], settings_json_content["Headset"]["Network"]))
                    main_logger.info("Datagram size in settings.json ({}): {}".format(case["case"], settings_json_content["Headset"]["DatagramSize"]))

                prepared_keys = prepare_keys(args, case)
                execution_script = "{tool} {keys}".format(tool=tool_path, keys=prepared_keys)

                case["prepared_keys"] = prepared_keys

                if args.execution_type == "server":
                    keys_description = "Server keys: {}".format(prepared_keys)
                    case["script_info"] = []
                    case["script_info"].append(keys_description)

                elif args.execution_type == "client":
                    keys_description = "Client keys: {}".format(prepared_keys)
                    case["script_info"].append(keys_description)

                script_path = os.path.join(args.output, "{}.bat".format(case["case"]))

                with open(script_path, "w") as f:
                    f.write(execution_script)

                if args.execution_type == "server":
                    PROCESS, last_log_line, android_client_closed = start_server_side_tests(args, case, PROCESS, android_client_closed, script_path, last_log_line, current_try, error_messages)
                else:
                    PROCESS, last_log_line = start_client_side_tests(args, case, PROCESS, script_path, last_log_line, audio_device_name, current_try, error_messages)

                execution_time = time.time() - case_start_time
                save_results(args, case, cases, execution_time = execution_time, test_case_status = "passed", error_messages = error_messages)

                break
            except Exception as e:
                PROCESS = close_streaming_process(args.execution_type, case, PROCESS)

                if (args.test_group in MC_CONFIG["android_client"]) and args.execution_type == "server":
                    # close Streaming SDK android app
                    close_android_app()
                    save_android_log(args, case, current_try, log_name_postfix="_android")

                last_log_line = save_logs(args, case, last_log_line, current_try)
                execution_time = time.time() - case_start_time
                save_results(args, case, cases, execution_time = execution_time, test_case_status = "failed", error_messages = error_messages)
                main_logger.error("Failed to execute test case (try #{}): {}".format(current_try, str(e)))
                main_logger.error("Traceback: {}".format(traceback.format_exc()))
            finally:
                current_try += 1
                main_logger.info("End of test case")
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
    parser.add_argument('--execution_type', required=True)
    parser.add_argument('--ip_address', required=True)
    parser.add_argument('--communication_port', required=True)
    parser.add_argument('--server_gpu_name', required=True)
    parser.add_argument('--server_os_name', required=True)
    parser.add_argument('--game_name', required=True)
    parser.add_argument('--common_actions_path', required=True)
    parser.add_argument('--collect_traces', required=True)
    parser.add_argument('--screen_resolution', required=True)
    parser.add_argument('--track_used_memory', required=False, default=False)

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

        # use OS name and GPU name from server (to skip and merge cases correctly)
        render_device = get_gpu() if args.server_gpu_name == "none" else args.server_gpu_name
        system_pl = platform.system() if args.server_os_name == "none" else args.server_os_name
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
