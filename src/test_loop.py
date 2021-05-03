#!/usr/bin/env python3
import streamlit as st
import time

time_view = st.json({})
while True:
    print(time.time())
    time_view.json({'t': time.time()})
    time.sleep(1)
