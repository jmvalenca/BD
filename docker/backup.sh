#!/bin/sh
# Backup diário da base de dados "contabilidade" (01:00, retenção de 30 dias).
# Corre dentro do container "backup" (imagem postgres:17, que inclui o pg_dump).
set -eu

DIR=/backups
ULTIMO=""

echo "Backup agendado: espera pelas 01:00 de cada dia."

while true; do
    DIA=$(date +%F)
    HORA=$(date +%H)
    if [ "$HORA" = "01" ] && [ "$ULTIMO" != "$DIA" ]; then
        echo "[$DIA 01:xx] A criar backup..."
        pg_dump -h db -U postgres -d contabilidade | gzip > "$DIR/contabilidade_$DIA.sql.gz"
        # manter só os 30 backups mais recentes
        ls -1t "$DIR"/contabilidade_*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm -f
        ULTIMO="$DIA"
        echo "Backup criado: $DIR/contabilidade_$DIA.sql.gz"
    fi
    sleep 60
done
