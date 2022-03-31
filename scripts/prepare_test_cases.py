import os
import argparse
from shutil import copyfile


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--os_name', required=True, type=str)

    args = parser.parse_args()

    target_json_name = "test_cases-{}.json".format(args.os_name.lower())
    renamed_json_name = "test_cases.json"

    target_package_name = "regression-{}.json".format(args.os_name.lower())
    renamed_package_name = "regression.json"

    for path, dirs, files in os.walk(os.path.join("..", "jobs")):
        for json_file in files:
            if json_file == target_json_name:
                copyfile(os.path.join(path, json_file), os.path.join(path, renamed_json_name))
            elif json_file == target_package_name:
                copyfile(os.path.join(path, json_file), os.path.join(path, renamed_package_name))
