# ETHO API 接口文档

## 基础信息

**Base URL**: `http://localhost:5000`  
**API版本**: v1.0  
**协议**: HTTP/HTTPS  
**数据格式**: JSON  
**字符编码**: UTF-8

## 通用响应格式

### 成功响应
```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

### 错误响应
```json
{
  "success": false,
  "error": "错误描述",
  "code": 400
}
```

## API端点列表

### 1. 系统健康检查

**GET** `/api/health`

检查后端服务状态。

**请求示例**:
```bash
curl http://localhost:5000/api/health
```

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "modules": ["cv_engine", "spatial", "behavioral_logic", "data_reporting"]
}
```

---

### 2. 视频上传

**POST** `/api/video/upload`

上传视频文件到后端服务器。

**请求参数**:
- Content-Type: `multipart/form-data`
- Body: 
  - `video`: 视频文件 (必需)

**请求示例**:
```bash
curl -X POST \
  -F "video=@experiment_video.mp4" \
  http://localhost:5000/api/video/upload
```

**响应示例**:
```json
{
  "success": true,
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "550e8400-e29b-41d4-a716-446655440000_experiment_video.mp4",
  "filepath": "/uploads/550e8400-e29b-41d4-a716-446655440000_experiment_video.mp4",
  "video_info": {
    "width": 1920,
    "height": 1080,
    "fps": 30.0,
    "frame_count": 9000,
    "duration": 300.0
  }
}
```

---

### 3. 视频信息查询

**GET** `/api/video/info`

获取已上传视频的详细信息。

**查询参数**:
- `video_path`: 视频文件路径 (必需)

**请求示例**:
```bash
curl "http://localhost:5000/api/video/info?video_path=/uploads/video.mp4"
```

**响应示例**:
```json
{
  "success": true,
  "video_info": {
    "width": 1920,
    "height": 1080,
    "fps": 30.0,
    "frame_count": 9000,
    "duration": 300.0
  }
}
```

---

### 4. 背景图像采集

**POST** `/api/background/capture`

从前端捕获的视频帧中保存背景图像。

**请求参数**:
- Content-Type: `multipart/form-data`
- Body:
  - `image`: 图像文件 (JPEG/PNG)

**请求示例**:
```bash
curl -X POST \
  -F "image=@background_frame.jpg" \
  http://localhost:5000/api/background/capture
```

**响应示例**:
```json
{
  "success": true,
  "background_id": "3841e50c-aeaa-4ac7-87ac-7d501b478122",
  "background_path": "/uploads/background_3841e50c-aeaa-4ac7-87ac-7d501b478122.jpg",
  "message": "背景图像已保存",
  "width": 1920,
  "height": 1080
}
```

---

### 5. ROI配置保存

**POST** `/api/rois`

保存感兴趣区域配置。

**请求体**:
```json
{
  "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
  "rois": [
    {
      "id": "roi_001",
      "name": "Center Zone",
      "type": "rectangle",
      "x": 160,
      "y": 120,
      "width": 320,
      "height": 240,
      "color": "hsl(210, 70%, 50%)"
    }
  ]
}
```

**响应示例**:
```json
{
  "success": true,
  "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
  "roi_count": 1,
  "message": "ROI配置已保存"
}
```

---

### 6. 追踪任务启动

**POST** `/api/tracking/start`

初始化追踪会话。

**请求体**:
```json
{
  "videoPath": "/uploads/video.mp4",
  "backgroundPath": "/uploads/background.jpg",
  "threshold": 50,
  "minArea": 100,
  "maxArea": 10000
}
```

**响应示例**:
```json
{
  "success": true,
  "tracking_id": "660e8400-e29b-41d4-a716-446655440001",
  "video_info": {
    "fps": 30.0,
    "total_frames": 9000,
    "width": 1920,
    "height": 1080
  },
  "message": "追踪会话已初始化"
}
```

---

### 7. 单帧处理

**POST** `/api/tracking/process-frame`

处理单个视频帧，返回质心坐标和二值化图像。

**请求体**:
```json
{
  "trackingId": "660e8400-e29b-41d4-a716-446655440001",
  "frameNumber": 150
}
```

**响应示例**:
```json
{
  "success": true,
  "frame_number": 150,
  "centroid": {
    "x": 320.5,
    "y": 240.3
  },
  "contour_area": 1250,
  "binary_frame": "base64_encoded_jpeg_image_data...",
  "trajectory_length": 150
}
```

**性能要求**:
- 处理延迟: < 100ms
- 坐标精度: ±0.5 像素

---

### 8. 追踪任务停止

**POST** `/api/tracking/stop`

停止追踪会话并返回完整轨迹数据。

**请求体**:
```json
{
  "trackingId": "660e8400-e29b-41d4-a716-446655440001"
}
```

**响应示例**:
```json
{
  "success": true,
  "tracking_id": "660e8400-e29b-41d4-a716-446655440001",
  "trajectory": [
    {
      "frame": 0,
      "x": 320.5,
      "y": 240.3,
      "detected": true,
      "area": 1250
    }
  ],
  "total_frames_processed": 9000,
  "message": "追踪已停止"
}
```

