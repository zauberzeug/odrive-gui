<img src="https://github.com/zauberzeug/odrive-gui/raw/main/screenshot.png" width="500" align="right">

# ODrive GUI

A Streamlit driven GUI to tweak and debug the ODrive hardware controller. Also packaged in a Docker image for easy usage.

## Usage

Just start the container with

```bash
docker run --privileged --rm -p 80:80 --name odrive -it zauberzeug/odrive-gui:latest
```

and access the interface at http://localhost/. It's convienient to use the `--privileged` parameter to allow access to usb, but you can also provide only the device you want to use.
