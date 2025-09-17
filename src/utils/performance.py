import time
import logging
from typing import Dict, Optional
from contextlib import contextmanager


class PerformanceTracker:
    """Track performance metrics for document processing"""

    def __init__(self):
        self.timings: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}

    def start_timing(self, stage: str) -> None:
        """Start timing a processing stage"""
        self.start_times[stage] = time.time()
        logging.info(f"⏱️ Starting stage: {stage}")

    def end_timing(self, stage: str) -> float:
        """End timing a processing stage and return duration"""
        if stage not in self.start_times:
            logging.warning(f"No start time found for stage: {stage}")
            return 0.0

        duration = time.time() - self.start_times[stage]
        self.timings[stage] = duration

        logging.info(f"✅ Completed stage: {stage} in {duration:.2f}s")
        return duration

    @contextmanager
    def time_stage(self, stage: str):
        """Context manager for timing a stage"""
        self.start_timing(stage)
        try:
            yield
        finally:
            self.end_timing(stage)

    def get_timing(self, stage: str) -> Optional[float]:
        """Get timing for a specific stage"""
        return self.timings.get(stage)

    def get_total_time(self) -> float:
        """Get total processing time"""
        return sum(self.timings.values())

    def log_summary(self, request_id: str) -> None:
        """Log comprehensive timing summary"""
        total_time = self.get_total_time()

        logging.info(f"📊 Performance Summary for Request {request_id}")
        logging.info(f"   Total Processing Time: {total_time:.2f}s ({total_time/60:.1f}m)")

        # Sort stages by duration (longest first)
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)

        for stage, duration in sorted_timings:
            percentage = (duration / total_time * 100) if total_time > 0 else 0
            logging.info(f"   {stage}: {duration:.2f}s ({percentage:.1f}%)")

    def get_performance_data(self) -> Dict[str, float]:
        """Get all timing data for API response"""
        return {
            "totalTime": self.get_total_time(),
            "stages": self.timings.copy()
        }


# Global instance for easy access
performance_tracker = PerformanceTracker()