FROM ubuntu:24.04

# normal settings
ENV TZ=Asia/Taipei \
    LANG=C.UTF-8 \
    CONFIG_DIR=/tmp/config \
    INFLUX_HOST=localhost \
    INFLUX_PORT=8086 \
    INFLUX_USER=testflinger-agent \
    INFLUX_PW=testflinger-agent

# device-connectors default config
ENV DC_CONFIG=device-connectors.yaml \
    DC_DUT_IP=127.0.0.1 \
    DC_DUT_SID=aabbccdd \
    DC_NODE_ID= \
    DC_NODE_NAME=core-taipei-testflinger \
    DC_AGENT_NAME=staging-tfagent-cid-REPLACE_TO_HOSTNAME \
    DC_MASS_USER=bot \
    DC_TIMEOUT=120

# testflinger-agent default config
ENV AGENT_CONFIG=agent.yaml \
    AGENT_ID=${DC_AGENT_NAME} \
    TESTFLINGER_SERVER=https://testflinger.canonical.com \
    AGENT_TIMEOUT=43200 \
    AGENT_OUTPUT_TIMEOUT=9000 \
    AGENT_EXEC_DIR=/testflinger/run/ \
    AGENT_LOG_DIR=/testflinger/log/ \
    AGENT_RESULT_DIR=/testflinger/result/ \
    AGENT_LOG_LEVEL=DEBUG \
    AGENT_JOB_QUEUE=staging-job-cid-REPLACE_TO_HOSTNAME \
    AGENT_SET_CMD=/bin/true \
    AGENT_PROV_CMD=/bin/true \
    AGENT_TEST_CMD="PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 testflinger-device-connector maas2 runtest -c ${CONFIG_DIR}/${DC_CONFIG} testflinger.json" \
    AGENT_CLEAN_CMD=/bin/true


# python
ARG PYTHON=python3

# preinstall packages
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get -y install \
               software-properties-common \
               gpg \
               ca-certificates \
               curl \
               git \
               git-lfs \
               netbase \
               less \
               openssh-client \
               patch \
               tzdata \
               python3-pip \
               python3-dev \
               ssh-import-id \
               jq \
               sshpass \
               build-essential && \
     apt-get clean && \
     rm -rf /tmp/* /var/cache/* /usr/share/doc/* /usr/share/man/* /var/lib/apt/lists/*

# For security reason, the code below should run with non-root.
# However, we have to install checkbox by apt command
# from testflinger-agent itself to get more flexiblity.
# Please use rootless mode to install Docker, nerdctl or podman.

# install testflinger-agent testflinger-cli and device-connectors
RUN git clone https://github.com/canonical/testflinger.git && \
    cd testflinger && \
    ${PYTHON} -m pip install pip -U && \
    ${PYTHON} -m pip install -I agent/ && \
    ${PYTHON} -m pip install -I device-connectors/ && \
    ${PYTHON} -m pip install -I cli/ && \
    rm -rf *

# create agent working dir
RUN mkdir -p ${AGENT_EXEC_DIR} ${AGENT_LOG_DIR} ${AGENT_RESULT_DIR} ${CONFIG_DIR}

COPY --chmod=0111 agent.sh ./

CMD ["./agent.sh"]
