"""
CampusNet: Congestion Detection Service
Analyzes segment metrics against configurable demonstration thresholds.
Distinguishes single-sample spikes from persistent congestion and generates explainable alerts.

DISCLAIMER: Heuristic threshold crossings identify observed traffic strain;
they do not constitute definitive proof of physical cable cuts or hardware failure.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class CongestionDetector:
    """
    Evaluates segment metrics and detects congestion events.
    """
    def __init__(
        self,
        warn_util: float = 70.0,
        crit_util: float = 85.0,
        warn_lat: float = 50.0,
        crit_lat: float = 100.0,
        warn_loss: float = 1.0,
        crit_loss: float = 3.0
    ):
        self.warn_util = warn_util
        self.crit_util = crit_util
        self.warn_lat = warn_lat
        self.crit_lat = crit_lat
        self.warn_loss = warn_loss
        self.crit_loss = crit_loss

    def evaluate_segment(
        self,
        segment: Dict[str, Any],
        historical_consecutive_triggers: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Evaluates a single segment against all metric thresholds.
        Returns a list of generated alert dictionaries.
        """
        alerts = []
        seg_id = segment.get("id", "unknown")
        seg_name = segment.get("name", "Unknown Segment")
        data_source = segment.get("data_source", "SIMULATED")
        now = datetime.now(timezone.utc).isoformat()

        # 1. Utilization Check
        util = segment.get("utilization_pct")
        if util is not None:
            try:
                util_val = float(util)
                if util_val >= self.crit_util:
                    alerts.append({
                        "segment_id": seg_id,
                        "segment_name": seg_name,
                        "metric_name": "utilization",
                        "observed_value": round(util_val, 2),
                        "threshold_value": self.crit_util,
                        "severity": "CRITICAL",
                        "trigger_rule": f"Utilization >= {self.crit_util}%",
                        "explanation": (
                            f"{seg_name} is operating at critical utilization ({util_val:.1f}%), "
                            f"exceeding the demo critical threshold of {self.crit_util}%. "
                            f"Queue buffer saturation and packet drop risk are elevated."
                        ),
                        "recommended_action": (
                            f"Apply QoS rate-limiting to low-priority flows in {seg_name} "
                            f"or reallocate unreserved link capacity from underutilized segments."
                        ),
                        "is_persistent": 1 if historical_consecutive_triggers >= 1 else 0,
                        "timestamp": now,
                        "data_source": data_source
                    })
                elif util_val >= self.warn_util:
                    alerts.append({
                        "segment_id": seg_id,
                        "segment_name": seg_name,
                        "metric_name": "utilization",
                        "observed_value": round(util_val, 2),
                        "threshold_value": self.warn_util,
                        "severity": "WARNING",
                        "trigger_rule": f"Utilization >= {self.warn_util}%",
                        "explanation": (
                            f"{seg_name} is operating at warning utilization ({util_val:.1f}%), "
                            f"crossing the warning threshold of {self.warn_util}%. Headroom is narrow."
                        ),
                        "recommended_action": (
                            f"Monitor traffic surge in {seg_name}. Prepare dynamic QoS priority reprioritization "
                            f"if load continues to trend upward."
                        ),
                        "is_persistent": 1 if historical_consecutive_triggers >= 1 else 0,
                        "timestamp": now,
                        "data_source": data_source
                    })
            except (ValueError, TypeError):
                pass

        # 2. Latency Check (only if metric is supplied)
        lat = segment.get("latency_ms")
        if lat is not None:
            try:
                lat_val = float(lat)
                if lat_val >= self.crit_lat:
                    alerts.append({
                        "segment_id": seg_id,
                        "segment_name": seg_name,
                        "metric_name": "latency",
                        "observed_value": round(lat_val, 2),
                        "threshold_value": self.crit_lat,
                        "severity": "CRITICAL",
                        "trigger_rule": f"Latency >= {self.crit_lat}ms",
                        "explanation": (
                            f"{seg_name} round-trip delay is {lat_val:.1f}ms, crossing the critical limit "
                            f"of {self.crit_lat}ms. Real-time video lectures and interactive terminals will degrade."
                        ),
                        "recommended_action": (
                            f"Enable DSCP Expedited Forwarding (EF) queueing for interactive traffic "
                            f"and reduce buffer depths to minimize bufferbloat."
                        ),
                        "is_persistent": 1 if historical_consecutive_triggers >= 1 else 0,
                        "timestamp": now,
                        "data_source": data_source
                    })
                elif lat_val >= self.warn_lat:
                    alerts.append({
                        "segment_id": seg_id,
                        "segment_name": seg_name,
                        "metric_name": "latency",
                        "observed_value": round(lat_val, 2),
                        "threshold_value": self.warn_lat,
                        "severity": "WARNING",
                        "trigger_rule": f"Latency >= {self.warn_lat}ms",
                        "explanation": (
                            f"{seg_name} observed latency ({lat_val:.1f}ms) crossed the warning threshold "
                            f"of {self.warn_lat}ms."
                        ),
                        "recommended_action": (
                            f"Inspect segment queuing delay and ensure delay-sensitive classes have strict priority."
                        ),
                        "is_persistent": 1 if historical_consecutive_triggers >= 1 else 0,
                        "timestamp": now,
                        "data_source": data_source
                    })
            except (ValueError, TypeError):
                pass

        # 3. Packet Loss Check (only if metric is supplied)
        loss = segment.get("packet_loss_pct")
        if loss is not None:
            try:
                loss_val = float(loss)
                if loss_val >= self.crit_loss:
                    alerts.append({
                        "segment_id": seg_id,
                        "segment_name": seg_name,
                        "metric_name": "packet_loss",
                        "observed_value": round(loss_val, 2),
                        "threshold_value": self.crit_loss,
                        "severity": "CRITICAL",
                        "trigger_rule": f"Packet Loss >= {self.crit_loss}%",
                        "explanation": (
                            f"{seg_name} exhibits {loss_val:.2f}% packet loss, exceeding the critical limit "
                            f"of {self.crit_loss}%. TCP retransmissions will trigger exponential backoff and stall throughput."
                        ),
                        "recommended_action": (
                            f"Immediate bandwidth guarantee enforcement required. Throttle non-critical background traffic "
                            f"to prevent tail-drop queuing."
                        ),
                        "is_persistent": 1 if historical_consecutive_triggers >= 1 else 0,
                        "timestamp": now,
                        "data_source": data_source
                    })
                elif loss_val >= self.warn_loss:
                    alerts.append({
                        "segment_id": seg_id,
                        "segment_name": seg_name,
                        "metric_name": "packet_loss",
                        "observed_value": round(loss_val, 2),
                        "threshold_value": self.warn_loss,
                        "severity": "WARNING",
                        "trigger_rule": f"Packet Loss >= {self.warn_loss}%",
                        "explanation": (
                            f"{seg_name} shows {loss_val:.2f}% packet drop, crossing the demo warning limit of {self.warn_loss}%."
                        ),
                        "recommended_action": (
                            f"Audit interface egress drops and verify RED/WRED queueing policy."
                        ),
                        "is_persistent": 1 if historical_consecutive_triggers >= 1 else 0,
                        "timestamp": now,
                        "data_source": data_source
                    })
            except (ValueError, TypeError):
                pass

        return alerts

    def evaluate_all(self, segments: List[Dict[str, Any]], history_map: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
        """
        Evaluates a collection of segments and aggregates all alerts.
        """
        all_alerts = []
        h_map = history_map or {}
        for seg in segments:
            seg_id = seg.get("id", "")
            prev_triggers = h_map.get(seg_id, 0)
            alerts = self.evaluate_segment(seg, historical_consecutive_triggers=prev_triggers)
            all_alerts.extend(alerts)
        return all_alerts
