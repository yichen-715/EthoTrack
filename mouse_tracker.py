"""
Mouse Tracking Script for Behavioral Analysis
Implements video processing and target tracking using OpenCV
"""

import cv2
import numpy as np
import argparse
import json
import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any


class MouseTracker:
    """
    A class for tracking mouse movement in video files.
    
    The tracking algorithm follows these steps:
    1. Convert video frame to grayscale
    2. Apply Gaussian blur for noise reduction
    3. Perform threshold binarization
    4. Detect and extract target contours
    5. Calculate centroid coordinates of the target
    """
    
    def __init__(
        self,
        blur_kernel_size: Tuple[int, int] = (5, 5),
        blur_sigma: int = 0,
        threshold_method: str = 'adaptive',
        threshold_value: int = 50,
        adaptive_block_size: int = 11,
        adaptive_c: int = 2,
        min_contour_area: int = 100,
        max_contour_area: int = 10000,
        use_background_subtraction: bool = True,
        background_history: int = 500,
        background_var_threshold: float = 50.0
    ):
        """
        Initialize the MouseTracker with configurable parameters.
        
        Args:
            blur_kernel_size: Kernel size for Gaussian blur (default: (5, 5))
            blur_sigma: Sigma value for Gaussian blur (0 = auto-calculated)
            threshold_method: 'binary', 'adaptive', or 'otsu'
            threshold_value: Threshold value for binary thresholding
            adaptive_block_size: Block size for adaptive thresholding
            adaptive_c: Constant subtracted from mean for adaptive thresholding
            min_contour_area: Minimum contour area to be considered as mouse
            max_contour_area: Maximum contour area to be considered as mouse
            use_background_subtraction: Whether to use MOG2 background subtraction
            background_history: History length for background subtractor (default: 500)
            background_var_threshold: Variance threshold for background subtractor (default: 50)
        """
        self.blur_kernel_size = blur_kernel_size
        self.blur_sigma = blur_sigma
        self.threshold_method = threshold_method
        self.threshold_value = threshold_value
        self.adaptive_block_size = adaptive_block_size
        self.adaptive_c = adaptive_c
        self.min_contour_area = min_contour_area
        self.max_contour_area = max_contour_area
        self.use_background_subtraction = use_background_subtraction
        
        if use_background_subtraction:
            self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=background_history,
                varThreshold=background_var_threshold,
                detectShadows=False
            )
        else:
            self.background_subtractor = None
        
        self.tracking_data: List[Dict[str, Any]] = []
        self.frame_count = 0
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Step 1 & 2: Apply Gaussian blur for noise reduction.
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Preprocessed blurred frame
        """
        blurred = cv2.GaussianBlur(frame, self.blur_kernel_size, self.blur_sigma)
        return blurred
    
    def apply_threshold(self, frame: np.ndarray) -> np.ndarray:
        """
        Step 3: Apply threshold binarization to highlight the target.
        
        Args:
            frame: Preprocessed grayscale frame
            
        Returns:
            Binary thresholded frame
        """
        if self.threshold_method == 'adaptive':
            binary = cv2.adaptiveThreshold(
                frame,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                self.adaptive_block_size,
                self.adaptive_c
            )
        elif self.threshold_method == 'otsu':
            _, binary = cv2.threshold(
                frame,
                0,
                255,
                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
        else:
            _, binary = cv2.threshold(
                frame,
                self.threshold_value,
                255,
                cv2.THRESH_BINARY_INV
            )
        
        return binary
    
    def detect_contours(self, binary_frame: np.ndarray) -> List:
        """
        Step 4: Detect and extract contours from binary frame.
        
        Args:
            binary_frame: Binary thresholded frame
            
        Returns:
            List of detected contours
        """
        contours, _ = cv2.findContours(
            binary_frame,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        return contours
    
    def calculate_centroid(self, contour: np.ndarray) -> Tuple[float, float]:
        """
        Step 5: Calculate the centroid of a contour.
        
        Args:
            contour: Input contour
            
        Returns:
            Tuple of (x, y) centroid coordinates
        """
        M = cv2.moments(contour)
        if M['m00'] == 0:
            cx = float(contour[0][0][0])
            cy = float(contour[0][0][1])
        else:
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
        return cx, cy
    
    def find_mouse_contour(self, contours: List) -> Optional[np.ndarray]:
        """
        Find the most likely mouse contour based on area constraints.
        
        Args:
            contours: List of detected contours
            
        Returns:
            The most likely mouse contour, or None if not found
        """
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_contour_area <= area <= self.max_contour_area:
                valid_contours.append((contour, area))
        
        if not valid_contours:
            return None
        
        valid_contours.sort(key=lambda x: x[1], reverse=True)
        return valid_contours[0][0]
    
    def process_frame(self, frame: np.ndarray) -> Optional[Tuple[float, float]]:
        """
        Process a single frame and return the mouse centroid.
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Tuple of (x, y) centroid coordinates, or None if not detected
        """
        centroid, _ = self.process_frame_with_binary(frame)
        return centroid
    
    def process_frame_with_binary(self, frame: np.ndarray) -> Tuple[Optional[Tuple[float, float]], np.ndarray]:
        """
        Process a single frame and return the mouse centroid along with binary image.
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Tuple of (centroid coordinates or None, binary image)
        """
        centroid, binary, _ = self.process_frame_full(frame)
        return centroid, binary
    
    def process_frame_full(self, frame: np.ndarray) -> Tuple[Optional[Tuple[float, float]], np.ndarray, Optional[np.ndarray]]:
        """
        Process a single frame and return centroid, binary image, and contour.
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Tuple of (centroid coordinates or None, binary image, mouse contour or None)
        """
        blurred = cv2.GaussianBlur(frame, self.blur_kernel_size, 0)
        
        if self.use_background_subtraction and self.background_subtractor is not None:
            fg_mask = self.background_subtractor.apply(blurred)
        else:
            gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
            fg_mask = self.apply_threshold(gray)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        mouse_contour = None
        centroid = None
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            
            if area > self.min_contour_area:
                mouse_contour = largest_contour
                centroid = self.calculate_centroid(mouse_contour)
        
        return centroid, fg_mask, mouse_contour
    
    def track_video_interactive(
        self,
        video_path: str,
        output_video_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Track mouse with interactive parameter adjustment using trackbars.
        
        Args:
            video_path: Path to input video file
            output_video_path: Path for output visualization video
            
        Returns:
            List of tracking data dictionaries
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Video info: {frame_width}x{frame_height} @ {fps:.2f} fps, {total_frames} frames")
        
        cv2.namedWindow('Controls', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Controls', 400, 350)
        
        params = {
            'blur_kernel': max(1, self.blur_kernel_size[0] // 2 * 2 + 1),
            'threshold': self.threshold_value,
            'min_area': self.min_contour_area,
            'max_area': self.max_contour_area,
            'morph_kernel': 5,
            'bg_threshold': 200
        }
        
        cv2.createTrackbar('Blur Kernel', 'Controls', params['blur_kernel'], 51, lambda x: None)
        cv2.createTrackbar('Threshold', 'Controls', params['threshold'], 255, lambda x: None)
        cv2.createTrackbar('Min Area', 'Controls', params['min_area'], 5000, lambda x: None)
        cv2.createTrackbar('Max Area', 'Controls', params['max_area'], 50000, lambda x: None)
        cv2.createTrackbar('Morph Kernel', 'Controls', params['morph_kernel'], 15, lambda x: None)
        cv2.createTrackbar('BG Threshold', 'Controls', params['bg_threshold'], 255, lambda x: None)
        
        cv2.setTrackbarPos('Blur Kernel', 'Controls', params['blur_kernel'])
        cv2.setTrackbarPos('Threshold', 'Controls', params['threshold'])
        cv2.setTrackbarPos('Min Area', 'Controls', params['min_area'])
        cv2.setTrackbarPos('Max Area', 'Controls', params['max_area'])
        cv2.setTrackbarPos('Morph Kernel', 'Controls', params['morph_kernel'])
        cv2.setTrackbarPos('BG Threshold', 'Controls', params['bg_threshold'])
        
        self.tracking_data = []
        self.frame_count = 0
        trajectory_points = []
        paused = False
        current_frame = None
        
        print("Starting interactive tracking...")
        print("Controls: SPACE=Pause/Resume, Q=Quit, R=Reset")
        
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.frame_count = 0
                    trajectory_points = []
                    self.tracking_data = []
                    continue
                
                current_frame = frame.copy()
                self.frame_count += 1
            else:
                if current_frame is None:
                    continue
                frame = current_frame.copy()
            
            params['blur_kernel'] = cv2.getTrackbarPos('Blur Kernel', 'Controls')
            params['threshold'] = cv2.getTrackbarPos('Threshold', 'Controls')
            params['min_area'] = cv2.getTrackbarPos('Min Area', 'Controls')
            params['max_area'] = cv2.getTrackbarPos('Max Area', 'Controls')
            params['morph_kernel'] = cv2.getTrackbarPos('Morph Kernel', 'Controls')
            params['bg_threshold'] = cv2.getTrackbarPos('BG Threshold', 'Controls')
            
            blur_kernel = max(1, params['blur_kernel'] if params['blur_kernel'] % 2 == 1 else params['blur_kernel'] + 1)
            self.blur_kernel_size = (blur_kernel, blur_kernel)
            self.min_contour_area = max(1, params['min_area'])
            self.max_contour_area = max(self.min_contour_area + 1, params['max_area'])
            
            blurred = cv2.GaussianBlur(frame, self.blur_kernel_size, 0)
            
            if self.use_background_subtraction and self.background_subtractor is not None:
                fg_mask = self.background_subtractor.apply(blurred)
            else:
                gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
                _, fg_mask = cv2.threshold(gray, params['threshold'], 255, cv2.THRESH_BINARY_INV)
            
            morph_k = max(1, params['morph_kernel'] if params['morph_kernel'] % 2 == 1 else params['morph_kernel'] + 1)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_k, morph_k))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            centroid = None
            mouse_contour = None
            
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)
                if area > self.min_contour_area:
                    mouse_contour = largest_contour
                    M = cv2.moments(mouse_contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        centroid = (cx, cy)
            
            display_frame = frame.copy()
            binary_colored = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2BGR)
            
            if centroid is not None:
                cx, cy = int(centroid[0]), int(centroid[1])
                
                if mouse_contour is not None:
                    cv2.drawContours(display_frame, [mouse_contour], -1, (0, 255, 0), 2)
                
                cv2.circle(display_frame, (cx, cy), 5, (0, 0, 255), -1)
                
                if mouse_contour is not None:
                    cv2.drawContours(binary_colored, [mouse_contour], -1, (0, 255, 0), 2)
                cv2.circle(binary_colored, (cx, cy), 5, (0, 0, 255), -1)
                
                if not paused:
                    trajectory_points.append((cx, cy))
            
            TRAJECTORY_LENGTH = 30
            if len(trajectory_points) > 1:
                recent_trajectory = trajectory_points[-TRAJECTORY_LENGTH:]
                if len(recent_trajectory) >= 2:
                    pts = np.array(recent_trajectory, dtype=np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    cv2.polylines(display_frame, [pts], False, (0, 0, 255), 1, cv2.LINE_AA)
            
            cv2.putText(display_frame, f"Frame: {self.frame_count}/{total_frames}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            status = "Tracking" if centroid is not None else "Lost"
            status_color = (0, 255, 0) if centroid is not None else (0, 0, 255)
            cv2.putText(display_frame, f"Status: {status}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            
            pause_status = "PAUSED" if paused else "RUNNING"
            cv2.putText(display_frame, f"[{pause_status}]", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            cv2.putText(binary_colored, "Binary Mask", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            combined = np.hstack((display_frame, binary_colored))
            cv2.imshow('Mouse Tracking - Original | Binary', combined)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                paused = not paused
            elif key == ord('r'):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.frame_count = 0
                trajectory_points = []
                self.tracking_data = []
                if self.background_subtractor is not None:
                    self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
                        history=500, varThreshold=50, detectShadows=False
                    )
                current_frame = None
                paused = False
            
            if self.frame_count % 100 == 0 and not paused:
                print(f"Processed {self.frame_count}/{total_frames} frames...")
        
        cap.release()
        cv2.destroyAllWindows()
        
        return self.tracking_data
    
    def track_video(
        self,
        video_path: str,
        output_video_path: Optional[str] = None,
        show_preview: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Track mouse throughout the entire video.
        
        Args:
            video_path: Path to input video file
            output_video_path: Path for output visualization video
            show_preview: Whether to show real-time preview
            
        Returns:
            List of tracking data dictionaries
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Video info: {frame_width}x{frame_height} @ {fps:.2f} fps, {total_frames} frames")
        
        video_writer = None
        if output_video_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(
                output_video_path,
                fourcc,
                fps,
                (frame_width, frame_height)
            )
        
        self.tracking_data = []
        self.frame_count = 0
        trajectory_points = []
        
        print("Starting tracking...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            self.frame_count += 1
            timestamp = self.frame_count / fps
            
            centroid, binary_frame, mouse_contour = self.process_frame_full(frame)
            
            frame_data = {
                'frame': self.frame_count,
                'timestamp': round(timestamp, 3),
                'x': None,
                'y': None,
                'detected': False
            }
            
            if centroid is not None:
                cx, cy = centroid
                frame_data['x'] = round(cx, 2)
                frame_data['y'] = round(cy, 2)
                frame_data['detected'] = True
                trajectory_points.append((int(cx), int(cy)))
                
                if video_writer is not None or show_preview:
                    if mouse_contour is not None:
                        cv2.drawContours(frame, [mouse_contour], -1, (0, 255, 0), 2)
                    cv2.circle(frame, (int(cx), int(cy)), 5, (0, 0, 255), -1)
            
            self.tracking_data.append(frame_data)
            
            TRAJECTORY_LENGTH = 30
            if video_writer is not None:
                if len(trajectory_points) >= 2:
                    recent_trajectory = trajectory_points[-TRAJECTORY_LENGTH:]
                    pts = np.array(recent_trajectory, dtype=np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    cv2.polylines(frame, [pts], False, (0, 0, 255), 1, cv2.LINE_AA)
                
                cv2.putText(
                    frame,
                    f"Frame: {self.frame_count}/{total_frames}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )
                
                status = "Tracking" if frame_data['detected'] else "Lost"
                status_color = (0, 255, 0) if frame_data['detected'] else (0, 0, 255)
                cv2.putText(
                    frame,
                    f"Status: {status}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    status_color,
                    2
                )
                
                video_writer.write(frame)
            
            if show_preview:
                binary_colored = cv2.cvtColor(binary_frame, cv2.COLOR_GRAY2BGR)
                
                if centroid is not None:
                    if mouse_contour is not None:
                        cv2.drawContours(binary_colored, [mouse_contour], -1, (0, 255, 0), 2)
                    cv2.circle(binary_colored, (int(cx), int(cy)), 5, (0, 0, 255), -1)
                
                cv2.putText(
                    binary_colored,
                    "Binary Mask",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )
                
                combined = np.hstack((frame, binary_colored))
                cv2.imshow('Mouse Tracking - Original | Binary', combined)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            if self.frame_count % 100 == 0:
                print(f"Processed {self.frame_count}/{total_frames} frames...")
        
        cap.release()
        if video_writer is not None:
            video_writer.release()
        if show_preview:
            cv2.destroyAllWindows()
        
        detected_count = sum(1 for d in self.tracking_data if d['detected'])
        detection_rate = detected_count / len(self.tracking_data) * 100 if self.tracking_data else 0
        
        print(f"\nTracking completed!")
        print(f"Total frames: {self.frame_count}")
        print(f"Detected frames: {detected_count}")
        print(f"Detection rate: {detection_rate:.2f}%")
        
        return self.tracking_data
    
    def save_tracking_data(self, output_path: str) -> None:
        """
        Save tracking data to a JSON file.
        
        Args:
            output_path: Path for output JSON file
        """
        output_data = {
            'metadata': {
                'total_frames': self.frame_count,
                'detected_frames': sum(1 for d in self.tracking_data if d['detected']),
                'tracking_date': datetime.now().isoformat(),
                'parameters': {
                    'blur_kernel_size': self.blur_kernel_size,
                    'threshold_method': self.threshold_method,
                    'min_contour_area': self.min_contour_area,
                    'max_contour_area': self.max_contour_area,
                    'use_background_subtraction': self.use_background_subtraction
                }
            },
            'tracking_data': self.tracking_data
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"Tracking data saved to: {output_path}")
    
    def save_trajectory_csv(self, output_path: str) -> None:
        """
        Save trajectory data to a CSV file.
        
        Args:
            output_path: Path for output CSV file
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('frame,timestamp,x,y,detected\n')
            for data in self.tracking_data:
                x = data['x'] if data['x'] is not None else ''
                y = data['y'] if data['y'] is not None else ''
                f.write(f"{data['frame']},{data['timestamp']},{x},{y},{data['detected']}\n")
        
        print(f"Trajectory CSV saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Mouse Tracking Script for Behavioral Analysis'
    )
    parser.add_argument(
        'video_path',
        type=str,
        help='Path to input video file'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output directory for results (default: same as video directory)'
    )
    parser.add_argument(
        '--no-preview',
        action='store_true',
        help='Disable real-time preview window'
    )
    parser.add_argument(
        '--blur-kernel',
        type=int,
        default=21,
        help='Gaussian blur kernel size (default: 21)'
    )
    parser.add_argument(
        '--threshold-method',
        type=str,
        choices=['binary', 'adaptive', 'otsu'],
        default='adaptive',
        help='Threshold method (default: adaptive)'
    )
    parser.add_argument(
        '--threshold-value',
        type=int,
        default=50,
        help='Threshold value for binary method (default: 50)'
    )
    parser.add_argument(
        '--min-area',
        type=int,
        default=100,
        help='Minimum contour area (default: 100)'
    )
    parser.add_argument(
        '--max-area',
        type=int,
        default=10000,
        help='Maximum contour area (default: 10000)'
    )
    parser.add_argument(
        '--no-background-sub',
        action='store_true',
        help='Disable background subtraction'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Enable interactive mode with parameter sliders'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_path):
        print(f"Error: Video file not found: {args.video_path}")
        return
    
    video_dir = os.path.dirname(args.video_path)
    video_name = os.path.splitext(os.path.basename(args.video_path))[0]
    
    output_dir = args.output if args.output else video_dir
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_video = os.path.join(output_dir, f"{video_name}_tracked.mp4")
    output_json = os.path.join(output_dir, f"{video_name}_tracking_data.json")
    output_csv = os.path.join(output_dir, f"{video_name}_trajectory.csv")
    
    tracker = MouseTracker(
        blur_kernel_size=(args.blur_kernel, args.blur_kernel),
        threshold_method=args.threshold_method,
        threshold_value=args.threshold_value,
        min_contour_area=args.min_area,
        max_contour_area=args.max_area,
        use_background_subtraction=not args.no_background_sub
    )
    
    try:
        if args.interactive:
            tracker.track_video_interactive(
                args.video_path,
                output_video_path=output_video
            )
        else:
            tracker.track_video(
                args.video_path,
                output_video_path=output_video,
                show_preview=not args.no_preview
            )
        
        tracker.save_tracking_data(output_json)
        tracker.save_trajectory_csv(output_csv)
        
        print(f"\nOutput files:")
        print(f"  Video: {output_video}")
        print(f"  JSON: {output_json}")
        print(f"  CSV: {output_csv}")
        
    except Exception as e:
        print(f"Error during tracking: {e}")
        raise


if __name__ == '__main__':
    main()
