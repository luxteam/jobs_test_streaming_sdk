from time import sleep
import psutil
import os
from glob import glob
import zipfile
import subprocess
from subprocess import PIPE, STDOUT
import shlex
import win32api
import sys
import traceback
from shutil import copyfile
from datetime import datetime
import pydirectinput, pyautogui
import win32gui
import win32con
import pyshark
import json

ROOT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_PATH)
from jobs_launcher.core.config import main_logger


def get_mc_config():
    with open(os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)), "multiconnection.json"), "r") as config:
        return json.load(config)


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
            sleep(0.5)
            ch.kill()
            sleep(0.5)
            status = ch.status()
        except psutil.NoSuchProcess:
            pass

    try:
        process.terminate()
        sleep(0.5)
        process.kill()
        sleep(0.5)
        status = process.status()
    except psutil.NoSuchProcess:
        pass


def collect_traces(archive_path, archive_name):
    gpuview_path = os.getenv("GPUVIEW_PATH")
    executable_name = "log_extended.cmd"
    target_name = "Merged.etl"

    try:
        for filename in glob(os.path.join(gpuview_path, "*.etl")):
            os.remove(filename)
    except Exception:
        pass

    script = "powershell \"Start-Process cmd '/k cd \"{}\" && .\\log_extended.cmd & exit 0' -Verb RunAs\"".format(gpuview_path)

    proc = psutil.Popen(script, stdout=PIPE, stderr=PIPE, shell=True)

    target_path = os.path.join(gpuview_path, target_name)

    start_time = datetime.now()

    while (datetime.now() - start_time).total_seconds() <= 30:
        if os.path.exists(target_path):
            sleep(5)
            break
    else:
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
            main_logger.info("Start closing")

            if process is not None:
                close_process(process)

            main_logger.info("Finish closing")

            # additional try to kill Streaming SDK server/client (to be sure that all processes are closed)
            subprocess.call("taskkill /f /im RemoteGameClient.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            subprocess.call("taskkill /f /im RemoteGameServer.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)

            if execution_type == "server":
                crash_window = win32gui.FindWindow(None, "RemoteGameServer.exe")
            else:
                crash_window = win32gui.FindWindow(None, "RemoteGameClient.exe")

            if crash_window:
                main_logger.info("Crash window was found. Closing it...")
                win32gui.PostMessage(crash_window, win32con.WM_CLOSE, 0, 0)

            process = None

        if process:
            main_logger.info("StreamingSDK instance was killed")
        else:
            main_logger.info("Keep StreamingSDK instance")

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
            main_logger.info("Android client was killed")

            return True

        else:
            main_logger.info("Keep Android client instance")
            return False
    except Exception as e:
        main_logger.error("Failed to close Streaming SDK Android app. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))


def save_logs(args, case, last_log_line, current_try, is_multiconnection=False):
    try:
        if not is_multiconnection:
            if hasattr(args, "execution_type"):
                execution_type = args.execution_type
            else:
                execution_type = "server"

            tool_path = args.server_tool if execution_type == "server" else args.client_tool
        else:
            execution_type = "second_client"
            tool_path = args.tool

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

        main_logger.info("Finish logs saving for {}".format(execution_type))

        return last_log_line
    except Exception as e:
        main_logger.error("Failed during logs saving. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        return None


def save_android_log(args, case, current_try, log_name_postfix="_client"):
    try:
        out, err = execute_adb_command("adb logcat -d", return_output=True)

        raw_logs = out.split(b"\r\n")

        log_lines = []

        for log_line in raw_logs:
            log_lines.append(log_line.decode("utf-8", "ignore").encode("utf-8", "ignore"))

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

        execute_adb_command("adb logcat -c")

        main_logger.info("Finish logs saving for Android client")
    except Exception as e:
        main_logger.error("Failed during android logs saving. Exception: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        return None


def start_streaming(execution_type, script_path):
    main_logger.info("Start StreamingSDK {}".format(execution_type))

    # start Streaming SDK process
    process = psutil.Popen(script_path, stdout=PIPE, stderr=PIPE, shell=True)

    main_logger.info("Start Streaming SDK")

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
            "heavenopengl": ["browser_x86.exe", "Heaven.exe"],
            "valleydx9": ["browser_x86.exe", "Valley.exe"],
            "valleydx11": ["browser_x86.exe", "Valley.exe"],
            "valleyopengl": ["browser_x86.exe", "Valley.exe"],
            "borderlands3": ["Borderlands3.exe"],
            "apexlegends": ["r5apex.exe"],
            "valorant": ["VALORANT-Win64-Shipping.exe"],
            "lol": ["LeagueClient.exe", "League of Legends.exe"],
            "csgo": ["csgo.exe"],
            "dota2dx11": ["dota2.exe"],
            "dota2vulkan": ["dota2.exe"],
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


def execute_adb_command(command, return_output=False):
    max_tries = 3
    current_try = 0

    while current_try < max_tries:
        current_try += 1

        try:
            command_process = subprocess.Popen(command, shell=False, stdin=PIPE, stdout=PIPE)
            out, err = command_process.communicate(timeout=30)
            main_logger.info("ADB command executed (try #{}): {}".format(command, current_try))
            if return_output:
                return out, err
            else:
                main_logger.info("ADB command out (try #{}): {}".format(out, current_try))
                main_logger.info("ADB command err (try #{}): {}".format(err, current_try))
                break
        except (psutil.TimeoutExpired, subprocess.TimeoutExpired) as err:
            main_logger.error("Failed to execute ADB command due to timeout (try #{}): {}".format(command, current_try))


def track_used_memory(case, execution_type):
    process_name = "RemoteGameClient.exe" if execution_type == "client" else "RemoteGameServer.exe"

    for process in psutil.process_iter():
        if process.name() == process_name:
            value = psutil.Process(process.pid).memory_full_info().uss / 1024 ** 2

            if "used_memory" in case and isinstance(case["used_memory"], list):
                case["used_memory"].append(value)
            else:
                case["used_memory"] = value
            break
    else:
        main_logger.error("Target process not found")


def multiconnection_start_android(test_group):
    # start Android client for multiconnection group
    if test_group in get_mc_config()["android_client"]:
        execute_adb_command("adb logcat -c")
        execute_adb_command("adb shell am start -a com.amd.wirelessvr.CONNECT -n com.amd.remotegameclient/.MainActivity")


# address is address of the opposite side
def analyze_encryption(case, execution_type, transport_protocol, is_encrypted, messages, address=None):
    if "expected_connection_problems" in case and execution_type in case["expected_connection_problems"]:
        main_logger.info("Ignore encryption analyzing due to expected problems")
        return

    encryption_is_valid = validate_encryption(execution_type, transport_protocol, "src", is_encrypted, address)

    if not encryption_is_valid:
        messages.add("Found invalid encryption. Packet: server -> client (found on {} side)".format(execution_type))

    encryption_is_valid = validate_encryption(execution_type, transport_protocol, "dst", is_encrypted, address)

    if not encryption_is_valid:
        messages.add("Found invalid encryption. Packet: client -> server (found on {} side)".format(execution_type))


def decode_payload(payload):
    result = ""
    for byte in payload.split(":"):
        result += chr(int(byte, 16))
    return result.encode("cp1251", "ignore").decode("utf8", "ignore")


# address is address of the opposite side
def validate_encryption(execution_type, transport_protocol, direction, is_encrypted, address):
    # number of packets which should be analyzed (some packets doesn't contain payload, they'll be skipped)
    packets_to_analyze = 5

    main_logger.info("Check first {} packets".format(packets_to_analyze))

    if execution_type == "client":
        capture_filter = "{direction} host {address} and {transport_protocol} {direction} port 1235".format(direction=direction, address=address, transport_protocol=transport_protocol)
    else:
        if direction == "src":
            capture_filter = "src host {address} and {transport_protocol} dst port 1235".format(address=address, transport_protocol=transport_protocol)
        else:
            capture_filter = "dst host {address} and {transport_protocol} src port 1235".format(address=address, transport_protocol=transport_protocol)

    main_logger.info("Capture filter: {}".format(capture_filter))

    packets = pyshark.LiveCapture("eth", bpf_filter=capture_filter)
    packets.sniff(timeout=2)

    main_logger.info(packets)

    non_encrypted_packet_found = False

    if packets_to_analyze <= 10:
        main_logger.warning("Not enough packets for analyze")
        return False

    if packets_to_analyze > len(packets):
        packets_to_analyze = len(packets)

    analyzed_packets = 0

    for packet in packets[:packets_to_analyze]:
        try:
            if transport_protocol == "udp":
                payload = packet.udp.payload
            else:
                payload = packet.tcp.payload
        except AttributeError:
            main_logger.warning("Could not get payload")
            continue
        except Exception as e:
            main_logger.error("Failed to get packet payload. Exception: {}".format(str(e)))
            main_logger.error("Traceback: {}".format(traceback.format_exc()))
            continue

        decoded_payload = decode_payload(payload)
        main_logger.info("Decoded payload: {}".format(decoded_payload))
        analyzed_packets += 1

        if "\"id\":" in decoded_payload or "\"DeviceID\":" in decoded_payload:
            non_encrypted_packet_found = True
            break

        if analyzed_packets >= packets_to_analyze:
            break

    packets.close()

    if is_encrypted == (not non_encrypted_packet_found):
        main_logger.info("Encryption is valid")
        return True
    else:
        main_logger.warning("Encryption isn't valid")
        return False


def contains_encryption_errors(error_messages):
    for message in error_messages:
        if message.startswith("Found invalid encryption"):
            return True
            break
    else:
        return False


def start_clumsy(keys, client_ip=None, server_ip=None, android_ip=None, second_client_ip=None):
    script = "powershell \"Start-Process cmd '/k clumsy.exe {} & exit 0' -Verb RunAs\"".format(keys.replace("\"", "\\\""))

    ips = {"client_ip": client_ip, "server_ip": server_ip, "android_ip": android_ip, "second_client_ip": second_client_ip}

    for ip_key, ip_value in ips.items():
        if ip_value is not None:
            script = script.replace("<{}>".format(ip_key), ip_value)

    psutil.Popen(script, stdout=PIPE, stderr=PIPE, shell=True)


def close_clumsy():
    script = "powershell \"Start-Process cmd '/k taskkill /im clumsy.exe & exit 0' -Verb RunAs\""
    psutil.Popen(script, stdout=PIPE, stderr=PIPE, shell=True)
