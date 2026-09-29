#!/usr/bin/env bash
#
# criar_dmg.sh — cria um .dmg "arrastar para Aplicações" a partir de uma .app,
# com assinatura e notarização opcionais.
#
# Uso:
#   ./criar_dmg.sh [caminho/para/App.app]        (por omissão: Movimentos.app)
#
# Assinatura e notarização (opcionais, via variáveis de ambiente):
#   SIGN_IDENTITY   Identidade de assinatura, p.ex.
#                   "Developer ID Application: O Teu Nome (TEAMID)"
#                   (lista as disponíveis com: security find-identity -v -p codesigning)
#   NOTARY_PROFILE  Nome do perfil guardado no Keychain para o notarytool.
#                   Cria-o uma vez com:
#                     xcrun notarytool store-credentials "meu-perfil" \
#                       --apple-id "email@exemplo.com" --team-id "TEAMID" \
#                       --password "app-specific-password"
#
# Exemplos:
#   ./criar_dmg.sh
#   SIGN_IDENTITY="Developer ID Application: Nome (ABCDE12345)" ./criar_dmg.sh
#   SIGN_IDENTITY="..." NOTARY_PROFILE="meu-perfil" ./criar_dmg.sh Movimentos.app

set -euo pipefail

APP_PATH="${1:-Movimentos.app}"
APP_PATH="${APP_PATH%/}"   # remove "/" final, se existir

# ---------- Verificações ----------
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Erro: este script tem de correr em macOS." >&2
    exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
    echo "Erro: não encontrei '$APP_PATH'." >&2
    exit 1
fi

if [[ -n "${NOTARY_PROFILE:-}" && -z "${SIGN_IDENTITY:-}" ]]; then
    echo "Erro: a notarização exige assinatura. Define também SIGN_IDENTITY." >&2
    exit 1
fi

APP_NAME="$(basename "$APP_PATH" .app)"
PLIST="$APP_PATH/Contents/Info.plist"

VERSION=""
if [[ -f "$PLIST" ]]; then
    VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST" 2>/dev/null || true)"
fi

if [[ -n "$VERSION" ]]; then
    DMG_NAME="${APP_NAME}-${VERSION}.dmg"
else
    DMG_NAME="${APP_NAME}.dmg"
fi

STAGING="$(mktemp -d -t "${APP_NAME}_dmg")"
trap 'rm -rf "$STAGING"' EXIT

echo "==> App:     $APP_PATH"
echo "==> Versão:  ${VERSION:-(não definida)}"
echo "==> Saída:   $DMG_NAME"

# ---------- 1. Assinar a app ----------
if [[ -n "${SIGN_IDENTITY:-}" ]]; then
    echo "==> A assinar a app..."
    # --options runtime (Hardened Runtime) é obrigatório para notarização.
    # --deep é prático para apps geradas por PyInstaller/py2app; para apps com
    # estrutura complexa pode ser preferível assinar cada binário individualmente.
    codesign --force --deep --timestamp --options runtime \
        --sign "$SIGN_IDENTITY" "$APP_PATH"

    codesign --verify --deep --strict --verbose=2 "$APP_PATH"
else
    echo "==> SIGN_IDENTITY não definida: a app não será assinada."
fi

# ---------- 2. Preparar conteúdo do DMG ----------
echo "==> A preparar conteúdo..."
ditto "$APP_PATH" "$STAGING/$APP_NAME.app"
ln -s /Applications "$STAGING/Applications"

# ---------- 3. Criar o DMG ----------
echo "==> A criar o DMG..."
rm -f "$DMG_NAME"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DMG_NAME"

# ---------- 4. Assinar o DMG ----------
if [[ -n "${SIGN_IDENTITY:-}" ]]; then
    echo "==> A assinar o DMG..."
    codesign --force --timestamp --sign "$SIGN_IDENTITY" "$DMG_NAME"
fi

# ---------- 5. Notarizar e agrafar ----------
if [[ -n "${NOTARY_PROFILE:-}" ]]; then
    echo "==> A enviar para notarização (pode demorar alguns minutos)..."
    xcrun notarytool submit "$DMG_NAME" \
        --keychain-profile "$NOTARY_PROFILE" \
        --wait

    echo "==> A agrafar o ticket de notarização..."
    xcrun stapler staple "$DMG_NAME"
    xcrun stapler validate "$DMG_NAME"

    echo "==> Verificação Gatekeeper:"
    spctl --assess --type open --context context:primary-signature -v "$DMG_NAME" || true
fi

echo ""
echo "Concluído: $(pwd)/$DMG_NAME"
