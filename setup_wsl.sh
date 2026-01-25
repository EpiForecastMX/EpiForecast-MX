#!/bin/bash
# Script para actualizar Ubuntu, instalar build-essential y configurar Miniconda
# chmod +x setup_miniconda.sh
# ./setup_miniconda.sh

echo "🔄 Actualizando repositorios..."
sudo apt update

echo "⬆️ Actualizando paquetes del sistema..."
sudo apt full-upgrade -y

echo "🛠️ Instalando build-essential..."
sudo apt install build-essential -y

echo "📥 Descargando instalador de Miniconda..."
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

echo "💿 Instalando Miniconda en modo silencioso..."
bash ./Miniconda3-latest-Linux-x86_64.sh -b

echo "✅ Activando Miniconda..."
source ~/miniconda3/bin/activate

echo "⚙️ Inicializando conda en la shell..."
conda init

echo "🧹 Limpiando instalador..."
rm ./Miniconda3-latest-Linux-x86_64.sh

echo "🎉 Instalación y configuración completadas. Cierra y vuelve a abrir tu terminal para aplicar conda init."