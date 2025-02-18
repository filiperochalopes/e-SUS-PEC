#!/bin/sh

sudo apt-get update && sudo apt-get install -y \
    locales coreutils wget apt-utils gnupg2 software-properties-common \
    file libfreetype6 ntp ttf-mscorefonts-installer fontconfig

sudo timedatectl set-timezone America/Sao_Paulo

sudo fc-cache -fv
sudo chmod -R 777 /usr/share/fonts/truetype/msttcorefonts

wget -O - https://apt.corretto.aws/corretto.key | sudo gpg --dearmor -o /usr/share/keyrings/corretto-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/corretto-keyring.gpg] https://apt.corretto.aws stable main" | sudo tee /etc/apt/sources.list.d/corretto.list

sudo apt-get update && sudo apt-get install -y java-17-amazon-corretto-jdk

export JAVA_TOOL_OPTIONS="-Duser.timezone=America/Sao_Paulo"
echo 'export JAVA_TOOL_OPTIONS="-Duser.timezone=America/Sao_Paulo"' >> ~/.bashrc

# A forma de utilizar JAVA_TOOL_OPTIONS não parece que deu muito certo nas versões instaladas, segue abaixo sugestão do Laboratório Bridge
sed -i '$d' ~/.bashrc # Removendo a linha que foi acrescentada no último comando

echo "America/Sao_Paulo" | sudo tee /etc/timezone
sudo ln -sf /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime && date

sudo reboot
