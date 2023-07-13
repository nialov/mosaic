from setuptools import setup

setup(
    name="mosaic",
    version="0.1",
    py_modules=["mosaic"],
    install_requires=[
        "Pillow",
    ],
    entry_points={
        "console_scripts": [
            "mosaic=mosaic:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
