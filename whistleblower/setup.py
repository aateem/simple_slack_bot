import setuptools


setuptools.setup(
    name="whistleblower-bot",
    version="0.0.1",
    author="Artem Roma",
    author_email="fuzzy.finder@gmail.com",
    description="Simple slack bot that listens for what you are saying ;)",
    url="https://github.com/aateem/simple_slack_bot",
    packages=setuptools.find_packages(),
    install_requires=["celery", "flask", "redis", "slackclient",],
    python_requires=">=3.7",
)
