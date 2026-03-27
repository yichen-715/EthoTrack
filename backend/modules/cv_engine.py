"""
CV Engine - Computer Vision and Video Processing Module
Handles video decoding, preprocessing, background subtraction, and target tracking

Performance Requirements:
- Video processing at original FPS
- Coordinate precision: ±0.5 pixel
- Real-time frame processing capability
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
import time


@dataclass
class TrackingResult:
    frame: int
    timestamp: float
    x: float
    y: float
    detected: bool
    area: float = 0.0
    velocity: float = 0.0
    binary_frame: Optional[str] = None


class CVEngine:
    """
    Core Computer Vision Engine for behavioral analysis.
    
    Responsibilities:
    1. Video frame decoding at original FPS
    2. Image preprocessing and denoising
    3. Background modeling and target extraction
    4. Centroid calculation with sub-pixel precision
    
    Technical Specifications:
    - Coordinate precision: ±0.5 pixel
    - Supports MOG2 and static background subtraction
    - Real-time processing capability
    """
    
    def __init__(
        self,
        blur_kernel_size: Tuple[int, int] = (21, 21),
        min_contour_area: int = 100,
        max_contour_area: int = 10000,
        mog2_history: int = 500,
        mog2_var_threshold: float = 50.0,
        mouse_type: str = 'auto',
        use_static_background: bool = False,
        static_background: Optional[np.ndarray] = None,
        threshold: int = 50
    ):
        self.blur_kernel_size = blur_kernel_size
        self.min_contour_area = min_contour_area
        self.max_contour_area = max_contour_area
        self.mouse_type = mouse_type
        self.use_static_background = use_static_background
        self.static_background = static_background
        self.threshold = threshold
        
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=mog2_history,
            varThreshold=mog2_var_threshold,
            detectShadows=False
        )
        
        self.morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._frame_count = 0
        self._last_process_time = 0
    
    def set_static_background(self, background_image: np.ndarray) -> None:
        """
        Set a static background image for subtraction.
        
        Args:
            background_image: BGR or grayscale background image
        """
        if len(background_image.shape) == 3:
            self.static_background = cv2.cvtColor(background_image, cv2.COLOR_BGR2GRAY)
        else:
            self.static_background = background_image.copy()
        
        self.static_background = cv2.GaussianBlur(
            self.static_background, 
            self.blur_kernel_size, 
            0
        )
        self.use_static_background = True
    
    def preprocess_frame(self, frame: np.ndarray, apply_blur: bool = True) -> np.ndarray:
        """
        Apply preprocessing: grayscale conversion and Gaussian blur.
        
        Args:
            frame: BGR input frame
            apply_blur: Whether to apply Gaussian blur
            
        Returns:
            Preprocessed grayscale frame
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if apply_blur:
            return cv2.GaussianBlur(gray, self.blur_kernel_size, 0)
        
        return gray
    
    def extract_foreground(self, frame: np.ndarray, return_binary: bool = False) -> np.ndarray:
        """
        Extract foreground mask using background subtraction.
        
        Args:
            frame: Preprocessed grayscale frame
            return_binary: Whether to return binary mask
            
        Returns:
            Foreground mask
        """
        if self.use_static_background and self.static_background is not None:
            diff = cv2.absdiff(frame, self.static_background)
            _, fg_mask = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
        else:
            fg_mask = self.background_subtractor.apply(frame)
        
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.morph_kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.morph_kernel)
        
        return fg_mask
    
    def find_target(self, fg_mask: np.ndarray) -> Tuple[Optional[Tuple[float, float]], Optional[np.ndarray], float]:
        """
        Find the target (mouse) in the foreground mask with sub-pixel precision.
        
        Args:
            fg_mask: Binary foreground mask
            
        Returns:
            Tuple of (centroid, contour, area)
            Centroid precision: ±0.5 pixel
        """
        contours, _ = cv2.findContours(
            fg_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return None, None, 0.0
        
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_contour_area <= area <= self.max_contour_area:
                valid_contours.append((contour, area))
        
        if not valid_contours:
            return None, None, 0.0
        
        valid_contours.sort(key=lambda x: x[1], reverse=True)
        mouse_contour, area = valid_contours[0]
        
        M = cv2.moments(mouse_contour)
        if M['m00'] == 0:
            return None, None, 0.0
        
        cx = M['m10'] / M['m00']
        cy = M['m01'] / M['m00']
        
        return (cx, cy), mouse_contour, area
    
    def process_single_frame(
        self,
        frame: np.ndarray,
        frame_number: int,
        fps: float = 30.0,
        return_binary: bool = False
    ) -> TrackingResult:
        """
        Process a single frame for real-time tracking.
        
        Args:
            frame: BGR input frame
            frame_number: Frame index
            fps: Video FPS for velocity calculation
            return_binary: Whether to include binary frame in result
            
        Returns:
            TrackingResult with centroid and metadata
        """
        start_time = time.time()
        
        preprocessed = self.preprocess_frame(frame)
        fg_mask = self.extract_foreground(preprocessed, return_binary)
        centroid, contour, area = self.find_target(fg_mask)
        
        timestamp = frame_number / fps
        velocity = 0.0
        
        result = TrackingResult(
            frame=frame_number,
            timestamp=timestamp,
            x=centroid[0] if centroid else 0.0,
            y=centroid[1] if centroid else 0.0,
            detected=centroid is not None,
            area=area,
            velocity=velocity
        )
        
        if return_binary:
            import base64
            _, buffer = cv2.imencode('.jpg', fg_mask)
            result.binary_frame = base64.b64encode(buffer).decode('utf-8')
        
        self._last_process_time = time.time() - start_time
        
        return result
    
    def process_video(
        self,
        video_path: str,
        start_frame: int = 0,
        end_frame: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> List[TrackingResult]:
        """
        Process entire video and return tracking results.
        
        Args:
            video_path: Path to video file
            start_frame: Frame to start processing from
            end_frame: Frame to stop processing at (None = entire video)
            progress_callback: Callback function for progress updates
            
        Returns:
            List of TrackingResult objects
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if end_frame is None:
            end_frame = total_frames
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        results = []
        self._frame_count = start_frame
        
        prev_centroid = None
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            if current_frame >= end_frame:
                break
            
            self._frame_count += 1
            timestamp = current_frame / fps
            
            preprocessed = self.preprocess_frame(frame)
            fg_mask = self.extract_foreground(preprocessed)
            centroid, contour, area = self.find_target(fg_mask)
            
            velocity = 0.0
            if centroid and prev_centroid:
                dx = centroid[0] - prev_centroid[0]
                dy = centroid[1] - prev_centroid[1]
                velocity = np.sqrt(dx*dx + dy*dy) * fps
            
            result = TrackingResult(
                frame=current_frame,
                timestamp=timestamp,
                x=centroid[0] if centroid else 0.0,
                y=centroid[1] if centroid else 0.0,
                detected=centroid is not None,
                area=area,
                velocity=velocity
            )
            results.append(result)
            
            if centroid:
                prev_centroid = centroid
            
            if progress_callback and current_frame % 30 == 0:
                progress = (current_frame - start_frame) / (end_frame - start_frame) * 100
                progress_callback(progress, current_frame, total_frames)
        
        cap.release()
        
        return results


class VideoProcessor:
    """High-level video processing interface."""
    
    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, Any]:
        """Get video metadata."""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        info = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        }
        
        cap.release()
        return info
    
    @staticmethod
    def extract_frame(video_path: str, frame_number: int) -> Optional[np.ndarray]:
        """Extract a single frame from video."""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            return None
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()
        
        return frame if ret else None
    
    @staticmethod
    def create_annotated_video(
        video_path: str,
        output_path: str,
        tracking_results: List[TrackingResult],
        rois: List[Dict] = None,
        fps: Optional[float] = None
    ) -> str:
        """Create annotated video with tracking overlay."""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        if fps is None:
            fps = cap.get(cv2.CAP_PROP_FPS)
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        trajectory_points = []
        
        for result in tracking_results:
            ret, frame = cap.read()
            if not ret:
                break
            
            if result.detected:
                cx, cy = int(result.x), int(result.y)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                trajectory_points.append((cx, cy))
                
                if len(trajectory_points) > 1:
                    pts = np.array(trajectory_points[-50:], dtype=np.int32)
                    cv2.polylines(frame, [pts], False, (0, 0, 255), 1)
            
            if rois:
                for roi in rois:
                    if roi['type'] == 'rectangle':
                        x, y = int(roi['x']), int(roi['y'])
                        w, h = int(roi['width']), int(roi['height'])
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            
            out.write(frame)
        
        cap.release()
        out.release()
        
        return output_path
