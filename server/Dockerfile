FROM ubuntu:22.04
COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /uvx /bin/

ENV DEBIAN_FRONTEND noninteractive
ENV HOME /root
ENV LC_ALL C.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
ENV PATH /srv/testflinger:$PATH
ENV UV_SYSTEM_PYTHON=true
# Enable this if you prefer to use testflinger.conf
# ENV TESTFLINGER_CONFIG=/srv/testflinger/testflinger.conf

# Install dependencies
RUN apt-get update \
  && apt-get install -y \
  --no-install-recommends \
  curl \
  git \
  procps \
  wget
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /var/log/testflinger \
  && chmod 755 /var/log/testflinger

# clone src in volume dir
WORKDIR /srv/testflinger
COPY . /srv/testflinger

# Install testflinger
RUN uv sync --frozen

CMD uv run gunicorn --bind 0.0.0.0:5000 app:app