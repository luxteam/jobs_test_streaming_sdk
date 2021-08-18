import json
from analyzeLogs import analyze_logs
import os
import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work_dir', required=True)
    parser.add_argument('--execution_type', required=True)
    parser.add_argument('--parse_logs', required=False, default="False")
    args = parser.parse_args()
    work_dir = args.work_dir

    json_files = list(
        filter(
            lambda x: x.endswith('RPR.json'), os.listdir(work_dir)
        )
    )

    reports = []

    for file in json_files:
        json_content = json.load(open(os.path.join(work_dir, file), 'r'))[0]

        if json_content.get('group_timeout_exceeded', False):
            json_content['message'].append('Test group timeout exceeded')

        if args.parse_logs == "True":
            analyze_logs(work_dir, json_content, args.execution_type)

        reports.append(json_content)
    with open(os.path.join(work_dir, 'report_compare.json'), 'w') as f: json.dump(reports, f, indent=4)
