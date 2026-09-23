# abrir_movimentos.ps1  —  script para o UTILIZADOR EXTERNO (Windows 10/11)
#
# Mesmo comportamento que abrir_movimentos.sh: liga por SSH ao computador da
# base de dados, arranca lá a aplicação Movimentos e abre-a no browser local.
# Use abrir_movimentos.cmd para lançar com duplo clique.
#
# Uso:  powershell -ExecutionPolicy Bypass -File abrir_movimentos.ps1 [user@host]
# Requisito: cliente OpenSSH do Windows (já incluído no Windows 10/11).

param(
    [string]$Destino      = "josevalenca@mbp-de-jose",
    [string]$ScriptRemoto = "~/Library/CloudStorage/Dropbox/BD/iniciar_movimentos.sh",
    [int]$PortaRemota     = 2718,
    [int]$PortaLocal      = 2718,
    [int]$EsperaMax       = 180
)

if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Error "Falta o cliente 'ssh'. Instale em Definições > Aplicações > Funcionalidades opcionais > Cliente OpenSSH."
    exit 1
}

# Procura um porto local livre.
while (Get-NetTCPConnection -LocalPort $PortaLocal -State Listen -ErrorAction SilentlyContinue) {
    $PortaLocal++
}
$Url = "http://localhost:$PortaLocal"

# Em segundo plano: espera que a app responda e abre o browser.
$vigia = Start-Job -ArgumentList $Url, $EsperaMax -ScriptBlock {
    param($Url, $EsperaMax)
    for ($i = 0; $i -lt $EsperaMax; $i++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1 | Out-Null
            Start-Process $Url
            return
        } catch { }
    }
}

Write-Host "A ligar a $Destino e a arrancar a aplicacao Movimentos..."
Write-Host "(tunel: $Url  ->  servidor 127.0.0.1:$PortaRemota)"
Write-Host "Para terminar: Ctrl+C nesta janela, ou o botao 'Fechar aplicacao' na app."
Write-Host ""

try {
    ssh -tt -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 `
        -L "${PortaLocal}:127.0.0.1:${PortaRemota}" `
        $Destino "PORT=$PortaRemota bash $ScriptRemoto"
} finally {
    Stop-Job $vigia -ErrorAction SilentlyContinue
    Remove-Job $vigia -Force -ErrorAction SilentlyContinue
}
