import socket
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
import keyboard
from threading import Thread
from utils import *
from actions import *

csgoFirstExec = True
pyautogui.FAILSAFE = False

# execute some cmd command on server (e.g. open game/benchmark)
class ExecuteCMD(Action):
    def parse(self):
        self.processes = self.params["processes"]
        self.cmd_command = self.params["arguments_line"]

    @Action.server_action_decorator
    def execute(self):
        process = psutil.Popen(self.cmd_command, stdout=PIPE, stderr=PIPE, shell=True)
        self.processes[self.cmd_command] = process
        self.logger.info("Executed: {}".format(self.cmd_command))

        return True


# check what some window exists (it allows to check that some game/benchmark is opened)
class CheckWindow(Action):
    def parse(self):
        self.processes = self.params["processes"]
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.window_name = parsed_arguments[0]
        self.process_name = parsed_arguments[1]
        self.is_game = (self.params["command"] == "check_game")
        self.test_group = self.params["args"].test_group

    @Action.server_action_decorator
    def execute(self):
        result = False

        window = win32gui.FindWindow(None, self.window_name)

        if window is not None and window != 0:
            self.logger.info("Window {} was succesfully found".format(self.window_name))

            if self.is_game:
                make_window_foreground(window, self.logger)
        else:
            self.logger.error("Window {} wasn't found at all".format(self.window_name))
            return False

        for process in psutil.process_iter():
            if self.process_name in process.name():
                self.logger.info("Process {} was succesfully found".format(self.process_name))
                self.processes[self.process_name] = process
                result = True
                break
        else:
            self.logger.info("Process {} wasn't found at all".format(self.process_name))
            result = False

        return result


def close_processes(processes, logger):
    result = True

    for process_name in processes:
        try:
            close_process(processes[process_name])
        except Exception as e:
            logger.error("Failed to close process: {}".format(str(e)))
            logger.error("Traceback: {}".format(traceback.format_exc()))
            result = False

    return result


def make_window_foreground(window, logger):
    try:
        win32gui.ShowWindow(window, 1)
        win32gui.SetForegroundWindow(window)
    except Exception as e:
        logger.error("Failed to make window foreground (SW_SHOWNNORMAL): {}".format(str(e)))
        logger.error("Traceback: {}".format(traceback.format_exc()))
        logger.info("Try to make window foreground with SW_SHOWNOACTIVATE value")

        try:
            win32gui.ShowWindow(window, 4)
            win32gui.SetForegroundWindow(window)
        except Exception as e1:
            logger.error("Failed to make window foreground (SW_SHOWNOACTIVATE): {}".format(str(e1)))
            logger.error("Traceback: {}".format(traceback.format_exc()))
            logger.info("Try to make window foreground with SW_SHOW value")

            try:
                win32gui.ShowWindow(window, 5)
                win32gui.SetForegroundWindow(window)
            except Exception as e1:
                logger.error("Failed to make window foreground (SW_SHOW): {}".format(str(e2)))
                logger.error("Traceback: {}".format(traceback.format_exc()))


# press some sequence of keys on server
class PressKeysServer(Action):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.keys_string = parsed_arguments[0]

    @Action.server_action_decorator
    def execute(self):
        keys = self.keys_string.split()

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

            self.logger.info("Press: {}. Duration: {}".format(key, duration))

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

                    if i != times - 1:
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
                    sleep(1.5)
                else:
                    sleep(0.2)

        return True


# abort the current case execution (all opened processes of game/benchmark will be closed)
class Abort(Action):
    def parse(self):
        self.processes = self.params["processes"]

    @Action.server_action_decorator
    def execute(self):
        result = close_processes(self.processes, self.logger)

        if result:
            self.logger.info("Processes was succesfully closed")
        else:
            self.logger.error("Failed to close processes")

        return result

    
    def analyze_result(self):
        self.state.is_aborted = True
        raise ClientActionException("Client sent abort command")


# retry the current case execution (all opened processes of game/benchmark won't be closed)
class Retry(Action):
    @Action.server_action_decorator
    def execute(self):
        return True

    def analyze_result(self):
        self.state.is_aborted = True
        raise ClientActionException("Client sent abort command")


