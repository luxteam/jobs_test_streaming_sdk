from time import sleep
import psutil
import os
from glob import glob
import zipfile
import subprocess
from subprocess import PIPE
import shlex
import win32api
import sys
import traceback
from shutil import copyfile
from datetime import datetime
import pydirectinput, pyautogui
import win32gui

ROOT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_PATH)
from jobs_launcher.core.config import main_logger


def is_case_skipped(case, render_platform):
    if case['status'] == 'skipped':
        return True

    return sum([render_platform & set(x) == set(x) for x in case.get('skip_on', '')])


def close_process(process):
    child_processes = []

    try:
        child_processes = process.children()
    except psutil.NoSuchProcess:
        pass

    for ch in child_processes:
        try:
            ch.terminate()
            sleep(5)
            ch.kill()
            sleep(5)
            status = ch.status()
        except psutil.NoSuchProcess:
            pass

    try:
        process.terminate()
        sleep(5)
        process.kill()
        sleep(5)
        status = process.status()
    except psutil.NoSuchProcess:
        pass


def collect_traces(archive_path, archive_name):
    traces_base_path = "C:\\JN\\GPUViewTraces"
    # traces can generate in gpuview dir
    gpuview_path = os.getenv("GPUVIEW_PATH")
    executable_name = "log_extended.cmd - Shortcut.lnk"
    target_name = "Merged.etl"

    try:
        for filename in glob(os.path.join(traces_base_path, "*.etl")):
            os.remove(filename)
    except Exception:
        pass

    try:
        for filename in glob(os.path.join(gpuview_path, "*.etl")):
            os.remove(filename)
    except Exception:
        pass

    proc = psutil.Popen(os.path.join(traces_base_path, executable_name), stdout=PIPE, stderr=PIPE, shell=True)

    proc.communicate()

    sleep(2)

    target_path = os.path.join(traces_base_path, target_name)

    if not os.path.exists(target_path):
        target_path = os.path.join(gpuview_path, target_name)

        if not os.path.exists(target_path):
            raise Exception("Could not find etl file by path {}".format(target_path))

    with zipfile.ZipFile(os.path.join(archive_path, archive_name), "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(target_path, arcname=target_name)


def parse_arguments(arguments):
    return shlex.split(arguments)


def is_workable_condition(process):
    # is process with Streaming SDK alive
    try:
        process.wait(timeout=0)
        main_logger.error("StreamingSDK was down")

        return False
    except psutil.TimeoutExpired as e:
        main_logger.info("StreamingSDK is alive") 

        return True


def should_case_be_closed(execution_type, case):
    return "keep_{}".format(execution_type) not in case or not case["keep_{}".format(execution_type)]


def close_streaming_process(execution_type, case, process):
    try:
        if should_case_be_closed(execution_type, case):
            # close the current Streaming SDK process
            if process is not None:
                close_process(process)

            # additional try to kill Streaming SDK server/client (to be sure that all processes are closed)

            status = 0

            while status != 128:
                status = subprocess.call("taskkill /f /im RemoteGameClient.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            status = 0

            while status != 128:
                status = subprocess.call("taskkill /f /im RemoteGameServer.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            process = None

        return process
    except Exception as e:
        main_logger.error("Failed to close Streaming SDK process. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        return None


def close_android_app(case=None, multiconnection=False):
    try:
        key = "android" if multiconnection else "client"

        if case is None or should_case_be_closed(key, case):
            execute_adb_command("adb shell am force-stop com.amd.remotegameclient")

            return True

        return False
    except Exception as e:
        main_logger.error("Failed to close Streaming SDK Android app. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))


def save_logs(args, case, last_log_line, current_try):
    try:
        if hasattr(args, "execution_type"):
            execution_type = args.execution_type
        else:
            execution_type = "server"

        tool_path = args.server_tool if execution_type == "server" else args.client_tool
        tool_path = os.path.abspath(tool_path)

        log_source_path = tool_path + ".log"
        log_destination_path = os.path.join(args.output, "tool_logs", case["case"] + "_{}".format(execution_type) + ".log")

        with open(log_source_path, "rb") as file:
            logs = file.read()

        # Firstly, convert utf-2 le bom to utf-8 with BOM. Secondly, remove BOM
        logs = logs.decode("utf-16-le").encode("utf-8").decode("utf-8-sig").encode("utf-8")

        lines = logs.split(b"\n")

        # index of first line of the current log in whole log file
        first_log_line_index = 0

        for i in range(len(lines)):
            if last_log_line is not None and last_log_line in lines[i]:
                first_log_line_index = i + 1
                break

        # update last log line
        for i in range(len(lines) - 1, -1, -1):
            if lines[i] and lines[i] != b"\r":
                last_log_line = lines[i]
                break

        if first_log_line_index != 0:
            lines = lines[first_log_line_index:]

        logs = b"\n".join(lines)

        with open(log_destination_path, "ab") as file:
            file.write("\n---------- Try #{} ----------\n\n".format(current_try).encode("utf-8"))
            file.write(logs)

        return last_log_line
    except Exception as e:
        main_logger.error("Failed during logs saving. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        return None


def save_android_log(args, case, last_log_line, current_try, log_name_postfix="_client"):
    try:
        command_process = subprocess.Popen("adb logcat -d", shell=False, stdin=PIPE, stdout=PIPE)
        out, err = command_process.communicate()

        raw_logs = out.split(b"\r\n")

        log_lines = []

        for log_line in raw_logs:
            log_lines.append(log_line.decode("utf-8", "ignore").encode("utf-8", "ignore"))

        # index of first line of the current log in whole log file
        first_log_line_index = 0

        for i in range(len(log_lines)):
            if last_log_line is not None and last_log_line in log_lines[i]:
                first_log_line_index = i + 1
                break

        # update last log line
        for i in range(len(log_lines) - 1, -1, -1):
            if log_lines[i] and log_lines[i] != b"\r":
                last_log_line = log_lines[i]
                break

        if first_log_line_index != 0:
            log_lines = log_lines[first_log_line_index:]

        log_destination_path = os.path.join(args.output, "tool_logs", case["case"] + log_name_postfix + ".log")

        with open(log_destination_path, "ab") as file:
            # filter Android client logs
            filtered_log_line = []

            for line in log_lines:
                prepared_line = line.decode("utf-8").lower()

                if "amf_trace" in prepared_line or "remotegameclient" in prepared_line:
                    filtered_log_line.append(line)

            file.write("\n---------- Try #{} ----------\n\n".format(current_try).encode("utf-8"))
            file.write(b"\n".join(filtered_log_line))

        return last_log_line
    except Exception as e:
        main_logger.error("Failed during android logs saving. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        return None


def start_streaming(execution_type, script_path, do_delay=True):
    main_logger.info("Start StreamingSDK {}".format(execution_type))

    # start Streaming SDK process
    process = psutil.Popen(script_path, stdout=PIPE, stderr=PIPE, shell=True)

    main_logger.info("Start Streaming SDK")

    if do_delay:
        # Wait a bit to launch streaming SDK client/server
        sleep(3)

    main_logger.info("Screen resolution: width = {}, height = {}".format(win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)))

    return process


def collect_iperf_info(args, log_name_base):
    iperf_base_path = "C:\\iperf"
    current_dir = os.getcwd()

    try:
        logs_path = os.path.join(args.output, "tool_logs")

        # change current dir to dir with iperf
        os.chdir(iperf_base_path)

        if args.execution_type == "server":
            # run iperf scripts
            proc = psutil.Popen("ServerTrafficListener.bat", stdout=PIPE, stderr=PIPE, shell=True)
            proc.communicate(timeout=30)
        else:
            # run iperf scripts
            proc = psutil.Popen("UDPTrafficTest.bat -d {} -s 130 -r 100 > result.log 2>&1".format(args.ip_address), stdout=PIPE, stderr=PIPE, shell=True)
            proc.communicate(timeout=30)

            # save output files
            copyfile("result.log", os.path.join(logs_path, log_name_base + "_iperf.log"))

    except Exception as e:
        main_logger.error("Failed during iperf execution. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

    os.chdir(current_dir)


def close_game(game_name):
    edge_x = win32api.GetSystemMetrics(0)
    edge_y = win32api.GetSystemMetrics(1)
    center_x = edge_x / 2
    center_y = edge_y / 2

    if game_name == "lol":
        pydirectinput.keyDown("esc")
        sleep(0.1)
        pydirectinput.keyUp("esc")

        sleep(2)

        pyautogui.moveTo(center_x - 360, center_y + 335)
        sleep(0.2)
        pyautogui.mouseDown()
        sleep(0.2)
        pyautogui.mouseUp()
        sleep(0.2)
        pyautogui.mouseDown()
        sleep(0.2)
        pyautogui.mouseUp()

        sleep(1)

        pyautogui.moveTo(center_x - 130, center_y - 50)
        sleep(0.2)
        pyautogui.mouseDown()
        sleep(0.2)
        pyautogui.mouseUp()

        sleep(3)


def close_game_process(game_name):
    try:
        games_processes = {
            "heavendx9": ["browser_x86.exe", "Heaven.exe"],
            "heavendx11": ["browser_x86.exe", "Heaven.exe"],
            "valleydx9": ["browser_x86.exe", "Valley.exe"],
            "valleydx11": ["browser_x86.exe", "Valley.exe"],
            "borderlands3": ["Borderlands3.exe"],
            "apexlegends": ["r5apex.exe"],
            "valorant": ["VALORANT-Win64-Shipping.exe"],
            "lol": ["LeagueClient.exe", "League of Legends.exe"],
            "csgo": ["csgo.exe"],
            "dota2": ["dota2.exe"]
        }

        if game_name in games_processes:
            processes_names = games_processes[game_name]

            for process in psutil.process_iter():
                if process.name() in processes_names:
                    process.kill()
                    main_logger.info("Target game process found. Close it")

    except Exception as e:
        main_logger.error("Failed to close game process. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))


def make_window_minimized(window):
    try:
        win32gui.ShowWindow(window, 2)
    except Exception as e:
        main_logger.error("Failed to make window minized: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))


def execute_adb_command(command):
    command_process = subprocess.Popen(command, shell=False, stdin=PIPE, stdout=PIPE)
    out, err = command_process.communicate()
    main_logger.info("ADB command executed: {}".format(command))
    main_logger.info("ADB command out: {}".format(out))
    main_logger.error("ADB command err: {}".format(err))


def track_used_memory(case, execution_type):
    #command = "powershell.exe (Get-Counter -Counter '\Process(remotegameserver)\Working Set - Private').CounterSamples[0].CookedValue"
    #result = subprocess.check_output(command, shell=True, text=True)
    #print(int(result) / 1024 ** 2)
    process_name = "remotegameclient" if execution_type == "client" else "remotegameserver"

    if not(os.system("powershell.exe Get-Process -name " + process_name + " -ErrorAction SilentlyContinue > null")):
        command = "powershell.exe (Get-Counter -Counter '\Process(" + process_name + ")\Working Set - Private').CounterSamples[0].CookedValue"
        value = int(subprocess.check_output(command, shell=True, text=True)) / 1024 ** 2
        if "used_memory" in case and isinstance(case["used_memory"], list):
            case["used_memory"].append(value)
        else:
            case["used_memory"] = value
    else:
        main_logger.error("Target process not found")


def multiconnection_start_android(test_group):
    # start Android client for multiconnection group
    if test_group == "Multiconnection":
        execute_adb_command("adb logcat -c")
        execute_adb_command("adb shell am start -n com.amd.remotegameclient/.MainActivity")
