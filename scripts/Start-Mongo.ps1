$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
$mongoData = Join-Path $projectRoot '.local\mongo'
$mongoLog = Join-Path $projectRoot '.local\mongo.log'
New-Item -ItemType Directory -Force -Path $mongoData | Out-Null
if (-not (Get-NetTCPConnection -LocalPort 27019 -State Listen -ErrorAction SilentlyContinue)) {
    $mongodExe = (Get-Command mongod -ErrorAction Stop).Source
    $mongoArguments = '--dbpath "{0}" --port 27019 --bind_ip 127.0.0.1 --replSet nexora --logpath "{1}"' -f $mongoData, $mongoLog
    Start-Process -FilePath $mongodExe -ArgumentList $mongoArguments -WindowStyle Hidden
}
& $pythonExe (Join-Path $PSScriptRoot 'init_mongo.py')
if ($LASTEXITCODE -ne 0) { throw 'Initialisation MongoDB interrompue.' }
