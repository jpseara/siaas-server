#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "`readlink -f ${BASH_SOURCE[0]}`" )" &> /dev/null && pwd )

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root or using sudo!"
  exit 1
fi

cd ${SCRIPT_DIR}
rm -f ./var/uid

# Reinstall venv if for some reason it disappeared
if ! source ./venv/bin/activate 2> /dev/null
then
	./siaas_server_venv_setup.sh
fi

source ./venv/bin/activate
python3 -u ./siaas_server.py
