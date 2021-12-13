import argparse
import os
import json
import sys
from glob import glob

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir)))
from jobs_launcher.core.config import SESSION_REPORT, TEST_REPORT_NAME_COMPARED, SCREENS_COLLECTION_KEY, VIDEO_KEY


KEYS_TO_COPY = [
    "min_server_latency", "max_server_latency", "median_server_latency",
    "server_trace_archive",
    "firstinstance_server", "secondinstance_server",
    "iperf_server",
    "used_memory_server",
    "android_log", "second_client_log",
    "used_memory_second_client",
    "second_client_configuration"
]


def get_test_status(test_status_one, test_status_two):
    test_statuses = (test_status_one, test_status_two)
    statuses = ("skipped", "error", "failed", "passed")

    for status in statuses:
        if status in test_statuses:
            return status


def format_script_info(script_info):
    client_keys = None
    server_keys = None
    second_client_keys = None
    other_info = []

    for line in script_info:
        if line.startswith("Client keys:"):
            client_keys = line
        elif line.startswith("Server keys:"):
            server_keys = line
        elif line.startswith("Second Client keys:"):
            second_client_keys = line
        elif line:
            other_info.append(line)

    result = []

    if client_keys:
        result.append(server_keys)
        result.append("")
        result.append(client_keys)
    else:
        result.append(server_keys)

    if second_client_keys:
        result.append("")
        result.extend(second_client_keys)

    result.append("")
    result.extend(other_info)

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--target_dir', required=True, metavar="<path>")
    parser.add_argument('--source_dir', required=True, metavar="<path>")
    parser.add_argument('--second_client_dir', required=True, metavar="<path>")

    args = parser.parse_args()

    for path, dirs, files in os.walk(os.path.abspath(args.target_dir)):
        for file in files:
            if file.endswith(TEST_REPORT_NAME_COMPARED):
                target_file_path = os.path.join(path, file) 

                source_file_path = os.path.join(args.source_dir, os.path.relpath(target_file_path, args.target_dir))

                if os.path.exists(source_file_path):
                    with open(target_file_path, "r") as f:
                        target_file_content = json.load(f)

                    with open(source_file_path, "r") as f:
                        source_file_content = json.load(f)

                    for i in range(len(target_file_content)):
                        for key in KEYS_TO_COPY:
                            if key in source_file_content[i]:
                                target_file_content[i][key] = source_file_content[i][key]

                        target_file_content[i]["test_status"] = get_test_status(target_file_content[i]["test_status"], source_file_content[i]["test_status"])

                        if "message" in source_file_content[i]:
                            target_file_content[i]["message"] += source_file_content[i]["message"]

                        target_file_content[i]["script_info"].extend(source_file_content[i]["script_info"])

                        target_file_content[i]["script_info"] = format_script_info(target_file_content[i]["script_info"])

                        if VIDEO_KEY in source_file_content[i]:
                            target_file_content[i]["android_" + VIDEO_KEY] = source_file_content[i][VIDEO_KEY]

                        if SCREENS_COLLECTION_KEY in source_file_content[i]:
                            target_file_content[i]["android_" + SCREENS_COLLECTION_KEY] = source_file_content[i][SCREENS_COLLECTION_KEY]

                    with open(target_file_path, "w", encoding="utf8") as f:
                        json.dump(target_file_content, f, indent=4, sort_keys=True)

                # get data from second client
                second_client_file_path = os.path.join(args.second_client_dir, os.path.relpath(target_file_path, args.target_dir))

                if os.path.exists(second_client_file_path):
                    with open(target_file_path, "r") as f:
                        target_file_content = json.load(f)

                    with open(second_client_file_path, "r") as f:
                        second_client_file_content = json.load(f)

                    for i in range(len(target_file_content)):
                        for key in KEYS_TO_COPY:
                            if key in second_client_file_content[i]:
                                target_file_content[i][key] = second_client_file_content[i][key]

                        target_file_content[i]["test_status"] = get_test_status(target_file_content[i]["test_status"], second_client_file_content[i]["test_status"])

                        if "message" in second_client_file_content[i]:
                            target_file_content[i]["message"] += second_client_file_content[i]["message"]

                        target_file_content[i]["script_info"].extend(second_client_file_content[i]["script_info"])

                        target_file_content[i]["script_info"] = format_script_info(target_file_content[i]["script_info"])

                        if VIDEO_KEY in second_client_file_content[i]:
                            target_file_content[i]["second_client_" + VIDEO_KEY] = second_client_file_content[i][VIDEO_KEY]

                        if SCREENS_COLLECTION_KEY in second_client_file_content[i]:
                            target_file_content[i]["second_client_" + SCREENS_COLLECTION_KEY] = second_client_file_content[i][SCREENS_COLLECTION_KEY]

                    with open(target_file_path, "w", encoding="utf8") as f:
                        json.dump(target_file_content, f, indent=4, sort_keys=True)

            elif file.endswith(SESSION_REPORT):
                target_file_path = os.path.join(path, file) 

                source_file_path = os.path.join(args.source_dir, os.path.relpath(target_file_path, args.target_dir))

                if os.path.exists(source_file_path):
                    with open(target_file_path, "r") as f:
                        target_file_content = json.load(f)

                    with open(source_file_path, "r") as f:
                        source_file_content = json.load(f)

                    if "machine_info" in source_file_content:
                    	target_file_content["machine_info"] = source_file_content["machine_info"]

                    for test_group in target_file_content["results"]:
                        target_group_data = target_file_content["results"][test_group][""]
                        source_group_data = source_file_content["results"][test_group][""]

                        for i in range(len(target_group_data["render_results"])):
                            for key in KEYS_TO_COPY:
                                if key in source_group_data["render_results"][i]:
                                    target_group_data["render_results"][i][key] = source_group_data["render_results"][i][key]

                            new_test_status = get_test_status(target_group_data["render_results"][i]["test_status"], source_group_data["render_results"][i]["test_status"])
                            old_test_status = target_group_data["render_results"][i]["test_status"]

                            target_group_data[new_test_status] += 1
                            target_group_data[old_test_status] -= 1

                            target_file_content["summary"][new_test_status] += 1
                            target_file_content["summary"][old_test_status] -= 1

                            target_group_data["render_results"][i]["test_status"] = new_test_status

                            if "message" in source_group_data["render_results"][i]:
                                target_group_data["render_results"][i]["message"] += source_group_data["render_results"][i]["message"]

                            target_group_data["render_results"][i]["script_info"].extend(source_group_data["render_results"][i]["script_info"])

                            target_group_data["render_results"][i]["script_info"] = format_script_info(target_group_data["render_results"][i]["script_info"])

                            if VIDEO_KEY in source_group_data["render_results"][i]:
                                target_group_data["render_results"][i]["android_" + VIDEO_KEY] = source_group_data["render_results"][i][VIDEO_KEY]

                            if SCREENS_COLLECTION_KEY in source_group_data["render_results"][i]:
                                target_group_data["render_results"][i]["android_" + SCREENS_COLLECTION_KEY] = source_group_data["render_results"][i][SCREENS_COLLECTION_KEY] 

                    with open(target_file_path, "w", encoding="utf8") as f:
                        json.dump(target_file_content, f, indent=4, sort_keys=True)

                # get data from second client
                second_client_file_path = os.path.join(args.second_client_dir, os.path.relpath(target_file_path, args.target_dir))

                if os.path.exists(second_client_file_path):
                    with open(target_file_path, "r") as f:
                        target_file_content = json.load(f)

                    with open(second_client_file_path, "r") as f:
                        second_client_file_content = json.load(f)

                    for test_group in target_file_content["results"]:
                        target_group_data = target_file_content["results"][test_group][""]
                        second_client_group_data = second_client_file_content["results"][test_group][""]

                        for i in range(len(target_group_data["render_results"])):
                            for key in KEYS_TO_COPY:
                                if key in second_client_group_data["render_results"][i]:
                                    target_group_data["render_results"][i][key] = second_client_group_data["render_results"][i][key]

                            new_test_status = get_test_status(target_group_data["render_results"][i]["test_status"], second_client_group_data["render_results"][i]["test_status"])
                            old_test_status = target_group_data["render_results"][i]["test_status"]

                            target_group_data[new_test_status] += 1
                            target_group_data[old_test_status] -= 1

                            target_file_content["summary"][new_test_status] += 1
                            target_file_content["summary"][old_test_status] -= 1

                            target_group_data["render_results"][i]["test_status"] = new_test_status

                            if "message" in second_client_group_data["render_results"][i]:
                                target_group_data["render_results"][i]["message"] += second_client_group_data["render_results"][i]["message"]

                            target_group_data["render_results"][i]["script_info"].extend(second_client_group_data["render_results"][i]["script_info"])

                            target_group_data["render_results"][i]["script_info"] = format_script_info(target_group_data["render_results"][i]["script_info"])

                            if VIDEO_KEY in second_client_group_data["render_results"][i]:
                                target_group_data["render_results"][i]["second_client_" + VIDEO_KEY] = second_client_group_data["render_results"][i][VIDEO_KEY]

                            if SCREENS_COLLECTION_KEY in second_client_group_data["render_results"][i]:
                                target_group_data["render_results"][i]["second_client_" + SCREENS_COLLECTION_KEY] = second_client_group_data["render_results"][i][SCREENS_COLLECTION_KEY] 

                    with open(target_file_path, "w", encoding="utf8") as f:
                        json.dump(target_file_content, f, indent=4, sort_keys=True)
