import os
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

REQUIREMENTS = [
    line.split("#")[0].strip()
    for line in open(os.path.join(os.path.dirname(__file__), "requirements.txt")).readlines()
    if line.split("#")[0].strip()
]

setuptools.setup(
    name="masscan-as-a-service",
    version="0.0.1",
    author="Antonin Kral",
    author_email="a.kral@bobek.cz",
    description="Wrapper around masscan to perform regular scans for opened ports",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bobek/masscan_as_a_service",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache License",
    ],
    entry_points={
        'console_scripts': [
            'masscan_as_a_service = masscan_as_a_service.__main__:main',
        ],
    },
    install_requires=REQUIREMENTS,
)
