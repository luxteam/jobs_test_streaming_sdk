import sys
import os
from time import sleep
import psutil
from subprocess import PIPE
import traceback
import win32gui
import win32api
import pyautogui
import pydirectinput
from threading import Thread
from utils import parse_arguments
from actions import *
import base64

pyautogui.FAILSAFE = False


# open some game if it doesn't launched (e.g. open game/benchmark)
class OpenGame(Action):
    def parse(self):
        games_launchers = {
            "heavendx9": "C:\\JN\\Heaven Benchmark 4.0.lnk",
            "heavendx11": "C:\\JN\\Heaven Benchmark 4.0.lnk",
            "valleydx9": "C:\\JN\\Valley Benchmark 1.0.lnk",
            "valleydx11": "C:\\JN\\Valley Benchmark 1.0.lnk",
            "borderlands3": "C:\\JN\\Borderlands3.exe - Shortcut.lnk",
            "apexlegends": "C:\\JN\\ApexLegends.exe - Shortcut.url"
        }

        games_windows = {
            "heavendx9": ["Unigine Heaven Benchmark 4.0 Basic (Direct3D9)", "Heaven.exe"],
            "heavendx11": ["Unigine Heaven Benchmark 4.0 Basic (Direct3D11)", "Heaven.exe"],
            "valleydx9": ["Unigine Valley Benchmark 1.0 Basic (Direct3D9)", "Valley.exe"],
            "valleydx11": ["Unigine Valley Benchmark 1.0 Basic (Direct3D11)", "Valley.exe"],
            "borderlands3": ["Borderlands® 3  ", "Borderlands3.exe"],
            "apexlegends": ["Apex Legends", "r5apex.exe"]
        }

        self.game_name = self.params["game_name"]
        self.game_launcher = games_launchers[self.game_name]
        self.game_window = games_windows[self.game_name][0]
        self.game_process_name = games_windows[self.game_name][1]

    def execute(self):
        game_launched = True

        window = win32gui.FindWindow(None, self.game_window)

        if window is not None and window != 0:
            self.logger.info("Window {} was succesfully found".format(self.game_window))

            make_window_foreground(window, self.logger)
        else:
            self.logger.error("Window {} wasn't found at all".format(self.game_window))
            game_launched = False

        for process in psutil.process_iter():
            if self.game_process_name in process.name():
                self.logger.info("Process {} was succesfully found".format(self.game_process_name))
                break
        else:
            self.logger.info("Process {} wasn't found at all".format(self.game_process_name))
            game_launched = False

        if not game_launched:
            psutil.Popen(self.game_launcher, stdout=PIPE, stderr=PIPE, shell=True)
            self.logger.info("Executed: {}".format(self.game_launcher))

            if self.game_name == "heavendx9" or self.game_name == "heavendx11":
                sleep(6)
                click("center_290", "center_-85", self.logger)
                if self.game_name == "heavendx9":
                    click("center_290", "center_-55", self.logger)
                else:
                    click("center_290", "center_-70", self.logger)
                click("center_280", "center_135", self.logger)
                sleep(30)
            if self.game_name == "valleydx9" or self.game_name == "valleydx11":
                sleep(6)
                click("center_290", "center_-70", self.logger)
                if self.game_name == "valleydx9":
                    click("center_290", "center_-40", self.logger)
                else:
                    click("center_290", "center_-55", self.logger)
                click("center_280", "center_135", self.logger)
                sleep(30)
            elif self.game_name == "borderlands3":
                sleep(150)
            elif self.game_name == "apexlegends":
                sleep(60)
                click("center_0", "center_0", self.logger)
                sleep(20)

                # do opening of lobby twice to avoid ads
                click("230", "920", self.logger)
                sleep(3)
                click("415", "130", self.logger)
                sleep(3)
                click("230", "1070", self.logger, delay=3)

                press_keys("esc", self.logger)
                sleep(1)

                click("230", "920", self.logger)
                sleep(3)
                click("415", "130", self.logger)
                sleep(3)
                click("230", "1070", self.logger, delay=3)

                sleep(90)
                click("center_0", "center_0", self.logger)
                press_keys("w+shift_15", self.logger)
                press_keys("esc", self.logger)
                sleep(1)
                click("center_0", "center_155", self.logger)
                sleep(2)
                click("center_680", "center_-190", self.logger)
                sleep(2)

            window = win32gui.FindWindow(None, self.game_window)

            if window is not None and window != 0:
                self.logger.info("Window {} was succesfully found".format(self.game_window))

                make_window_foreground(window, self.logger)
            else:
                raise Exception("Window {} wasn't found at all".format(self.game_window))


def make_window_foreground(window, logger):
    try:
        win32gui.ShowWindow(window, 4)
        win32gui.SetForegroundWindow(window)
    except Exception as e:
        logger.error("Failed to make window foreground: {}".format(str(e)))
        logger.error("Traceback: {}".format(traceback.format_exc()))


# Do click 
class Click(Action):
    def execute(self):
        pyautogui.click()
        sleep(0.2)


# Execute sleep 
class DoSleep(Action):
    def parse(self):
        self.seconds = self.params["arguments_line"]

    def execute(self):
        sleep(int(self.seconds))


# Press some sequence of keys on server
class PressKeys(Action):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.keys_string = parsed_arguments[0]

    def execute(self):
        press_keys(self.keys_string, self.logger)


