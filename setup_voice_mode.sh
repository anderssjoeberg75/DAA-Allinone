#!/bin/bash

# Voice Mode Setup Script for DAA
# This script installs all necessary dependencies for voice mode

echo "🎤 DAA Voice Mode - Dependency Installation"
echo "==========================================="
echo ""

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "🐧 Detected OS: $NAME"
fi

echo ""
echo "📦 Step 1: Installing system dependencies..."
echo "This requires sudo access."
echo ""

# Install PortAudio (required for PyAudio)
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio pulseaudio-utils

if [ $? -eq 0 ]; then
    echo "✅ System dependencies installed successfully"
else
    echo "❌ Failed to install system dependencies"
    exit 1
fi

echo ""
echo "📦 Step 2: Installing Python dependencies..."
echo ""

# Navigate to backend directory
cd "$(dirname "$0")/backend" || exit 1

# Install PyAudio via pip (if not already installed)
pip3 install PyAudio==0.2.14

if [ $? -eq 0 ]; then
    echo "✅ PyAudio installed successfully"
else
    echo "❌ Failed to install PyAudio"
    exit 1
fi

echo ""
echo "🧪 Step 3: Testing PyAudio..."
echo ""

# Test PyAudio import
python3 -c "import pyaudio; print('✅ PyAudio imports successfully')"

if [ $? -eq 0 ]; then
    echo "✅ PyAudio test passed"
else
    echo "❌ PyAudio test failed"
    exit 1
fi

echo ""
echo "🔍 Step 4: Checking audio devices..."
echo ""

# List audio devices
python3 << EOF
import pyaudio
p = pyaudio.PyAudio()

print("Available audio devices:")
print("-" * 50)

for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"{i}: {info['name']}")
    print(f"   Max Input Channels: {info['maxInputChannels']}")
    print(f"   Max Output Channels: {info['maxOutputChannels']}")
    print(f"   Default Sample Rate: {info['defaultSampleRate']}")
    print()

# Get default devices
try:
    default_input = p.get_default_input_device_info()
    print(f"✅ Default Input Device: {default_input['name']}")
except:
    print("⚠️  No default input device found")

try:
    default_output = p.get_default_output_device_info()
    print(f"✅ Default Output Device: {default_output['name']}")
except:
    print("⚠️  No default output device found")

p.terminate()
EOF

echo ""
echo "✨ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Review the audio devices listed above"
echo "2. Ensure your microphone is connected"
echo "3. Run the voice mode implementation"
echo ""
