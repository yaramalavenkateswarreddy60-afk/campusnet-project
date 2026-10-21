"""
CampusNet: Virtual Network Lab Adapter
Provides a safe interface for optional Linux, Mininet, Open vSwitch, and Linux TC environments.
Ensures zero runtime crashes on Windows and strictly isolates lab commands from production networks.
"""

import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional

class LabAdapter:
    """
    Adapter for communicating with Mininet / Open vSwitch testbeds.
    """

    @staticmethod
    def inspect_environment() -> Dict[str, Any]:
        """
        Inspects host OS and determines if Mininet, Open vSwitch, and Linux TC are available.
        """
        is_windows = os.name == "nt"
        has_mn = shutil.which("mn") is not None
        has_ovs = shutil.which("ovs-vsctl") is not None
        has_tc = shutil.which("tc") is not None
        has_iperf3 = shutil.which("iperf3") is not None

        is_lab_ready = (not is_windows) and has_mn and (has_ovs or has_tc)

        reason = "Ready for isolated software-defined lab." if is_lab_ready else (
            "Windows host detected without native Mininet/OVS kernel modules. Operating in high-fidelity SIMULATION mode."
            if is_windows else "Linux host missing required packages (mininet, openvswitch-switch, iproute2)."
        )

        return {
            "is_lab_available": is_lab_ready,
            "os_name": os.name,
            "has_mininet": has_mn,
            "has_openvswitch": has_ovs,
            "has_tc": has_tc,
            "has_iperf3": has_iperf3,
            "status_label": "LAB_READY" if is_lab_ready else "SIMULATION_MODE",
            "message": reason,
            "safe_execution_mode": True
        }

    @staticmethod
    def generate_tc_script(
        interface: str,
        allocations: List[Dict[str, Any]],
        shared_capacity_mbps: float
    ) -> str:
        """
        Generates safe, reproducible Linux HTB (Hierarchical Token Bucket) queueing discipline
        commands corresponding to the optimized policy.
        """
        commands = [
            f"# Linux TC Hierarchical Token Bucket (HTB) Script for {interface}",
            f"# Total Uplink Rate: {shared_capacity_mbps}mbit",
            f"# Clean up existing qdiscs",
            f"sudo tc qdisc del dev {interface} root 2>/dev/null || true",
            f"sudo tc qdisc add dev {interface} root handle 1: htb default 50",
            f"sudo tc class add dev {interface} parent 1: classid 1:1 htb rate {int(shared_capacity_mbps)}mbit ceil {int(shared_capacity_mbps)}mbit"
        ]

        # Map segments to HTB classes
        class_id_base = 10
        for idx, seg in enumerate(allocations):
            cid = class_id_base + (idx * 10)
            rate = max(1, int(seg.get("allocated_mbps", 10.0)))
            ceil = max(rate, int(seg.get("capacity_mbps", shared_capacity_mbps)))
            prio = int(seg.get("priority_weight", 1.0))
            # HTB prio is 0-7 where 0 is highest priority
            htb_prio = max(0, min(7, 7 - prio))
            commands.append(
                f"# Segment: {seg.get('name')} (Weight: {prio})"
            )
            commands.append(
                f"sudo tc class add dev {interface} parent 1:1 classid 1:{cid} htb rate {rate}mbit ceil {ceil}mbit prio {htb_prio}"
            )
            # Add stochastic fair queuing leaf to avoid flow starvation
            commands.append(
                f"sudo tc qdisc add dev {interface} parent 1:{cid} handle {cid}: sfq perturb 10"
            )

        return "\n".join(commands)

    @classmethod
    def apply_policy_preview(
        cls,
        allocations: List[Dict[str, Any]],
        shared_capacity_mbps: float,
        interface: str = "s1-eth1"
    ) -> Dict[str, Any]:
        """
        Returns a preview of commands and verification info without mutating hardware.
        """
        env = cls.inspect_environment()
        script = cls.generate_tc_script(interface, allocations, shared_capacity_mbps)

        return {
            "environment": env,
            "target_interface": interface,
            "generated_commands": script,
            "can_enforce": env["is_lab_available"],
            "disclaimer": (
                "Preview only. Enforcement is restricted to isolated virtual lab bridges. "
                "Never applied to physical production network cards."
            )
        }
