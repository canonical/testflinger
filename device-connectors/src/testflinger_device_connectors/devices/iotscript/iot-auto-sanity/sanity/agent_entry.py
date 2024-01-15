import argparse
from sanity.agent import start_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sanity-launcher",
        help="the launcher configuration for iot sanity",
        required=True,
    )
    args = parser.parse_args()

    start_agent(args.sanity_launcher)
