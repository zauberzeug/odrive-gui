#!/usr/bin/env python3
import streamlit as st
import random
import session

state = session.get_state()

letters = list('ABCDEF')

if state.letter is None:
    state.letter = random.choice(letters)

state.letter = st.radio('Letter', letters, letters.index(state.letter))

if st.button('Select "A"'):
    state.letter = 'A'

st.write('state.letter ==', state.letter)

state.sync()
