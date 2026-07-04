#!/usr/bin/env bash
# Keep the localhost.run tunnel alive — reconnects if it drops
while true; do
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 80:localhost:8776 nokey@localhost.run 2>&1
    echo "[tunnel] disconnected, reconnecting in 3s..."
    sleep 3
done
