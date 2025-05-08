#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="smartbolt-iot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "paho-mqtt>=1.5.0",
    ],
) 