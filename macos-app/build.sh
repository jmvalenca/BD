#!/usr/bin/env bash
# Compila a aplicação macOS Movimentos.app.
# Requisitos: Xcode Command Line Tools (xcode-select --install).
set -euo pipefail
cd "$(dirname "$0")"

APP="Movimentos.app"
mkdir -p "$APP/Contents/MacOS"
cp Info.plist "$APP/Contents/"

swiftc -O -o "$APP/Contents/MacOS/Movimentos" MovimentosApp.swift

echo "✅ Criado $APP"
echo "   Teste:  open ./Movimentos.app"
echo "   Para instalar: arraste Movimentos.app para /Applications"
