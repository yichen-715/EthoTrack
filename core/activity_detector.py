"""
活动检测器 - Activity Detector
用于强迫游泳实验的活动检测
通过帧差法计算像素变化率来评估动物运动强度
"""

import cv2
import numpy as np
from typing import Tuple, Optional


class ActivityDetector:
    """活动检测器类"""
    
    def __init__(self, activity_threshold: int = 15, 
                 immobility_threshold: float = 5.0,
                 swimming_threshold: float = 20.0):
        """
        初始化活动检测器
        
        Args:
            activity_threshold: 活动阈值（像素差异阈值，0-255）
            immobility_threshold: 不动阈值（活动率百分比）
            swimming_threshold: 游泳阈值（活动率百分比）
        """
        self.activity_threshold = activity_threshold
        self.immobility_threshold = immobility_threshold
        self.swimming_threshold = swimming_threshold
        
        # 上一帧（灰度图）
        self.prev_frame = None
        
    def set_thresholds(self, activity_threshold: Optional[int] = None,
                      immobility_threshold: Optional[float] = None,
                      swimming_threshold: Optional[float] = None):
        """更新阈值"""
        if activity_threshold is not None:
            self.activity_threshold = activity_threshold
        if immobility_threshold is not None:
            self.immobility_threshold = immobility_threshold
        if swimming_threshold is not None:
            self.swimming_threshold = swimming_threshold
    
    def reset(self):
        """重置检测器"""
        self.prev_frame = None
    
    def calculate_activity(self, frame: np.ndarray, 
                          arena_mask: Optional[np.ndarray] = None) -> Tuple[float, np.ndarray, str]:
        """
        计算当前帧的活动率
        
        Args:
            frame: 当前帧（BGR格式）
            arena_mask: 竞技场掩码（可选，只分析掩码内的区域）
            
        Returns:
            activity_rate: 活动率（百分比，0-100）
            diff_image: 帧差图像（用于可视化）
            behavior_state: 行为状态 ('immobile', 'swimming', 'struggling')
        """
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 如果是第一帧，保存并返回0活动率
        if self.prev_frame is None:
            self.prev_frame = gray.copy()
            
            # 创建空白差异图像
            if arena_mask is not None:
                diff_image = np.zeros_like(gray)
            else:
                diff_image = np.zeros_like(gray)
            
            return 0.0, diff_image, 'immobile'
        
        # 计算帧差
        diff = cv2.absdiff(self.prev_frame, gray)
        
        # 应用竞技场掩码（如果提供）
        if arena_mask is not None:
            diff_masked = cv2.bitwise_and(diff, diff, mask=arena_mask)
        else:
            diff_masked = diff
        
        # 应用活动阈值
        _, thresh = cv2.threshold(diff_masked, self.activity_threshold, 255, cv2.THRESH_BINARY)
        
        # 计算活动像素数量
        activity_pixels = cv2.countNonZero(thresh)
        
        # 计算总像素数量（竞技场内）
        if arena_mask is not None:
            total_pixels = cv2.countNonZero(arena_mask)
        else:
            total_pixels = gray.shape[0] * gray.shape[1]
        
        # 计算活动率（百分比）
        if total_pixels > 0:
            activity_rate = (activity_pixels / total_pixels) * 100.0
        else:
            activity_rate = 0.0
        
        # 分类行为状态
        behavior_state = self._classify_behavior(activity_rate)
        
        # 创建可视化图像（反转：白色=无变化，黑色=有运动）
        diff_image = cv2.bitwise_not(thresh)
        
        # 更新上一帧
        self.prev_frame = gray.copy()
        
        return activity_rate, diff_image, behavior_state
    
    def _classify_behavior(self, activity_rate: float) -> str:
        """
        根据活动率分类行为状态
        
        Args:
            activity_rate: 活动率（百分比）
            
        Returns:
            behavior_state: 'immobile', 'swimming', 或 'struggling'
        """
        if activity_rate < self.immobility_threshold:
            return 'immobile'  # 不动/漂浮
        elif activity_rate < self.swimming_threshold:
            return 'swimming'  # 游泳
        else:
            return 'struggling'  # 挣扎
    
    def get_behavior_label(self, behavior_state: str) -> str:
        """
        获取行为状态的中文标签
        
        Args:
            behavior_state: 行为状态
            
        Returns:
            中文标签
        """
        labels = {
            'immobile': '不动',
            'swimming': '游泳',
            'struggling': '挣扎'
        }
        return labels.get(behavior_state, '未知')
    
    def get_behavior_color(self, behavior_state: str) -> Tuple[int, int, int]:
        """
        获取行为状态的颜色（BGR格式）
        
        Args:
            behavior_state: 行为状态
            
        Returns:
            BGR颜色元组
        """
        colors = {
            'immobile': (128, 128, 128),   # 灰色
            'swimming': (255, 255, 0),     # 青色
            'struggling': (0, 0, 255)      # 红色
        }
        return colors.get(behavior_state, (255, 255, 255))


