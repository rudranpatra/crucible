from setuptools import setup, find_packages

setup(
    name="crucible-gym",
    version="0.1.0",
    description="Adversarial Intelligence Engine for CI/CD Pipelines",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Crucible",
    license="Apache-2.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pyyaml>=6.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": ["pytest", "pytest-asyncio", "black", "mypy"],
    },
    entry_points={
        "console_scripts": [
            "crucible=cli.crucible:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Testing",
    ],
)
