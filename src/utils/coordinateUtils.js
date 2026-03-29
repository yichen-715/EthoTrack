import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000/api';

class CoordinateTransformer {
  constructor(canvasWidth, canvasHeight, videoWidth, videoHeight) {
    this.canvasWidth = canvasWidth;
    this.canvasHeight = canvasHeight;
    this.videoWidth = videoWidth;
    this.videoHeight = videoHeight;
    this.scaleX = videoWidth / canvasWidth;
    this.scaleY = videoHeight / canvasHeight;
  }

  updateDimensions(canvasWidth, canvasHeight, videoWidth, videoHeight) {
    this.canvasWidth = canvasWidth;
    this.canvasHeight = canvasHeight;
    this.videoWidth = videoWidth;
    this.videoHeight = videoHeight;
    this.scaleX = videoWidth / canvasWidth;
    this.scaleY = videoHeight / canvasHeight;
  }

  transformPoint(x, y) {
    return {
      x: Math.round(x * this.scaleX),
      y: Math.round(y * this.scaleY)
    };
  }

  transformPoints(points) {
    const transformed = [];
    for (let i = 0; i < points.length; i += 2) {
      const transformedPoint = this.transformPoint(points[i], points[i + 1]);
      transformed.push(transformedPoint.x, transformedPoint.y);
    }
    return transformed;
  }

  transformROI(roi) {
    const transformed = { ...roi };
    
    if (roi.type === 'polygon') {
      transformed.points = this.transformPoints(roi.points);
    } else if (roi.type === 'rectangle') {
      const topLeft = this.transformPoint(roi.x, roi.y);
      const bottomRight = this.transformPoint(roi.x + roi.width, roi.y + roi.height);
      transformed.x = topLeft.x;
      transformed.y = topLeft.y;
      transformed.width = bottomRight.x - topLeft.x;
      transformed.height = bottomRight.y - topLeft.y;
    } else if (roi.type === 'circle') {
      const center = this.transformPoint(roi.x, roi.y);
      transformed.x = center.x;
      transformed.y = center.y;
      transformed.radius = Math.round(roi.radius * this.scaleX);
    }
    
    return transformed;
  }

  transformROIs(rois) {
    return rois.map(roi => this.transformROI(roi));
  }

  getScaleInfo() {
    return {
      canvasSize: { width: this.canvasWidth, height: this.canvasHeight },
      videoSize: { width: this.videoWidth, height: this.videoHeight },
      scale: { x: this.scaleX, y: this.scaleY }
    };
  }
}

class BackendAPI {
  constructor(baseUrl = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.axiosInstance = axios.create({
      baseURL: baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  async sendROIs(rois, videoInfo) {
    try {
      const response = await this.axiosInstance.post('/rois', {
        rois: rois,
        videoInfo: videoInfo
      });
      return response.data;
    } catch (error) {
      console.error('发送ROI数据失败:', error);
      throw error;
    }
  }

  async startTracking(videoPath, roiConfig) {
    try {
      const response = await this.axiosInstance.post('/tracking/start', {
        videoPath: videoPath,
        roiConfig: roiConfig
      });
      return response.data;
    } catch (error) {
      console.error('启动追踪失败:', error);
      throw error;
    }
  }

  async getTrackingStatus(trackingId) {
    try {
      const response = await this.axiosInstance.get(`/tracking/status/${trackingId}`);
      return response.data;
    } catch (error) {
      console.error('获取追踪状态失败:', error);
      throw error;
    }
  }

  async getTrackingResults(trackingId) {
    try {
      const response = await this.axiosInstance.get(`/tracking/results/${trackingId}`);
      return response.data;
    } catch (error) {
      console.error('获取追踪结果失败:', error);
      throw error;
    }
  }

  async uploadVideo(file) {
    try {
      const formData = new FormData();
      formData.append('video', file);
      
      const response = await this.axiosInstance.post('/video/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      return response.data;
    } catch (error) {
      console.error('上传视频失败:', error);
      throw error;
    }
  }

  async getVideoInfo(videoPath) {
    try {
      const response = await this.axiosInstance.get('/video/info', {
        params: { path: videoPath }
      });
      return response.data;
    } catch (error) {
      console.error('获取视频信息失败:', error);
      throw error;
    }
  }
}

const exportROIConfig = (rois, videoInfo, transformer) => {
  const transformedROIs = transformer.transformROIs(rois);
  
  const config = {
    version: '1.0',
    exportTime: new Date().toISOString(),
    video: {
      width: videoInfo.videoWidth,
      height: videoInfo.videoHeight,
      frameRate: videoInfo.frameRate,
      duration: videoInfo.duration
    },
    canvas: {
      width: transformer.canvasWidth,
      height: transformer.canvasHeight,
      scale: {
        x: transformer.scaleX,
        y: transformer.scaleY
      }
    },
    rois: transformedROIs.map((roi, index) => ({
      id: index,
      name: roi.name || `ROI_${index}`,
      type: roi.type,
      color: roi.color?.value || '#00ff00',
      coordinates: getROICoordinates(roi)
    }))
  };
  
  return config;
};

const getROICoordinates = (roi) => {
  switch (roi.type) {
    case 'polygon':
      return {
        points: roi.points,
        pointCount: roi.points.length / 2
      };
    case 'rectangle':
      return {
        x: roi.x,
        y: roi.y,
        width: roi.width,
        height: roi.height
      };
    case 'circle':
      return {
        x: roi.x,
        y: roi.y,
        radius: roi.radius
      };
    default:
      return roi;
  }
};

const downloadROIConfig = (config, filename = 'roi_config.json') => {
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const generatePythonROI = (roi) => {
  let code = '';
  
  switch (roi.type) {
    case 'polygon':
      const points = roi.points;
      const pointPairs = [];
      for (let i = 0; i < points.length; i += 2) {
        pointPairs.push(`(${points[i]}, ${points[i + 1]})`);
      }
      code = `roi_points = np.array([${pointPairs.join(', ')}], dtype=np.int32)`;
      break;
    case 'rectangle':
      code = `roi_rect = (${roi.x}, ${roi.y}, ${roi.width}, ${roi.height})`;
      break;
    case 'circle':
      code = `roi_circle = (${roi.x}, ${roi.y}, ${roi.radius})`;
      break;
  }
  
  return code;
};

export {
  CoordinateTransformer,
  BackendAPI,
  exportROIConfig,
  downloadROIConfig,
  generatePythonROI
};
