FROM zauberzeug/streamlit:latest

RUN apt-get update && apt-get install -y libusb-1.0-0 libusb-1.0-0-dev

RUN python3 -m pip install odrive

COPY src .
