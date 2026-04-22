#!/bin/sh
if [ -d /app/config.yml ]; then
    echo "ERROR: /app/config.yml is a directory, not a file."
    echo "On the host, run:"
    echo "  rm -rf ./config.yml && cp config.yml.example config.yml"
    echo "Then edit config.yml (set scanner.network and scanner.interface), and restart."
    exit 1
fi
exec "$@"
