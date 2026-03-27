"""
Spatial Module - Geometry and Physical Quantity Calculations
Handles pixel-to-cm conversion, point-in-polygon tests, and velocity calculations

Performance Requirements:
- Pixel to cm conversion error: < 0.1 cm
- Point-in-polygon accuracy: 100%
- Distance calculation precision: ±0.5 pixel
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ScaleCalibration:
    pixels_per_cm: float
    calibration_points: List[Dict]
    real_length_cm: float
    calibration_error: float = 0.0


@dataclass
class PhysicalMetrics:
    total_distance_cm: float
    avg_speed_cm_s: float
    max_speed_cm_s: float
    immobility_time_s: float
    immobility_frames: int


class SpatialCalculator:
    """
    Spatial geometry and physical quantity calculation module.
    
    Responsibilities:
    1. Pixel to physical distance conversion (error < 0.1 cm)
    2. Point-in-polygon position relationship (accuracy 100%)
    3. Instantaneous physical quantity calculation
    
    Technical Specifications:
    - Conversion precision: ±0.1 cm
    - Point-in-polygon: 100% accuracy using ray casting or OpenCV
    - Distance calculation: Euclidean with sub-pixel precision
    """
    
    def __init__(self, scale_calibration: Optional[ScaleCalibration] = None):
        self.scale_calibration = scale_calibration
    
    def set_calibration(self, pixels_per_cm: float, calibration_error: float = 0.0) -> None:
        """
        Set scale calibration with precision tracking.
        
        Args:
            pixels_per_cm: Pixels per centimeter ratio
            calibration_error: Estimated calibration error in cm
        """
        self.scale_calibration = ScaleCalibration(
            pixels_per_cm=pixels_per_cm,
            calibration_points=[],
            real_length_cm=0.0,
            calibration_error=calibration_error
        )
    
    def pixels_to_cm(self, pixels: float) -> float:
        """
        Convert pixels to centimeters.
        
        Args:
            pixels: Distance in pixels
            
        Returns:
            Distance in centimeters (precision: ±0.1 cm)
        """
        if self.scale_calibration is None:
            return pixels
        return pixels / self.scale_calibration.pixels_per_cm
    
    def cm_to_pixels(self, cm: float) -> float:
        """
        Convert centimeters to pixels.
        
        Args:
            cm: Distance in centimeters
            
        Returns:
            Distance in pixels
        """
        if self.scale_calibration is None:
            return cm
        return cm * self.scale_calibration.pixels_per_cm
    
    @staticmethod
    def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """
        Calculate Euclidean distance between two points.
        
        Args:
            p1: First point (x, y)
            p2: Second point (x, y)
            
        Returns:
            Distance with sub-pixel precision
        """
        return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
    
    @staticmethod
    def point_in_rectangle(point: Tuple[float, float], roi: Dict) -> bool:
        """
        Check if point is inside rectangle ROI.
        
        Args:
            point: (x, y) coordinates
            roi: Rectangle ROI with x, y, width, height
            
        Returns:
            True if point is inside rectangle
        """
        x, y = point
        return (roi['x'] <= x <= roi['x'] + roi['width'] and
                roi['y'] <= y <= roi['y'] + roi['height'])
    
    @staticmethod
    def point_in_circle(point: Tuple[float, float], roi: Dict) -> bool:
        """
        Check if point is inside circular ROI.
        
        Args:
            point: (x, y) coordinates
            roi: Circle ROI with center and radius
            
        Returns:
            True if point is inside circle
        """
        x, y = point
        cx, cy = roi['center']['x'], roi['center']['y']
        radius = roi['radius']
        return np.sqrt((x - cx)**2 + (y - cy)**2) <= radius
    
    @staticmethod
    def point_in_polygon(point: Tuple[float, float], polygon_points: List[Tuple[float, float]]) -> bool:
        """
        Check if point is inside polygon using ray casting algorithm.
        Accuracy: 100%
        
        Args:
            point: (x, y) coordinates
            polygon_points: List of polygon vertices
            
        Returns:
            True if point is inside polygon
        """
        x, y = point
        n = len(polygon_points)
        inside = False
        j = n - 1
        
        for i in range(n):
            xi, yi = polygon_points[i]
            xj, yj = polygon_points[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    def point_in_roi(self, point: Tuple[float, float], roi: Dict) -> bool:
        """
        Check if point is inside ROI (any type).
        
        Args:
            point: (x, y) coordinates
            roi: ROI configuration with type and geometry
            
        Returns:
            True if point is inside ROI
        """
        roi_type = roi.get('type', 'rectangle')
        
        if roi_type == 'rectangle':
            return self.point_in_rectangle(point, roi)
        elif roi_type == 'circle':
            return self.point_in_circle(point, roi)
        elif roi_type == 'polygon':
            points = roi.get('points', [])
            if len(points) >= 3:
                polygon_points = [(p['x'], p['y']) if isinstance(p, dict) else (p[0], p[1]) for p in points]
                return self.point_in_polygon(point, polygon_points)
        return False
    
    def calculate_instantaneous_velocity(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        fps: float
    ) -> float:
        distance = self.euclidean_distance(p1, p2)
        velocity_px_s = distance * fps
        
        if self.scale_calibration:
            return self.pixels_to_cm(velocity_px_s)
        return velocity_px_s
    
    def calculate_trajectory_metrics(
        self,
        trajectory: List[Dict],
        fps: float,
        immobility_threshold_px: float = 2.0
    ) -> PhysicalMetrics:
        if not trajectory:
            return PhysicalMetrics(0, 0, 0, 0, 0)
        
        total_distance_px = 0.0
        speeds = []
        immobility_frames = 0
        prev_point = None
        
        for point in trajectory:
            if not point.get('detected', False):
                continue
            
            current_point = (point['x'], point['y'])
            
            if prev_point is not None:
                distance = self.euclidean_distance(prev_point, current_point)
                total_distance_px += distance
                speeds.append(distance * fps)
                
                if distance < immobility_threshold_px:
                    immobility_frames += 1
            
            prev_point = current_point
        
        total_distance_cm = self.pixels_to_cm(total_distance_px)
        avg_speed_cm_s = self.pixels_to_cm(np.mean(speeds)) if speeds else 0
        max_speed_cm_s = self.pixels_to_cm(np.max(speeds)) if speeds else 0
        immobility_time_s = immobility_frames / fps
        
        return PhysicalMetrics(
            total_distance_cm=total_distance_cm,
            avg_speed_cm_s=avg_speed_cm_s,
            max_speed_cm_s=max_speed_cm_s,
            immobility_time_s=immobility_time_s,
            immobility_frames=immobility_frames
        )
    
    def calculate_roi_time_distribution(
        self,
        trajectory: List[Dict],
        rois: List[Dict],
        fps: float
    ) -> Dict[str, Dict[str, float]]:
        roi_stats = {}
        
        for roi in rois:
            roi_name = roi.get('name', f"ROI_{roi.get('id', 'unknown')}")
            roi_stats[roi_name] = {
                'frames': 0,
                'time_seconds': 0.0,
                'percentage': 0.0
            }
        
        total_frames = 0
        
        for point in trajectory:
            if not point.get('detected', False):
                continue
            
            total_frames += 1
            position = (point['x'], point['y'])
            
            for roi in rois:
                if self.point_in_roi(position, roi):
                    roi_name = roi.get('name', f"ROI_{roi.get('id', 'unknown')}")
                    roi_stats[roi_name]['frames'] += 1
        
        if total_frames > 0:
            for roi_name in roi_stats:
                frames = roi_stats[roi_name]['frames']
                roi_stats[roi_name]['time_seconds'] = frames / fps
                roi_stats[roi_name]['percentage'] = (frames / total_frames) * 100
        
        return roi_stats
