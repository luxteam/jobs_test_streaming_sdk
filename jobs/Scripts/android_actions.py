import sys
import os
from time import sleep, strftime, gmtime
import psutil
import subprocess
from subprocess import PIPE
import traceback
import win32gui
import win32api
import pyautogui
import pydirectinput
from pyffmpeg import FFmpeg
from threading import Thread
from utils import parse_arguments, execute_adb_command, get_mc_config
from actions import *
import base64
import keyboard
from pyffmpeg import FFmpeg

pyautogui.FAILSAFE = False
MC_CONFIG = get_mc_config()


# open some game if it doesn't launched (e.g. open game/benchmark)
class OpenGame(Action):
    def parse(self):
        games_launchers = {
            "heavendx9": "C:\\JN\\Heaven Benchmark 4.0.lnk",
            "heavendx11": "C:\\JN\\Heaven Benchmark 4.0.lnk",
            "heavenopengl": "C:\\JN\\Heaven Benchmark 4.0.lnk",
            "valleydx9": "C:\\JN\\Valley Benchmark 1.0.lnk",
            "valleydx11": "C:\\JN\\Valley Benchmark 1.0.lnk",
            "valleyopengl": "C:\\JN\\Valley Benchmark 1.0.lnk",
            "borderlands3": "C:\\JN\\Borderlands3.exe - Shortcut.lnk",
            "apexlegends": "C:\\JN\\ApexLegends.exe - Shortcut.url",
            "valorant": "C:\\JN\\VALORANT.exe - Shortcut.lnk",
            "lol": "C:\\JN\\League of Legends.lnk",
            "dota2dx11": "C:\\JN\\dota2.exe.lnk",
            "dota2vulkan": "C:\\JN\\dota2.exe.lnk",
            "csgo": "C:\\JN\\csgo.exe.url",
            "nothing": None
        }

        games_windows = {
            "heavendx9": ["Unigine Heaven Benchmark 4.0 Basic (Direct3D9)", "Heaven.exe"],
            "heavendx11": ["Unigine Heaven Benchmark 4.0 Basic (Direct3D11)", "Heaven.exe"],
            "heavenopengl": ["Unigine Heaven Benchmark 4.0 Basic (OpenGL)", "Heaven.exe"],
            "valleydx9": ["Unigine Valley Benchmark 1.0 Basic (Direct3D9)", "Valley.exe"],
            "valleydx11": ["Unigine Valley Benchmark 1.0 Basic (Direct3D11)", "Valley.exe"],
            "valleyopengl": ["Unigine Valley Benchmark 1.0 Basic (OpenGL)", "Valley.exe"],
            "borderlands3": ["Borderlands® 3  ", "Borderlands3.exe"],
            "apexlegends": ["Apex Legends", "r5apex.exe"],
            "valorant": ["VALORANT  ", "VALORANT-Win64-Shipping.exe"],
            "lol": ["League of Legends (TM) Client", "League of Legends.exe"],
            "dota2dx11": ["Dota 2", "dota2.exe"],
            "dota2vulkan": ["Dota 2", "dota2.exe"],
            "csgo": ["Counter-Strike: Global Offensive - Direct3D 9", "csgo.exe"],
            "nothing": [None, None]
        }

        self.game_name = self.params["game_name"]
        self.game_launcher = games_launchers[self.game_name]
        self.game_window = games_windows[self.game_name][0]
        self.game_process_name = games_windows[self.game_name][1]

    def execute(self):
        if self.game_launcher is None or self.game_window is None or self.game_process_name is None:
            return

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
            if self.game_name == "lol":
                sleep(240)

            psutil.Popen(self.game_launcher, stdout=PIPE, stderr=PIPE, shell=True)
            self.logger.info("Executed: {}".format(self.game_launcher))

            if self.game_name == "heavendx9" or self.game_name == "heavendx11" or self.game_name == "heavenopengl":
                sleep(6)
                click("center_290", "center_-85", self.logger)
                if self.game_name == "heavendx11":
                    click("center_290", "center_-70", self.logger)
                elif self.game_name == "heavendx9":
                    click("center_290", "center_-55", self.logger)
                else:
                    click("center_290", "center_-40", self.logger)
                click("center_280", "center_135", self.logger)
                sleep(30)
            if self.game_name == "valleydx9" or self.game_name == "valleydx11" or self.game_name == "valleyopengl":
                sleep(6)
                click("center_290", "center_-70", self.logger)
                if self.game_name == "valleydx11":
                    click("center_290", "center_-55", self.logger)
                elif self.game_name == "valleydx9":
                    click("center_290", "center_-40", self.logger)
                else:
                    click("center_290", "center_-25", self.logger)
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
            elif self.game_name == "valorant":
                sleep(60)
                click("380", "edge_-225", self.logger)
                sleep(1)
                click("360", "210", self.logger)
                sleep(60)

                # do opening of lobby twice to avoid ads
                click("center_0", "25", self.logger)
                sleep(1)
                click("center_0", "85", self.logger)
                sleep(3)

                press_keys("esc", self.logger)

                click("center_0", "25", self.logger)
                sleep(1)
                click("center_0", "85", self.logger)
                sleep(3)

                click("center_-300", "edge_-95", self.logger)
                sleep(1)
                click("center_-300", "edge_-155", self.logger)
                sleep(3)

                click("center_0", "center_225", self.logger)
                sleep(30)

                click("center_-260", "center_-55", self.logger)
                sleep(2)
                click("center_0", "center_110", self.logger)
                sleep
            elif self.game_name == "lol":
                sleep(90)
                click("center_-520", "center_-340", self.logger)
                sleep(1)
                click("center_-390", "center_-280", self.logger)
                sleep(1)
                click("center_-15", "center_-160", self.logger)
                sleep(1)
                click("center_-110", "center_310", self.logger)
                sleep(1)
                click("center_-110", "center_310", self.logger)
                sleep(1)
                click("center_150", "center_-210", self.logger)
                sleep(1)
                click("center_0", "center_230", self.logger)
                sleep(60)
                click("center_0", "center_0", self.logger)
                press_keys("shift+x ctrl+shift+i shift+y:17 ctrl+e ctrl+r", self.logger)
            elif self.game_name == "dota2dx11" or self.game_name == "dota2vulkan":
                sleep(30)
                click("center_0", "center_0", self.logger)
                press_keys("esc", self.logger)
                sleep(10)

                click("90", "30", self.logger)
                sleep(1)
                click("center_-270", "center_-485", self.logger)
                sleep(1)
                click("center_-725", "center_255", self.logger)
                sleep(1)
                if self.game_name == "dota2dx11":
                    click("center_-725", "center_300", self.logger)
                else:
                    click("center_-725", "center_345", self.logger)
                sleep(1)
                press_keys("esc", self.logger)
                sleep(3)
                click("edge_-35", "35", self.logger)
                sleep(1)
                click("center_-115", "center_45", self.logger)
                sleep(1)
                psutil.Popen(self.game_launcher, stdout=PIPE, stderr=PIPE, shell=True)
                self.logger.info("Executed: {}".format(self.game_launcher))
                sleep(30)
                press_keys("esc", self.logger)
                sleep(10)

                click("center_-510", "center_-570", self.logger)
                sleep(1)
                click("center_-342", "center_-230", self.logger)
                sleep(1)
                click("center_380", "center_-292", self.logger)
                sleep(15)
                click("center_-335", "center_427", self.logger)
                click("center_-335", "center_427", self.logger)
                sleep(1)
                click("center_-923", "center_-370", self.logger)
                sleep(1)
                click("center_-912", "center_-328", self.logger)
                sleep(1)
                click("center_-797", "center_-250", self.logger)
            elif self.game_name == "csgo":
                sleep(30)
                press_keys("esc", self.logger)
                sleep(5)
                click("center_-919", "center_-437", self.logger)
                sleep(1)
                click("center_-662", "center_-463", self.logger)
                sleep(1)
                click("center_-662", "center_-249", self.logger)
                sleep(1)
                click("center_-4", "center_-118", self.logger)
                sleep(1)
                click("center_672", "center_551", self.logger)
                sleep(1)
                click("center_155", "center_117", self.logger)
                sleep(40)
                press_keys("w_3", self.logger)

                # enter commands to csgo console
                commands = [
                    "`",
                    "sv_cheats 1",
                    "give weapon_deagle",
                    "give weapon_molotov",
                    "sv_infinite_ammo 1",
                    "`"
                ]
                for command in commands:
                    if command != "`":
                        keyboard.write(command)
                    else:
                        pydirectinput.press("`")
                    sleep(0.5)
                    pydirectinput.press("enter")

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
class MakeScreen(MulticonnectionAction):
    def parse(self):
        self.screen_path = self.params["screen_path"]
        self.screen_name = self.params["arguments_line"]
        self.current_image_num = self.params["current_image_num"]
        self.current_try = self.params["current_try"]
        self.client_type = self.params["client_type"]
        self.test_group = self.params["args"].test_group

    def execute(self):
        if not self.screen_name:
            make_screen(self.screen_path, self.current_try, self.logger)
        else:
            make_screen(self.screen_path, self.current_try, self.logger, self.screen_name + self.client_type, self.current_image_num)
            self.params["current_image_num"] += 1

            if self.test_group in MC_CONFIG["android_client"]:
                if self.test_group in MC_CONFIG["second_win_client"]:
                    self.logger.info("Wait second client answer")
                    response = self.second_sock.recv(1024).decode("utf-8")
                    self.logger.info("Second client answer: {}".format(response))
                    self.sock.send(response.encode("utf-8"))
                else:
                    self.sock.send("done".encode("utf-8"))


