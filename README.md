# ODrive GUI

A web-based GUI to tweak and debug the ODrive motor controller.
It also comes packaged in a Docker image for easy usage.

<img src="https://github.com/zauberzeug/odrive-gui/raw/main/screenshot.png" width="100%">

## Usage

Install required packages

```bash
python3 -m pip install -r requirements.txt
```

and start the app:

```bash
python3 src/main.py
```

Or just start the Docker container with

```bash
docker run -p 8080:8080 --name odrive --rm -it --privileged zauberzeug/odrive-gui:latest
```

and access the interface at http://localhost:8080/.
It is convenient (but insecure) to use the `--privileged` parameter to allow access to USB.
You can also provide only the device you want to use with `--device=/dev/ttyUSB0` or similar.
