"""
Behavioral Logic Engine - Behavior state machine and event detection
Implements behavioral analysis logic with biological meaning
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ZoneType(Enum):
    ARENA = "arena"
    CENTER = "center"
    PERIPHERY = "periphery"
    CORNER = "corner"
    UNKNOWN = "unknown"


@dataclass
class ZoneTransition:
    from_zone: str
    to_zone: str
    frame: int
    timestamp: float
    position: Tuple[float, float]


@dataclass
class BehavioralEvent:
    event_type: str
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    duration: float
    zone: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BehavioralStateMachine:
    """
    Behavioral Logic Engine for analyzing animal behavior.
    
    Responsibilities:
    1. Zone transition detection with debouncing
    2. Entry/exit event classification
    3. Behavioral state tracking
    4. Event aggregation and statistics
    """
    
    def __init__(
        self,
        rois: List[Dict],
        entry_debounce_frames: int = 15,
        min_stay_frames: int = 15,
        immobility_threshold_px: float = 2.0,
        immobility_min_frames: int = 30
    ):
        self.rois = rois
        self.entry_debounce_frames = entry_debounce_frames
        self.min_stay_frames = min_stay_frames
        self.immobility_threshold_px = immobility_threshold_px
        self.immobility_min_frames = immobility_min_frames
        
        self._current_zone = None
        self._zone_history: List[str] = []
        self._debounce_counter = 0
        self._pending_zone = None
        
        self._position_history: List[Tuple[float, float]] = []
        self._frame_history: List[int] = []
        
        self.transitions: List[ZoneTransition] = []
        self.events: List[BehavioralEvent] = []
    
    def _point_in_roi(self, point: Tuple[float, float], roi: Dict) -> bool:
        x, y = point
        roi_type = roi.get('type', 'rectangle')
        
        if roi_type == 'rectangle':
            return (roi['x'] <= x <= roi['x'] + roi['width'] and
                    roi['y'] <= y <= roi['y'] + roi['height'])
        elif roi_type == 'circle':
            cx, cy = roi['center']['x'], roi['center']['y']
            radius = roi['radius']
            return np.sqrt((x - cx)**2 + (y - cy)**2) <= radius
        elif roi_type == 'polygon':
            points = roi.get('points', [])
            if len(points) < 3:
                return False
            polygon_points = [(p['x'], p['y']) if isinstance(p, dict) else (p[0], p[1]) for p in points]
            return self._point_in_polygon(point, polygon_points)
        
        return False
    
    def _point_in_polygon(self, point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
        x, y = point
        n = len(polygon)
        inside = False
        j = n - 1
        
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    def _get_zone_for_point(self, point: Tuple[float, float]) -> str:
        center_zone = None
        corner_zones = []
        arena_zone = None
        
        for roi in self.rois:
            roi_name = roi.get('name', '')
            roi_id = roi.get('id', '')
            
            if roi_id == 'center-zone' or '中心' in roi_name:
                if self._point_in_roi(point, roi):
                    center_zone = roi
            elif 'corner' in roi_id.lower() or '角' in roi_name:
                if self._point_in_roi(point, roi):
                    corner_zones.append(roi)
            elif roi_id == 'arena' or '全场' in roi_name:
                arena_zone = roi
        
        if center_zone:
            return center_zone.get('name', '中心区')
        
        if corner_zones:
            return corner_zones[0].get('name', '角落区')
        
        if arena_zone and self._point_in_roi(point, arena_zone):
            return '边缘区'
        
        return "outside"
    
    def process_frame(
        self,
        frame: int,
        timestamp: float,
        position: Tuple[float, float],
        detected: bool
    ) -> Optional[ZoneTransition]:
        if not detected:
            return None
        
        detected_zone = self._get_zone_for_point(position)
        
        self._position_history.append(position)
        self._frame_history.append(frame)
        
        transition = None
        
        if detected_zone != self._current_zone:
            if detected_zone != self._pending_zone:
                self._pending_zone = detected_zone
                self._debounce_counter = 1
            else:
                self._debounce_counter += 1
                
                if self._debounce_counter >= self.entry_debounce_frames:
                    transition = ZoneTransition(
                        from_zone=self._current_zone or "outside",
                        to_zone=detected_zone,
                        frame=frame,
                        timestamp=timestamp,
                        position=position
                    )
                    self.transitions.append(transition)
                    self._current_zone = detected_zone
                    self._pending_zone = None
                    self._debounce_counter = 0
        else:
            self._pending_zone = None
            self._debounce_counter = 0
        
        self._zone_history.append(detected_zone)
        
        return transition
    
    def detect_immobility_event(
        self,
        current_frame: int,
        current_position: Tuple[float, float]
    ) -> Optional[BehavioralEvent]:
        if len(self._position_history) < self.immobility_min_frames:
            return None
        
        recent_positions = self._position_history[-self.immobility_min_frames:]
        recent_frames = self._frame_history[-self.immobility_min_frames:]
        
        total_movement = 0
        for i in range(1, len(recent_positions)):
            dx = recent_positions[i][0] - recent_positions[i-1][0]
            dy = recent_positions[i][1] - recent_positions[i-1][1]
            total_movement += np.sqrt(dx*dx + dy*dy)
        
        avg_movement = total_movement / (len(recent_positions) - 1) if len(recent_positions) > 1 else 0
        
        if avg_movement < self.immobility_threshold_px:
            return BehavioralEvent(
                event_type="immobility",
                start_frame=recent_frames[0],
                end_frame=current_frame,
                start_time=recent_frames[0] / 30.0,
                end_time=current_frame / 30.0,
                duration=(current_frame - recent_frames[0]) / 30.0,
                zone=self._current_zone or "unknown",
                metadata={'avg_movement_px': avg_movement}
            )
        
        return None
    
    def get_zone_statistics(self, fps: float = 30.0) -> Dict[str, Dict]:
        if not self._zone_history:
            return {}
        
        zone_stats = {}
        total_frames = len(self._zone_history)
        
        for zone in set(self._zone_history):
            frames = self._zone_history.count(zone)
            zone_stats[zone] = {
                'frames': frames,
                'time_seconds': frames / fps,
                'percentage': (frames / total_frames) * 100
            }
        
        return zone_stats
    
    def get_transition_summary(self) -> Dict[str, int]:
        summary = {}
        
        for transition in self.transitions:
            key = f"{transition.from_zone}->{transition.to_zone}"
            summary[key] = summary.get(key, 0) + 1
        
        return summary
    
    def get_entry_count(self, zone_name: str) -> int:
        count = 0
        for transition in self.transitions:
            if transition.to_zone == zone_name:
                count += 1
        return count
    
    def get_exit_count(self, zone_name: str) -> int:
        count = 0
        for transition in self.transitions:
            if transition.from_zone == zone_name:
                count += 1
        return count
    
    def reset(self):
        self._current_zone = None
        self._zone_history = []
        self._debounce_counter = 0
        self._pending_zone = None
        self._position_history = []
        self._frame_history = []
        self.transitions = []
        self.events = []


class OpenFieldAnalyzer(BehavioralStateMachine):
    """
    Specialized analyzer for Open Field Test experiments.
    
    Implements standard open field metrics:
    - Total distance traveled
    - Time in center vs periphery
    - Center zone entries
    - Thigmotaxis (wall-hugging) index
    
    区域划分规则:
    1. 基础模式（无角落区）:
       - 全场区: 实验场地的完整区域范围
       - 中心区: 位于全场区中央的特定区域
       - 边缘区: 全场区内除中心区以外的环形区域
         判定: 在全场区内且不在中心区内 = 边缘区
    
    2. 包含角落区模式:
       - 中心区: 保持原有定义不变
       - 角落区: 全场区内划分出的4个小区域
       - 边缘区: 全场区减去中心区和角落区后的剩余区域
         判定: 在全场区内，且既不在中心区内也不在任何角落区内 = 边缘区
    """
    
    def __init__(self, arena_config: Dict, video_width: int = None, video_height: int = None, **kwargs):
        self._video_width = video_width
        self._video_height = video_height
        rois = self._build_rois_from_arena(arena_config)
        super().__init__(rois=rois, **kwargs)
        self.arena_config = arena_config
        self.center_ratio = arena_config.get('centerRatio', 30)
        self.corner_ratio = arena_config.get('cornerRatio', 20)
        self._has_corners = arena_config.get('hasCorners', False)
        self._arena = None
        self._center_zone = None
    
    def _build_rois_from_arena(self, arena_config: Dict) -> List[Dict]:
        rois = []
        
        if 'arena' in arena_config and arena_config['arena']:
            arena = arena_config['arena']
            center_ratio = arena_config.get('centerRatio', 30) / 100
            corner_ratio = arena_config.get('cornerRatio', 20) / 100
            has_corners = arena_config.get('hasCorners', arena_config.get('showCorners', False))
            
            video_width = self._video_width or 1
            video_height = self._video_height or 1
            
            arena_x = arena['x'] * video_width if arena['x'] <= 1 else arena['x']
            arena_y = arena['y'] * video_height if arena['y'] <= 1 else arena['y']
            arena_width = arena['width'] * video_width if arena['width'] <= 1 else arena['width']
            arena_height = arena['height'] * video_height if arena['height'] <= 1 else arena['height']
            
            rois.append({
                'id': 'arena',
                'name': '全场区',
                'type': 'rectangle',
                'x': arena_x,
                'y': arena_y,
                'width': arena_width,
                'height': arena_height,
                'priority': 0
            })
            
            center_width = arena_width * center_ratio
            center_height = arena_height * center_ratio
            center_x = arena_x + (arena_width - center_width) / 2
            center_y = arena_y + (arena_height - center_height) / 2
            
            rois.append({
                'id': 'center-zone',
                'name': '中心区',
                'type': 'rectangle',
                'x': center_x,
                'y': center_y,
                'width': center_width,
                'height': center_height,
                'priority': 10
            })
            
            if has_corners:
                corner_width = arena_width * corner_ratio
                corner_height = arena_height * corner_ratio
                
                corners = [
                    {'id': 'corner-tl', 'name': '左上角', 'x': arena_x, 'y': arena_y},
                    {'id': 'corner-tr', 'name': '右上角', 'x': arena_x + arena_width - corner_width, 'y': arena_y},
                    {'id': 'corner-bl', 'name': '左下角', 'x': arena_x, 'y': arena_y + arena_height - corner_height},
                    {'id': 'corner-br', 'name': '右下角', 'x': arena_x + arena_width - corner_width, 'y': arena_y + arena_height - corner_height},
                ]
                
                for corner in corners:
                    rois.append({
                        'id': corner['id'],
                        'name': corner['name'],
                        'type': 'rectangle',
                        'x': corner['x'],
                        'y': corner['y'],
                        'width': corner_width,
                        'height': corner_height,
                        'priority': 5
                    })
            
            self._has_corners = has_corners
            self._arena = {'x': arena_x, 'y': arena_y, 'width': arena_width, 'height': arena_height}
            self._center_zone = {
                'x': center_x,
                'y': center_y,
                'width': center_width,
                'height': center_height
            }
        
        return rois
    
    def calculate_thigmotaxis_index(self, trajectory: List[Dict], arena: Dict) -> float:
        if not trajectory:
            return 0.0
        
        periphery_frames = 0
        total_frames = 0
        
        center_zone = None
        for roi in self.rois:
            if 'center' in roi.get('name', '').lower():
                center_zone = roi
                break
        
        if not center_zone:
            return 0.0
        
        for point in trajectory:
            if not point.get('detected', False):
                continue
            
            total_frames += 1
            position = (point['x'], point['y'])
            
            if not self._point_in_roi(position, center_zone):
                periphery_frames += 1
        
        return periphery_frames / total_frames if total_frames > 0 else 0.0
    
    def get_open_field_metrics(
        self,
        trajectory: List[Dict],
        fps: float,
        scale_calibration: Optional[float] = None
    ) -> Dict[str, Any]:
        total_distance_px = 0.0
        prev_point = None
        
        for point in trajectory:
            if not point.get('detected', False):
                continue
            
            current_point = (point['x'], point['y'])
            
            if prev_point is not None:
                dx = current_point[0] - prev_point[0]
                dy = current_point[1] - prev_point[1]
                total_distance_px += np.sqrt(dx*dx + dy*dy)
            
            prev_point = current_point
        
        total_distance = total_distance_px
        if scale_calibration:
            total_distance = total_distance_px / scale_calibration
        
        zone_stats = self.get_zone_statistics(fps)
        center_entries = self.get_entry_count('中心区')
        thigmotaxis = self.calculate_thigmotaxis_index(trajectory, self.arena_config.get('arena', {}))
        
        corner_stats = {}
        corner_names = ['左上角', '右上角', '左下角', '右下角']
        for corner_name in corner_names:
            if corner_name in zone_stats:
                corner_stats[corner_name] = zone_stats[corner_name]
        
        periphery_time = zone_stats.get('边缘区', {})
        corner_total_time = sum(stats.get('time_seconds', 0) for stats in corner_stats.values())
        
        return {
            'total_distance': {
                'pixels': total_distance_px,
                'cm': total_distance if scale_calibration else None,
                'unit': 'cm' if scale_calibration else 'px'
            },
            'center_zone': zone_stats.get('中心区', zone_stats.get('center-zone', {})),
            'periphery_zone': periphery_time,
            'corner_zones': corner_stats,
            'center_entries': center_entries,
            'thigmotaxis_index': thigmotaxis,
            'zone_statistics': zone_stats,
            'transitions': self.get_transition_summary(),
            'has_corners': self._has_corners
        }
