"""
Static Background Subtraction Mouse Tracker
解决长时间静止物体被误判为背景的问题
"""

import cv2
import numpy as np
import argparse
import json
import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any


class StaticBackgroundTracker:
    """
    使用静态背景相减法的小鼠追踪器
    
    算法流程：
    1. 加载预存的绝对背景图（或拍摄空场景）
    2. 将当前帧与背景图进行逐像素相减
    3. 设定阈值提取前景物体
    4. 形态学处理去噪
    5. 轮廓检测与质心计算
    """
    
    def __init__(
        self,
        background_image_path: Optional[str] = None,
        blur_kernel_size: Tuple[int, int] = (5, 5),
        diff_threshold: int = 30,
        min_contour_area: int = 100,
        max_contour_area: int = 10000,
        morph_kernel_size: int = 5,
        use_gaussian_threshold: bool = True
    ):
        """
        初始化静态背景追踪器
        
        Args:
            background_image_path: 背景图像路径（PNG格式）
            blur_kernel_size: 高斯模糊核大小
            diff_threshold: 像素差异阈值（默认30，值越小越敏感）
            min_contour_area: 最小轮廓面积
            max_contour_area: 最大轮廓面积
            morph_kernel_size: 形态学核大小
            use_gaussian_threshold: 是否使用自适应阈值
        """
        self.blur_kernel_size = blur_kernel_size
        self.diff_threshold = diff_threshold
        self.min_contour_area = min_contour_area
        self.max_contour_area = max_contour_area
        self.morph_kernel_size = morph_kernel_size
        self.use_gaussian_threshold = use_gaussian_threshold
        
        self.background_image = None
        if background_image_path and os.path.exists(background_image_path):
            self.load_background(background_image_path)
        
        self.tracking_data: List[Dict[str, Any]] = []
        self.frame_count = 0
    
    def load_background(self, background_image_path: str) -> None:
        """加载背景图像"""
        self.background_image = cv2.imread(background_image_path)
        if self.background_image is None:
            raise ValueError(f"无法加载背景图像: {background_image_path}")
        print(f"已加载背景图像: {background_image_path}")
        print(f"背景图像尺寸: {self.background_image.shape}")
    
    def capture_background(self, video_path: str, output_path: str, frame_skip: int = 0) -> None:
        """
        从视频中捕获纯净背景
        
        Args:
            video_path: 视频文件路径
            output_path: 输出背景图像路径
            frame_skip: 跳过的帧数（用于跳过开头的晃动帧）
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")
        
        for _ in range(frame_skip):
            cap.read()
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            raise ValueError("无法读取视频帧")
        
        self.background_image = frame.copy()
        cv2.imwrite(output_path, self.background_image)
        print(f"背景图像已保存至: {output_path}")
    
    def capture_best_background(self, video_path: str, output_path: str, 
                                start_frame: int = 0, end_frame: int = 50,
                                method: str = 'median') -> None:
        """
        从视频中捕获最佳背景（多帧融合）
        
        Args:
            video_path: 视频文件路径
            output_path: 输出背景图像路径
            start_frame: 起始帧
            end_frame: 结束帧
            method: 融合方法 ('median' 或 'mean')
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")
        
        frames = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        for frame_idx in range(start_frame, end_frame):
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        
        cap.release()
        
        if not frames:
            raise ValueError("无法读取视频帧")
        
        if method == 'median':
            self.background_image = np.median(frames, axis=0).astype(np.uint8)
        else:
            self.background_image = np.mean(frames, axis=0).astype(np.uint8)
        
        cv2.imwrite(output_path, self.background_image)
        print(f"最佳背景图像已保存至: {output_path} (基于 {len(frames)} 帧)")
    
    def process_frame(self, frame: np.ndarray) -> Tuple[Optional[Tuple[float, float]], np.ndarray, Optional[np.ndarray]]:
        """
        处理单帧图像
        
        Args:
            frame: 输入BGR帧
            
        Returns:
            Tuple of (质心坐标或None, 二值化图像, 轮廓或None)
        """
        if self.background_image is None:
            raise ValueError("未加载背景图像，请先调用 load_background() 或 capture_background()")
        
        if frame.shape != self.background_image.shape:
            frame = cv2.resize(frame, (self.background_image.shape[1], self.background_image.shape[0]))
        
        blurred = cv2.GaussianBlur(frame, self.blur_kernel_size, 0)
        bg_blurred = cv2.GaussianBlur(self.background_image, self.blur_kernel_size, 0)
        
        diff = cv2.absdiff(blurred, bg_blurred)
        
        if self.use_gaussian_threshold:
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, fg_mask = cv2.threshold(gray_diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        else:
            fg_mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, fg_mask = cv2.threshold(fg_mask, self.diff_threshold, 255, cv2.THRESH_BINARY)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.morph_kernel_size, self.morph_kernel_size))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        mouse_contour = None
        centroid = None
        
        if contours:
            valid_contours = [c for c in contours if self.min_contour_area <= cv2.contourArea(c) <= self.max_contour_area]
            if valid_contours:
                mouse_contour = max(valid_contours, key=cv2.contourArea)
                M = cv2.moments(mouse_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    centroid = (cx, cy)
        
        return centroid, fg_mask, mouse_contour
    
    def track_video(
        self,
        video_path: str,
        output_video_path: Optional[str] = None,
        show_preview: bool = False
    ) -> List[Dict[str, Any]]:
        """追踪视频中的小鼠"""
        if self.background_image is None:
            raise ValueError("请先加载背景图像或捕获新背景")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"视频信息: {frame_width}x{frame_height} @ {fps:.2f} fps, {total_frames} 帧")
        
        video_writer = None
        if output_video_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))
        
        self.tracking_data = []
        self.frame_count = 0
        trajectory_points = []
        
        print("开始追踪...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            self.frame_count += 1
            timestamp = self.frame_count / fps
            
            centroid, fg_mask, mouse_contour = self.process_frame(frame)
            
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
                
                cv2.putText(frame, f"帧: {self.frame_count}/{total_frames}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                status = "追踪中" if frame_data['detected'] else "丢失"
                status_color = (0, 255, 0) if frame_data['detected'] else (0, 0, 255)
                cv2.putText(frame, f"状态: {status}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                
                video_writer.write(frame)
            
            if show_preview:
                fg_colored = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2BGR)
                
                if centroid is not None:
                    if mouse_contour is not None:
                        cv2.drawContours(fg_colored, [mouse_contour], -1, (0, 255, 0), 2)
                    cv2.circle(fg_colored, (int(cx), int(cy)), 5, (0, 0, 255), -1)
                
                cv2.putText(fg_colored, "前景 Mask", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                combined = np.hstack((frame, fg_colored))
                cv2.imshow('Static BG Tracking - Original | Foreground', combined)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            if self.frame_count % 100 == 0:
                print(f"已处理 {self.frame_count}/{total_frames} 帧...")
        
        cap.release()
        if video_writer is not None:
            video_writer.release()
        if show_preview:
            cv2.destroyAllWindows()
        
        detected_count = sum(1 for d in self.tracking_data if d['detected'])
        detection_rate = detected_count / len(self.tracking_data) * 100 if self.tracking_data else 0
        
        print(f"\n追踪完成!")
        print(f"总帧数: {self.frame_count}")
        print(f"检测帧数: {detected_count}")
        print(f"检测率: {detection_rate:.2f}%")
        
        return self.tracking_data
    
    def track_video_interactive(
        self,
        video_path: str,
        output_video_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """交互模式追踪"""
        if self.background_image is None:
            raise ValueError("请先加载背景图像或捕获新背景")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"视频信息: {frame_width}x{frame_height} @ {fps:.2f} fps, {total_frames} 帧")
        
        cv2.namedWindow('Controls', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Controls', 400, 300)
        
        params = {
            'diff_threshold': self.diff_threshold,
            'min_area': self.min_contour_area,
            'max_area': self.max_contour_area,
            'morph_kernel': self.morph_kernel_size,
            'blur_kernel': max(1, self.blur_kernel_size[0])
        }
        
        cv2.createTrackbar('Diff Threshold', 'Controls', params['diff_threshold'], 100, lambda x: None)
        cv2.createTrackbar('Min Area', 'Controls', params['min_area'], 5000, lambda x: None)
        cv2.createTrackbar('Max Area', 'Controls', params['max_area'], 50000, lambda x: None)
        cv2.createTrackbar('Morph Kernel', 'Controls', params['morph_kernel'], 15, lambda x: None)
        cv2.createTrackbar('Blur Kernel', 'Controls', params['blur_kernel'], 21, lambda x: None)
        
        cv2.setTrackbarPos('Diff Threshold', 'Controls', params['diff_threshold'])
        cv2.setTrackbarPos('Min Area', 'Controls', params['min_area'])
        cv2.setTrackbarPos('Max Area', 'Controls', params['max_area'])
        cv2.setTrackbarPos('Morph Kernel', 'Controls', params['morph_kernel'])
        cv2.setTrackbarPos('Blur Kernel', 'Controls', params['blur_kernel'])
        
        self.tracking_data = []
        self.frame_count = 0
        trajectory_points = []
        paused = False
        current_frame = None
        
        print("开始交互追踪...")
        print("控制: 空格=暂停/继续, Q=退出, R=重置")
        
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
            
            params['diff_threshold'] = cv2.getTrackbarPos('Diff Threshold', 'Controls')
            params['min_area'] = cv2.getTrackbarPos('Min Area', 'Controls')
            params['max_area'] = cv2.getTrackbarPos('Max Area', 'Controls')
            params['morph_kernel'] = cv2.getTrackbarPos('Morph Kernel', 'Controls')
            
            blur_k = cv2.getTrackbarPos('Blur Kernel', 'Controls')
            blur_k = max(1, blur_k if blur_k % 2 == 1 else blur_k + 1)
            
            self.diff_threshold = params['diff_threshold']
            self.min_contour_area = params['min_area']
            self.max_contour_area = max(self.min_contour_area + 1, params['max_area'])
            self.morph_kernel_size = params['morph_kernel']
            self.blur_kernel_size = (blur_k, blur_k)
            
            centroid, fg_mask, mouse_contour = self.process_frame(frame)
            
            display_frame = frame.copy()
            fg_colored = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2BGR)
            
            if centroid is not None:
                cx, cy = int(centroid[0]), int(centroid[1])
                
                if mouse_contour is not None:
                    cv2.drawContours(display_frame, [mouse_contour], -1, (0, 255, 0), 2)
                    cv2.drawContours(fg_colored, [mouse_contour], -1, (0, 255, 0), 2)
                
                cv2.circle(display_frame, (cx, cy), 5, (0, 0, 255), -1)
                cv2.circle(fg_colored, (cx, cy), 5, (0, 0, 255), -1)
                
                if not paused:
                    trajectory_points.append((cx, cy))
            
            TRAJECTORY_LENGTH = 30
            if len(trajectory_points) > 1:
                recent_trajectory = trajectory_points[-TRAJECTORY_LENGTH:]
                if len(recent_trajectory) >= 2:
                    pts = np.array(recent_trajectory, dtype=np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    cv2.polylines(display_frame, [pts], False, (0, 0, 255), 1, cv2.LINE_AA)
            
            cv2.putText(display_frame, f"帧: {self.frame_count}/{total_frames}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            status = "追踪中" if centroid is not None else "丢失"
            status_color = (0, 255, 0) if centroid is not None else (0, 0, 255)
            cv2.putText(display_frame, f"状态: {status}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            
            pause_status = "已暂停" if paused else "运行中"
            cv2.putText(display_frame, f"[{pause_status}]", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            cv2.putText(fg_colored, "前景 Mask", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            combined = np.hstack((display_frame, fg_colored))
            cv2.imshow('Static BG Tracking - Original | Foreground', combined)
            
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
                current_frame = None
                paused = False
            
            if self.frame_count % 100 == 0 and not paused:
                print(f"已处理 {self.frame_count}/{total_frames} 帧...")
        
        cap.release()
        cv2.destroyAllWindows()
        
        return self.tracking_data
    
    def save_tracking_data(self, output_path: str) -> None:
        """保存追踪数据到JSON"""
        output_data = {
            'metadata': {
                'total_frames': self.frame_count,
                'detected_frames': sum(1 for d in self.tracking_data if d['detected']),
                'tracking_date': datetime.now().isoformat(),
                'method': 'static_background_subtraction',
                'parameters': {
                    'background_image_loaded': self.background_image is not None,
                    'diff_threshold': self.diff_threshold,
                    'min_contour_area': self.min_contour_area,
                    'max_contour_area': self.max_contour_area,
                    'morph_kernel_size': self.morph_kernel_size,
                    'blur_kernel_size': self.blur_kernel_size
                }
            },
            'tracking_data': self.tracking_data
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"追踪数据已保存至: {output_path}")
    
    def save_trajectory_csv(self, output_path: str) -> None:
        """保存轨迹到CSV"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('frame,timestamp,x,y,detected\n')
            for data in self.tracking_data:
                x = data['x'] if data['x'] is not None else ''
                y = data['y'] if data['y'] is not None else ''
                f.write(f"{data['frame']},{data['timestamp']},{x},{y},{data['detected']}\n")
        
        print(f"轨迹CSV已保存至: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='静态背景相减小鼠追踪器')
    parser.add_argument('video_path', type=str, help='视频文件路径')
    parser.add_argument('-b', '--background', type=str, default=None, help='背景图像路径')
    parser.add_argument('-c', '--capture-bg', action='store_true', help='从视频捕获背景')
    parser.add_argument('--bg-start', type=int, default=0, help='捕获背景起始帧')
    parser.add_argument('--bg-end', type=int, default=50, help='捕获背景结束帧')
    parser.add_argument('--bg-output', type=str, default='background.png', help='背景图像输出路径')
    parser.add_argument('-o', '--output', type=str, default=None, help='输出目录')
    parser.add_argument('-i', '--interactive', action='store_true', help='交互模式')
    parser.add_argument('--no-preview', action='store_true', help='禁用预览')
    parser.add_argument('--diff-threshold', type=int, default=30, help='像素差异阈值')
    parser.add_argument('--min-area', type=int, default=100, help='最小轮廓面积')
    parser.add_argument('--max-area', type=int, default=10000, help='最大轮廓面积')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_path):
        print(f"错误: 视频文件不存在: {args.video_path}")
        return
    
    video_dir = os.path.dirname(args.video_path)
    video_name = os.path.splitext(os.path.basename(args.video_path))[0]
    output_dir = args.output if args.output else video_dir
    
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    tracker = StaticBackgroundTracker(
        background_image_path=args.background,
        diff_threshold=args.diff_threshold,
        min_contour_area=args.min_area,
        max_contour_area=args.max_area
    )
    
    if args.capture_bg:
        print("正在捕获背景图像...")
        tracker.capture_best_background(
            args.video_path, 
            args.bg_output,
            start_frame=args.bg_start,
            end_frame=args.bg_end
        )
        args.background = args.bg_output
    
    if args.background:
        tracker.load_background(args.background)
    else:
        print("警告: 未提供背景图像，将尝试从视频捕获...")
        bg_auto = os.path.join(output_dir, 'auto_background.png')
        tracker.capture_best_background(args.video_path, bg_auto, start_frame=5, end_frame=30)
        tracker.load_background(bg_auto)
    
    output_video = os.path.join(output_dir, f"{video_name}_static_tracked.mp4")
    output_json = os.path.join(output_dir, f"{video_name}_static_tracking.json")
    output_csv = os.path.join(output_dir, f"{video_name}_static_trajectory.csv")
    
    try:
        if args.interactive:
            tracker.track_video_interactive(args.video_path, output_video)
        else:
            tracker.track_video(
                args.video_path,
                output_video_path=output_video,
                show_preview=not args.no_preview
            )
        
        tracker.save_tracking_data(output_json)
        tracker.save_trajectory_csv(output_csv)
        
        print(f"\n输出文件:")
        print(f"  视频: {output_video}")
        print(f"  JSON: {output_json}")
        print(f"  CSV: {output_csv}")
        
    except Exception as e:
        print(f"追踪错误: {e}")
        raise


if __name__ == '__main__':
    main()
