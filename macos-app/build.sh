#!/usr/bin/env bash
# Compila a aplicação macOS Movimentos.app.
# Requisitos: Xcode Command Line Tools (xcode-select --install).
set -euo pipefail
cd "$(dirname "$0")"

APP="Movimentos.app"
mkdir -p "$APP/Contents/MacOS"
cp Info.plist "$APP/Contents/"

# Ícone: gera AppIcon.icns a partir de icone.png (1024x1024) com sips + iconutil.
# Para mudar o ícone basta substituir icone.png (ou editar icone.svg e exportar).
if [ -f icone.png ]; then
    TMP="$(mktemp -d)"; ICONSET="$TMP/AppIcon.iconset"; mkdir -p "$ICONSET"
    for s in 16 32 128 256 512; do
        sips -z "$s" "$s" icone.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
        sips -z $((s * 2)) $((s * 2)) icone.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
    done
    mkdir -p "$APP/Contents/Resources"
    iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
    rm -rf "$TMP"
fi

# -parse-as-library: necessário porque usamos @main num único ficheiro
# (sem esta flag o swiftc trata o ficheiro como script e rejeita o @main).
swiftc -parse-as-library -O -o "$APP/Contents/MacOS/Movimentos" MovimentosApp.swift

touch "$APP"   # para o Finder/Dock notarem o novo ícone

echo "✅ Criado $APP"
echo "   Teste:  open ./Movimentos.app"
echo "   Para instalar: arraste Movimentos.app para /Applications"
