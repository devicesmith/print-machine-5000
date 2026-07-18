APP_NAME := webhook
APP_DIR := $(shell pwd)
VENV_DIR := $(APP_DIR)/.venv
PYTHON := /usr/bin/python3
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
NGROK := /usr/local/bin/ngrok
PORT := 5000
USER := $(shell whoami)

SYSTEMD_DIR := /etc/systemd/system
WEBHOOK_SERVICE := $(SYSTEMD_DIR)/webhook.service
NGROK_SERVICE := $(SYSTEMD_DIR)/ngrok.service

.PHONY: help venv deps services enable start stop restart status logs install uninstall daemon-reload

help:
	@echo "Targets:"
	@echo "  make venv         - Create Python virtual environment"
	@echo "  make deps         - Install Python dependencies into venv"
	@echo "  make services     - Install systemd service files"
	@echo "  make enable       - Enable services at boot"
	@echo "  make start        - Start services now"
	@echo "  make stop         - Stop services"
	@echo "  make restart      - Restart services"
	@echo "  make status       - Show service status"
	@echo "  make logs         - Tail service logs"
	@echo "  make install      - Run venv + deps + services + enable + start"
	@echo "  make uninstall    - Stop, disable, and remove services"

venv:
	$(PYTHON) -m venv $(VENV_DIR)

deps: venv
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt

services:
	@echo "Installing systemd services..."
	@printf '%s\n' \
		'[Unit]' \
		'Description=Webhook Flask App' \
		'After=network.target' \
		'' \
		'[Service]' \
		'User=$(USER)' \
		'WorkingDirectory=$(APP_DIR)' \
		'ExecStart=$(VENV_PYTHON) $(APP_DIR)/webhook.py' \
		'Restart=always' \
		'RestartSec=5' \
		'Environment=PYTHONUNBUFFERED=1' \
		'' \
		'[Install]' \
		'WantedBy=multi-user.target' | sudo tee $(WEBHOOK_SERVICE) > /dev/null
	@printf '%s\n' \
		'[Unit]' \
		'Description=ngrok tunnel' \
		'After=network.target webhook.service' \
		'Wants=webhook.service' \
		'' \
		'[Service]' \
		'User=$(USER)' \
		'ExecStart=$(NGROK) http $(PORT)' \
		'Restart=always' \
		'RestartSec=5' \
		'' \
		'[Install]' \
		'WantedBy=multi-user.target' | sudo tee $(NGROK_SERVICE) > /dev/null
	@sudo systemctl daemon-reload

enable:
	sudo systemctl enable webhook.service
	sudo systemctl enable ngrok.service

start:
	sudo systemctl start webhook.service
	sudo systemctl start ngrok.service

stop:
	-sudo systemctl stop ngrok.service
	-sudo systemctl stop webhook.service

restart:
	sudo systemctl restart webhook.service
	sudo systemctl restart ngrok.service

status:
	-sudo systemctl status webhook.service --no-pager
	-sudo systemctl status ngrok.service --no-pager

logs:
	journalctl -u webhook.service -u ngrok.service -f

daemon-reload:
	sudo systemctl daemon-reload

install: deps services enable start

uninstall:
	-sudo systemctl stop ngrok.service
	-sudo systemctl stop webhook.service
	-sudo systemctl disable ngrok.service
	-sudo systemctl disable webhook.service
	-sudo rm -f $(WEBHOOK_SERVICE) $(NGROK_SERVICE)
	sudo systemctl daemon-reload
