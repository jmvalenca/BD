#!/bin/bash
# Backup diário da base de dados "contabilidade" (a partir da 01:00, hora de Lisboa).
# Corre dentro do container "backup" (imagem postgres:17, que inclui o pg_dump).
#
# - Os ficheiros ficam em /backups, que é a pasta backups/ do projeto no Mac.
# - Um backup só é aceite se o pg_dump terminar sem erro e o .gz for válido;
#   caso contrário é descartado e tenta-se de novo 15 minutos depois.
# - Se o backup do dia ainda não existir (Mac a dormir, Docker fechado...),
#   é feito logo que o container arranque, desde que já passe da 01:00.
# - São mantidos os 30 backups mais recentes.
set -uo pipefail

DIR=/backups
MANTER=30
HORA_INICIO=1          # não fazer backups antes desta hora (0-23)
ESPERA_ERRO=900        # segundos até nova tentativa após falha

mkdir -p "$DIR"
echo "Serviço de backup iniciado (fuso: ${TZ:-UTC}). Backups em $DIR."

fazer_backup() {
    local dia="$1"
    local final="$DIR/contabilidade_$dia.sql.gz"
    local tmp="$DIR/.contabilidade_$dia.sql.gz.tmp"

    echo "[$(date '+%F %T')] A criar backup de $dia..."
    if pg_dump -h db -U postgres -d contabilidade | gzip > "$tmp" \
        && gzip -t "$tmp" \
        && [ "$(gzip -dc "$tmp" | head -c 100000 | grep -c 'PostgreSQL database dump')" -ge 1 ]; then
        mv "$tmp" "$final"
        echo "[$(date '+%F %T')] Backup criado: $final ($(du -h "$final" | cut -f1))"
        # rodar: manter só os $MANTER backups válidos mais recentes
        ls -1t "$DIR"/contabilidade_*.sql.gz 2>/dev/null | tail -n +$((MANTER + 1)) | xargs -r rm -f
        return 0
    else
        rm -f "$tmp"
        echo "[$(date '+%F %T')] ERRO: backup de $dia falhou; nova tentativa daqui a $((ESPERA_ERRO / 60)) min." >&2
        return 1
    fi
}

while true; do
    DIA=$(date +%F)
    HORA=$((10#$(date +%H)))
    if [ "$HORA" -ge "$HORA_INICIO" ] && [ ! -f "$DIR/contabilidade_$DIA.sql.gz" ]; then
        if ! fazer_backup "$DIA"; then
            sleep "$ESPERA_ERRO"
            continue
        fi
    fi
    sleep 60
done
