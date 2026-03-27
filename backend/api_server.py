"""
ETHO Backend API Server
Flask-based REST API for animal behavioral analysis

Four Core Modules:
1. CV Engine - Video processing and target tracking
2. Spatial Module - Geometry and physical calculations
3. Behavioral Logic - State machine and event detection
4. Data & Reporting - Storage, heatmaps, and reports
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import os
import sqlite3
import uuid
from datetime import datetime
from threading import Thread
import numpy as np
import cv2

from modules.cv_engine import CVEngine, VideoProcessor, TrackingResult
from modules.spatial import SpatialCalculator, ScaleCalibration, PhysicalMetrics
from modules.behavioral_logic import BehavioralStateMachine, OpenFieldAnalyzer
from modules.data_reporting import DatabaseManager, HeatmapGenerator, ReportGenerator

TRACKING_TASKS = {}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ROI_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'roi_configs')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(ROI_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=UPLOAD_FOLDER, static_url_path='/uploads')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

from collections import OrderedDict
from threading import Lock

class LRUCache:
    def __init__(self, max_size=10):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = Lock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    self.cache.popitem(last=False)
            self.cache[key] = value
    
    def clear(self):
        with self.lock:
            self.cache.clear()

BACKGROUND_CACHE = LRUCache(max_size=10)
MORPHOLOGY_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
GAUSSIAN_KERNEL_SIZE = (21, 21)
JPEG_ENCODE_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, 60]

db_manager = DatabaseManager(os.path.join(DATA_FOLDER, 'etho_database.db'))
heatmap_generator = HeatmapGenerator('results/heatmaps')
report_generator = ReportGenerator('results/reports')


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'name': 'ETHO Backend API',
        'version': '1.0.0',
        'description': 'Animal Behavioral Analysis System',
        'endpoints': {
            'health': '/api/health',
            'video_upload': '/api/video/upload',
            'video_info': '/api/video/info',
            'rois': '/api/rois',
            'tracking_start': '/api/tracking/start',
            'tracking_status': '/api/tracking/status/<id>',
            'tracking_results': '/api/tracking/results/<id>',
            'analysis_export': '/api/analysis/export',
            'experiments': '/api/experiments'
        },
        'documentation': 'https://github.com/your-repo/etho'
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'modules': ['cv_engine', 'spatial', 'behavioral_logic', 'data_reporting']
    })


@app.route('/api/video/upload', methods=['POST'])
def upload_video():
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': '未找到视频文件'}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'}), 400
        
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        video_info = VideoProcessor.get_video_info(filepath)
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': filename,
            'filepath': filepath,
            'video_info': video_info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/video/info', methods=['GET'])
def get_video_info():
    try:
        video_path = request.args.get('path')
        if not video_path or not os.path.exists(video_path):
            return jsonify({'success': False, 'error': '视频文件不存在'}), 404
        
        info = VideoProcessor.get_video_info(video_path)
        
        return jsonify({
            'success': True,
            'info': info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/video/frame', methods=['GET'])
def get_video_frame():
    try:
        video_path = request.args.get('path')
        frame_number = int(request.args.get('frame', 0))
        
        if not video_path or not os.path.exists(video_path):
            return jsonify({'success': False, 'error': '视频文件不存在'}), 404
        
        frame = VideoProcessor.extract_frame(video_path, frame_number)
        
        if frame is None:
            return jsonify({'success': False, 'error': '无法提取帧'}), 400
        
        return jsonify({
            'success': True,
            'frame_number': frame_number,
            'shape': frame.shape
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rois', methods=['POST'])
def save_rois():
    try:
        data = request.json
        rois = data.get('rois', [])
        video_info = data.get('videoInfo', {})
        
        config_id = str(uuid.uuid4())
        config = {
            'id': config_id,
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'video': video_info,
            'rois': rois
        }
        
        config_path = os.path.join(ROI_FOLDER, f'{config_id}.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'config_id': config_id,
            'message': 'ROI配置已保存',
            'config_path': config_path
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rois/<config_id>', methods=['GET'])
def get_roi_config(config_id):
    try:
        config_path = os.path.join(ROI_FOLDER, f'{config_id}.json')
        if not os.path.exists(config_path):
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tracking/start', methods=['POST'])
def start_tracking():
    try:
        data = request.json
        video_path = data.get('videoPath')
        roi_config = data.get('roiConfig', {})
        algorithm_params = data.get('algorithmParams', {})
        subject_info = data.get('subjectInfo', {})
        scale_calibration = data.get('scaleCalibration')
        arena_config = data.get('arenaConfig', {})
        
        if not video_path or not os.path.exists(video_path):
            return jsonify({'success': False, 'error': '视频文件不存在'}), 400
        
        tracking_id = str(uuid.uuid4())
        
        TRACKING_TASKS[tracking_id] = {
            'status': 'pending',
            'progress': 0,
            'video_path': video_path,
            'roi_config': roi_config,
            'algorithm_params': algorithm_params,
            'subject_info': subject_info,
            'scale_calibration': scale_calibration,
            'arena_config': arena_config,
            'started_at': datetime.now().isoformat()
        }
        
        thread = Thread(target=run_tracking_task, args=(tracking_id,))
        thread.start()
        
        return jsonify({
            'success': True,
            'tracking_id': tracking_id,
            'message': '追踪任务已启动'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def run_tracking_task(tracking_id):
    try:
        task = TRACKING_TASKS[tracking_id]
        task['status'] = 'running'
        
        video_path = task['video_path']
        roi_config = task['roi_config']
        algorithm_params = task.get('algorithm_params', {})
        scale_calibration = task.get('scale_calibration')
        arena_config = task.get('arena_config', {})
        
        cv_engine = CVEngine(
            mog2_history=algorithm_params.get('mog2History', 500),
            mog2_var_threshold=algorithm_params.get('mog2VarThreshold', 50),
            min_contour_area=algorithm_params.get('minArea', 100),
            max_contour_area=algorithm_params.get('maxArea', 10000)
        )
        
        def progress_callback(progress, current_frame, total_frames):
            task['progress'] = progress
            task['current_frame'] = current_frame
            task['total_frames'] = total_frames
            socketio.emit('tracking_progress', {
                'tracking_id': tracking_id,
                'progress': progress,
                'current_frame': current_frame,
                'total_frames': total_frames
            })
        
        tracking_results = cv_engine.process_video(
            video_path,
            progress_callback=progress_callback
        )
        
        trajectory = [
            {
                'frame': r.frame,
                'timestamp': r.timestamp,
                'x': r.x,
                'y': r.y,
                'detected': r.detected,
                'area': r.area,
                'velocity': r.velocity
            }
            for r in tracking_results
        ]
        
        spatial_calc = SpatialCalculator()
        if scale_calibration:
            spatial_calc.set_calibration(scale_calibration.get('pixelsPerCm', 1.0))
        
        video_info = VideoProcessor.get_video_info(video_path)
        fps = video_info.get('fps', 30.0)
        
        physical_metrics = spatial_calc.calculate_trajectory_metrics(trajectory, fps)
        
        rois = roi_config.get('rois', [])
        if arena_config.get('arena'):
            video_width = video_info.get('width')
            video_height = video_info.get('height')
            analyzer = OpenFieldAnalyzer(arena_config, video_width=video_width, video_height=video_height)
            
            for point in trajectory:
                if point['detected']:
                    analyzer.process_frame(
                        point['frame'],
                        point['timestamp'],
                        (point['x'], point['y']),
                        True
                    )
            
            open_field_metrics = analyzer.get_open_field_metrics(
                trajectory,
                fps,
                scale_calibration.get('pixelsPerCm') if scale_calibration else None
            )
            
            zone_stats = open_field_metrics.get('zone_statistics', {})
        else:
            zone_stats = spatial_calc.calculate_roi_time_distribution(trajectory, rois, fps)
        
        task['trajectory'] = trajectory
        task['metrics'] = {
            'total_distance': physical_metrics.total_distance_cm,
            'avg_speed': physical_metrics.avg_speed_cm_s,
            'max_speed': physical_metrics.max_speed_cm_s,
            'immobility_time': physical_metrics.immobility_time_s,
            'zone_stats': zone_stats
        }
        task['status'] = 'completed'
        task['completed_at'] = datetime.now().isoformat()
        
        socketio.emit('tracking_complete', {
            'tracking_id': tracking_id,
            'metrics': task['metrics']
        })
        
    except Exception as e:
        TRACKING_TASKS[tracking_id]['status'] = 'failed'
        TRACKING_TASKS[tracking_id]['error'] = str(e)
        
        socketio.emit('tracking_error', {
            'tracking_id': tracking_id,
            'error': str(e)
        })


@app.route('/api/tracking/status/<tracking_id>', methods=['GET'])
def get_tracking_status(tracking_id):
    if tracking_id not in TRACKING_TASKS:
        return jsonify({'success': False, 'error': '追踪任务不存在'}), 404
    
    task = TRACKING_TASKS[tracking_id]
    
    response = {
        'success': True,
        'tracking_id': tracking_id,
        'status': task['status'],
        'progress': task.get('progress', 0),
        'started_at': task['started_at'],
        'current_frame': task.get('current_frame', 0),
        'total_frames': task.get('total_frames', 0)
    }
    
    if task['status'] == 'failed':
        response['error'] = task.get('error')
    
    return jsonify(response)


@app.route('/api/tracking/results/<tracking_id>', methods=['GET'])
def get_tracking_results(tracking_id):
    if tracking_id not in TRACKING_TASKS:
        return jsonify({'success': False, 'error': '追踪任务不存在'}), 404
    
    task = TRACKING_TASKS[tracking_id]
    
    if task['status'] != 'completed':
        return jsonify({
            'success': False,
            'error': f"追踪任务状态: {task['status']}"
        }), 400
    
    return jsonify({
        'success': True,
        'tracking_id': tracking_id,
        'trajectory': task.get('trajectory', []),
        'metrics': task.get('metrics', {}),
        'completed_at': task.get('completed_at')
    })


@app.route('/api/experiments', methods=['GET'])
def list_experiments():
    try:
        subject_id = request.args.get('subject_id')
        group = request.args.get('group')
        limit = int(request.args.get('limit', 100))
        
        experiments = db_manager.list_experiments(
            subject_id=subject_id,
            group=group,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'experiments': experiments
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/experiments/<experiment_id>', methods=['GET'])
def get_experiment_detail(experiment_id):
    try:
        experiment = db_manager.get_experiment(experiment_id)
        if not experiment:
            return jsonify({'success': False, 'error': '实验不存在'}), 404
        
        trajectory = db_manager.get_trajectory(experiment_id)
        
        return jsonify({
            'success': True,
            'experiment': experiment,
            'trajectory': trajectory
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/experiments/<experiment_id>/heatmap', methods=['POST'])
def generate_experiment_heatmap(experiment_id):
    try:
        experiment = db_manager.get_experiment(experiment_id)
        if not experiment:
            return jsonify({'success': False, 'error': '实验不存在'}), 404
        
        trajectory = db_manager.get_trajectory(experiment_id)
        if not trajectory:
            return jsonify({'success': False, 'error': '没有轨迹数据'}), 400
        
        data = request.json or {}
        bandwidth = data.get('bandwidth', 15.0)
        scale_mode = data.get('scaleMode', 'auto')
        max_value = data.get('maxValue', 10.0)
        
        video_info = experiment.get('video_info', {})
        width = video_info.get('width', 640)
        height = video_info.get('height', 480)
        
        heatmap_base64 = heatmap_generator.generate_heatmap_base64(
            trajectory, width, height, bandwidth, scale_mode, max_value
        )
        
        return jsonify({
            'success': True,
            'heatmap': heatmap_base64,
            'trajectory_points': len(trajectory)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/experiments/clear', methods=['POST'])
def clear_all_experiments():
    try:
        db_path = db_manager.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM trajectories')
        cursor.execute('DELETE FROM roi_configs')
        cursor.execute('DELETE FROM experiments')
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '所有实验数据已清除'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connected', {'message': 'Connected to ETHO Backend'})


@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')


@app.route('/api/background/capture', methods=['POST'])
def capture_background():
    """
    Capture background frame with ROI mask support.
    Optimized for precise background subtraction.
    """
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': '未找到背景图像'}), 400
        
        file = request.files['image']
        bg_id = str(uuid.uuid4())
        filename = f"background_{bg_id}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        import cv2
        bg_image = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if bg_image is None:
            return jsonify({'success': False, 'error': '无法读取背景图像'}), 400
        
        # Apply Gaussian blur for noise reduction
        bg_blur = cv2.GaussianBlur(bg_image, (21, 21), 0)
        blur_path = os.path.join(UPLOAD_FOLDER, f"background_{bg_id}_blur.jpg")
        cv2.imwrite(blur_path, bg_blur)
        
        return jsonify({
            'success': True,
            'background_id': bg_id,
            'background_path': f'uploads/{filename}',
            'background_blur_path': f'uploads/background_{bg_id}_blur.jpg',
            'message': '背景图像已保存',
            'width': bg_image.shape[1],
            'height': bg_image.shape[0]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/video/preview-binary', methods=['POST'])
def preview_binary_frame():
    """
    Preview binary frame with background subtraction.
    Supports real-time parameter adjustment with <50ms latency.
    """
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': '未找到图像'}), 400
        
        threshold = int(request.form.get('threshold', 50))
        min_area = int(request.form.get('minArea', 50))
        max_area = int(request.form.get('maxArea', 10000))
        background_path = request.form.get('backgroundPath', None)
        arena_config_str = request.form.get('arenaConfig', None)
        arena_config = json.loads(arena_config_str) if arena_config_str else None
        
        file = request.files['image']
        import base64
        
        file_bytes = np.frombuffer(file.read(), np.uint8)
        frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'success': False, 'error': '无法解码图像'}), 400
        
        height, width = frame.shape[:2]
        
        if arena_config and arena_config.get('arena'):
            arena = arena_config['arena']
            mask = np.zeros((height, width), dtype=np.uint8)
            x = int(arena['x'] * width)
            y = int(arena['y'] * height)
            w = int(arena['width'] * width)
            h = int(arena['height'] * height)
            cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
        else:
            mask = None
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, GAUSSIAN_KERNEL_SIZE, 0)
        
        if background_path:
            if not os.path.isabs(background_path):
                background_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), background_path)
            
            if os.path.exists(background_path):
                bg_blur = BACKGROUND_CACHE.get(background_path)
                if bg_blur is None:
                    background = cv2.imread(background_path, cv2.IMREAD_GRAYSCALE)
                    if background is not None:
                        bg_blur = cv2.GaussianBlur(background, GAUSSIAN_KERNEL_SIZE, 0)
                        BACKGROUND_CACHE.put(background_path, bg_blur)
                    else:
                        bg_blur = None
                
                if bg_blur is not None:
                    diff = cv2.absdiff(bg_blur, blur)
                    _, binary = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
                else:
                    binary = cv2.adaptiveThreshold(
                        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY_INV, 21, 5
                    )
            else:
                binary = cv2.adaptiveThreshold(
                    blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 21, 5
                )
        else:
            binary = cv2.adaptiveThreshold(
                 blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                 cv2.THRESH_BINARY_INV, 21, 5
            )
        
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, MORPHOLOGY_KERNEL)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, MORPHOLOGY_KERNEL)
        
        if mask is not None:
            binary = cv2.bitwise_and(binary, mask)
        
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filtered_binary = np.zeros_like(binary)
        centroid = None
        contour_points = None
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                cv2.drawContours(filtered_binary, [contour], -1, 255, -1)
                
                M = cv2.moments(contour)
                if M['m00'] != 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    centroid = {'x': cx, 'y': cy}
                    
                    epsilon = 0.01 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    
                    if len(approx) > 50:
                        step = len(approx) // 25
                        contour_points = approx[::step].reshape(-1, 2).tolist()
                    else:
                        contour_points = approx.reshape(-1, 2).tolist()
                break
        
        _, buffer = cv2.imencode('.jpg', filtered_binary, JPEG_ENCODE_PARAMS)
        binary_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'binary_frame': binary_base64,
            'centroid': centroid,
            'contour_points': contour_points
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tracking/session/start', methods=['POST'])
def start_tracking_session():
    try:
        data = request.json
        video_path = data.get('videoPath')
        background_path = data.get('backgroundPath')
        threshold = data.get('threshold', 50)
        min_area = data.get('minArea', 100)
        max_area = data.get('maxArea', 10000)
        
        if not video_path or not os.path.exists(video_path):
            return jsonify({'success': False, 'error': '视频文件不存在'}), 400
        
        if not background_path:
            return jsonify({'success': False, 'error': '背景图像不存在'}), 400
        
        if not os.path.isabs(background_path):
            background_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), background_path)
        
        if not os.path.exists(background_path):
            return jsonify({'success': False, 'error': '背景图像不存在'}), 400
        
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({'success': False, 'error': '无法打开视频文件'}), 400
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        background = cv2.imread(background_path, cv2.IMREAD_GRAYSCALE)
        if background is None:
            cap.release()
            return jsonify({'success': False, 'error': '无法读取背景图像'}), 400
        background_blur = cv2.GaussianBlur(background, (21, 21), 0)
        
        tracking_id = str(uuid.uuid4())
        
        TRACKING_TASKS[tracking_id] = {
            'status': 'ready',
            'video_path': video_path,
            'background_path': background_path,
            'threshold': threshold,
            'min_area': min_area,
            'max_area': max_area,
            'fps': fps,
            'total_frames': total_frames,
            'width': width,
            'height': height,
            'started_at': datetime.now().isoformat(),
            'trajectory': [],
            '_cap': cap,
            '_background_blur': background_blur,
            '_last_frame': -1
        }
        
        return jsonify({
            'success': True,
            'tracking_id': tracking_id,
            'video_info': {
                'fps': fps,
                'total_frames': total_frames,
                'width': width,
                'height': height
            },
            'message': '追踪会话已初始化'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tracking/process-frame', methods=['POST'])
def process_single_frame():
    try:
        data = request.json
        tracking_id = data.get('trackingId')
        frame_number = data.get('frameNumber')
        
        if tracking_id not in TRACKING_TASKS:
            return jsonify({'success': False, 'error': '追踪会话不存在'}), 404
        
        task = TRACKING_TASKS[tracking_id]
        
        import cv2
        import base64

        if frame_number is None:
            return jsonify({'success': False, 'error': '缺少帧号'}), 400
        
        try:
            frame_number = int(frame_number)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '帧号必须是整数'}), 400
        
        total_frames = task.get('total_frames', 0)
        if frame_number < 0 or (total_frames > 0 and frame_number >= total_frames):
            return jsonify({
                'success': False, 
                'error': f'帧号超出范围 (0-{total_frames-1})'
            }), 400

        cap = task.get('_cap')
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(task['video_path'])
            task['_cap'] = cap

        last_frame = task.get('_last_frame', -1)
        if frame_number <= last_frame and task.get('trajectory'):
            last_point = task['trajectory'][-1]
            return jsonify({
                'success': True,
                'frame_number': frame_number,
                'centroid': {'x': last_point['x'], 'y': last_point['y']},
                'contour_area': last_point.get('area', 0),
                'contour_points': [],
                'binary_frame': None,
                'trajectory_length': len(task['trajectory'])
            })

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        task['_last_frame'] = frame_number
        
        if not ret:
            return jsonify({'success': False, 'error': '无法读取帧'}), 400
        
        background_blur = task.get('_background_blur')
        if background_blur is None:
            background = cv2.imread(task['background_path'], cv2.IMREAD_GRAYSCALE)
            if background is None:
                return jsonify({'success': False, 'error': '无法读取背景图像'}), 400
            background_blur = cv2.GaussianBlur(background, (21, 21), 0)
            task['_background_blur'] = background_blur

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to both
        gray_blur = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Calculate absolute difference
        diff = cv2.absdiff(background_blur, gray_blur)
        
        # Use threshold to create binary image
        # THRESH_BINARY: pixels > threshold become white (255)
        # This is correct for diff image where mouse appears bright
        _, binary = cv2.threshold(diff, task['threshold'], 255, cv2.THRESH_BINARY)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        centroid = None
        contour_area = 0
        contour_points = []
        if contours:
            valid_contours = [c for c in contours if task['min_area'] <= cv2.contourArea(c) <= task['max_area']]
            if valid_contours:
                largest = max(valid_contours, key=cv2.contourArea)
                contour_area = int(cv2.contourArea(largest))
                M = cv2.moments(largest)
                if M['m00'] != 0:
                    cx = float(M['m10'] / M['m00'])
                    cy = float(M['m01'] / M['m00'])
                    centroid = {'x': cx, 'y': cy}
                    contour_points = largest.reshape(-1, 2).tolist()
                    task['trajectory'].append({
                        'frame': frame_number,
                        'timestamp': frame_number / (task.get('fps') or 30.0),
                        'x': cx,
                        'y': cy,
                        'area': contour_area,
                        'detected': True
                    })
        
        _, binary_buffer = cv2.imencode('.jpg', binary)
        binary_base64 = base64.b64encode(binary_buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'frame_number': frame_number,
            'centroid': centroid,
            'contour_area': contour_area,
            'contour_points': contour_points,
            'binary_frame': binary_base64,
            'trajectory_length': len(task['trajectory'])
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tracking/stop', methods=['POST'])
def stop_tracking_session():
    try:
        data = request.json
        tracking_id = data.get('trackingId')
        subject_info = data.get('subjectInfo', {})
        video_path = data.get('videoPath')
        
        print(f"[Stop Tracking] Request received - trackingId: {tracking_id}")
        print(f"[Stop Tracking] Available tracking IDs: {list(TRACKING_TASKS.keys())}")
        
        if tracking_id not in TRACKING_TASKS:
            return jsonify({'success': False, 'error': '追踪会话不存在'}), 404
        
        task = TRACKING_TASKS[tracking_id]

        cap = task.get('_cap')
        if cap is not None:
            try:
                cap.release()
                del task['_cap']
            except Exception:
                pass

        trajectory = task.get('trajectory', [])
        task['status'] = 'completed'
        task['completed_at'] = datetime.now().isoformat()
        
        print(f"[Stop Tracking] Trajectory points: {len(trajectory)}")
        
        try:
            experiment_id = db_manager.save_experiment(
                experiment_id=tracking_id,
                subject_id=subject_info.get('id', 'unknown'),
                group=subject_info.get('group', ''),
                experiment_type='Open Field',
                video_path=video_path or task.get('video_path', ''),
                config=task.get('roi_config', {}),
                metrics={}
            )
            
            if trajectory:
                db_manager.save_trajectory(experiment_id, trajectory)
                print(f"Trajectory data saved: {len(trajectory)} points to experiment {experiment_id}")
        except Exception as db_error:
            print(f"Failed to save trajectory to database: {db_error}")
        
        return jsonify({
            'success': True,
            'tracking_id': tracking_id,
            'trajectory': trajectory,
            'total_frames_processed': len(trajectory),
            'message': '追踪已停止'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/heatmap', methods=['POST'])
def generate_heatmap():
    """
    Generate scientific-grade heatmap using KDE.
    All computation performed on backend.
    """
    try:
        data = request.json
        tracking_id = data.get('trackingId')
        bandwidth = data.get('bandwidth', 15.0)
        scale_mode = data.get('scaleMode', 'auto')
        max_value = data.get('maxValue', 10.0)
        arena_config = data.get('arenaConfig')
        
        print(f"[Heatmap] Request received - trackingId: {tracking_id}")
        print(f"[Heatmap] Available tracking IDs: {list(TRACKING_TASKS.keys())}")
        
        if tracking_id not in TRACKING_TASKS:
            print(f"[Heatmap] Tracking ID not found in TRACKING_TASKS")
            return jsonify({'success': False, 'error': '追踪会话不存在'}), 404
        
        task = TRACKING_TASKS[tracking_id]
        trajectory = task.get('trajectory', [])
        
        print(f"[Heatmap] Trajectory points: {len(trajectory)}")
        
        if not trajectory:
            return jsonify({'success': False, 'error': '没有轨迹数据'}), 400
        
        width = task.get('width', 640)
        height = task.get('height', 480)
        
        heatmap_base64 = heatmap_generator.generate_heatmap_base64(
            trajectory, width, height, bandwidth, scale_mode, max_value, arena_config
        )
        
        print(f"[Heatmap] Heatmap generated successfully")
        
        return jsonify({
            'success': True,
            'heatmap': heatmap_base64,
            'trajectory_points': len(trajectory),
            'message': '热力图已生成'
        })
    except Exception as e:
        print(f"[Heatmap] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/export', methods=['POST'])
def export_analysis_report():
    """
    Export complete analysis report in Excel format.
    All computation and file generation performed on backend.
    """
    try:
        data = request.json
        tracking_id = data.get('trackingId')
        subject_info = data.get('subjectInfo', {})
        rois = data.get('rois', [])
        scale_calibration = data.get('scaleCalibration')
        
        if tracking_id not in TRACKING_TASKS:
            return jsonify({'success': False, 'error': '追踪会话不存在'}), 404
        
        task = TRACKING_TASKS[tracking_id]
        trajectory = task.get('trajectory', [])
        
        if not trajectory:
            return jsonify({'success': False, 'error': '没有轨迹数据'}), 400
        
        spatial_calc = SpatialCalculator()
        if scale_calibration:
            spatial_calc.set_calibration(scale_calibration.get('pixelsPerCm', 1.0))
        
        fps = task.get('fps', 30.0)
        physical_metrics = spatial_calc.calculate_trajectory_metrics(trajectory, fps)
        
        zone_stats = {}
        if rois:
            zone_stats = spatial_calc.calculate_roi_time_distribution(trajectory, rois, fps)
        
        experiment_data = {
            'subject_id': subject_info.get('id', 'unknown'),
            'group': subject_info.get('group', ''),
            'experiment_type': 'Open Field',
            'metrics': {
                'total_distance': physical_metrics.total_distance_cm,
                'avg_speed': physical_metrics.avg_speed_cm_s,
                'max_speed': physical_metrics.max_speed_cm_s,
                'immobility_time': physical_metrics.immobility_time_s
            },
            'config': {
                'rois': rois,
                'scale_calibration': scale_calibration
            }
        }
        
        report_path = report_generator.generate_excel_report(
            experiment_data, trajectory, zone_stats
        )
        
        return jsonify({
            'success': True,
            'report_path': report_path,
            'metrics': {
                'total_distance_cm': physical_metrics.total_distance_cm,
                'avg_speed_cm_s': physical_metrics.avg_speed_cm_s,
                'max_speed_cm_s': physical_metrics.max_speed_cm_s,
                'immobility_time_s': physical_metrics.immobility_time_s
            },
            'zone_stats': zone_stats,
            'message': '报告已生成'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/metrics', methods=['POST'])
def calculate_metrics():
    """
    Calculate physical metrics from trajectory data.
    All calculations performed on backend.
    """
    try:
        data = request.json
        tracking_id = data.get('trackingId')
        scale_calibration = data.get('scaleCalibration')
        
        if tracking_id not in TRACKING_TASKS:
            return jsonify({'success': False, 'error': '追踪会话不存在'}), 404
        
        task = TRACKING_TASKS[tracking_id]
        trajectory = task.get('trajectory', [])
        
        if not trajectory:
            return jsonify({'success': False, 'error': '没有轨迹数据'}), 400
        
        spatial_calc = SpatialCalculator()
        if scale_calibration:
            spatial_calc.set_calibration(scale_calibration.get('pixelsPerCm', 1.0))
        
        fps = task.get('fps', 30.0)
        physical_metrics = spatial_calc.calculate_trajectory_metrics(trajectory, fps)
        
        return jsonify({
            'success': True,
            'metrics': {
                'total_distance_cm': physical_metrics.total_distance_cm,
                'avg_speed_cm_s': physical_metrics.avg_speed_cm_s,
                'max_speed_cm_s': physical_metrics.max_speed_cm_s,
                'immobility_time_s': physical_metrics.immobility_time_s,
                'immobility_frames': physical_metrics.immobility_frames
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("ETHO Backend API Server")
    print("Animal Behavioral Analysis System")
    print("=" * 60)
    print("\nCore Modules:")
    print("  1. CV Engine - Video processing & target tracking")
    print("  2. Spatial Module - Geometry & physical calculations")
    print("  3. Behavioral Logic - State machine & event detection")
    print("  4. Data & Reporting - Storage, heatmaps & reports")
    print("\nAPI Endpoints:")
    print("  GET  /api/health - Health check")
    print("  POST /api/video/upload - Upload video file")
    print("  GET  /api/video/info - Get video information")
    print("  POST /api/rois - Save ROI configuration")
    print("  POST /api/tracking/start - Start tracking task")
    print("  GET  /api/tracking/status/<id> - Get tracking status")
    print("  GET  /api/tracking/results/<id> - Get tracking results")
    print("  POST /api/analysis/export - Export analysis report")
    print("  POST /api/analysis/heatmap - Generate heatmap")
    print("  GET  /api/experiments - List experiments")
    print("\n" + "=" * 60)
    print(f"Starting server on http://localhost:5000")
    print("=" * 60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
