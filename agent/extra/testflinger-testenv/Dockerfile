ARG BASE_IMAGE=ubuntu:20.04

# Bring in the official Rust image as a reference stage.
FROM rust:1.99-slim AS rust-source

# Build stage: compile wheels from requirements file for packages that need a Rust toolchain
# Rust is copied in from rust-source and only used here, so the final image doesn't ship Rust.
FROM ${BASE_IMAGE} AS wheel-builder
ENV container=docker
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential python3-dev python3-pip python3-venv \
    pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /tmp/wheel-venv && /tmp/wheel-venv/bin/pip install --upgrade pip
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
COPY --from=rust-source /usr/local/rustup /usr/local/rustup
COPY --from=rust-source /usr/local/cargo /usr/local/cargo
COPY requirements-wheels.txt /tmp/requirements-wheels.txt
RUN /tmp/wheel-venv/bin/pip wheel --wheel-dir /wheels -r /tmp/requirements-wheels.txt

FROM ${BASE_IMAGE}
ENV container=docker
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y expect build-essential curl jq gettext git openssh-client pipx python3-dev python3-pip python3-psutil python3-requests python3-setuptools python3-venv software-properties-common sudo sshpass virtualenv wget 
RUN pipx install uv && ln -s /root/.local/bin/uv /usr/local/bin/uv

# Prebuilt  wheels so pip/pipx don't need a Rust toolchain in this imagec
ENV PIP_FIND_LINKS=/wheels
COPY --from=wheel-builder /wheels /wheels

RUN adduser -u 1000 --disabled-password ubuntu || /bin/true
RUN echo "ubuntu ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    echo 'Defaults:ubuntu env_keep += "http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY"' >> /etc/sudoers.d/ubuntu && \
    chmod 0440 /etc/sudoers.d/ubuntu
#Avoid sudo rlimit error
RUN echo "Set disable_coredump false" >> /etc/sudo.conf
USER ubuntu
WORKDIR /home/ubuntu
CMD [ "/bin/bash" ]
