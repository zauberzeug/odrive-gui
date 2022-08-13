#!/usr/bin/env python3
import asyncio
import functools
import sys

import odrive
from nicegui import task_logger, ui

from controls import controls

ui.colors(primary='#6e93d6')

message = ui.markdown()


def show_message(text: str):
    message.content = text
    print(text, flush=True)


async def startup():
    try:
        show_message('# searching for odrive')
        loop = asyncio.get_running_loop()
        odrv = await loop.run_in_executor(None, functools.partial(odrive.find_any, timeout=15))
        message.visible = False
        controls(odrv)
    except TimeoutError:
        show_message('# could not find any odrive')

ui.on_startup(startup)

ui.run(title='ODrive Motor Tuning')
