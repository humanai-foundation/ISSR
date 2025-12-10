Write-Host "Setting up Ollama MIE Classification Model..." -ForegroundColor Cyan

# 1. Wait for Ollama to be ready
Write-Host "Waiting for Ollama to be ready..."
$ollamaReady = $false
while (-not $ollamaReady) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -Method Get -ErrorAction Stop
        if ($response.StatusCode -eq 200) { $ollamaReady = $true }
    }
    catch {
        Write-Host "Ollama not ready yet, waiting..."
        Start-Sleep -Seconds 2
    }
}
Write-Host "Ollama is ready!" -ForegroundColor Green

# 2. Check if MIE model already exists
$existingModels = ollama list
if ($existingModels -match "mie-expert") {
    Write-Host "MIE Expert model already exists" -ForegroundColor Green
}
else {
    Write-Host "Creating MIE Expert model..." -ForegroundColor Yellow
    
    # Navigate to the models folder where the 'Modelfile' is located
    Set-Location "ollama/models"
    
    # Run the creation command
    ollama create mie-expert -f Modelfile
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "MIE Expert model created successfully!" -ForegroundColor Green
    }
    else {
        Write-Host "Failed to create MIE Expert model" -ForegroundColor Red
        exit 1
    }
    # Return to previous directory
    Set-Location ..\..
}

# 3. Test the model
Write-Host "Testing MIE Expert model..." -ForegroundColor Cyan
$testPayload = @{
    model = "mie-expert"
    prompt = "Test article: U.S. military conducted airstrikes in Syria. Is this an MIE?"
    stream = $false
} | ConvertTo-Json

try {
    $testResponse = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $testPayload -ContentType "application/json"
    Write-Host "Response received:"
    Write-Host $testResponse.response -ForegroundColor Gray
}
catch {
    Write-Host "Test failed." -ForegroundColor Red
}

Write-Host ""
Write-Host "Ollama setup complete! You can now run the MIE classification system." -ForegroundColor Green