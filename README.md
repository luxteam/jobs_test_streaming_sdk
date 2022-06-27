# Autotests for Streaming SDK

## Parameters
 1. Parameters of `run_windows.bat` script below:

    * `FILE_FILTER` - package name.
    * `TESTS_FILTER` - names of test groups.
    * `EXECUTION_TYPE` - client / server.
    * `IP_ADDRESS` - ip address of server machine.
    * `COMMUNICATION_PORT` - port for autotests on server machine.
    * `RETRIES` - unused parameter, retries isn't supported for now.
    * `SERVER_GPU_NAME` - name of GPU on server machine.
    * `SERVER_OS_NAME` - name of OS on server machine.
    * `GAME_NAME` - Name of game / benchmark
    * `COLLECT_TRACES` - specify collecting of GPUView traces. Values: False, AfterTests, BeforeTests.
    * `SCREEN_RESOLUTION` - resolution of screen on client side.

 2. Parameters of `run_andoird.bat` script below:

    * `FILE_FILTER` - package name.
    * `TESTS_FILTER` - names of test groups.
    * `RETRIES` - unused parameter, retries isn't supported for now.
    * `GAME_NAME` - Name of game / benchmark

 3. Parameters of `run_mc.bat` script below:

    * `FILE_FILTER` - package name.
    * `TESTS_FILTER` - names of test groups.
    * `IP_ADDRESS` - ip address of server machine.
    * `COMMUNICATION_PORT` - port for autotests on server machine.
    * `SERVER_GPU_NAME` - name of GPU on server machine.
    * `SERVER_OS_NAME` - name of OS on server machine.
    * `SCREEN_RESOLUTION` - resolution of screen on client side.

## Examples
 1. Windows client + Windows server:
    * Run on machine with Windows client:
    > run_windows.bat "regression.0.json~" "" "client" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2Vulkan" False 1920x1080
    * Run on machine with Windows server:
    > run_windows.bat "regression.0.json~" "" "server" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2Vulkan" False 1920x1080
 2. Android client + Windows server:
    * Run on machine with Windows server: 
    > run_android.bat "none" "GeneralQoS Audio Codecs CaptureType ConversionType" 2 "Dota2DX11
 3. 2x Windows clients + Windows server:
    * Run on machine with Windows first client:
    > run_windows.bat "none" "MulticonnectionWW" "client" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2DX11" False 1920x1080
    * Run on machine with Windows second client: 
    > run_mc.bat "none" "MulticonnectionWW" "172.31.0.72" "90" "AMD Radeon RX 5700 XT" "Windows 10(64bit)" 1920x1200
    * Run on machine with Windows server: 
    > run_windows.bat "none" "MulticonnectionWW" "server" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2DX11" False 1920x1080
 4. Windows client + Andoid client + Windows server:
    * Run on machine with Windows client:
    > run_windows.bat "none" "MulticonnectionWA" "client" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2DX11" False 1920x1080
    * Run on machine with Windows server:
    > run_windows.bat "none" "MulticonnectionWA" "server" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2DX11" False 1920x1080
 5. 2x Windows clients + Andoid client + Windows server:
    * Run on machine with Windows first client:
    > run_windows.bat "none" "MulticonnectionWWA" "client" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2DX11" False 1920x1080
    * Run on machine with Windows second client:
    > run_mc.bat "none" "MulticonnectionWWA" "172.31.0.72" "90" "AMD Radeon RX 5700 XT" "Windows 10(64bit)" 1920x1200
    * Run on machine with Windows server:
    > run_windows.bat "none" "MulticonnectionWWA" "server" "172.31.0.72" "90" 2 "AMD Radeon RX 5700 XT" "Windows 10(64bit)" "Dota2DX11" False 1920x1080