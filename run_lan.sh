#!/bin/bash
# LAN Access Script for Korespondensi + Streamlit Living Archive

LAN_IP=$(ip route get 8.8.8.8 | awk '{print $7; exit}')
echo "LAN IP: $LAN_IP"

# Replace localhost links with LAN IP (if any)
grep -rl "localhost:8501" templates/ static/ | xargs sed -i "s/localhost:8501/$LAN_IP:8501/g"

# Start/Restart services
systemctl restart korespondensi-server.service

# Tail logs
tail -f logs/web_app.log logs/main.log
