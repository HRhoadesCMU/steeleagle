# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import streamlit as st
import redis
import pandas as pd
import json
import zmq
import time
import hmac

DATA_TYPES = {
    "latitude": "float",
    "longitude": "float",
    "rel_altitude": "float",
    "abs_altitude": "float",
    "bearing": "int",
    # "sats": int,
}

COLORS = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "darkblue",
    "darkgreen",
    "pink",
    "beige",
    "lightred",
    "lightblue",
    "lightgreen",
    "darkpurple",
    "gray",
    "cadetblue",
    "lightgray",
    "black",
]

if "control_pressed" not in st.session_state:
    st.session_state.control_pressed = False
if "inactivity_time" not in st.session_state:
    st.session_state.inactivity_time = 1 #min

def authenticated():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    a,b,c = st.columns(3)
    b.text_input(
        "Password", type="password", on_change=password_entered, key="password",
    )
    if "password_correct" in st.session_state:
        b.error("Authentication failed.", icon=":material/block:")
    return False

@st.cache_resource
def connect_redis():
    red = redis.Redis(
        host=st.secrets.redis,
        port=st.secrets.redis_port,
        username=st.secrets.redis_user,
        password=st.secrets.redis_pw,
        decode_responses=True,
    )
    return red

@st.cache_resource
def connect_redis_publisher():
    red = redis.Redis(
        host=st.secrets.redis,
        port=st.secrets.redis_port,
        username=st.secrets.redis_user,
        password=st.secrets.redis_pw,
    )
    subscriber = red.pubsub(ignore_subscribe_messages=True)
    return subscriber

@st.cache_resource
def connect_zmq():
    ctx = zmq.Context()
    z = ctx.socket(zmq.REQ)
    z.connect(f'tcp://{st.secrets.zmq}:{st.secrets.zmq_port}')
    return z


def get_drones():
    l = {}
    red = connect_redis()
    for k in red.keys("drone:*"):
        last_seen = float(red.hget(k, "last_seen"))
        if time.time() - last_seen <  st.session_state.inactivity_time * 60: # minutes -> seconds
            drone_name = k.split(":")[-1]
            drone_model = red.hget(k, "model")
            if drone_model == "":
                drone_model = "unknown"
            bat = int(red.hget(k, "battery"))
            if bat == 0:
               bat_status = ":green-badge[:material/battery_full:]"
            elif bat == 1:
                bat_status = ":orange-badge[:material/battery_3_bar:]"
            else:
                bat_status = ":red-badge[:material/battery_alert:]"

            mag = int(red.hget(k, "mag"))
            if mag == 0:
                mag_status = ":green-badge[:material/explore:]"
            elif mag == 1:
                mag_status = ":orange-badge[:material/explore:]"
            else:
                mag_status = ":red-badge[:material/explore:]"

            sats = int(red.hget(k, "sats"))
            if sats == 0:
                sat_status = ":green-badge[:material/satellite_alt:]"
            elif sats == 1:
                sat_status = ":orange-badge[:material/satellite_alt:]"
            elif sats == 2:
                sat_status = ":red-badge[:material/satellite_alt:]"

            slam = red.hget(k, "slam_registering")
            if slam:
                slam_status = ":green-badge[:material/globe_location_pin:]"
            else:
                slam_status = ":red-badge[:material/globe_location_pin:]"
            # markdown format
            # "**golden eagle (_ANAFI USA_) :green-badge[:material/explore: mag] :orange-badge[:material/satellite_alt: sats] :red-badge[:material/globe_location_pin: slam]**"

            l[drone_name] = f"**{drone_name} (_{drone_model}_) {bat_status}{mag_status}{sat_status}{slam_status}** "

    return l

def stream_to_dataframe(results, types=DATA_TYPES ) -> pd.DataFrame:
    _container = {}
    for item in results:
        _container[item[0]] = json.loads(json.dumps(item[1]))

    df = pd.DataFrame.from_dict(_container, orient='index')
    if types is not None:
        try:
            df = df.astype(types)
        except KeyError as e:
            print(e)

    return df

def control_drone(drone):
    st.session_state.selected_drone = drone
    st.session_state.control_pressed = True


def menu(with_control=True):
    st.sidebar.page_link("overview.py", label=":satellite_antenna: Overview")
    st.sidebar.page_link("pages/plan.py", label=":ledger: Mission Planning")
    st.sidebar.page_link("pages/detections.py", label=":bangbang: Detected Objects")



