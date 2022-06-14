set PATH=c:\python39\;c:\python39\scripts\;%PATH%
set FILE_FILTER=%1
set TESTS_FILTER="%2"
set IP_ADDRESS="%3"
set COMMUNICATION_PORT="%4"
set SERVER_GPU_NAME=%5
set SERVER_OS_NAME=%6
for /f %%i in ('C:\Python39\python.exe get_screen_resolution.py') do set SCREEN_RESOLUTION=%%i

python prepare_xmls.py --os_name "MC"
python prepare_test_cases.py --os_name "Windows"

python -m pip install -r ../jobs_launcher/install/requirements.txt

python ..\jobs_launcher\executeTests.py --test_filter %TESTS_FILTER% --file_filter %FILE_FILTER% --tests_root ..\jobs --work_root ..\Work\Results --work_dir StreamingSDK --cmd_variables clientTool "..\StreamingSDK\RemoteGameClient.exe" ipAddress %IP_ADDRESS% communicationPort %COMMUNICATION_PORT% serverGPUName %SERVER_GPU_NAME% serverOSName %SERVER_OS_NAME% screenResolution %SCREEN_RESOLUTION%