def make_screen(screen_path, current_try, logger, screen_name = "", current_image_num = 0):
    try:
        screen_path = os.path.join(screen_path, "{:03}_{}_try_{:02}.png".format(current_image_num, screen_name, current_try + 1))
        out, err = execute_adb_command("adb exec-out screencap -p", return_output=True)

        with open(screen_path, "wb") as file:
            file.write(out)

        logger.error("Screencap command err: {}".format(err))
    except Exception as e:
        logger.error("Failed to make screenshot: {}".format(str(e)))
        logger.error("Traceback: {}".format(traceback.format_exc()))


# Make sequence of screens with delay. It supports initial delay before the first test case
class SleepAndScreen(MulticonnectionAction):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.initial_delay = parsed_arguments[0]
        self.number_of_screens = parsed_arguments[1]
        self.delay = parsed_arguments[2]
        self.screen_path = self.params["screen_path"]
        self.screen_name = parsed_arguments[3]
        self.current_image_num = self.params["current_image_num"]
        self.current_try = self.params["current_try"]
        self.client_type = self.params["client_type"]
        self.test_group = self.params["args"].test_group

    def execute(self):
        sleep(float(self.initial_delay))

        screen_number = 1

        while True:
            make_screen(self.screen_path, self.current_try, self.logger, self.screen_name + self.client_type, self.current_image_num)
            self.params["current_image_num"] += 1
            self.current_image_num = self.params["current_image_num"]
            screen_number += 1

            if screen_number > int(self.number_of_screens):
                break
            else:
                sleep(float(self.delay))

        if self.test_group in MC_CONFIG["android_client"]:
            if self.test_group in MC_CONFIG["second_win_client"]:
                self.logger.info("Wait second client answer")
                response = self.second_sock.recv(1024).decode("utf-8")
                self.logger.info("Second client answer: {}".format(response))
                self.sock.send(response.encode("utf-8"))
            else:
                self.sock.send("done".encode("utf-8"))


