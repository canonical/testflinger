ARG BASE_IMAGE=ubuntu:22.04

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
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    expect build-essential curl jq gettext git openssh-client pipx python3-dev \
    python3-pip python3-psutil python3-requests python3-setuptools python3-venv \
    software-properties-common sudo sshpass virtualenv wget lsb-release
RUN pipx install uv && ln -s /root/.local/bin/uv /usr/local/bin/uv

RUN adduser -u 1000 --disabled-password ubuntu || /bin/true
RUN echo "ubuntu ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    echo 'Defaults:ubuntu env_keep += "http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY"' >> /etc/sudoers.d/ubuntu && \
    chmod 0440 /etc/sudoers.d/ubuntu
#Avoid sudo rlimit error
RUN echo "Set disable_coredump false" >> /etc/sudo.conf

# Prebuilt wheels so pip/pipx don't need a Rust toolchain in this image
ENV PIP_FIND_LINKS=/wheels
COPY --from=wheel-builder /wheels /wheels

# Everything below this line is run as the ubuntu user
USER ubuntu
WORKDIR /home/ubuntu

# Fetch certification-lab-ci-tools pinned to a full commit hash
ARG TOOLS_REPO="https://github.com/canonical/certification-lab-ci-tools.git"
ARG TOOLS_PATH="/home/ubuntu/tools"
ARG COMMIT_HASH="09ec8009c6554a2b24505b1a1c16bc94a7231d48"
RUN git init -q ${TOOLS_PATH} && \
    git -C ${TOOLS_PATH} fetch -q --depth 1 ${TOOLS_REPO} ${COMMIT_HASH} && \
    git -C ${TOOLS_PATH} checkout -q --detach FETCH_HEAD && \
    test "$(git -C ${TOOLS_PATH} rev-parse HEAD)" = "${COMMIT_HASH}" && \
    rm -rf ${TOOLS_PATH}/.git
LABEL com.canonical.testflinger.tools-commit="${COMMIT_HASH}"

# Install cert-tools packages via pipx
RUN pipx install ${TOOLS_PATH}/cert-tools/launcher && \
    pipx install ${TOOLS_PATH}/cert-tools/toolbox && \
    pipx install ${TOOLS_PATH}/cert-tools/snapstore && \
    pipx inject toolbox ${TOOLS_PATH}/cert-tools/snapstore

# Append scriptlets and ~/.local/bin to PATH
ARG SCRIPTLETS_PATH="${TOOLS_PATH}/scriptlets"
ENV PATH="${PATH}:${SCRIPTLETS_PATH}:${SCRIPTLETS_PATH}/sru-helpers:/home/ubuntu/.local/bin"
# Used by the `_run` scriptlet to locate scriptlets on the device
ENV TOOLS_PATH_DEVICE=".scriptlets"

CMD [ "/bin/bash" ]
