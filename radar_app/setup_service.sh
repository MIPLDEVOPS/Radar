#!/bin/bash

# Define variables
SERVICE_NAME="radar"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
USER="vasd"
APP_DIR="/home/${USER}/radar_app"
START_SCRIPT="${APP_DIR}/start_radar.sh"

# Check if script is run as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please use sudo."
   exit 1
fi

# Check if the application directory exists
if [[ ! -d "${APP_DIR}" ]]; then
    echo "Error: Directory ${APP_DIR} does not exist."
    exit 1
fi

# Check if the start script exists and is executable
if [[ ! -f "${START_SCRIPT}" ]]; then
    echo "Error: Start script ${START_SCRIPT} does not exist."
    exit 1
fi
if [[ ! -x "${START_SCRIPT}" ]]; then
    echo "Making ${START_SCRIPT} executable..."
    chmod +x "${START_SCRIPT}"
fi

# Create the systemd service file
echo "Creating systemd service file at ${SERVICE_FILE}..."
cat > "${SERVICE_FILE}" << EOL
[Unit]
Description=Radar Listener + API Server
After=network.target

[Service]
Type=simple
ExecStart=${START_SCRIPT}
WorkingDirectory=${APP_DIR}
Restart=always
RestartSec=5
User=${USER}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

# Set permissions for the service file
echo "Setting permissions for ${SERVICE_FILE}..."
chmod 644 "${SERVICE_FILE}"

# Reload systemd to recognize the new service
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable the service to start on boot
echo "Enabling ${SERVICE_NAME} service..."
systemctl enable "${SERVICE_NAME}.service"

# Start the service
echo "Starting ${SERVICE_NAME} service..."
systemctl start "${SERVICE_NAME}.service"

# Check the status of the service
echo "Checking status of ${SERVICE_NAME} service..."
systemctl status "${SERVICE_NAME}.service" --no-pager

echo "Service ${SERVICE_NAME} has been created and started successfully."