class ActivityDataCollector:
    """活动数据收集器"""
    
    def __init__(self, fps: float = 30.0):
        """
        初始化数据收集器
        
        Args:
            fps: 视频帧率
        """
        self.fps = fps
        self.reset()
    
    def reset(self):
        """重置收集器"""
        self.activity_data = []  # 存储每帧的活动数据
        self.start_time = 0.0
        self.first_immobility_time = None  # 首次不动时间
    
    def add_frame_data(self, frame_idx: int, activity_rate: float, behavior_state: str):
        """
        添加一帧的数据
        
        Args:
            frame_idx: 帧索引
            activity_rate: 活动率
            behavior_state: 行为状态
        """
        time = frame_idx / self.fps
        
        self.activity_data.append({
            'frame': frame_idx,
            'time': time,
            'activity_rate': activity_rate,
            'state': behavior_state
        })
        
        # 记录首次不动时间
        if behavior_state == 'immobile' and self.first_immobility_time is None:
            self.first_immobility_time = time
    
    def get_summary(self) -> dict:
        """
        获取汇总统计数据
        
        Returns:
            包含各项统计指标的字典
        """
        if not self.activity_data:
            return {
                'total_duration': 0.0,
                'immobility_time': 0.0,
                'swimming_time': 0.0,
                'struggling_time': 0.0,
                'immobility_percentage': 0.0,
                'swimming_percentage': 0.0,
                'struggling_percentage': 0.0,
                'latency_to_immobility': 0.0,
                'frame_count': 0
            }
        
        # 计算总时长
        total_duration = len(self.activity_data) / self.fps
        
        # 统计各状态的帧数
        immobile_frames = sum(1 for d in self.activity_data if d['state'] == 'immobile')
        swimming_frames = sum(1 for d in self.activity_data if d['state'] == 'swimming')
        struggling_frames = sum(1 for d in self.activity_data if d['state'] == 'struggling')
        
        # 转换为时间（秒）
        immobility_time = immobile_frames / self.fps
        swimming_time = swimming_frames / self.fps
        struggling_time = struggling_frames / self.fps
        
        # 计算百分比
        total_frames = len(self.activity_data)
        immobility_percentage = (immobile_frames / total_frames * 100) if total_frames > 0 else 0.0
        swimming_percentage = (swimming_frames / total_frames * 100) if total_frames > 0 else 0.0
        struggling_percentage = (struggling_frames / total_frames * 100) if total_frames > 0 else 0.0
        
        # 不动潜伏期
        latency_to_immobility = self.first_immobility_time if self.first_immobility_time is not None else total_duration
        
        return {
            'total_duration': total_duration,
            'immobility_time': immobility_time,
            'swimming_time': swimming_time,
            'struggling_time': struggling_time,
            'immobility_percentage': immobility_percentage,
            'swimming_percentage': swimming_percentage,
            'struggling_percentage': struggling_percentage,
            'latency_to_immobility': latency_to_immobility,
            'frame_count': total_frames
        }
    
    def get_activity_data(self) -> list:
        """获取原始活动数据"""
        return self.activity_data.copy()

