#!/bin/bash

# Atualizar pacotes e instalar dependências
sudo apt-get update 
sudo apt-get install -y ca-certificates curl 

# Adicionar chave GPG oficial do Docker
sudo install -m 0755 -d /etc/apt/keyrings 
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc 
sudo chmod a+r /etc/apt/keyrings/docker.asc 

# Adicionar repositório do Docker, garantindo compatibilidade
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Atualizar pacotes e instalar Docker e Docker Compose
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Adicionar usuário ao grupo docker para evitar uso do sudo
sudo usermod -aG docker $USER
newgrp docker

# Criar alias para docker compose
echo "alias dc='docker compose'" >> ~/.bashrc
source ~/.bashrc

# Gerar valores aleatórios
ADMIN_PASSWORD=$(openssl rand -base64 12 | tr -d '=+/')
echo "Generated ADMIN_PASSWORD:"
echo "$ADMIN_PASSWORD"
SECRET_TOKEN=$(openssl rand -base64 16 | tr -d '=+/')
echo "Generated SECRET_TOKEN:"
echo "$SECRET_TOKEN"
PASSWORD_SALT=$(openssl passwd -6 $(openssl rand -base64 12))
echo "Generated PASSWORD_SALT:"
echo "$PASSWORD_SALT"

# Exibir versão do Docker e Docker Compose
docker --version
docker compose version
