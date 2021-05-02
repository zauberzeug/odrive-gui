# ODrive GUI

A Streamlit driven GUI to tweak and debug the ODrive hardware controller. All packaged in a Docker image for easy usage.

# Build

Currently it only builds on x86 and not arm64 (l4t, nvidia jetson)

    docker build . -t zauberzeug/odrive-gui:streamlit-latest

# Run

    docker run --privileged --rm -p 80:80 --name odrive -it -v "$(pwd)"/src:/app zauberzeug/odrive-gui:streamlit-latest