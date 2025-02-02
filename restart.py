#!/bin/bash

# Script to install ROCm and resolve missing libmctl-dev package issue on Ubuntu 24.04

# Step 1: Update package list
echo "Updating package list..."
sudo apt update

# Step 2: Add ROCm repository
echo "Adding ROCm repository..."
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/debian/ ubuntu main' | sudo tee /etc/apt/sources.list.d/rocm.list
sudo apt update

# Step 3: Install ROCm and dependencies
echo "Installing ROCm and dependencies..."
sudo apt install -y rocm-dkms

# Step 4: Check for and install libhsakmt-dev (if needed)
echo "Checking for libhsakmt-dev..."
if ! dpkg -l | grep -q libhsakmt-dev; then
    echo "Installing libhsakmt-dev..."
    sudo apt install -y libhsakmt-dev
else
    echo "libhsakmt-dev is already installed."
fi

# Step 5: Verify installation
echo "Verifying ROCm installation..."
/opt/rocm/bin/rocminfo
/opt/rocm/opencl/bin/clinfo

echo "ROCm installation script completed."