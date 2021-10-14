import os
from time import sleep, strftime, gmtime
import traceback
import pyautogui
import pyscreenshot
import json
import pydirectinput
from pyffmpeg import FFmpeg
from threading import Thread
from utils import collect_traces, parse_arguments, collect_iperf_info, track_used_memory
import win32api
from actions import *

pyautogui.FAILSAFE = False


# [Server action] send request to execute some cmd command on server
# [Result] wait answer from server. Answer must be 'done'
class ExecuteCMD(Action):
    def parse(self):
        self.action = self.params["action_line"]

    def execute(self):
        self.sock.send(self.action.encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = True, abort_if_fail = True)


# [Server action] send request to check what some window exists
# [Result] wait answer from server. Answer can be any
class CheckWindow(Action):
    def parse(self):
        self.action = self.params["action_line"]

    def execute(self):
        self.sock.send(self.action.encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = True, abort_if_fail = False)


# [Server action] send request to press some sequence of keys on server
# [Result] wait answer from server. Answer must be 'done'
class PressKeysServer(Action):
    def parse(self):
        self.action = self.params["action_line"]

    def execute(self):
        self.sock.send(self.action.encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = True, abort_if_fail = True)


# [Server action] send request to abort the current case execution
# [Result] wait answer from server. Answer can be any
class Abort(Action):
    def execute(self):
        self.sock.send("abort".encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = False, abort_if_fail = False)


# [Server action] send request to retry the current case execution
# [Result] wait answer from server. Answer can be any
class Retry(Action):
    def execute(self):
        self.sock.send("retry".encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = False, abort_if_fail = False)


# [Server action] send request to start the next test case
# [Result] wait answer from server. Answer can be any
class NextCase(Action):
    def execute(self):
        self.sock.send("next_case".encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = False, abort_if_fail = False)


class IPerf(Action):
    def execute(self):
        self.sock.send("iperf".encode("utf-8"))

        response = self.sock.recv(1024).decode("utf-8")

        self.logger.info("Server iperf answer: {}".format(response))

        # start iperf execution
        if response == "start":
            collect_iperf_info(self.params["args"], self.params["case"]["case"])
            self.params["iperf_executed"] = True
        else:
            # finish execution
            pass


# [Server action] send request to do click on server side
# [Result] wait answer from server. Answer must be 'done'
class ClickServer(Action):
    def parse(self):
        self.action = self.params["action_line"]

    def execute(self):
        self.sock.send(self.action.encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = True, abort_if_fail = True)


# [Server action] send request to start doing test actions on server side
# [Result] wait answer from server. Answer must be 'done'
class StartTestActionsServer(Action):
    def parse(self):
        self.action = self.params["action_line"]

    def execute(self):
        self.sock.send(self.action.encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = True, abort_if_fail = True)


# [Client action] do screenshot
class MakeScreen(Action):
    def parse(self):
        self.screen_path = self.params["screen_path"]
        self.screen_name = self.params["arguments_line"]
        self.current_image_num = self.params["current_image_num"]
        self.current_try = self.params["current_try"]

    def execute(self):
        if not self.screen_name:
            make_screen(self.screen_path, self.current_try)
        else:
            make_screen(self.screen_path, self.current_try, self.screen_name, self.current_image_num)
            self.params["current_image_num"] += 1


def make_screen(screen_path, current_try, screen_name = "", current_image_num = 0):
    screen = pyscreenshot.grab()

    if screen_name:
        screen = screen.convert("RGB")
        screen.save(os.path.join(screen_path, "{:03}_{}_try_{:02}.jpg".format(current_image_num, screen_name, current_try + 1)))


# [Client action] record video
class RecordVideo(Action):
    def parse(self):
        self.audio_device_name = self.params["audio_device_name"]
        self.video_path = self.params["output_path"]
        self.video_name = self.params["case"]["case"]
        self.resolution = self.params["args"].screen_resolution
        self.duration = int(self.params["arguments_line"])

    def execute(self):
        video_full_path = os.path.join(self.video_path, self.video_name + ".mp4")
        time_flag_value = strftime("%H:%M:%S", gmtime(int(self.duration)))

        recorder = FFmpeg()
        self.logger.info("Start to record video")

        recorder.options("-f gdigrab -video_size {resolution} -i desktop -f dshow -i audio=\"{audio_device_name}\" -t {time} -q:v 3 -pix_fmt yuv420p {video}"
            .format(resolution=self.resolution, audio_device_name=self.audio_device_name, time=time_flag_value, video=video_full_path))

        self.logger.info("Finish to record video")


# [Client action] move mouse to the specified position
class Move(Action):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.x = parsed_arguments[0]
        self.y = parsed_arguments[1]

    def execute(self):
        self.logger.info("Move to x = {}, y = {}".format(self.x, self.y))
        pyautogui.moveTo(int(self.x), int(self.y))
        sleep(0.2)


