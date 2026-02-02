"""
Real-Time Streaming Data Producer
Continuously generates and streams data center metrics to Kafka/Kinesis/Local.
Maintains state so data evolves naturally across cycles.
"""

import json
import logging
import os
import sys
import time
import signal
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import threading

import numpy as np

from synthetic_generator import (
    StreamDataGenerator,
    DataCenterConfig,
    SyntheticServerMetricsGenerator,
    SyntheticCoolingMetricsGenerator,
    SyntheticWeatherDataGenerator,
)


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data_producer.log"),
    ],
)
logger = logging.getLogger(__name__)


class OutputBackend(ABC):
    """Abstract base class for output backends (Kafka, Files, etc.)"""

    @abstractmethod
    def send(self, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        """Send message to backend. Returns True if successful."""
        pass

    @abstractmethod
    def close(self):
        """Clean up resources."""
        pass


class LocalFileBackend(OutputBackend):
    """Output to local JSON files (for testing/development)."""

    def __init__(self, output_dir: str = "/tmp/data_center_stream"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"LocalFileBackend initialized: {output_dir}")

    def send(self, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        try:
            timestamp = message.get("timestamp", datetime.now(timezone.utc).isoformat())
            # Create subdirectories by type and date
            date_str = timestamp[:10]  # YYYY-MM-DD
            type_dir = os.path.join(self.output_dir, date_str)
            os.makedirs(type_dir, exist_ok=True)

            # Write to separate files for each metric type
            for metric_type in ["server_metrics", "cooling_metrics", "weather_data"]:
                if metric_type in message:
                    file_path = os.path.join(
                        type_dir,
                        f"{metric_type}_{timestamp.replace(':', '-').replace('Z', '')}.jsonl",
                    )
                    with open(file_path, "a") as f:
                        if metric_type == "weather_data":
                            f.write(json.dumps(message[metric_type]) + "\n")
                        else:
                            for item in message[metric_type]:
                                f.write(json.dumps(item) + "\n")
            return True
        except Exception as e:
            logger.error(f"Error writing to file: {e}")
            return False

    def close(self):
        logger.info("LocalFileBackend closed")


class KafkaBackend(OutputBackend):
    """Output to Kafka topic (for production)."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "data-center-metrics",
    ):
        try:
            from kafka import KafkaProducer
            from kafka.errors import KafkaError

            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            self.topic = topic
            logger.info(
                f"KafkaBackend initialized: {bootstrap_servers}, topic: {topic}"
            )
        except ImportError:
            logger.error("Kafka library not installed. Use: pip install kafka-python")
            raise

    def send(self, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        try:
            # Send each metric type as separate messages for better partitioning
            timestamp = message.get("timestamp", "")

            # Server metrics
            if "server_metrics" in message:
                for metric in message["server_metrics"]:
                    self.producer.send(
                        f"{self.topic}-servers",
                        value=metric,
                        key=metric.get("server_id", "").encode("utf-8"),
                    )

            # Cooling metrics
            if "cooling_metrics" in message:
                for metric in message["cooling_metrics"]:
                    self.producer.send(
                        f"{self.topic}-cooling",
                        value=metric,
                        key=metric.get("chiller_id", "").encode("utf-8"),
                    )

            # Weather data
            if "weather_data" in message:
                self.producer.send(
                    f"{self.topic}-weather",
                    value=message["weather_data"],
                    key=timestamp.encode("utf-8"),
                )

            return True
        except Exception as e:
            logger.error(f"Error sending to Kafka: {e}")
            return False

    def close(self):
        if hasattr(self, "producer"):
            self.producer.close()
        logger.info("KafkaBackend closed")


class StdoutBackend(OutputBackend):
    """Output to stdout for monitoring."""

    def __init__(self, summarize: bool = True):
        self.summarize = summarize
        logger.info("StdoutBackend initialized")

    def send(self, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        try:
            if self.summarize:
                # Print summary instead of full JSON
                timestamp = message.get("timestamp")
                server_count = len(message.get("server_metrics", []))
                cooling_count = len(message.get("cooling_metrics", []))

                avg_cpu = np.mean(
                    [m["cpu_utilization"] for m in message.get("server_metrics", [])]
                )
                avg_power = np.mean(
                    [m["power_draw_watts"] for m in message.get("server_metrics", [])]
                )

                weather = message.get("weather_data", {})
                pue = next(
                    (
                        m["data_center_pue"]
                        for m in message.get("cooling_metrics", [])
                        if "data_center_pue" in m
                    ),
                    None,
                )

                print(
                    f"[{timestamp}] Servers: {server_count} | "
                    f"Avg CPU: {avg_cpu:.1f}% | Avg Power: {avg_power:.0f}W | "
                    f"PUE: {pue:.2f} | "
                    f"Outdoor: {weather.get('outdoor_temperature_celsius')}°C | "
                    f"Renewable Score: {weather.get('renewable_energy_score'):.0f}/100"
                )
            else:
                print(json.dumps(message, indent=2))
            return True
        except Exception as e:
            logger.error(f"Error printing to stdout: {e}")
            return False

    def close(self):
        logger.info("StdoutBackend closed")


class StatefulStreamProducer:
    """
    Main producer that maintains state and continuously streams data.
    Key features:
    - State persistence: Metrics evolve naturally across cycles
    - Configurable output backends
    - Dynamic interval adjustment for burst simulation
    - Graceful shutdown
    """

    def __init__(
        self,
        config: DataCenterConfig,
        backend: OutputBackend,
        interval_seconds: float = 60.0,
        num_servers_per_batch: Optional[int] = None,
    ):
        self.config = config
        self.backend = backend
        self.interval_seconds = interval_seconds
        self.num_servers_per_batch = num_servers_per_batch or config.num_servers

        # Initialize generators
        self.data_generator = StreamDataGenerator(config)

        # State tracking
        self.batch_count = 0
        self.messages_sent = 0
        self.messages_failed = 0
        self.start_time = datetime.now(timezone.utc)
        self.is_running = False

        # For dynamic interval adjustment
        self.interval_lock = threading.Lock()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(
            f"Producer initialized: interval={interval_seconds}s, "
            f"servers={config.num_servers}, batches_per_server={self.num_servers_per_batch}"
        )

    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received. Stopping producer...")
        self.is_running = False

    def set_interval(self, interval_seconds: float):
        """Dynamically change the interval (e.g., for burst simulation)."""
        with self.interval_lock:
            old_interval = self.interval_seconds
            self.interval_seconds = interval_seconds
            logger.info(f"Interval changed: {old_interval}s -> {interval_seconds}s")

    def get_stats(self) -> Dict[str, Any]:
        """Get producer statistics."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return {
            "batch_count": self.batch_count,
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "uptime_seconds": elapsed,
            "messages_per_minute": (
                (self.messages_sent / elapsed) * 60 if elapsed > 0 else 0
            ),
        }

    def run(self, max_batches: Optional[int] = None):
        """
        Main streaming loop.

        Args:
            max_batches: Stop after N batches (None = infinite)
        """
        self.is_running = True
        self.batch_count = 0
        current_time = datetime.now(timezone.utc)

        logger.info(f"Starting producer stream (max_batches={max_batches})...")

        try:
            while self.is_running:
                if max_batches and self.batch_count >= max_batches:
                    logger.info(f"Reached max batches ({max_batches}). Stopping.")
                    break

                # Generate batch
                batch = self.data_generator.generate_batch(current_time)

                # Send to backend
                if self.backend.send(batch):
                    self.messages_sent += 1
                else:
                    self.messages_failed += 1

                self.batch_count += 1

                # Log stats every 10 batches
                if self.batch_count % 10 == 0:
                    stats = self.get_stats()
                    logger.info(
                        f"Stats: Batches={stats['batch_count']}, "
                        f"Sent={stats['messages_sent']}, "
                        f"Failed={stats['messages_failed']}, "
                        f"Rate={stats['messages_per_minute']:.1f}/min"
                    )

                # Sleep with lock to allow dynamic adjustment
                with self.interval_lock:
                    interval = self.interval_seconds

                if interval > 0:
                    time.sleep(interval)

                # Advance time for next batch
                current_time += timedelta(seconds=interval)

        except Exception as e:
            logger.error(f"Error in producer loop: {e}", exc_info=True)
        finally:
            self.shutdown()

    def shutdown(self):
        """Clean shutdown."""
        self.is_running = False
        stats = self.get_stats()
        logger.info(
            f"Producer stopped. Final stats: "
            f"Batches={stats['batch_count']}, "
            f"Sent={stats['messages_sent']}, "
            f"Failed={stats['messages_failed']}, "
            f"Uptime={stats['uptime_seconds']:.1f}s"
        )
        self.backend.close()


def main():
    """Entry point for the producer."""
    parser = argparse.ArgumentParser(
        description="Real-time Data Center Metrics Producer"
    )

    # Data generation arguments
    parser.add_argument(
        "--num-servers",
        type=int,
        default=100,
        help="Number of servers to simulate",
    )
    parser.add_argument("--num-racks", type=int, default=10, help="Number of racks")
    parser.add_argument(
        "--num-chillers", type=int, default=4, help="Number of chillers"
    )

    # Streaming arguments
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Interval between batches in seconds (default: 60)",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Maximum batches to generate (None = infinite)",
    )

    # Output backend arguments
    parser.add_argument(
        "--backend",
        choices=["local", "kafka", "stdout"],
        default="stdout",
        help="Output backend",
    )
    parser.add_argument(
        "--kafka-servers",
        default="localhost:9092",
        help="Kafka bootstrap servers (CSV)",
    )
    parser.add_argument(
        "--kafka-topic",
        default="data-center-metrics",
        help="Kafka topic prefix",
    )
    parser.add_argument(
        "--output-dir",
        default="/tmp/data_center_stream",
        help="Output directory for local backend",
    )

    args = parser.parse_args()

    # Create config
    config = DataCenterConfig(
        num_servers=args.num_servers,
        num_racks=args.num_racks,
        num_chillers=args.num_chillers,
    )

    # Create backend
    if args.backend == "local":
        backend = LocalFileBackend(args.output_dir)
    elif args.backend == "kafka":
        backend = KafkaBackend(args.kafka_servers, args.kafka_topic)
    else:  # stdout
        backend = StdoutBackend(summarize=True)

    # Create and run producer
    producer = StatefulStreamProducer(config, backend, args.interval)
    producer.run(max_batches=args.max_batches)


if __name__ == "__main__":
    main()
