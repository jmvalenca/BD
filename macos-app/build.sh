#!/usr/bin/env bash
# Compila a aplicação macOS Movimentos.app.
# Requisitos: Xcode Command Line Tools (xcode-select --install).
set -euo pipefail
cd "$(dirname "$0")"

APP="Movimentos.app"
mkdir -p "$APP/Contents/MacOS"
cp Info.plist "$APP/Contents/"

# -parse-as-library: necessário porque usamos @main num único ficheiro
# (sem esta flag o swiftc trata o ficheiro como script e rejeita o @main).
swiftc -parse-as-library -O -o "$APP/Contents/MacOS/Movimentos" MovimentosApp.swift

echo "✅ Criado $APP"
echo "   Teste:  open ./Movimentos.app"
echo "   Para instalar: arraste Movimentos.app para /Applications"
