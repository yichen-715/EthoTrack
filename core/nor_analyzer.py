import math
import numpy as np
from typing import Dict, List, Tuple, Optional
from core.logger import logger

class NORAnalyzer:
    """新物体识别(NOR)实验的核心分析器"""
    def __init__(self, fps: float = 30.0, px_to_cm: float = 1.0, sniffing_angle_threshold: float = 45.0):
        """
        初始化 NOR 分析器
        
        Args:
            fps: 视频的实际处理帧率
            px_to_cm: 像素到厘米的换算比例
            sniffing_angle_threshold: 判定为探索的最大允许夹角（度），即动物朝向与动物到物体中心的连线夹角
        """
        self.fps = fps
        self.px_to_cm = px_to_cm
        self.sniffing_angle_threshold = sniffing_angle_threshold
        self.reset()
        
    def reset(self):
        """重置所有统计数据"""
        # 结果字典：记录各个物体的探索累加时间和帧数
        self.object_stats = {}
        
        # 详细逐帧记录 [{'frame_idx': 1, 'time': 0.033, 'x': 100, 'y': 100, 'status': 'novel_obj_1', ...}, ...]
        self.trajectory_data: List[Dict] = []
        
        # 运动学指标准备变量
        self.total_distance_px = 0.0
        self.total_frames = 0
        self.prev_point_cm = None
        self.previous_state = 'arena'
        
    def setup_objects(self, objects_data: List[Dict]):
        """
        根据画好的 ROI 配置加载物体数据并初始化其统计容器
        
        Args:
            objects_data: 从 nor_zone_dialog 保存的 `objects` 配置字典列表
        """
        self.objects = objects_data
        self.object_stats = {}
        for obj in self.objects:
            obj_id = obj['id']
            obj_type = obj['type']
            self.object_stats[obj_id] = {'type': obj_type, 'frames': 0, 'time_sec': 0.0, 'entries': 0}
            logger.debug(f"[NOR] 载入物体: ID={obj_id}, 类型={obj_type}")
        
    def process_frame_data(self, frame_idx: int, detection_data: Dict) -> str:
        """
        计算单帧的数据，并在类中累加统计值。
        
        Args:
            frame_idx: 当前帧号
            detection_data: 字典，包含 'centroid', 'three_points' 其中三点包含 'head', 'center', 'tail' 的 (x,y) 元组
            
        Returns:
            状态字符串：比如 'familiar_obj_1', 'novel_obj_2', 'arena' (在场内没探索) 或 'none' (未检测到)
        """
        self.total_frames += 1
        current_time = frame_idx / self.fps if self.fps > 0 else 0
        state = 'arena'
        
        # 获取用于判定运动学指标代表位置，优先使用质心
        center_pt = detection_data.get('centroid')
        three_points = detection_data.get('three_points')
        
        if not center_pt and three_points:
            center_pt = three_points.get('center')
            
        # 如果本帧完全没有检测到动物
        if not center_pt:
            self.trajectory_data.append({
                'frame': frame_idx, 'time': current_time,
                'x': None, 'y': None, 'state': 'none'
            })
            return 'none'
            
        # 1. 更新总运动距离 (使用简单的欧几里得距离)
        current_pt_px = np.array(center_pt)
        if self.prev_point_cm is not None:
            dist_px = np.linalg.norm(current_pt_px - self.prev_point_cm)
            self.total_distance_px += dist_px
        self.prev_point_cm = current_pt_px
        
        # 2. 探索探测核心逻辑 (Sniffing Detection)
        head_pt = None
        if three_points and 'head' in three_points:
            head_pt = three_points['head']
            
        # 若需要更精确探测，且有头部坐标，直接判断头部是否在扩展区内 (不再判断头部与物体夹角)
        if head_pt:
            for obj in self.objects:
                if self._check_point_in_sniffing_zone(head_pt, obj):
                    state = obj['id']
                    self.object_stats[state]['frames'] += 1
                    self.object_stats[state]['time_sec'] = self.object_stats[state]['frames'] / self.fps
                    break
                    
        # 降级方案：如果未能提取头部点（只有质心），则判断质心是否在 Sniffing Zone 内
        elif center_pt:
            for obj in self.objects:
                if self._check_point_in_sniffing_zone(center_pt, obj):
                    state = obj['id']
                    self.object_stats[state]['frames'] += 1
                    self.object_stats[state]['time_sec'] = self.object_stats[state]['frames'] / self.fps
                    break
                    
        # 记录本帧坐标与状态
        self.trajectory_data.append({
            'frame': frame_idx, 'time': current_time, 
            'x': center_pt[0], 'y': center_pt[1], 
            'head_x': head_pt[0] if head_pt else None,
            'head_y': head_pt[1] if head_pt else None,
            'state': state
        })
        
        # 判断进出逻辑，增加频次
        if state != 'none' and state != 'arena' and state != self.previous_state:
            self.object_stats[state]['entries'] += 1
            # logger.debug(f"[NOR] 进入物体区域: {state} (类型: {self.object_stats[state]['type']})")
            
        if state != 'none':
            self.previous_state = state
        
        return state
        
    # ------------- 核心数学算理 -------------

    def _check_point_in_sniffing_zone(self, point: Tuple[float, float], obj: Dict) -> bool:
        """纯粹点包含算法：检查 point 是否在物体的扩展交互圈内"""
        x, y = point
        rect = obj['rect']
        radius = obj['interaction_radius']
        
        obj_type = obj.get('shape', 'circle')
        
        if obj_type == 'circle':
            # 物体的实际中心点和实际半径
            cx = rect['x'] + rect['width'] / 2.0
            cy = rect['y'] + rect['height'] / 2.0
            obj_radius = min(rect['width'], rect['height']) / 2.0
            
            # 扩展交互圈的半径
            sniffing_radius = obj_radius + radius
            
            # 判断到圆心距离
            dist = math.hypot(x - cx, y - cy)
            return dist <= sniffing_radius
            
        elif obj_type == 'rectangle':
            # 将矩形探测区优化为带圆角的扩展缓冲区，以提供更符合动物嗅探规律的检测
            rect_x, rect_y = rect['x'], rect['y']
            rect_w, rect_h = rect['width'], rect['height']
            
            # 找到点在基准矩形内的最接近点
            closest_x = max(rect_x, min(x, rect_x + rect_w))
            closest_y = max(rect_y, min(y, rect_y + rect_h))
            
            # 计算目标点到该最接近点的距离，如在矩形内距离为0，在其外则为到边缘或顶点的距离
            dist = math.hypot(x - closest_x, y - closest_y)
            return dist <= radius
            
        elif obj_type == 'triangle':
            # 等腰三角形（顶点朝上），扩张版：顶点各向外推 radius
            rx, ry = rect['x'], rect['y']
            rw, rh = rect['width'], rect['height']
            # 三个顶点（向外扩张 radius）
            tip   = (rx + rw / 2.0, ry - radius)          # 顶端上移
            bl_pt = (rx - radius,   ry + rh + radius)     # 左下外移
            br_pt = (rx + rw + radius, ry + rh + radius)  # 右下外移
            # 使用向量叉积判断点是否在三角形内
            def _sign(p1, p2, p3):
                return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
            pt = (x, y)
            d1 = _sign(pt, tip, br_pt)
            d2 = _sign(pt, br_pt, bl_pt)
            d3 = _sign(pt, bl_pt, tip)
            has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
            has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
            return not (has_neg and has_pos)
            
        return False


    def _check_sniffing_with_angle(self, head_pt: Tuple[float, float], center_pt: Tuple[float, float], obj: Dict) -> bool:
        """
        组合检测：
        1. 检查头部是否在扩展交互区 (Sniffing Zone) 内
        2. 若在，进一步计算：身体运动朝向 (Center -> Head) 和 物体中心相对身位的朝向 (Center -> ObjectCenter) 的夹角是否小于阈值
        """
        if not self._check_point_in_sniffing_zone(head_pt, obj):
            return False
            
        # 获取物体的几何中心
        rect = obj['rect']
        obj_cx = rect['x'] + rect['width'] / 2.0
        obj_cy = rect['y'] + rect['height'] / 2.0
        
        # 向量 A: 动物朝向 (身体中心 -> 头部)
        vec_animal_dir = (head_pt[0] - center_pt[0], head_pt[1] - center_pt[1])
        
        # 向量 B: 物体方向 (身体中心 -> 物体中心)
        vec_to_obj = (obj_cx - center_pt[0], obj_cy - center_pt[1])
        
        # 计算夹角
        dot_product = vec_animal_dir[0] * vec_to_obj[0] + vec_animal_dir[1] * vec_to_obj[1]
        norm_a = math.hypot(*vec_animal_dir)
        norm_b = math.hypot(*vec_to_obj)
        
        if norm_a == 0 or norm_b == 0:
            return False
            
        # 防止浮点数精度超界溢出 [-1, 1]
        cos_theta = max(-1.0, min(1.0, dot_product / (norm_a * norm_b)))
        angle_deg = math.degrees(math.acos(cos_theta))
        
        return angle_deg <= self.sniffing_angle_threshold
        
    # ------------- 结果统计 -------------

    def get_summary_results(self) -> Dict:
        """
        计算该竞技场内的最终统计学结果 (DI, PI, 运动学数据等)
        """
        time_familiar = 0.0
        time_novel = 0.0
        freq_familiar = 0
        freq_novel = 0
        
        for obj_id, st in self.object_stats.items():
            if st['type'] == 'familiar':
                time_familiar += st['time_sec']
                freq_familiar += st.get('entries', 0)
            elif st['type'] == 'novel':
                time_novel += st['time_sec']
                freq_novel += st.get('entries', 0)
                
        # Discrimination Index (DI) = (T_novel - T_familiar) / (T_novel + T_familiar)
        total_exploration = time_novel + time_familiar
        
        di = 0.0
        pi = 0.0
        if total_exploration > 0:
            di = (time_novel - time_familiar) / total_exploration
            pi = (time_novel / total_exploration) * 100.0
            
        # logger.debug(f"[NOR] 总结: Familiar={time_familiar:.1f}s, Novel={time_novel:.1f}s, DI={di:.2f}, PI={pi:.1f}%")

        # 运动学换算 (px -> cm)
        total_dist_cm = self.total_distance_px * self.px_to_cm
        duration_sec = self.total_frames / self.fps if self.fps > 0 else 0
        avg_speed = total_dist_cm / duration_sec if duration_sec > 0 else 0
        
        return {
            'time_familiar': time_familiar,
            'time_novel': time_novel,
            'freq_familiar': freq_familiar,
            'freq_novel': freq_novel,
            'total_exploration': total_exploration,
            'discrimination_index': di,
            'preference_index': pi,
            'total_distance_cm': total_dist_cm,
            'avg_speed_cm_s': avg_speed,
            'duration_sec': duration_sec
        }
