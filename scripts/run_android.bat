set PATH=c:\python39\;c:\python39\scripts\;%PATH%
set FILE_FILTER=%1
set TESTS_FILTER="%2"
set GAME_NAME=%3
set CIS_OS=Android
if not defined RETRIES set RETRIES=1

python prepare_xmls.py --os_name "Android"
python prepare_test_cases.py --os_name "Android"

python -m pip install -r ../jobs_launcher/install/requirements.txt

python ..\jobs_launcher\executeTests.py --test_filter %TESTS_FILTER% --file_filter %FILE_FILTER% --tests_root ..\jobs --work_root ..\Work\Results --work_dir StreamingSDK --cmd_variables clientTool "..\StreamingSDKAndroid\app-arm.apk" serverTool "..\StreamingSDK\RemoteGameServer.exe" retries %RETRIES% gameName %GAME_NAME%
