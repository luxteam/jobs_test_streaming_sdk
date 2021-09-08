import os
import argparse
from shutil import copyfile


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--os_name', required=True, type=str)

    args = parser.parse_args()

    target_xml_name = "test_cases-{}.json".format(args.os_name.lower())
    renamed_xml_name = "test_cases.json"

    for path, dirs, files in os.walk(os.path.join("..", "jobs", "Tests")):
        for xml_file in files:
        	if xml_file == target_xml_name:
        		copyfile(os.path.join(path, xml_file), os.path.join(path, renamed_xml_name))
