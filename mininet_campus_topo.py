#!/usr/bin/env python3
"""
CampusNet: Mininet Virtual Campus Network Topology
Optional advanced network lab script for Linux / WSL2 environments.

Topology:
  [h_lab]   (Computer Lab)       ---\
  [h_class] (Smart Classrooms)   ----\
  [h_lib]   (Library)            ---- [s1: Gateway Core Switch] ==== [h_gw: Internet Uplink]
  [h_admin] (Administration)     ----/
  [h_guest] (Guest Wi-Fi)        ---/

Usage (Requires Linux root/sudo with Mininet and Open vSwitch installed):
  sudo python3 mininet_campus_topo.py
"""

import sys
import time

try:
    from mininet.net import Mininet
    from mininet.node import Controller, RemoteController, OVSKernelSwitch
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info
    from mininet.link import TCLink
except ImportError:
    print("[ERROR] Mininet is not installed in this Python environment.")
    print("This script is an optional advanced lab component for Linux / WSL2.")
    print("The core CampusNet web application runs independently on Windows without Mininet.")
    sys.exit(0)


def build_campus_network():
    """Builds and starts the 5-segment virtual campus testbed."""
    net = Mininet(controller=Controller, switch=OVSKernelSwitch, link=TCLink)

    info("*** Adding Controller\n")
    net.addController("c0")

    info("*** Adding Core Switch\n")
    s1 = net.addSwitch("s1")

    info("*** Adding Segment Hosts\n")
    h_lab   = net.addHost("h_lab",   ip="10.0.1.10/24", mac="00:00:00:00:01:01")
    h_class = net.addHost("h_class", ip="10.0.2.10/24", mac="00:00:00:00:02:01")
    h_lib   = net.addHost("h_lib",   ip="10.0.3.10/24", mac="00:00:00:00:03:01")
    h_admin = net.addHost("h_admin", ip="10.0.4.10/24", mac="00:00:00:00:04:01")
    h_guest = net.addHost("h_guest", ip="10.0.5.10/24", mac="00:00:00:00:05:01")

    # Internet / Campus Gateway host
    h_gw = net.addHost("h_gw", ip="10.0.0.1/24", mac="00:00:00:00:00:01")

    info("*** Creating Links with Modeled Capacities\n")
    # Gateway link modeled at 800 Mbps shared bandwidth (scaled to 80 Mbps in local lab if constrained)
    net.addLink(s1, h_gw, bw=100, delay="2ms", loss=0)

    # Segment links
    net.addLink(h_lab,   s1, bw=30, delay="10ms")
    net.addLink(h_class, s1, bw=25, delay="15ms")
    net.addLink(h_lib,   s1, bw=15, delay="5ms")
    net.addLink(h_admin, s1, bw=10, delay="2ms")
    net.addLink(h_guest, s1, bw=20, delay="25ms")

    info("*** Starting Network\n")
    net.start()

    info("*** Configuring Linux TC QoS Queues on Switch Egress\n")
    # Apply TC Hierarchical Token Bucket (HTB) on core switch egress port to gateway (s1-eth1)
    s1.cmd("tc qdisc del dev s1-eth1 root 2>/dev/null || true")
    s1.cmd("tc qdisc add dev s1-eth1 root handle 1: htb default 50")
    s1.cmd("tc class add dev s1-eth1 parent 1: classid 1:1 htb rate 100mbit ceil 100mbit")

    # Classes: Admin (Class 10, prio 0), Smart Class (Class 20, prio 1), Computer Lab (Class 30, prio 2), Library (Class 40, prio 3), Guest (Class 50, prio 4)
    s1.cmd("tc class add dev s1-eth1 parent 1:1 classid 1:10 htb rate 15mbit ceil 20mbit prio 0")
    s1.cmd("tc class add dev s1-eth1 parent 1:1 classid 1:20 htb rate 30mbit ceil 40mbit prio 1")
    s1.cmd("tc class add dev s1-eth1 parent 1:1 classid 1:30 htb rate 25mbit ceil 35mbit prio 2")
    s1.cmd("tc class add dev s1-eth1 parent 1:1 classid 1:40 htb rate 15mbit ceil 20mbit prio 3")
    s1.cmd("tc class add dev s1-eth1 parent 1:1 classid 1:50 htb rate 10mbit ceil 15mbit prio 4")

    info("*** Network Ready. Testing Connectivity...\n")
    net.pingAll()

    info("*** Starting Mininet Interactive CLI. Type 'exit' to terminate.\n")
    CLI(net)

    info("*** Stopping Network\n")
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    build_campus_network()
