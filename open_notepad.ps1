param (
    [string]$filePath,
    [int]$lineNumber
)

# Открыть файл в блокноте
Start-Process notepad.exe $filePath

# Дождаться открытия файла
Start-Sleep -Seconds 1

# Скопировать строки до нужной линии
$content = Get-Content -Path $filePath -TotalCount $lineNumber

# Подсчитать количество символов до нужной линии
$totalChars = ($content | ForEach-Object { $_.Length + 2 }).Sum()  # +2 для CRLF

# Открыть файл в блокноте и перейти к нужной линии
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("^g") # Нажать Ctrl+G
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("$lineNumber{ENTER}") # Ввести номер линии и нажать Enter
