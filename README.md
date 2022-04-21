# ODrive GUI

A web-based GUI to tweak and debug the ODrive motor controller.
It also comes packaged in a Docker image for easy usage.

<img src="https://github.com/zauberzeug/odrive-gui/raw/main/screenshot.png" width="100%">

## Usage

Just start the container with

```bash
docker run --privileged -p 80:80 --name odrive -it zauberzeug/odrive-gui:latest
```

and access the interface at http://localhost/.
It is convenient to use the `--privileged` parameter to allow access to USB.
But you can also provide only the device you want to use.
