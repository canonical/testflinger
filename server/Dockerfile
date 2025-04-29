FROM ubuntu:22.04

# Set up uv
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /uvx /bin/
ENV UV_SYSTEM_PYTHON=true

WORKDIR /srv/testflinger
ENV PATH="/srv/testflinger:$PATH"

ENV HOME /root
ENV LC_ALL C.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
# Enable this if you prefer to use testflinger.conf
# ENV TESTFLINGER_CONFIG=/srv/testflinger/testflinger.conf

# Install dependencies
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update \
  && apt-get install -y \
  --no-install-recommends \
  curl \
  git \
  procps \
  wget
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p -m 755 /var/log/testflinger

# Install the project dependencies using lock file and settings
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-dev

# Add the rest of the project and install testflinger (optimal layer caching)
ADD . /srv/testflinger
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev

# Run the testflinger server
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
