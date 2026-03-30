"""
Interactive Burst Simulator & Monitoring Console
Allows real-time adjustment of streaming parameters and monitoring of producer state.
Useful for testing how the system handles varying load patterns.
"""

import json
import time
import threading
import logging
from datetime import datetime
from typing import Optional

import numpy as np

from streaming_producer import (
    StatefulStreamProducer,
    LocalFileBackend,
    DataCenterConfig,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BurstSimulator:
    """
    Simulates different load patterns by adjusting the producer interval.
    Patterns:
    - normal: Regular 60s intervals
    - gradual_spike: Linearly decrease interval to simulate burst
    - sudden_spike: Immediate interval drop
    - oscillating: Rhythmic spike pattern
    """

    def __init__(self, producer: StatefulStreamProducer):
        self.producer = producer
        self.is_running = False
        self.current_pattern = "normal"
        self.thread: Optional[threading.Thread] = None

    def pattern_normal(self, duration_seconds: int = 300):
        """Maintain normal 60s interval."""
        logger.info(f"Starting NORMAL pattern for {duration_seconds}s")
        self.producer.set_interval(60.0)
        end_time = time.time() + duration_seconds
        while self.is_running and time.time() < end_time:
            time.sleep(1)

    def pattern_gradual_spike(self, duration_seconds: int = 300, min_interval: float = 1.0):
        """Gradually decrease interval to simulate workload spike."""
        logger.info(f"Starting GRADUAL_SPIKE pattern: {duration_seconds}s, min_interval={min_interval}s")
        
        start_time = time.time()
        while self.is_running and (time.time() - start_time) < duration_seconds:
            elapsed = time.time() - start_time
            # Linear interpolation from 60s to min_interval
            progress = elapsed / duration_seconds
            interval = 60.0 - (progress * (60.0 - min_interval))
            interval = max(interval, min_interval)
            
            self.producer.set_interval(interval)
            time.sleep(2)  # Update interval every 2 seconds

    def pattern_sudden_spike(self, duration_seconds: int = 120, spike_interval: float = 0.5):
        """Sudden drop to simulate unexpected traffic spike."""
        logger.info(f"Starting SUDDEN_SPIKE pattern: {duration_seconds}s at {spike_interval}s interval")
        self.producer.set_interval(spike_interval)
        
        end_time = time.time() + duration_seconds
        while self.is_running and time.time() < end_time:
            time.sleep(1)

    def pattern_oscillating(self, duration_seconds: int = 600, cycle_seconds: int = 60):
        """Oscillating pattern: normal -> spike -> normal (repeating)."""
        logger.info(f"Starting OSCILLATING pattern: {duration_seconds}s, cycle={cycle_seconds}s")
        
        start_time = time.time()
        while self.is_running and (time.time() - start_time) < duration_seconds:
            elapsed = time.time() - start_time
            position_in_cycle = (elapsed % cycle_seconds) / cycle_seconds
            
            # Sine wave oscillation between 60s and 1s
            interval = 30 + 29 * np.sin(position_in_cycle * 2 * np.pi)
            interval = max(interval, 0.5)
            
            self.producer.set_interval(interval)
            time.sleep(0.5)

    def run_pattern(self, pattern_name: str, **kwargs):
        """Run a pattern in a background thread."""
        pattern_func = getattr(self, f"pattern_{pattern_name}", None)
        if not pattern_func:
            logger.error(f"Unknown pattern: {pattern_name}")
            return False

        if self.thread and self.thread.is_alive():
            logger.warning("Pattern already running. Stop it first.")
            return False

        self.is_running = True
        self.current_pattern = pattern_name
        self.thread = threading.Thread(target=pattern_func, kwargs=kwargs, daemon=True)
        self.thread.start()
        return True

    def stop_pattern(self):
        """Stop current pattern."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"Pattern '{self.current_pattern}' stopped")


class ProducerMonitor:
    """Monitor and display producer statistics in real-time."""

    def __init__(self, producer: StatefulStreamProducer, update_interval: float = 5.0):
        self.producer = producer
        self.update_interval = update_interval
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

    def run(self):
        """Start monitoring in background thread."""
        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop monitoring."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _monitor_loop(self):
        """Continuous monitoring loop."""
        while self.is_running:
            stats = self.producer.get_stats()
            self._print_stats(stats)
            time.sleep(self.update_interval)

    @staticmethod
    def _print_stats(stats: dict):
        """Pretty-print statistics."""
        uptime_min = stats["uptime_seconds"] / 60
        print(
            f"\n{'='*70}"
            f"\nProducer Stats | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            f"\n{'='*70}"
            f"\n  Batches Generated:     {stats['batch_count']:,}"
            f"\n  Messages Sent:         {stats['messages_sent']:,}"
            f"\n  Messages Failed:       {stats['messages_failed']:,}"
            f"\n  Success Rate:          {(stats['messages_sent'] / max(1, stats['messages_sent'] + stats['messages_failed']) * 100):.1f}%"
            f"\n  Throughput:            {stats['messages_per_minute']:.1f} batches/min"
            f"\n  Uptime:                {uptime_min:.1f} minutes"
            f"\n{'='*70}\n"
        )


class InteractiveConsole:
    """Interactive CLI for controlling the producer and simulator."""

    def __init__(self, producer: StatefulStreamProducer):
        self.producer = producer
        self.simulator = BurstSimulator(producer)
        self.monitor = ProducerMonitor(producer)

    def print_help(self):
        """Print available commands."""
        help_text = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    Data Center Stream Producer Console                      ║
╚════════════════════════════════════════════════════════════════════════════╝

PRODUCER COMMANDS:
  stats                 - Show current producer statistics
  interval <seconds>    - Set interval (e.g., 'interval 5' for 5 second intervals)
  
PATTERN COMMANDS (Burst Simulation):
  pattern normal [duration]           - Normal operation (default 300s)
  pattern gradual [duration] [min]    - Gradual spike (default 300s, min 1s)
  pattern sudden [duration] [interval] - Sudden spike (default 120s at 0.5s)
  pattern oscillate [duration] [cycle] - Oscillating load (default 600s, cycle 60s)
  stop-pattern                        - Stop current pattern
  
MONITORING:
  monitor on/off        - Enable/disable stats monitoring
  
GENERAL:
  help                  - Show this message
  quit/exit             - Gracefully shutdown producer

EXAMPLES:
  >>> interval 1              # Change to 1 second intervals
  >>> pattern sudden 60 0.1   # 60 second spike at 100ms intervals
  >>> pattern gradual 300 0.5 # 5 minute gradual spike down to 0.5s intervals
  >>> monitor on              # Enable real-time monitoring
        """
        print(help_text)

    def handle_command(self, command: str):
        """Parse and execute user command."""
        parts = command.strip().split()
        if not parts:
            return

        cmd = parts[0].lower()

        try:
            if cmd == "help":
                self.print_help()

            elif cmd == "stats":
                stats = self.producer.get_stats()
                print(json.dumps(stats, indent=2))

            elif cmd == "interval":
                if len(parts) < 2:
                    print("Usage: interval <seconds>")
                    return
                interval = float(parts[1])
                self.producer.set_interval(interval)
                print(f"✓ Interval set to {interval}s")

            elif cmd == "pattern":
                if len(parts) < 2:
                    print("Usage: pattern <normal|gradual|sudden|oscillate> [duration] [param]")
                    return

                pattern = parts[1].lower()
                duration = int(parts[2]) if len(parts) > 2 else None
                param = float(parts[3]) if len(parts) > 3 else None

                kwargs = {}
                if duration:
                    kwargs["duration_seconds"] = duration
                if param:
                    if pattern == "gradual":
                        kwargs["min_interval"] = param
                    elif pattern == "sudden":
                        kwargs["spike_interval"] = param
                    elif pattern == "oscillate":
                        kwargs["cycle_seconds"] = int(param)

                self.simulator.run_pattern(pattern, **kwargs)
                print(f"✓ Pattern '{pattern}' started")

            elif cmd == "stop-pattern":
                self.simulator.stop_pattern()
                self.producer.set_interval(60.0)  # Reset to normal

            elif cmd == "monitor":
                if len(parts) < 2:
                    print("Usage: monitor <on|off>")
                    return
                if parts[1].lower() == "on":
                    self.monitor.run()
                    print("✓ Monitoring started (updates every 5s)")
                else:
                    self.monitor.stop()
                    print("✓ Monitoring stopped")

            elif cmd in ["quit", "exit"]:
                print("Shutting down...")
                return False

            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")

        except Exception as e:
            print(f"Error: {e}")

        return True

    def run(self):
        """Start interactive console."""
        print("\n" + "="*80)
        print("Data Center Stream Producer - Interactive Console")
        print("Type 'help' for available commands")
        print("="*80 + "\n")

        self.print_help()

        while True:
            try:
                command = input("\n>>> ").strip()
                if not self.handle_command(command):
                    break
            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except EOFError:
                break

        self.monitor.stop()


def demo():
    """
    Demonstration: Show how burst simulation works.
    This runs non-interactively to demonstrate the system.
    """
    logger.info("Starting demo: Normal operation -> Burst -> Normal")

    # Create producer with local file backend
    config = DataCenterConfig(num_servers=50, num_racks=5)
    backend = LocalFileBackend("/tmp/demo_stream")
    producer = StatefulStreamProducer(config, backend, interval_seconds=60.0)

    # Start producer in background
    producer_thread = threading.Thread(target=producer.run, args=(None,), daemon=True)
    producer_thread.start()

    # Initialize simulator and monitor
    simulator = BurstSimulator(producer)
    monitor = ProducerMonitor(producer, update_interval=10.0)
    monitor.run()

    # Run demo patterns
    patterns = [
        ("normal", {"duration_seconds": 60}),
        ("gradual_spike", {"duration_seconds": 60, "min_interval": 0.5}),
        ("sudden_spike", {"duration_seconds": 30, "spike_interval": 0.1}),
        ("normal", {"duration_seconds": 60}),
    ]

    for pattern_name, kwargs in patterns:
        logger.info(f"Running pattern: {pattern_name}")
        simulator.run_pattern(pattern_name, **kwargs)
        time.sleep(kwargs.get("duration_seconds", 60) + 5)

    # Cleanup
    producer.shutdown()
    monitor.stop()
    logger.info("Demo completed")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        # Create producer (will be controlled via console)
        config = DataCenterConfig(num_servers=100, num_racks=10)
        backend = LocalFileBackend("/tmp/data_center_stream")
        producer = StatefulStreamProducer(config, backend, interval_seconds=60.0)

        # Start producer in background
        producer_thread = threading.Thread(target=producer.run, args=(None,), daemon=True)
        producer_thread.start()

        # Run console
        console = InteractiveConsole(producer)
        console.run()

        # Cleanup
        producer.shutdown()
