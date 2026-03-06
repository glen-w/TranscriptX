#!/usr/bin/env python3
"""
Setup script for TranscriptX package.
"""

from setuptools import setup, find_packages

setup(
    name="transcriptx",
    version="0.42",
    description="Advanced transcript analysis and visualization toolkit",
    author="TranscriptX Team",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # Core dependencies will be installed from requirements.txt
    ],
)
