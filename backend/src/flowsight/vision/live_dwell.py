"""Observed zone visits, including active visits, without extending lost tracks."""

from __future__ import annotations

import math
from decimal import Decimal

from flowsight.scene.geometry import _point_in_polygon


class LiveDwellCounter:
    def __init__(self, shops, *, max_tracks=2048):
        if not 1 <= max_tracks <= 2048:
            raise ValueError("Invalid dwell tracking limit")
        self.shops = list(shops)
        self.max_tracks = max_tracks
        self.active = {}
        self.totals = {}
        self.horizon = Decimal(-1)
        self.segment = -1
        for shop in self.shops:
            for role in ("interior", "front"):
                self.totals[(str(shop.shop_id), role)] = [Decimal(0), 0]

    def _close(self, key):
        start, end = self.active.pop(key)
        duration = end - start
        if duration > 0:
            aggregate = self.totals[key[:2]]
            aggregate[0] += duration
            aggregate[1] += 1

    def discontinue(self):
        for key in list(self.active):
            self._close(key)

    def observe(self, timestamp, segment, feet):
        if not timestamp.is_finite() or timestamp < 0 or timestamp <= self.horizon:
            return
        if segment != self.segment or timestamp - self.horizon > 1:
            self.discontinue()
        self.horizon, self.segment = timestamp, segment
        valid = {
            track: foot
            for track, foot in feet.items()
            if all(math.isfinite(value) and 0 <= value <= 1 for value in foot)
        }
        for shop in self.shops:
            for role in ("interior", "front"):
                polygon = getattr(shop, f"{role}_polygon")
                prefix = (str(shop.shop_id), role)
                inside = {
                    track
                    for track, foot in valid.items()
                    if polygon and _point_in_polygon(foot, polygon)
                }
                for key in list(self.active):
                    if key[:2] == prefix and key[2] not in inside:
                        self._close(key)
                for track in sorted(inside):
                    key = (*prefix, track)
                    if key not in self.active:
                        if len(self.active) >= self.max_tracks:
                            self._close(min(self.active, key=lambda item: self.active[item][1]))
                        self.active[key] = (timestamp, timestamp)
                    else:
                        self.active[key] = (self.active[key][0], timestamp)

    def snapshot(self):
        totals = {key: list(value) for key, value in self.totals.items()}
        for key, (start, end) in self.active.items():
            if end > start:
                totals[key[:2]][0] += end - start
                totals[key[:2]][1] += 1
        result = {}
        for shop in self.shops:
            item = {}
            for role in ("interior", "front"):
                total, count = totals[(str(shop.shop_id), role)]
                item[f"{role}_average_seconds"] = float(total / count) if count else None
                item[f"{role}_sample_count"] = count
            result[str(shop.shop_id)] = item
        return result
