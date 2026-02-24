#!/bin/bash
# Fetch images for each identifier and print the duration of each call

for id in \
  dillards-surepos-500-4852-e70-c38104 \
  dell-dgx-station-gb300-c38102 \
  hp-200-g2a-16-inch-notebook-pc5cd53931n2-c38114 \
  dell-pro-rugged-14-rb14250-c38119 \
  dell-pro-rugged-13-ra13250-c38118 \
  lenovo-thinkstation-p8-c38129 \
  dell-14-d14260-c38125 \
  c-rsb-3720-c38113 \
  dell-14-d14260-c38124 \
  hp-200-g2a-14-inch-notebook-pc000577145p-c38143 \
  nvidia-gb300-galaxy-c38090 \
  hp-200-g2i-14-inch-notebook-pc0005771495-c38145 \
  hp-200-g2i-14-inch-notebook-pc00057714gj-c38146 \
  hp-200-g2a-14-inch-notebook-pc000577141z-c38144 \
  hp-eliteboard-g1a-next-gen-ai-pc-c38148 \
  hp-eliteboard-g1a-next-gen-ai-pc-c38147 \
  dell-15-d15265-c38157 \
  dell-15-dc15250-0d78-c38155 \
  dell-pro-essential-15-pv15265-c38156 \
  dell-15-d15265-c38158 \
  dell-pro-15-essential-pv15250-0de3-c38159 \
  dell-pro-15-essential-pv15260-c38161 \
  dell-15-dc15260-c38162 \
  dell-15-dc15260-c38160 \
  hp-200-g2a-14-inch-notebook-pc0005771449-c38164 \
  hp-200-g2a-14-inch-notebook-pc0005771424-c38163 \
  hp-200-g2i-14-inch-notebook-pc000577148t-c38165 \
  hp-200-g2i-14-inch-notebook-pc00057714gv-c38166 \
  qualcomm-rb4-qcs8275-c38153 \
  hp-z6-g5-a-workstation-desktop-pc-c38168 \
  hp-z6-g5-a-workstation-desktop-pc-c38169 \
  hp-z6-g5-a-workstation-desktop-pc-c38170 \
  nvidia-jetson-agx-thor-c38072 \
  rpiz2-003 \
  rpiz2-004 \
  rpiz2-002 \
  dell-pro-micro-thin-client-q9m1260-c38022 \
  mediatek-g520-evk-c36941 \
  nvidia-n1x-gb10-soc-c38082 \
  nvidia-n1x-gb10-soc-c38084 \
  nvidia-n1x-gb10-soc-c38081 \
  nvidia-n1x-gb10-soc-c38083 \
  nvidia-n1x-gb10-soc-c38080 \
  pune-002 \
  shiner-beats-essential-001 \
  carrier-imx-9331-c38052 \
  lenovo-thinkstation-p5-gen2-c38192 \
  nvidia-igx-thor-developer-kit-c38099 \
  nvidia-igx-thor-developer-kit-c38100 \
  hp-pro-mini-400-g9-desktop-pc-c38193 \
  dell-pro-precision-7-14-pw714260-c38195 \
  dell-pro-precision-7-16-pw716260-c38196 \
  canonical-mcimx6ull-evk-c36783 \
  rpi5b16g-001 \
  canonical-mcimx93-qsb-c36158

do
  start=$(date +%s%3N)
  curl -s "https://testflinger.canonical.com/v1/agents/images/$id" > /dev/null
  end=$(date +%s%3N)
  duration=$((end - start))
  echo "$id: ${duration}ms"
done
