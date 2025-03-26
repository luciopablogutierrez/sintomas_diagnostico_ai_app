# Script para configurar curl en PowerShell de Windows

# Verificar si curl.exe está disponible
$curlExe = Get-Command curl.exe -ErrorAction SilentlyContinue

# Verificar si el alias curl existe
$curlAlias = Get-Alias curl -ErrorAction SilentlyContinue

# Mostrar información sobre la configuración actual
Write-Host "\nConfiguración actual de curl en PowerShell:\n" -ForegroundColor Green

if ($curlExe) {
    Write-Host "✅ curl.exe está disponible en: $($curlExe.Source)" -ForegroundColor Green
} else {
    Write-Host "❌ curl.exe no está disponible en el sistema" -ForegroundColor Red
}

if ($curlAlias) {
    Write-Host "✅ El alias 'curl' está configurado y apunta a: $($curlAlias.Definition)" -ForegroundColor Green
} else {
    Write-Host "❌ No existe un alias 'curl' configurado" -ForegroundColor Red
}

# Configurar el alias curl para usar curl.exe en lugar de Invoke-WebRequest
if ($curlExe) {
    # Eliminar el alias existente si existe
    if ($curlAlias) {
        Remove-Item Alias:curl -Force
        Write-Host "\nSe ha eliminado el alias 'curl' anterior" -ForegroundColor Yellow
    }
    
    # Crear un nuevo alias que apunte a curl.exe
    Set-Alias -Name curl -Value curl.exe -Scope Global
    Write-Host "\n✅ Se ha configurado el alias 'curl' para usar curl.exe" -ForegroundColor Green
    
    # Crear una función para facilitar el uso de curl
    function Invoke-Curl {
        param(
            [Parameter(ValueFromRemainingArguments=$true)]
            $Arguments
        )
        
        & curl.exe @Arguments
    }
    
    # Crear un alias adicional para la función
    Set-Alias -Name curlw -Value Invoke-Curl -Scope Global
    Write-Host "✅ Se ha creado el alias 'curlw' como alternativa" -ForegroundColor Green
    
    # Sugerir agregar al perfil de PowerShell para hacerlo permanente
    Write-Host "\nPara hacer esta configuración permanente, agregue las siguientes líneas a su perfil de PowerShell:" -ForegroundColor Cyan
    Write-Host "Set-Alias -Name curl -Value curl.exe -Scope Global" -ForegroundColor White
    Write-Host "function Invoke-Curl { param([Parameter(ValueFromRemainingArguments=`$true)] `$Arguments) & curl.exe @Arguments }" -ForegroundColor White
    Write-Host "Set-Alias -Name curlw -Value Invoke-Curl -Scope Global" -ForegroundColor White
    
    # Ruta del perfil de PowerShell
    $profilePath = $PROFILE
    Write-Host "\nRuta de su perfil de PowerShell: $profilePath" -ForegroundColor Cyan
    
    # Verificar si el perfil existe
    if (Test-Path $profilePath) {
        Write-Host "El archivo de perfil existe. Puede editarlo manualmente." -ForegroundColor Green
    } else {
        Write-Host "El archivo de perfil no existe. Puede crearlo con: New-Item -Path $profilePath -Type File -Force" -ForegroundColor Yellow
    }
} else {
    Write-Host "\n❌ No se puede configurar el alias porque curl.exe no está disponible" -ForegroundColor Red
    Write-Host "Puede instalar curl desde: https://curl.se/windows/" -ForegroundColor Yellow
}

# Probar la configuración
Write-Host "\nProbando la configuración de curl:\n" -ForegroundColor Green

if ($curlExe) {
    Write-Host "Versión de curl:" -ForegroundColor Cyan
    curl.exe --version | Select-Object -First 1
    
    # Probar una petición a un endpoint
    Write-Host "\nProbando una petición HTTP:" -ForegroundColor Cyan
    Write-Host "curl.exe -s -o nul -w 'Código de estado: %{http_code}' https://www.google.com" -ForegroundColor White
    
    try {
        $result = curl.exe -s -o nul -w "Código de estado: %{http_code}" https://www.google.com
        Write-Host $result -ForegroundColor Green
        
        # Probar el endpoint /health si el servidor está en ejecución
        Write-Host "\nProbando el endpoint /health del backend:" -ForegroundColor Cyan
        Write-Host "curl.exe -s -o nul -w 'Código de estado: %{http_code}' http://localhost:8000/health" -ForegroundColor White
        
        try {
            $healthResult = curl.exe -s -o nul -w "Código de estado: %{http_code}" http://localhost:8000/health
            Write-Host $healthResult -ForegroundColor Green
        } catch {
            Write-Host "No se pudo conectar al endpoint /health. Asegúrese de que el servidor esté en ejecución." -ForegroundColor Red
        }
    } catch {
        Write-Host "Error al realizar la prueba HTTP: $_" -ForegroundColor Red
    }
}

Write-Host "\nConfiguración de curl completada." -ForegroundColor Green