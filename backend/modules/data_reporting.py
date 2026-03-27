"""
Data & Reporting Module - Database storage, heatmap generation, and report export
Handles data persistence, visualization, and scientific report generation

Performance Requirements:
- Scientific-grade KDE heatmap generation
- Multi-format report export (Excel, CSV, JSON)
- Efficient database operations
"""

import os
import json
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from scipy.ndimage import gaussian_filter
from scipy.stats import gaussian_kde
import base64
from io import BytesIO
import logging

logging.basicConfig(level=logging.INFO)


class DatabaseManager:
    """
    SQLite database manager for experiment data persistence.
    
    Responsibilities:
    1. Experiment metadata storage
    2. Trajectory data storage
    3. ROI configuration storage
    4. Query and retrieval operations
    """
    
    def __init__(self, db_path: str = 'data/etho_database.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                group_name TEXT,
                experiment_type TEXT,
                video_path TEXT,
                created_at TEXT,
                config_json TEXT,
                metrics_json TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trajectories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                frame INTEGER,
                timestamp REAL,
                x REAL,
                y REAL,
                detected INTEGER,
                velocity REAL,
                zone TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS roi_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                roi_name TEXT,
                roi_type TEXT,
                roi_data TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_experiment(
        self,
        experiment_id: str,
        subject_id: str,
        group: str,
        experiment_type: str,
        video_path: str,
        config: Dict,
        metrics: Dict
    ) -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO experiments 
            (experiment_id, subject_id, group_name, experiment_type, video_path, created_at, config_json, metrics_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            experiment_id,
            subject_id,
            group,
            experiment_type,
            video_path,
            datetime.now().isoformat(),
            json.dumps(config),
            json.dumps(metrics)
        ))
        
        conn.commit()
        conn.close()
        
        return experiment_id
    
    def save_trajectory(
        self,
        experiment_id: str,
        trajectory: List[Dict],
        zone_assignments: List[str] = None
    ):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for i, point in enumerate(trajectory):
            zone = zone_assignments[i] if zone_assignments else None
            cursor.execute('''
                INSERT INTO trajectories 
                (experiment_id, frame, timestamp, x, y, detected, velocity, zone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                experiment_id,
                point.get('frame', i),
                point.get('timestamp', 0.0),
                point.get('x', 0.0),
                point.get('y', 0.0),
                1 if point.get('detected', False) else 0,
                point.get('velocity', 0.0),
                zone
            ))
        
        conn.commit()
        conn.close()
    
    def get_experiment(self, experiment_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM experiments WHERE experiment_id = ?
        ''', (experiment_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'experiment_id': row[0],
                'subject_id': row[1],
                'group': row[2],
                'experiment_type': row[3],
                'video_path': row[4],
                'created_at': row[5],
                'config': json.loads(row[6]) if row[6] else {},
                'metrics': json.loads(row[7]) if row[7] else {}
            }
        return None
    
    def get_trajectory(self, experiment_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT frame, timestamp, x, y, detected, velocity, zone
            FROM trajectories 
            WHERE experiment_id = ?
            ORDER BY frame
        ''', (experiment_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'frame': row[0],
                'timestamp': row[1],
                'x': row[2],
                'y': row[3],
                'detected': bool(row[4]),
                'velocity': row[5],
                'zone': row[6]
            }
            for row in rows
        ]
    
    def list_experiments(
        self,
        subject_id: str = None,
        group: str = None,
        experiment_type: str = None,
        limit: int = 100
    ) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM experiments WHERE 1=1'
        params = []
        
        if subject_id:
            query += ' AND subject_id = ?'
            params.append(subject_id)
        if group:
            query += ' AND group_name = ?'
            params.append(group)
        if experiment_type:
            query += ' AND experiment_type = ?'
            params.append(experiment_type)
        
        query += f' ORDER BY created_at DESC LIMIT {limit}'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        experiments = []
        for row in rows:
            exp_id = row[0]
            cursor.execute('SELECT COUNT(*) FROM trajectories WHERE experiment_id = ?', (exp_id,))
            count = cursor.fetchone()[0]
            
            experiments.append({
                'experiment_id': row[0],
                'subject_id': row[1],
                'group': row[2],
                'experiment_type': row[3],
                'video_path': row[4],
                'created_at': row[5],
                'trajectory_count': count
            })
        
        conn.close()
        return experiments


class HeatmapGenerator:
    """
    Scientific-grade heatmap generation using Kernel Density Estimation.
    
    Responsibilities:
    1. Position density heatmap with KDE
    2. Zone time distribution charts
    3. Trajectory visualization
    
    Technical Specifications:
    - Uses Gaussian KDE for smooth density estimation
    - High-resolution output (150+ DPI)
    - Supports multiple color maps
    """
    
    def __init__(self, output_dir: str = 'results/heatmaps'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_density_heatmap(
        self,
        trajectory: List[Dict],
        video_width: int,
        video_height: int,
        bandwidth: float = 50.0,
        output_path: Optional[str] = None,
        use_kde: bool = True
    ) -> np.ndarray:
        """
        Generate position density heatmap using KDE or Gaussian filter.
        
        Args:
            trajectory: List of trajectory points
            video_width: Video width in pixels
            video_height: Video height in pixels
            bandwidth: Smoothing bandwidth
            output_path: Path to save heatmap image
            use_kde: Use Kernel Density Estimation for scientific-grade results
            
        Returns:
            2D numpy array representing density
        """
        if not trajectory:
            logging.warning("[Heatmap] No trajectory data provided")
            return np.zeros((video_height, video_width))
        
        x_coords = []
        y_coords = []
        
        for point in trajectory:
            if point.get('detected', False):
                x_coords.append(point['x'])
                y_coords.append(point['y'])
        
        logging.info(f"[Heatmap] Extracted {len(x_coords)} detected points from {len(trajectory)} total points")
        
        if not x_coords:
            logging.warning("[Heatmap] No detected points found, using all points")
            for point in trajectory:
                x_coords.append(point['x'])
                y_coords.append(point['y'])
        
        if not x_coords:
            logging.warning("[Heatmap] No coordinates found at all")
            return np.zeros((video_height, video_width))
        
        if use_kde and len(x_coords) > 10:
            heatmap = self._generate_kde_heatmap(
                x_coords, y_coords, 
                video_width, video_height, 
                bandwidth
            )
        else:
            heatmap = self._generate_simple_heatmap(
                x_coords, y_coords,
                video_width, video_height,
                bandwidth
            )
        
        if output_path:
            self._save_heatmap_image(heatmap, output_path)
        
        return heatmap
    
    def _generate_kde_heatmap(
        self,
        x_coords: List[float],
        y_coords: List[float],
        width: int,
        height: int,
        bandwidth: float
    ) -> np.ndarray:
        """
        Generate heatmap using Kernel Density Estimation.
        Scientific-grade smooth density estimation.
        
        Args:
            x_coords: X coordinates
            y_coords: Y coordinates
            width: Image width
            height: Image height
            bandwidth: KDE bandwidth
            
        Returns:
            Density heatmap
        """
        positions = np.vstack([x_coords, y_coords])
        
        try:
            kernel = gaussian_kde(positions, bw_method=bandwidth/100)
        except (np.linalg.LinAlgError, ValueError, RuntimeError) as e:
            import logging
            logging.warning(f"KDE computation failed: {e}, falling back to simple heatmap")
            return self._generate_simple_heatmap(x_coords, y_coords, width, height, bandwidth)
        
        xi = np.linspace(0, width, width)
        yi = np.linspace(0, height, height)
        xx, yy = np.meshgrid(xi, yi)
        
        positions_grid = np.vstack([xx.ravel(), yy.ravel()])
        density = kernel(positions_grid)
        heatmap = np.reshape(density, (height, width))
        
        return heatmap
    
    def _generate_simple_heatmap(
        self,
        x_coords: List[float],
        y_coords: List[float],
        width: int,
        height: int,
        bandwidth: float
    ) -> np.ndarray:
        """
        Generate simple heatmap using Gaussian filter.
        
        Args:
            x_coords: X coordinates
            y_coords: Y coordinates
            width: Image width
            height: Image height
            bandwidth: Gaussian sigma
            
        Returns:
            Density heatmap
        """
        heatmap = np.zeros((height, width))
        
        for x, y in zip(x_coords, y_coords):
            xi, yi = int(x), int(y)
            if 0 <= xi < width and 0 <= yi < height:
                heatmap[yi, xi] += 1
        
        heatmap = gaussian_filter(heatmap, sigma=bandwidth)
        
        return heatmap
    
    def generate_heatmap_base64(
        self,
        trajectory: List[Dict],
        video_width: int,
        video_height: int,
        bandwidth: float = 15.0,
        scale_mode: str = 'auto',
        max_value: float = 10.0,
        arena_config: Dict = None
    ) -> str:
        """
        Generate heatmap and return as base64 encoded image.
        
        Args:
            trajectory: List of trajectory points
            video_width: Video width
            video_height: Video height
            bandwidth: Gaussian kernel size (1-50, default 15)
            scale_mode: 'auto' or 'fixed'
            max_value: Max value for fixed scale mode (1-3600 seconds)
            arena_config: Arena configuration for cropping
            
        Returns:
            Base64 encoded PNG image
        """
        logging.info(f"[Heatmap] generate_heatmap_base64 called with {len(trajectory)} points")
        
        heatmap = self.generate_density_heatmap(
            trajectory, video_width, video_height, bandwidth
        )
        
        logging.info(f"[Heatmap] Density heatmap generated, shape: {heatmap.shape}")
        
        if arena_config and arena_config.get('arena'):
            arena = arena_config['arena']
            x_start = int(arena['x'] * video_width)
            y_start = int(arena['y'] * video_height)
            x_end = int((arena['x'] + arena['width']) * video_width)
            y_end = int((arena['y'] + arena['height']) * video_height)
            heatmap = heatmap[y_start:y_end, x_start:x_end]
            logging.info(f"[Heatmap] Cropped to arena: {heatmap.shape}")
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        if scale_mode == 'fixed' and max_value > 0:
            vmax = max_value
        else:
            vmax = None
        
        x_coords = []
        y_coords = []
        for point in trajectory:
            if point.get('detected', False):
                x_coords.append(point['x'])
                y_coords.append(point['y'])
        
        logging.info(f"[Heatmap] Points for KDE: {len(x_coords)}")
        
        if len(x_coords) > 10:
            try:
                import seaborn as sns
                ax.set_xlim(0, video_width)
                ax.set_ylim(video_height, 0)
                
                bw_adjust = bandwidth / 30.0
                
                kde = sns.kdeplot(
                    x=x_coords, 
                    y=y_coords, 
                    cmap="jet",
                    fill=True,
                    bw_adjust=bw_adjust,
                    alpha=0.6,
                    ax=ax,
                    thresh=0.05,
                    levels=100
                )
                
                if scale_mode == 'fixed' and max_value > 0:
                    if ax.collections:
                        ax.collections[0].set_clim(0, max_value)
                
                if ax.collections:
                    cbar = plt.colorbar(ax.collections[0], ax=ax, orientation='horizontal', pad=0.08, shrink=0.8)
                    cbar.set_label('Density', fontsize=10)
                    if scale_mode == 'fixed' and max_value > 0:
                        cbar.set_ticks([0, max_value/2, max_value])
                    
            except Exception as e:
                logging.warning(f"KDE plot failed: {e}, using simple heatmap")
                sns.heatmap(
                    heatmap,
                    cmap='jet',
                    cbar_kws={'label': 'Density', 'orientation': 'horizontal', 'shrink': 0.8},
                    xticklabels=False,
                    yticklabels=False,
                    ax=ax,
                    vmin=0 if scale_mode == 'fixed' else None,
                    vmax=vmax
                )
        else:
            sns.heatmap(
                heatmap,
                cmap='jet',
                cbar_kws={'label': 'Density', 'orientation': 'horizontal', 'shrink': 0.8},
                xticklabels=False,
                yticklabels=False,
                ax=ax,
                vmin=0 if scale_mode == 'fixed' else None,
                vmax=vmax
            )
        
        ax.set_aspect('equal')
        
        buffer = BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                    facecolor='#1a1a2e', edgecolor='none')
        plt.close(fig)
        
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return image_base64
    
    def _save_heatmap_image(self, heatmap: np.ndarray, output_path: str):
        plt.figure(figsize=(10, 8))
        
        sns.heatmap(
            heatmap,
            cmap='hot',
            cbar_kws={'label': 'Density'},
            xticklabels=False,
            yticklabels=False
        )
        
        plt.title('Position Density Heatmap', fontsize=14)
        plt.xlabel('X Position (pixels)', fontsize=12)
        plt.ylabel('Y Position (pixels)', fontsize=12)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def generate_zone_time_chart(
        self,
        zone_stats: Dict[str, Dict],
        output_path: str
    ):
        zones = list(zone_stats.keys())
        times = [zone_stats[z]['time_seconds'] for z in zones]
        
        plt.figure(figsize=(10, 6))
        
        bars = plt.bar(zones, times, color=sns.color_palette('husl', len(zones)))
        
        plt.xlabel('Zone', fontsize=12)
        plt.ylabel('Time (seconds)', fontsize=12)
        plt.title('Time Distribution Across Zones', fontsize=14)
        
        for bar, time_val in zip(bars, times):
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f'{time_val:.1f}s',
                ha='center',
                va='bottom',
                fontsize=10
            )
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()


class ReportGenerator:
    """
    Generate analysis reports in multiple formats.
    
    Supported formats:
    - Excel (.xlsx) with multiple sheets
    - CSV for trajectory data
    - JSON for programmatic access
    """
    
    def __init__(self, output_dir: str = 'results/reports'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_excel_report(
        self,
        experiment_data: Dict,
        trajectory: List[Dict],
        zone_stats: Dict,
        output_filename: str = None
    ) -> str:
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            subject_id = experiment_data.get('subject_id', 'unknown')
            output_filename = f'report_{subject_id}_{timestamp}.xlsx'
        
        output_path = os.path.join(self.output_dir, output_filename)
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            summary_df = pd.DataFrame([{
                'Subject ID': experiment_data.get('subject_id', ''),
                'Group': experiment_data.get('group', ''),
                'Experiment Type': experiment_data.get('experiment_type', ''),
                'Analysis Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Total Distance (px)': experiment_data.get('metrics', {}).get('total_distance', 0),
                'Average Speed (px/s)': experiment_data.get('metrics', {}).get('avg_speed', 0),
                'Max Speed (px/s)': experiment_data.get('metrics', {}).get('max_speed', 0),
                'Immobility Time (s)': experiment_data.get('metrics', {}).get('immobility_time', 0)
            }])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            trajectory_df = pd.DataFrame(trajectory)
            trajectory_df.to_excel(writer, sheet_name='Trajectory', index=False)
            
            zone_df = pd.DataFrame([
                {
                    'Zone': zone_name,
                    'Time (s)': stats['time_seconds'],
                    'Percentage': f"{stats['percentage']:.2f}%",
                    'Frames': stats['frames']
                }
                for zone_name, stats in zone_stats.items()
            ])
            zone_df.to_excel(writer, sheet_name='Zone Statistics', index=False)
            
            rois = experiment_data.get('config', {}).get('rois', [])
            if rois:
                roi_df = pd.DataFrame([
                    {
                        'ROI Name': roi.get('name', ''),
                        'Type': roi.get('type', ''),
                        'X': roi.get('x', 0),
                        'Y': roi.get('y', 0),
                        'Width': roi.get('width', 0),
                        'Height': roi.get('height', 0)
                    }
                    for roi in rois
                ])
                roi_df.to_excel(writer, sheet_name='ROI Configuration', index=False)
        
        return output_path
    
    def generate_csv_export(
        self,
        trajectory: List[Dict],
        output_filename: str = None
    ) -> str:
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'trajectory_{timestamp}.csv'
        
        output_path = os.path.join(self.output_dir, output_filename)
        
        df = pd.DataFrame(trajectory)
        df.to_csv(output_path, index=False)
        
        return output_path
    
    def generate_json_report(
        self,
        experiment_data: Dict,
        trajectory: List[Dict],
        zone_stats: Dict,
        output_filename: str = None
    ) -> str:
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            subject_id = experiment_data.get('subject_id', 'unknown')
            output_filename = f'report_{subject_id}_{timestamp}.json'
        
        output_path = os.path.join(self.output_dir, output_filename)
        
        report = {
            'metadata': {
                'subject_id': experiment_data.get('subject_id', ''),
                'group': experiment_data.get('group', ''),
                'experiment_type': experiment_data.get('experiment_type', ''),
                'analysis_date': datetime.now().isoformat(),
                'software_version': '1.0.0'
            },
            'metrics': experiment_data.get('metrics', {}),
            'zone_statistics': zone_stats,
            'trajectory': trajectory[:100],
            'config': experiment_data.get('config', {})
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return output_path