# [Client action] do click on client side
class Click(Action):
    def execute(self):
        pyautogui.click()
        sleep(0.2)


# [Client action] execute sleep on client side
class DoSleep(Action):
    def parse(self):
        self.seconds = self.params["arguments_line"]

    def execute(self):
        sleep(int(self.seconds))


# [Client action] press some sequence of keys on client
class PressKeys(Action):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.keys_string = parsed_arguments[0]

    def execute(self):
        keys = self.keys_string.split()

        for i in range(len(keys)):
            key = keys[i]

            self.logger.info("Press: {}".format(key))
            pyautogui.press(key)

            # if it isn't the last key - make a delay
            if i != len(keys) - 1:
                # pressing of enter can require more long delay (e.g. opening of new tab/window)
                if "enter" in key:
                    sleep(2)
                else:
                    sleep(1)


# [Client action] make sequence of screens with delay. It supports initial delay before the first test case
# Starts collecting of the traces if it's required
class SleepAndScreen(Action):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.initial_delay = parsed_arguments[0]
        self.number_of_screens = parsed_arguments[1]
        self.delay = parsed_arguments[2]
        self.collect_traces = self.params["args"].collect_traces
        self.screen_path = self.params["screen_path"]
        self.screen_name = parsed_arguments[3]
        self.archive_path = self.params["archive_path"]
        self.archive_name = self.params["case"]["case"]
        self.collect_traces = self.params["args"].collect_traces
        self.current_image_num = self.params["current_image_num"]
        self.current_try = self.params["current_try"]

    def execute(self):
        sleep(float(self.initial_delay))

        screen_number = 1

        while True:
            make_screen(self.screen_path, self.current_try, self.screen_name, self.current_image_num)
            self.params["current_image_num"] += 1
            self.current_image_num = self.params["current_image_num"]
            screen_number += 1

            if screen_number > int(self.number_of_screens):
                break
            else:
                sleep(float(self.delay))
                
        try:
            self.sock.send("gpuview".encode("utf-8"))
            response = self.sock.recv(1024).decode("utf-8")
            self.logger.info("Server response for 'gpuview' action: {}".format(response))

            if self.collect_traces == "AfterTests":
                collect_traces(self.archive_path, self.archive_name + "_client.zip")
        except Exception as e:
            self.logger.warning("Failed to collect GPUView traces: {}".format(str(e)))
            self.logger.warning("Traceback: {}".format(traceback.format_exc()))


# [Client + Server action] record metrics on client and server sides
# [Result] wait answer from server. Answer must be 'done'
class RecordMetrics(Action):
    def parse(self):
        self.action = self.params["action_line"]

    def execute(self):
        if "used_memory_client" not in self.params["case"]:
            self.params["case"]["used_memory_client"] = []

        if self.params["args"].track_used_memory:
            track_used_memory(self.params["case"], "client")

        self.sock.send(self.action.encode("utf-8"))

    def analyze_result(self):
        self.wait_server_answer(analyze_answer = True, abort_if_fail = True)


def do_test_actions(game_name, logger):
    try:
        if game_name == "apexlegends":
            for i in range(40):
                pydirectinput.press("q")
                sleep(1)
        elif game_name == "valorant":
            for i in range(10):
                pydirectinput.press("x")
                sleep(1)
                pyautogui.click()
                sleep(3)
        elif game_name == "lol":
            center_x = win32api.GetSystemMetrics(0) / 2
            center_y = win32api.GetSystemMetrics(1) / 2

            for i in range(5):
                pydirectinput.press("e")
                sleep(0.1)
                pydirectinput.press("e")
                sleep(0.1)

                pydirectinput.press("r")
                sleep(0.1)
                pydirectinput.press("r")
                sleep(3)

                # get time to do server actions
                sleep(4)

    except Exception as e:
        logger.error("Failed to do test actions: {}".format(str(e)))
        logger.error("Traceback: {}".format(traceback.format_exc()))


# [Client action] start doing test actions on client side
class StartTestActionsClient(Action):
    def parse(self):
        self.game_name = self.params["game_name"]

    def execute(self):
        gpu_view_thread = Thread(target=do_test_actions, args=(self.game_name.lower(), self.logger,))
        gpu_view_thread.daemon = True
        gpu_view_thread.start()


# [Client action] skip N next cases if the previous action was successfully done (e.g. skip actions to open game / benchmark if it's already opened)
class SkipIfDone(Action):
    def parse(self):
        self.commands_to_skip = self.params["arguments_line"]

    def execute(self):
        if self.state.prev_action_done:
            self.state.commands_to_skip += int(self.commands_to_skip)