def press_keys(keys_string, logger):
    keys = keys_string.split()

    # press keys one by one
    # possible formats
    # * space - press space
    # * space_10 - press space down for 10 seconds
    # * space+shift - press space and shift
    # * space+shift:10 - press space and shift 10 times
    for i in range(len(keys)):
        key = keys[i]

        duration = 0

        if "_" in key:
            parts = key.split("_")
            key = parts[0]
            duration = int(parts[1])

        logger.info("Press: {}. Duration: {}".format(key, duration))

        if duration == 0:
            times = 1

            if ":" in key:
                parts = key.split(":")
                key = parts[0]
                times = int(parts[1])

            keys_to_press = key.split("+")

            for i in range(times):
                for key_to_press in keys_to_press:
                    pydirectinput.keyDown(key_to_press)

                sleep(0.1)

                for key_to_press in keys_to_press:
                    pydirectinput.keyUp(key_to_press)

                sleep(0.5)
        else:
            keys_to_press = key.split("+")

            for key_to_press in keys_to_press:
                pydirectinput.keyDown(key_to_press)

            sleep(duration)

            for key_to_press in keys_to_press:
                pydirectinput.keyUp(key_to_press)

        # if it isn't the last key - make a delay
        if i != len(keys) - 1:
            if "enter" in key:
                sleep(2)
            else:
                sleep(1)


# Do screenshot
class MakeScreen(Action):
    def parse(self):
        self.driver = self.params["driver"]
        self.screen_path = self.params["screen_path"]
        self.screen_name = self.params["arguments_line"]
        self.current_image_num = self.params["current_image_num"]
        self.current_try = self.params["current_try"]

    def execute(self):
        if not self.screen_name:
            make_screen(self.driver, self.screen_path, self.current_try, self.logger)
        else:
            make_screen(self.driver, self.screen_path, self.current_try, self.logger, self.screen_name, self.current_image_num)
            self.params["current_image_num"] += 1


def make_screen(driver, screen_path, current_try, logger, screen_name = "", current_image_num = 0):
    try:
        screen_base64 = driver.get_screenshot_as_base64()

        screen_path = os.path.join(screen_path, "{:03}_{}_try_{:02}.jpg".format(current_image_num, screen_name, current_try + 1))

        with open(screen_path, "wb") as screen:
            screen.write(base64.b64decode(screen_base64))
    except Exception as e:
        logger.error("Failed to make screenshot: {}".format(str(e)))
        logger.error("Traceback: {}".format(traceback.format_exc()))


# Make sequence of screens with delay. It supports initial delay before the first test case
class SleepAndScreen(Action):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.initial_delay = parsed_arguments[0]
        self.number_of_screens = parsed_arguments[1]
        self.delay = parsed_arguments[2]
        self.screen_path = self.params["screen_path"]
        self.screen_name = parsed_arguments[3]
        self.current_image_num = self.params["current_image_num"]
        self.current_try = self.params["current_try"]
        self.driver = self.params["driver"]

    def execute(self):
        sleep(float(self.initial_delay))

        screen_number = 1

        while True:
            make_screen(self.driver, self.screen_path, self.current_try, self.logger, self.screen_name, self.current_image_num)
            self.params["current_image_num"] += 1
            self.current_image_num = self.params["current_image_num"]
            screen_number += 1

            if screen_number > int(self.number_of_screens):
                break
            else:
                sleep(float(self.delay))


# Record video
class RecordVideo(Action):
    def parse(self):
        self.video_path = self.params["output_path"]
        self.video_name = self.params["case"]["case"] + ".mp4"
        self.driver = self.params["driver"]
        self.duration = int(self.params["arguments_line"])

    def execute(self):
        try:
            self.logger.info("Start to record video")

            self.driver.start_recording_screen(timeLimit = float(self.duration))
            sleep(float(self.duration))
            video_base64 = self.driver.stop_recording_screen()

            self.logger.info("Finish to record video")
            
            with open(os.path.join(self.video_path, self.video_name), "wb") as video:
                video.write(base64.b64decode(video_base64))
        except Exception as e:
            self.logger.error("Failed to make screenshot: {}".format(str(e)))
            self.logger.error("Traceback: {}".format(traceback.format_exc()))


def click(x_description, y_description, logger, delay = 0.2):
    if "center_" in x_description:
        x = win32api.GetSystemMetrics(0) / 2 + int(x_description.replace("center_", ""))
    elif "edge_" in x_description:
        x = win32api.GetSystemMetrics(0) + int(x_description.replace("edge_", ""))
    else:
        x = int(x_description)

    if "center_" in y_description:
        y = win32api.GetSystemMetrics(1) / 2 + int(y_description.replace("center_", ""))
    elif "edge_" in y_description:
        y = win32api.GetSystemMetrics(1) + int(y_description.replace("edge_", ""))
    else:
        y = int(y_description)

    logger.info("Click at x = {}, y = {}".format(x, y))

    pyautogui.moveTo(x, y)
    sleep(delay)
    pyautogui.click()


class StartActions(Action):
    def parse(self):
        self.game_name = self.params["game_name"]

    def execute(self):
        gpu_view_thread = Thread(target=do_test_actions, args=(self.game_name.lower(), self.logger,))
        gpu_view_thread.daemon = True
        gpu_view_thread.start()


def do_test_actions(game_name, logger):
    try:
        if game_name == "apexlegends":
            for i in range(40):
                pydirectinput.press("q")
                pydirectinput.keyDown("a")
                pydirectinput.keyDown("space")
                sleep(0.5)
                pydirectinput.keyUp("a")
                pydirectinput.keyUp("space")

                pydirectinput.press("q")
                pydirectinput.keyDown("d")
                pydirectinput.keyDown("space")
                sleep(0.5)
                pydirectinput.keyUp("d")
                pydirectinput.keyUp("space")
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