---

### 9. 物理指标计算

**POST** `/api/analysis/metrics`

计算轨迹的物理指标（距离、速度等）。

**请求体**:
```json
{
  "trackingId": "660e8400-e29b-41d4-a716-446655440001",
  "scaleCalibration": {
    "pixelsPerCm": 25.4
  }
}
```

**响应示例**:
```json
{
  "success": true,
  "metrics": {
    "total_distance_cm": 1250.5,
    "avg_speed_cm_s": 4.17,
    "max_speed_cm_s": 15.3,
    "immobility_time_s": 45.2,
    "immobility_frames": 1356
  }
}
```

**精度要求**:
- 距离转换误差: < 0.1 cm
- 速度计算精度: ±0.01 cm/s

---

### 10. 热力图生成

**POST** `/api/analysis/heatmap`

生成科研级密度热力图（使用KDE算法）。

**请求体**:
```json
{
  "trackingId": "660e8400-e29b-41d4-a716-446655440001",
  "bandwidth": 50.0
}
```

**响应示例**:
```json
{
  "success": true,
  "heatmap": "base64_encoded_png_image_data...",
  "trajectory_points": 8500,
  "message": "热力图已生成"
}
```

**技术规格**:
- 算法: Kernel Density Estimation (KDE)
- 分辨率: 150 DPI
- 格式: PNG (Base64编码)

---

### 11. 分析报告导出

**POST** `/api/analysis/export`

导出完整的Excel分析报告。

**请求体**:
```json
{
  "trackingId": "660e8400-e29b-41d4-a716-446655440001",
  "subjectInfo": {
    "id": "M001",
    "group": "WT"
  },
  "rois": [...],
  "scaleCalibration": {
    "pixelsPerCm": 25.4
  }
}
```

**响应示例**:
```json
{
  "success": true,
  "report_path": "/results/reports/report_M001_20240115_103000.xlsx",
  "metrics": {
    "total_distance_cm": 1250.5,
    "avg_speed_cm_s": 4.17,
    "max_speed_cm_s": 15.3,
    "immobility_time_s": 45.2
  },
  "zone_stats": {
    "Center Zone": {
      "frames": 2500,
      "time_seconds": 83.3,
      "percentage": 27.8
    }
  },
  "message": "报告已生成"
}
```

**报告内容**:
- Summary Sheet: 实验概览和主要指标
- Trajectory Sheet: 逐帧轨迹数据
- Zone Statistics Sheet: 区域停留统计
- ROI Configuration Sheet: ROI配置详情

---

### 12. 实验列表查询

**GET** `/api/experiments`

查询实验历史记录。

**查询参数**:
- `subjectId`: 小鼠编号 (可选)
- `group`: 实验组别 (可选)
- `limit`: 返回数量限制 (默认: 100)

**请求示例**:
```bash
curl "http://localhost:5000/api/experiments?group=WT&limit=50"
```

**响应示例**:
```json
{
  "success": true,
  "experiments": [
    {
      "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
      "subject_id": "M001",
      "group": "WT",
      "experiment_type": "Open Field",
      "video_path": "/uploads/video.mp4",
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "count": 1
}
```

---

### 13. 实验详情查询

**GET** `/api/experiments/{experiment_id}`

查询单个实验的详细信息和轨迹数据。

**请求示例**:
```bash
curl http://localhost:5000/api/experiments/550e8400-e29b-41d4-a716-446655440000
```

**响应示例**:
```json
{
  "success": true,
  "experiment": {
    "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
    "subject_id": "M001",
    "group": "WT",
    "experiment_type": "Open Field",
    "video_path": "/uploads/video.mp4",
    "created_at": "2024-01-15T10:30:00",
    "config": {...},
    "metrics": {...}
  },
  "trajectory": [...]
}
```

---

## WebSocket实时通信

### 连接端点
`ws://localhost:5000/socket.io`

### 事件类型

#### 1. tracking_progress
追踪进度更新事件。

**数据格式**:
```json
{
  "tracking_id": "660e8400-e29b-41d4-a716-446655440001",
  "progress": 45.5,
  "current_frame": 4095,
  "total_frames": 9000
}
```

---

## 错误代码说明

| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 性能指标

| API端点 | 响应时间 | 说明 |
|---------|---------|------|
| /api/health | < 10ms | 健康检查 |
| /api/video/upload | < 5s | 视频上传 (100MB文件) |
| /api/tracking/process-frame | < 100ms | 单帧处理 |
| /api/analysis/metrics | < 500ms | 指标计算 |
| /api/analysis/heatmap | < 2s | 热力图生成 |
| /api/analysis/export | < 3s | 报告导出 |

## 安全考虑

### CORS配置
- 允许来源: `http://localhost:3000`
- 允许方法: GET, POST, OPTIONS
- 允许头部: Content-Type, Authorization

### 文件上传限制
- 最大文件大小: 500MB
- 允许格式: .mp4, .avi, .mov, .jpg, .png

### 数据验证
- 所有输入参数进行类型检查
- 文件路径进行安全验证
- SQL注入防护

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2024-01-15 | 初始版本，实现核心API |
