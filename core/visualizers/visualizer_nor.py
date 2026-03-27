import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import os
import seaborn as sns
from typing import List, Dict, Optional

class NORVisualizer:
    """新物体识别 (NOR) 结果可视化工具"""
    
    @staticmethod
    def draw_trajectory(bg_idx: np.ndarray, 
                       trajectory_data: List[Dict], 
                       objects_data: List[Dict],
                       arena_rect: Optional[Dict] = None,
                       output_path: str = "") -> np.ndarray:
        """
        在背景图上绘制带有区域颜色的运动轨迹
        """
        # 复制背景，若无背景则创建白底
        if bg_idx is not None and bg_idx.size > 0:
            if len(bg_idx.shape) == 2:
                img = cv2.cvtColor(bg_idx, cv2.COLOR_GRAY2BGR)
            else:
                img = bg_idx.copy()
        else:
            if arena_rect:
                h = int(arena_rect['y'] + arena_rect['height'] + 50)
                w = int(arena_rect['x'] + arena_rect['width'] + 50)
            else:
                h, w = 600, 800
            img = np.ones((h, w, 3), dtype=np.uint8) * 255
            
        # 定义颜色映射
        color_map = {
            'none': (200, 200, 200),  # 浅灰: 未检测到
            'arena': (0, 0, 255),     # 红色: 在竞技场普通运动
        }
        
        # 为每个新/旧物体定义颜色 (新物体：橙/红，旧物体：蓝)
        for obj in objects_data:
            obj_id = obj['id']
            if obj['type'] == 'novel':
                color_map[obj_id] = (0, 165, 255) # 橙色 BGR
            else:
                color_map[obj_id] = (255, 0, 0)   # 蓝色 BGR
                
        # --- 1. 绘制物体范围标示 ---
        overlay = img.copy()
        for obj in objects_data:
            rect = obj['rect']
            r = obj['interaction_radius']
            color = color_map.get(obj['id'], (0, 255, 0))
            
            x, y, w_obj, h_obj = int(rect['x']), int(rect['y']), int(rect['width']), int(rect['height'])
            
            if obj.get('shape') == 'circle':
                # 画中心实体圆
                cx, cy = x + w_obj // 2, y + h_obj // 2
                radius = min(w_obj, h_obj) // 2
                cv2.circle(overlay, (cx, cy), radius, color, -1)
                
                # 画探索扩展圈
                cv2.circle(img, (cx, cy), radius + r, color, 2)
            else:
                # 画矩形实体
                cv2.rectangle(overlay, (x, y), (x + w_obj, y + h_obj), color, -1)
                
                # 画探索扩展框
                cv2.rectangle(img, (x - r, y - r), (x + w_obj + r, y + h_obj + r), color, 2)
                
        # 融合半透明物体标示
        cv2.addWeighted(overlay, 0.4, img, 0.6, 0, img)
        
        # --- 2. 绘制轨迹线 ---
        valid_points = []
        for d in trajectory_data:
            if d['x'] is not None and d['y'] is not None:
                valid_points.append(d)
                
        for i in range(1, len(valid_points)):
            p1 = valid_points[i-1]
            p2 = valid_points[i]
            
            pt1 = (int(p1['x']), int(p1['y']))
            pt2 = (int(p2['x']), int(p2['y']))
            
            # 使用 p2 落入的状态作为这段轨迹的颜色
            state = p2.get('state', 'arena')
            color = color_map.get(state, (0, 0, 255))
            
            # 绘制不同粗细突出探索
            thickness = 2 if state == 'arena' else 3
            cv2.line(img, pt1, pt2, color, thickness, cv2.LINE_AA)
            
        # 若指定了输出地址则保存
        if output_path:
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            cv2.imwrite(output_path, img)
            
        return img
        
    @staticmethod
    def generate_heatmap(bg_idx: np.ndarray, 
                        trajectory_data: List[Dict],
                        arena_rect: Optional[Dict] = None,
                        output_path: str = "",
                        resolution: int = 20) -> np.ndarray:
        """
        生成空间停留热力图（核密度估计/二维直方图法）
        """
        # 提取有效坐标
        x_coords = []
        y_coords = []
        for d in trajectory_data:
            if d['x'] is not None and d['y'] is not None:
                x_coords.append(d['x'])
                y_coords.append(d['y'])
                
        if not x_coords or bg_idx is None:
            return bg_idx
            
        h, w = bg_idx.shape[:2]
        if len(bg_idx.shape) == 2:
            bg_color = cv2.cvtColor(bg_idx, cv2.COLOR_GRAY2BGR)
        else:
            bg_color = bg_idx.copy()
            
        # 使用 matplotlib 和 seaborn 生成带有 kde 的热力图
        fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
        fig.patch.set_alpha(0)
        ax.axis('off')
        
        # 翻转 y 轴使得与图像坐标系一致
        ax.set_ylim(h, 0)
        ax.set_xlim(0, w)
        
        # KDE 热力图，使用 jet（彩虹）色彩
        sns.kdeplot(x=x_coords, y=y_coords, cmap="jet", fill=True, 
                   bw_adjust=0.5, alpha=0.6, ax=ax, thresh=0.05)
                   
        # 转换 matplotlib 图像为 numpy 数组
        canvas = FigureCanvas(fig)
        canvas.draw()
        
        # 获取图像数据
        buf = canvas.buffer_rgba()
        heatmap_img = np.asarray(buf)
        
        plt.close(fig)
        
        # 将RGBA转为BGR并混合
        heatmap_bgr = cv2.cvtColor(heatmap_img, cv2.COLOR_RGBA2BGR)
        
        # 提取非白色区域创建掩码并融合
        gray_hm = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray_hm, 250, 255, cv2.THRESH_BINARY_INV)
        
        # Alpha blending
        alpha = 0.5
        for c in range(3):
            bg_color[:, :, c] = np.where(mask == 255, 
                                       bg_color[:, :, c] * (1 - alpha) + heatmap_bgr[:, :, c] * alpha, 
                                       bg_color[:, :, c])
                                       
        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            cv2.imwrite(output_path, bg_color)
            
        return bg_color