# start the next test case (it stops waiting of the next command)
class NextCase(Action):
    @Action.server_action_decorator
    def execute(self):
        if self.params["args"].track_used_memory:
            track_used_memory(self.params["case"], "server")

        return True

    def analyze_result(self):
        self.state.wait_next_command = False


class IPerf(Action):
    def parse(self):
        self.json_content = self.params["json_content"]

    def execute(self):
        execute_iperf = None

        for message in self.json_content["message"]:
            if "Network problem:" in message:
                execute_iperf = True
                break

        iperf_answer = "start" if execute_iperf else "skip"

        self.logger.info("IPerf answer: {}".format(iperf_answer))
        self.sock.send(iperf_answer.encode("utf-8"))

        if execute_iperf:
            collect_iperf_info(self.params["args"], self.params["case"]["case"])
            self.params["iperf_executed"] = True


# do click on server side
class ClickServer(Action):
    def parse(self):
        parsed_arguments = parse_arguments(self.params["arguments_line"])
        self.x_description = parsed_arguments[0]
        self.y_description = parsed_arguments[1]
        if len(parsed_arguments) > 2:
            self.delay = float(parsed_arguments[2])
        else:
            self.delay = 0.2

    @Action.server_action_decorator
    def execute(self):
        if "center_" in self.x_description:
            x = win32api.GetSystemMetrics(0) / 2 + int(self.x_description.replace("center_", ""))
        elif "edge_" in self.x_description:
            x = win32api.GetSystemMetrics(0) + int(self.x_description.replace("edge_", ""))
        else:
            x = int(self.x_description)

        if "center_" in self.y_description:
            y = win32api.GetSystemMetrics(1) / 2 + int(self.y_description.replace("center_", ""))
        elif "edge_" in self.y_description:
            y = win32api.GetSystemMetrics(1) + int(self.y_description.replace("edge_", ""))
        else:
            y = int(self.y_description)

        self.logger.info("Click at x = {}, y = {}".format(x, y))

        pyautogui.moveTo(x, y)
        sleep(self.delay)
        pyautogui.click()

        return True


# start doing test actions on server side
class DoTestActions(Action):
    def parse(self):
        self.game_name = self.params["game_name"]
        self.stage = 0

    def execute(self):
        try:
            if self.game_name == "borderlands3":
                pass
            elif self.game_name == "valorant":
                sleep(2.0)
                pydirectinput.keyDown("space")
                sleep(0.1)
                pydirectinput.keyUp("space")            
            elif self.game_name == "apexlegends":
                pydirectinput.keyDown("a")
                pydirectinput.keyDown("space")
                sleep(0.5)
                pydirectinput.keyUp("a")
                pydirectinput.keyUp("space")

                pydirectinput.keyDown("d")
                pydirectinput.keyDown("space")
                sleep(0.5)
                pydirectinput.keyUp("d")
                pydirectinput.keyUp("space")
                pyautogui.click(button="right")
            elif self.game_name == "lol":
                edge_x = win32api.GetSystemMetrics(0)
                edge_y = win32api.GetSystemMetrics(1)
                center_x = edge_x / 2
                center_y = edge_y / 2

                # avoit to long cycle of test actions (split it to parts)

                if self.stage == 0:
                    sleep(2)
                elif self.stage == 1:
                    sleep(2)
                elif self.stage == 2:
                    pyautogui.moveTo(center_x + 360, center_y - 360)
                    sleep(0.1)
                    pyautogui.click()
                    sleep(0.1)
                    pyautogui.moveTo(edge_x - 255, edge_y - 60)
                    sleep(0.1)
                    pyautogui.click(button="right")
                    sleep(1.5)
                elif self.stage == 3:
                    pyautogui.moveTo(edge_x - 290, edge_y - 20)
                    sleep(0.1)
                    pyautogui.click()
                    sleep(0.1)
                    pyautogui.moveTo(center_x, center_y)
                    sleep(0.1)
                    pyautogui.click(button="right")
                    sleep(1.5)

                self.stage += 1

                if self.stage > 3:
                    self.stage = 0
            elif self.game_name == "dota2":
                sleep(1)
                pydirectinput.press("r")
                sleep(1)
                pydirectinput.press("w")
                sleep(1)
            elif self.game_name == "csgo":
                global csgoFirstExec
                if csgoFirstExec:
                    csgoFirstExec = False
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
                        sleep(0.25)
                        pydirectinput.press("enter")

                pydirectinput.press("4")
                sleep(1.5)
                pyautogui.click()
            else:
                sleep(0.5)
                
        except Exception as e:
            self.logger.error("Failed to do test actions: {}".format(str(e)))
            self.logger.error("Traceback: {}".format(traceback.format_exc()))

    def analyze_result(self):
        self.state.executing_test_actions = True


