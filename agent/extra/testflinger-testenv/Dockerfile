ARG BASE_IMAGE=ubuntu:20.04
FROM ${BASE_IMAGE}
ENV container=docker
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y expect build-essential curl jq gettext git openssh-client pipx python3-dev python3-pip python3-psutil python3-requests python3-setuptools python3-venv software-properties-common sudo sshpass virtualenv wget 
RUN adduser -u 1000 --disabled-password ubuntu || /bin/true
RUN echo "ubuntu ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    chmod 0440 /etc/sudoers.d/ubuntu
#Avoid sudo rlimit error
RUN echo "Set disable_coredump false" >> /etc/sudo.conf
USER ubuntu
WORKDIR /home/ubuntu
CMD [ "/bin/bash" ]
