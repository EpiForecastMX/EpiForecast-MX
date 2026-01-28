#!/bin/bash
# Script para configurar entorno de desarrollo en WSL/Ubuntu
# Incluye: build-essential, Miniconda, Ghostscript, AWS CLI y DVC
#
# Uso:
#   chmod +x setup_wsl.sh
#   ./setup_wsl.sh
#
# Después de ejecutar:
#   1. Cierra y abre la terminal
#   2. cd al proyecto y ejecuta: make setup-linux

set -e  # Salir si hay error

echo "🔄 Actualizando repositorios..."
sudo apt update

echo "⬆️ Actualizando paquetes del sistema..."
sudo apt full-upgrade -y

echo "🛠️ Instalando build-essential..."
sudo apt install build-essential -y

echo "👻 Instalando Ghostscript (requerido para extracción de PDFs)..."
sudo apt install ghostscript -y

echo "☁️ Instalando AWS CLI..."
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    sudo apt install unzip -y
    unzip awscliv2.zip
    sudo ./aws/install
    rm -rf awscliv2.zip aws/
    echo "✅ AWS CLI instalado."
else
    echo "✅ AWS CLI ya está instalado."
fi

echo "📥 Descargando instalador de Miniconda..."
if [ ! -d "$HOME/miniconda3" ]; then
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    
    echo "💿 Instalando Miniconda en modo silencioso..."
    bash ./Miniconda3-latest-Linux-x86_64.sh -b
    
    echo "🧹 Limpiando instalador..."
    rm ./Miniconda3-latest-Linux-x86_64.sh
else
    echo "✅ Miniconda ya está instalado."
fi

echo "✅ Activando Miniconda..."
source ~/miniconda3/bin/activate

echo "⚙️ Inicializando conda en la shell..."
conda init

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🎉 Instalación del sistema completada!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📋 Siguientes pasos:"
echo ""
echo "   1. Cierra y vuelve a abrir tu terminal"
echo ""
echo "   2. Configura tus credenciales de AWS:"
echo "      aws configure"
echo "      # Ingresa tu Access Key ID, Secret Access Key y región (us-east-1)"
echo ""
echo "   3. Clona el repositorio (si no lo tienes):"
echo "      git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git"
echo ""
echo "   4. Configura el proyecto:"
echo "      cd EpiForecast-MX"
echo "      make setup-linux"
echo ""
echo "═══════════════════════════════════════════════════════════════"