# Stops the application processes started by Start-Hub.ps1 (Django, Celery, course worker, Vite).
# MongoDB, Redis and Mailpit keep running in Docker so that data and emails stay available.
$patterns = 'manage.py runserver', 'celery.*-A config worker', 'process_course_jobs', 'vite'
$processes = Get-CimInstance Win32_Process | Where-Object { $cmd = $_.CommandLine; $cmd -and ($patterns | Where-Object { $cmd -match $_ }) }
$processes | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "$($processes.Count) processus arrêté(s). Infrastructure Docker conservée (docker stop nexora-mongo nexora-redis mailpit pour l’arrêter)."
