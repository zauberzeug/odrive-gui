FROM intelligentdesigns/streamlit-plus:extra-latest

RUN apt-get update && apt-get install -y libusb-1.0-0 libusb-1.0-0-dev

RUN python3 -m pip install odrive

COPY src /app

EXPOSE 80

CMD streamlit run main.py --server.port 80