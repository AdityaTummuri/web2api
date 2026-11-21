from setuptools import setup, find_packages

setup(
    name="web2api-client",
    version="2.0.0",
    description="Universal Python client for the Web2API standalone server",
    author="Web2API Team",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.25.0",
    ],
    python_requires=">=3.8",
)