def compress_video(temp_video_path, target_video_path, logger):
    recorder = FFmpeg()
    logger.info("Start video compressing")

    recorder.options("-i {} -pix_fmt yuv420p {}".format(temp_video_path, target_video_path))

    os.remove(temp_video_path)

    logger.info("Finish to compress video")


# Record video
class RecordVideo(MulticonnectionAction):
    def parse(self):
        self.video_path = self.params["output_path"]
        self.target_video_name = self.params["case"]["case"] + self.params["client_type"] + ".mp4"
        self.temp_video_name = self.params["case"]["case"] + self.params["client_type"] + "_temp.mp4"
        self.duration = int(self.params["arguments_line"])
        self.test_group = self.params["args"].test_group

    def execute(self):
        try:
            self.logger.info("Start to record video")
            execute_adb_command("adb shell screenrecord --time-limit={} /sdcard/video.mp4".format(self.duration))
            self.logger.info("Finish to record video")

            temp_video_path = os.path.join(self.video_path, self.temp_video_name)

            execute_adb_command("adb pull /sdcard/video.mp4 {}".format(temp_video_path))

            target_video_path = os.path.join(self.video_path, self.target_video_name)

            compressing_thread = Thread(target=compress_video, args=(temp_video_path, target_video_path, self.logger))
            compressing_thread.start()
        except Exception as e:
            self.logger.error("Failed to make screenshot: {}".format(str(e)))
            self.logger.error("Traceback: {}".format(traceback.format_exc()))

        if self.test_group in MC_CONFIG["android_client"]:
            if self.test_group in MC_CONFIG["second_win_client"]:
                self.logger.info("Wait second client answer")
                response = self.second_sock.recv(1024).decode("utf-8")
                self.logger.info("Second client answer: {}".format(response))
                self.sock.send(response.encode("utf-8"))
            else:
                self.sock.send("done".encode("utf-8"))


