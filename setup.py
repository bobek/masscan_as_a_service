import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

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
            'perform_masscan = masscan_as_a_service.perform_masscan:main',
        ],
    },
)
