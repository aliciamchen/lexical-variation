#!/bin/bash
current_datetime=$(date +"%Y%m%d_%H%M%S")

mkdir -p data/"$current_datetime"

while true; do
    rsync -avh --progress root@45.55.59.202:~/.empirica/local/tajriba.json data/"$current_datetime"/

    sleep 300
done