class RecordMicrophone(Action):
    def parse(self):
        self.duration = int(self.params["arguments_line"])
        self.action = self.params["action_line"]
        self.test_group = self.params["args"].test_group
        self.audio_path = self.params["output_path"]
        self.audio_name = self.params["case"]["case"] + "android"

    def execute(self):
        try:
            audio_full_path = os.path.join(self.audio_path, self.audio_name + ".mp4")
            time_flag_value = strftime("%H:%M:%S", gmtime(int(self.duration)))

            recorder = FFmpeg()
            self.logger.info("Start to record video")

            recorder.options("-f dshow -i audio=\"Microphone (AMD Streaming Audio Device)\" -t {time} {audio}"
                .format(time=time_flag_value, audio=audio_full_path))
        except Exception as e:
            self.logger.error("Error due microphone recording")
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
            for i in range(30):
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
                pydirectinput.keyDown("space")
                sleep(0.1)
                pydirectinput.keyUp("space")

                pydirectinput.press("x")
                sleep(1)
                pyautogui.click()
                sleep(3)
        elif game_name == "dota2dx11" or game_name == "dota2vulkan":
            for i in range(6):
                pydirectinput.press("r")
                sleep(3)
                pydirectinput.press("w")
                sleep(3)
        elif game_name == "csgo":
            for i in range(20):
                pydirectinput.press("4")
                sleep(1.5)
                pyautogui.click()
            
        elif game_name == "lol":
            edge_x = win32api.GetSystemMetrics(0)
            edge_y = win32api.GetSystemMetrics(1)
            center_x = edge_x / 2
            center_y = edge_y / 2

            for i in range(5):
                pydirectinput.press("e")
                sleep(0.1)
                pydirectinput.press("e")
                sleep(0.1)

                pydirectinput.press("r")
                sleep(0.1)
                pydirectinput.press("r")
                sleep(3)

                pyautogui.moveTo(center_x + 360, center_y - 360)
                sleep(0.1)
                pyautogui.click()
                sleep(0.1)
                pyautogui.moveTo(edge_x - 255, edge_y - 60)
                sleep(0.1)
                pyautogui.click(button="right")
                sleep(1.5)
                pyautogui.moveTo(edge_x - 290, edge_y - 20)
                sleep(0.1)
                pyautogui.click()
                sleep(0.1)
                pyautogui.moveTo(center_x, center_y)
                sleep(0.1)
                pyautogui.click(button="right")
                sleep(1.5)

    except Exception as e:
        logger.error("Failed to do test actions: {}".format(str(e)))
        logger.error("Traceback: {}".format(traceback.format_exc()))