# collect gpuview traces on server side
class GPUView(Action):
    def parse(self):
        self.collect_traces = self.params["args"].collect_traces
        self.archive_path = self.params["archive_path"]
        self.archive_name = self.params["case"]["case"]

    def execute(self):
        if self.collect_traces == "AfterTests":
            self.sock.send("start".encode("utf-8"))

            try:
                collect_traces(self.archive_path, self.archive_name + "_server.zip")
            except Exception as e:
                self.logger.warning("Failed to collect GPUView traces: {}".format(str(e)))
                self.logger.warning("Traceback: {}".format(traceback.format_exc()))
        else:
            self.sock.send("skip".encode("utf-8"))


# record metrics on server side
class RecordMetrics(Action):
    def parse(self):
        self.test_group = self.params["args"].test_group

    @Action.server_action_decorator
    def execute(self):
        try:
            if self.test_group == "MulticonnectionWW" or self.test_group == "MulticonnectionWWA":
                self.sock.send("record_metrics".encode("utf-8"))
        except Exception as e:
            self.logger.error("Failed to send action to second windows client: {}".format(str(e)))
            self.logger.error("Traceback: {}".format(traceback.format_exc()))

        if "used_memory" not in self.params["case"]:
            self.params["case"]["used_memory"] = []

        if self.params["args"].track_used_memory:
            track_used_memory(self.params["case"], "server")

        return True


class MakeScreen(MulticonnectionAction):
    def parse(self):
        self.action = self.params["action_line"]
        self.test_group = self.params["args"].test_group

    def execute(self):
        try:
            self.second_sock.send(self.action.encode("utf-8"))

            if self.test_group == "MulticonnectionWW":
                self.logger.info("Wait second client answer")
                response = self.second_sock.recv(1024).decode("utf-8")
                self.logger.info("Second client answer: {}".format(response))
                self.sock.send(response.encode("utf-8"))
        except Exception as e:
            self.logger.error("Failed to communicate with second windows client: {}".format(str(e)))
            self.logger.error("Traceback: {}".format(traceback.format_exc()))


class SleepAndScreen(MulticonnectionAction):
    def parse(self):
        self.action = self.params["action_line"]
        self.test_group = self.params["args"].test_group

    def execute(self):
        try:
            self.second_sock.send(self.action.encode("utf-8"))

            if self.test_group == "MulticonnectionWW":
                self.logger.info("Wait second client answer")
                response = self.second_sock.recv(1024).decode("utf-8")
                self.logger.info("Second client answer: {}".format(response))
                self.sock.send(response.encode("utf-8"))
        except Exception as e:
            self.logger.error("Failed to send action to second windows client: {}".format(str(e)))
            self.logger.error("Traceback: {}".format(traceback.format_exc()))


class RecordVideo(MulticonnectionAction):
    def parse(self):
        self.action = self.params["action_line"]
        self.test_group = self.params["args"].test_group

    def execute(self):
        try:
            self.second_sock.send(self.action.encode("utf-8"))

            if self.test_group == "MulticonnectionWW":
                self.logger.info("Wait second client answer")
                response = self.second_sock.recv(1024).decode("utf-8")
                self.logger.info("Second client answer: {}".format(response))
                self.sock.send(response.encode("utf-8"))
        except Exception as e:
            self.logger.error("Failed to send action to second windows client: {}".format(str(e)))
            self.logger.error("Traceback: {}".format(traceback.format_exc()))
