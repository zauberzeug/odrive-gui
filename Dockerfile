FROM zauberzeug/nicegui:0.8.4

RUN apt-get update && apt-get install -y libusb-1.0-0 libusb-1.0-0-dev && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install odrive

COPY src .
