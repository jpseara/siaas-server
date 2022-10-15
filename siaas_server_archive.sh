#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "`readlink -f ${BASH_SOURCE[0]}`" )" &> /dev/null && pwd )

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root or using sudo!"
  exit 1
fi

BACKUP_OWNER="`loginctl user-status | head -1 | awk '{print $1}'`"
bak_user=`id -u "${BACKUP_OWNER}"`
bak_group=`id -g "${BACKUP_OWNER}"`
now=`date +%Y%m%d%H%M%S`

cd ${SCRIPT_DIR}
./venv/bin/pip3 freeze > ./requirements.txt
chmod 664 ./requirements.txt
rm -rf ./__pycache__
rm -rf ./tmp
rm -rf ./var
sudo chown -R ${bak_user}:${bak_group} .

cd ..
tar --exclude='siaas-server/venv' --exclude='siaas-server/.git*' -cpzf ./siaas-server-${now}.tgz siaas-server
chown ${bak_user}:${bak_group} siaas-server-${now}.tgz
chmod 664 siaas-server-${now}.tgz

stat siaas-server-${now}.tgz
