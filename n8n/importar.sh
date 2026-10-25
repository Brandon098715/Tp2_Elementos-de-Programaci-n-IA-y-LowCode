#!/bin/sh
# Importa en n8n la credencial SMTP y los 3 workflows, y los publica (activa).
# Se ejecuta DENTRO del contenedor de n8n:
#
#   docker compose exec n8n sh /import/importar.sh
#   docker compose restart n8n
#
# Es seguro ejecutarlo más de una vez: si ya existen, se actualizan (mismo id).
set -e

echo "==> Importando credencial SMTP (Mailpit, sin usuario ni contraseña)"
n8n import:credentials --input=/import/credentials/smtp_mailpit.json

echo "==> Importando workflows"
n8n import:workflow --separate --input=/import/workflows

echo "==> Publicando workflows"
for id in tp2IngresoOferta tp2MatchingIA001 tp2ReporteDiario; do
  n8n publish:workflow --id="$id"
done

echo "Listo. Reiniciá n8n para que tome los cambios: docker compose restart n8n"
