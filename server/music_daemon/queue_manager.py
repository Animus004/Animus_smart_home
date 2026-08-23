"""
Deterministic Thread-Safe Playback Queue Manager for Animus Music Daemon.
Supports manual queuing, auto-radio mode, track history, and skip/previous navigation.
"""

from dataclasses import dataclass, field
import logging
import threading
from typing import Optional, List, Dict, Any

logger = logging.getLogger("music_daemon.queue_manager")


@dataclass
class QueueTrack:
    video_id: str
    title: str
    artist: str
    duration: Optional[int] = None
    stream_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_authenticated: bool = False
    source: str = "manual"  # "manual", "radio", "preset"


class PlaybackQueue:
    """
    Thread-safe playback queue manager.
    Maintains upcoming tracks, playback history, auto-radio preferences,
    and cursor position.
    """
    def __init__(self, auto_radio: bool = True, max_history: int = 50):
        self._lock = threading.RLock()
        self._queue: List[QueueTrack] = []
        self._history: List[QueueTrack] = []
        self._current_track: Optional[QueueTrack] = None
        self._auto_radio: bool = auto_radio
        self._max_history: int = max_history

    @property
    def auto_radio(self) -> bool:
        with self._lock:
            return self._auto_radio

    @auto_radio.setter
    def auto_radio(self, value: bool):
        with self._lock:
            self._auto_radio = value

    @property
    def current_track(self) -> Optional[QueueTrack]:
        with self._lock:
            return self._current_track

    def set_current_track(self, track: Optional[QueueTrack]):
        with self._lock:
            if self._current_track is not None:
                self._history.append(self._current_track)
                if len(self._history) > self._max_history:
                    self._history.pop(0)
            self._current_track = track

    def enqueue(self, track: QueueTrack) -> int:
        """
        Appends a track to the end of the queue.
        Returns the new queue length.
        """
        with self._lock:
            self._queue.append(track)
            logger.info(f"[QUEUE] Enqueued track '{track.title}' by '{track.artist}' (Queue length: {len(self._queue)})")
            return len(self._queue)

    def enqueue_next(self, track: QueueTrack) -> int:
        """
        Inserts a track to play immediately next (front of queue).
        Returns the new queue length.
        """
        with self._lock:
            self._queue.insert(0, track)
            logger.info(f"[QUEUE] Enqueued NEXT track '{track.title}' by '{track.artist}' (Queue length: {len(self._queue)})")
            return len(self._queue)

    def enqueue_multiple(self, tracks: List[QueueTrack]) -> int:
        with self._lock:
            self._queue.extend(tracks)
            logger.info(f"[QUEUE] Enqueued {len(tracks)} tracks (Total queue length: {len(self._queue)})")
            return len(self._queue)

    def pop_next(self) -> Optional[QueueTrack]:
        """
        Pops and returns the next track from the queue.
        """
        with self._lock:
            if self._queue:
                next_track = self._queue.pop(0)
                logger.info(f"[QUEUE] Popped next track '{next_track.title}' from queue (Remaining: {len(self._queue)})")
                return next_track
            return None

    def peek_next(self) -> Optional[QueueTrack]:
        with self._lock:
            return self._queue[0] if self._queue else None

    def pop_previous(self) -> Optional[QueueTrack]:
        """
        Retrieves the most recent track from history and re-queues the current track at the front.
        """
        with self._lock:
            if not self._history:
                return None
            prev_track = self._history.pop()
            if self._current_track:
                self._queue.insert(0, self._current_track)
                self._current_track = None
            return prev_track

    def clear(self):
        with self._lock:
            cleared_count = len(self._queue)
            self._queue.clear()
            logger.info(f"[QUEUE] Cleared {cleared_count} tracks from queue.")

    def clear_all(self):
        with self._lock:
            self._queue.clear()
            self._history.clear()
            self._current_track = None
            logger.info("[QUEUE] Cleared queue, history, and current track.")

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

    def get_queue_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "video_id": t.video_id,
                    "title": t.title,
                    "artist": t.artist,
                    "duration": t.duration,
                    "thumbnail_url": t.thumbnail_url,
                    "source": t.source
                }
                for t in self._queue
            ]

    def get_history_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "video_id": t.video_id,
                    "title": t.title,
                    "artist": t.artist,
                    "duration": t.duration,
                    "thumbnail_url": t.thumbnail_url,
                    "source": t.source
                }
                for t in self._history
            ]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "queue_length": len(self._queue),
                "history_length": len(self._history),
                "auto_radio": self._auto_radio,
                "current_track": {
                    "video_id": self._current_track.video_id,
                    "title": self._current_track.title,
                    "artist": self._current_track.artist,
                    "duration": self._current_track.duration,
                    "thumbnail_url": self._current_track.thumbnail_url,
                    "source": self._current_track.source
                } if self._current_track else None,
                "upcoming": self.get_queue_items()[:10]
            }
