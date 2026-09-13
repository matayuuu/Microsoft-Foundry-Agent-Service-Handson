FROM mcr.microsoft.com/devcontainers/python:3.2.3-3.13-bookworm

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends graphviz=2.42.2-7+deb12u1 \
    && apt-get clean \
    && git --version \
    && python3.13 --version \
    && dot -V
