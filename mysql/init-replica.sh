#!/bin/bash
set -e

echo "[Replica] Esperando al master..."
until mysql -h mysql_master -u root -proot -e "SELECT 1" 2>/dev/null; do
    sleep 3
done

echo "[Replica] Master listo. Obteniendo posicion del binlog..."

LOG_FILE=$(mysql -h mysql_master -u root -proot -e "SHOW MASTER STATUS;" 2>/dev/null | awk 'NR==2{print $1}')
LOG_POS=$(mysql -h mysql_master -u root -proot -e "SHOW MASTER STATUS;" 2>/dev/null | awk 'NR==2{print $2}')

echo "[Replica] Archivo: $LOG_FILE | Posicion: $LOG_POS"

mysql -u root -proot <<-SQL
    STOP SLAVE;
    CHANGE MASTER TO
        MASTER_HOST='mysql_master',
        MASTER_USER='replicator',
        MASTER_PASSWORD='replicator123',
        MASTER_LOG_FILE='${LOG_FILE}',
        MASTER_LOG_POS=${LOG_POS};
    START SLAVE;
SQL

echo "[Replica] Replicacion iniciada correctamente."
