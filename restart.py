#!/bin/bash

# Script to install ROCm on Ubuntu 24.04 (or fallback if not supported)

# Step 1: Update package list
echo "Updating package list..."
sudo apt update

# Step 2: Add ROCm repository
echo "Adding ROCm repository..."
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/debian/ ubuntu main' | sudo tee /etc/apt/sources.list.d/rocm.list
sudo apt update

# Step 3: Check if rocm-dkms is available
echo "Checking for rocm-dkms..."
if apt-cache show rocm-dkms &> /dev/null; then
    echo "Installing ROCm and dependencies..."
    sudo apt install -y rocm-dkms
else
    echo "ERROR: rocm-dkms package not found. Ubuntu 24.04 may not be supported yet."
    echo "Please use a supported Ubuntu version (e.g., 22.04 LTS) or check the ROCm documentation."
    exit 1
fi

# Step 4: Verify installation
echo "Verifying ROCm installation..."
if command -v /opt/rocm/bin/rocminfo &> /dev/null; then
    /opt/rocm/bin/rocminfo
    echo "ROCm installation successful!"
else
    echo "ROCm installation failed. Please check the logs and try again."
    exit 1
fi