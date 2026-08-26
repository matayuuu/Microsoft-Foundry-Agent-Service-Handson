ARG VARIANT=1-3.13-bookworm
FROM mcr.microsoft.com/devcontainers/python:${VARIANT}

# The base image's obsolete Yarn source can block apt updates used by Features.
RUN rm -f /etc/apt/sources.list.d/yarn.list
