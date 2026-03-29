import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Stage, Layer, Line, Rect, Circle, RegularPolygon, Transformer } from 'react-konva';

const TOOL_TYPES = {
  SELECT: 'select',
  RECTANGLE: 'rectangle',
  POLYGON: 'polygon',
  CIRCLE: 'circle'
};

const hslToRgba = (hslStr, alpha = 0.2) => {
  const match = hslStr.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/);
  if (!match) return `rgba(100, 150, 255, ${alpha})`;
  
  let h = parseInt(match[1]) / 360;
  let s = parseInt(match[2]) / 100;
  let l = parseInt(match[3]) / 100;
  
  let r, g, b;
  if (s === 0) {
    r = g = b = l;
  } else {
    const hue2rgb = (p, q, t) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1/6) return p + (q - p) * 6 * t;
      if (t < 1/2) return q;
      if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1/3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1/3);
  }
  
  return `rgba(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)}, ${alpha})`;
};

const PlaybackControls = ({
  isPlaying,
  onPlayPause,
  currentTime,
  duration,
  onSeek,
  playbackRate,
  onRateChange,
  currentFrame,
  totalFrames,
  fps
}) => {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  return (
    <div className="playback-controls">
      <button 
        className={`play-btn ${isPlaying ? 'playing' : ''}`}
        onClick={onPlayPause}
      >
        {isPlaying ? '⏸️' : '▶️'}
      </button>
      
      <div className="time-display">
        <span className="current-time">{formatTime(currentTime)}</span>
        <span className="time-separator">/</span>
        <span className="total-time">{formatTime(duration)}</span>
      </div>
      
      <div className="progress-container">
        <input
          type="range"
          className="progress-slider"
          min="0"
          max={duration || 100}
          step={1 / (fps || 30)}
          value={currentTime}
          onChange={(e) => onSeek(parseFloat(e.target.value))}
        />
        <div 
          className="progress-fill"
          style={{ width: `${(currentTime / duration) * 100}%` }}
        />
      </div>
      
      <div className="frame-display">
        帧: {currentFrame} / {totalFrames}
      </div>
      
      <div className="speed-control">
        <label>倍速:</label>
        <select 
          value={playbackRate}
          onChange={(e) => onRateChange(parseFloat(e.target.value))}
        >
          <option value="0.25">0.25x</option>
          <option value="0.5">0.5x</option>
          <option value="1">1x</option>
          <option value="2">2x</option>
          <option value="4">4x</option>
        </select>
      </div>
    </div>
  );
};

const MainWorkspace = ({
  videoFile,
  videoInfo,
  rois,
  setROIs,
  trackingData,
  setTrackingData,
  isTracking,
  setIsTracking,
  trackingId,
  setTrackingId,
  currentTime,
  setCurrentTime,
  currentFrame,
  setCurrentFrame,
  scaleCalibration,
  setScaleCalibration,
  timeRange,
  algorithmParams,
  activeTool,
  onToolChange,
  onUndo,
  onClear,
  history,
  setHistory,
  calibrationMode,
  calibrationPoints,
  onCalibrationClick,
  arenaConfig,
  onArenaChange,
  subjectInfo
}) => {
  const videoRef = useRef(null);
  const stageRef = useRef(null);
  const animationRef = useRef(null);
  const containerRef = useRef(null);
  const transformerRef = useRef(null);
  const trackingRequestInFlightRef = useRef(false);
  const latestTrackingFrameRef = useRef(-1);
  
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawingPoints, setDrawingPoints] = useState([]);
  const [selectedROI, setSelectedROI] = useState(null);
  const [selectedArena, setSelectedArena] = useState(false);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [trajectoryPoints, setTrajectoryPoints] = useState([]);
  const [mousePosition, setMousePosition] = useState(null);
  const [videoReady, setVideoReady] = useState(false);
  const [viewMode, setViewMode] = useState('realtime');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [backgroundPath, setBackgroundPath] = useState(null);
  const [trackingEnabled, setTrackingEnabled] = useState(false);
  const trackingIdRef = useRef(null);
  const [centroidPosition, setCentroidPosition] = useState(null);
  const [binaryFrame, setBinaryFrame] = useState(null);
  const [previewBinaryFrame, setPreviewBinaryFrame] = useState(null);
  const [contourData, setContourData] = useState(null);
  const [trajectoryHistory, setTrajectoryHistory] = useState([]);
  const [trackingFPS, setTrackingFPS] = useState(30);
  const TRAJECTORY_DURATION_MS = 1000;
  const TRAJECTORY_MAX_POINTS = 10;

  const normalizeFPS = (fps) => {
    const value = Number(fps);
    return Number.isFinite(value) && value > 1 && value < 240 ? value : 30;
  };

  const videoSrc = useMemo(() => {
    if (videoFile) {
      return URL.createObjectURL(videoFile);
    }
    return null;
  }, [videoFile]);

  useEffect(() => {
    return () => {
      if (videoSrc) {
        URL.revokeObjectURL(videoSrc);
      }
    };
  }, [videoSrc]);

  useEffect(() => {
    setVideoReady(false);
    setIsPlaying(false);
    setCurrentTime(0);
    setCurrentFrame(0);
    setBinaryFrame(null);
    setPreviewBinaryFrame(null);
    setCentroidPosition(null);
    setContourData(null);
    setTrackingData(null);
    setIsTracking(false);
  }, [videoFile]);

  const processingRef = useRef(false);
  const lastSentFrameTimeRef = useRef(0);
  const MIN_FRAME_INTERVAL = 16;

  const processFrame = useCallback(() => {
    if (!videoRef.current || !videoReady || !backgroundPath) return;
    
    const now = performance.now();
    if (processingRef.current && (now - lastSentFrameTimeRef.current) < 100) {
      return;
    }
    
    lastSentFrameTimeRef.current = now;
    processingRef.current = true;
    
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob((blob) => {
      if (!blob) {
        processingRef.current = false;
        return;
      }

      const formData = new FormData();
      formData.append('image', blob, 'frame.jpg');
      formData.append('threshold', String(algorithmParams.threshold || 50));
      formData.append('minArea', String(algorithmParams.minArea || 50));
      formData.append('maxArea', String(algorithmParams.maxArea || 10000));
      if (backgroundPath) {
        formData.append('backgroundPath', backgroundPath);
      }
      if (arenaConfig?.arena) {
        formData.append('arenaConfig', JSON.stringify(arenaConfig));
      }
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 200);
      
      fetch('http://localhost:5000/api/video/preview-binary', {
        method: 'POST',
        body: formData,
        signal: controller.signal
      })
      .then(res => res.json())
      .then(data => {
        clearTimeout(timeoutId);
        processingRef.current = false;
        
        if (data.success) {
          setPreviewBinaryFrame(`data:image/jpeg;base64,${data.binary_frame}`);
          
          if (data.centroid && videoInfo) {
            const scaleX = canvasSize.width / videoInfo.width;
            const scaleY = canvasSize.height / videoInfo.height;
            const scaledCentroid = {
              x: data.centroid.x * scaleX,
              y: data.centroid.y * scaleY
            };
            setCentroidPosition(scaledCentroid);
            
            setTrajectoryHistory(prev => {
              const now = Date.now();
              const newHistory = [...prev, { ...scaledCentroid, timestamp: now }];
              const filtered = newHistory.filter(p => now - p.timestamp <= TRAJECTORY_DURATION_MS);
              return filtered.slice(-TRAJECTORY_MAX_POINTS);
            });
          } else {
            setCentroidPosition(null);
          }
          
          if (data.contour_points && data.contour_points.length > 0 && videoInfo) {
            const scaleX = canvasSize.width / videoInfo.width;
            const scaleY = canvasSize.height / videoInfo.height;
            const scaledPoints = data.contour_points.map(p => ({
              x: p[0] * scaleX,
              y: p[1] * scaleY
            }));
            setContourData(scaledPoints);
          } else {
            setContourData(null);
          }
        }
      })
      .catch(err => {
        clearTimeout(timeoutId);
        processingRef.current = false;
        if (err.name !== 'AbortError') {
          console.error('Frame processing error:', err);
        }
      });
    }, 'image/jpeg', 0.85);
  }, [videoReady, algorithmParams.threshold, algorithmParams.minArea, algorithmParams.maxArea, backgroundPath, canvasSize, videoInfo, arenaConfig]);

  useEffect(() => {
    if (videoReady && backgroundPath) {
      processFrame();
    }
  }, [viewMode, videoReady, backgroundPath, processFrame]);

  useEffect(() => {
    if (isPlaying && videoReady && backgroundPath) {
      let lastFrameTime = 0;
      let animationId;
      
      const processLoop = (timestamp) => {
        if (timestamp - lastFrameTime >= MIN_FRAME_INTERVAL) {
          lastFrameTime = timestamp;
          processFrame();
        }
        animationId = requestAnimationFrame(processLoop);
      };
      
      animationId = requestAnimationFrame(processLoop);
      return () => cancelAnimationFrame(animationId);
    }
  }, [isPlaying, videoReady, backgroundPath, processFrame]);

  const stopTracking = useCallback(async () => {
    const currentTrackingId = trackingIdRef.current;
    if (!currentTrackingId) {
      setTrackingEnabled(false);
      setIsTracking(false);
      setIsAnalyzing(false);
      setIsPlaying(false);
      if (videoRef.current) {
        videoRef.current.pause();
      }
      return;
    }
    
    try {
      const res = await fetch('http://localhost:5000/api/tracking/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          trackingId: currentTrackingId,
          subjectInfo: subjectInfo
        })
      });
      const data = await res.json();
      
      if (data.success) {
        trackingRequestInFlightRef.current = false;
        latestTrackingFrameRef.current = -1;
        setTrackingEnabled(false);
        setIsTracking(false);
        setIsAnalyzing(false);
        setIsPlaying(false);
        if (videoRef.current) {
          videoRef.current.pause();
        }
        setCentroidPosition(null);
        setContourData(null);
        setBinaryFrame(null);
        setTrajectoryHistory([]);
        setTrackingData(prev => ({
          ...(prev || {}),
          trajectory: data.trajectory || prev?.trajectory || [],
          isTracking: false,
          currentLocation: null,
          currentZone: null,
          currentState: '等待追踪',
          status: '等待追踪'
        }));
        console.log('Tracking stopped, trajectory points:', data.trajectory?.length);
      }
    } catch (error) {
      console.error('Failed to stop tracking:', error);
      setTrackingEnabled(false);
      setIsTracking(false);
      setIsAnalyzing(false);
      setIsPlaying(false);
    }
  }, []);

  useEffect(() => {
    if (isPlaying && trackingEnabled && trackingIdRef.current && videoRef.current && videoReady) {
      const interval = setInterval(() => {
        const video = videoRef.current;
        if (!video || trackingRequestInFlightRef.current || !videoInfo) return;

        const startTime = Math.max(0, Number(timeRange?.start || 0));
        const endTime = Number(timeRange?.end ?? 0);

        if (video.currentTime < startTime) {
          video.currentTime = startTime;
          return;
        }

        if (Number.isFinite(endTime) && endTime > 0 && video.currentTime >= endTime) {
          stopTracking();
          return;
        }

        const fps = normalizeFPS(trackingFPS || videoInfo?.fps);
        const frameNumber = Math.floor(video.currentTime * fps);

        // Skip duplicate frame requests
        if (frameNumber <= latestTrackingFrameRef.current) return;

        trackingRequestInFlightRef.current = true;

        fetch('http://localhost:5000/api/tracking/process-frame', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            trackingId: trackingId,
            frameNumber: frameNumber
          })
        })
        .then(res => res.json())
        .then(data => {
          trackingRequestInFlightRef.current = false;
          if (data.success) {
            latestTrackingFrameRef.current = frameNumber;

            setTrackingData(prev => {
              const prevTrajectory = prev?.trajectory || [];
              let nextTrajectory = prevTrajectory;

              if (data.centroid) {
                const hasSameFrame = prevTrajectory.length > 0 && prevTrajectory[prevTrajectory.length - 1].frame === frameNumber;
                if (!hasSameFrame) {
                  nextTrajectory = [
                    ...prevTrajectory,
                    {
                      frame: frameNumber,
                      timestamp: frameNumber / fps,
                      x: data.centroid.x,
                      y: data.centroid.y,
                      detected: true
                    }
                  ];
                }
              }

              const lastTrackPoint = nextTrajectory.length > 0 ? nextTrajectory[nextTrajectory.length - 1] : null;
              const prevTrackPoint = nextTrajectory.length > 1 ? nextTrajectory[nextTrajectory.length - 2] : null;

              let location = '未知区域';
              if (lastTrackPoint) {
                if (arenaConfig?.arena) {
                  const arena = arenaConfig.arena;
                  const centerRatio = (arenaConfig.centerRatio || 30) / 100;
                  const cornerRatio = (arenaConfig.cornerRatio || 20) / 100;
                  const showCorners = arenaConfig.showCorners || arenaConfig.hasCorners;
                  
                  const videoWidth = videoInfo?.width || 1;
                  const videoHeight = videoInfo?.height || 1;
                  
                  const arenaX = arena.x * videoWidth;
                  const arenaY = arena.y * videoHeight;
                  const arenaWidth = arena.width * videoWidth;
                  const arenaHeight = arena.height * videoHeight;
                  
                  const inArena = lastTrackPoint.x >= arenaX && 
                                  lastTrackPoint.x <= arenaX + arenaWidth &&
                                  lastTrackPoint.y >= arenaY && 
                                  lastTrackPoint.y <= arenaY + arenaHeight;
                  
                  if (inArena) {
                    const centerWidth = arenaWidth * centerRatio;
                    const centerHeight = arenaHeight * centerRatio;
                    const centerX = arenaX + (arenaWidth - centerWidth) / 2;
                    const centerY = arenaY + (arenaHeight - centerHeight) / 2;
                    
                    const inCenter = lastTrackPoint.x >= centerX && 
                                     lastTrackPoint.x <= centerX + centerWidth &&
                                     lastTrackPoint.y >= centerY && 
                                     lastTrackPoint.y <= centerY + centerHeight;
                    
                    if (inCenter) {
                      location = '中心区';
                    } else if (showCorners) {
                      const cornerWidth = arenaWidth * cornerRatio;
                      const cornerHeight = arenaHeight * cornerRatio;
                      
                      const corners = [
                        { name: '左上角', x: arenaX, y: arenaY },
                        { name: '右上角', x: arenaX + arenaWidth - cornerWidth, y: arenaY },
                        { name: '左下角', x: arenaX, y: arenaY + arenaHeight - cornerHeight },
                        { name: '右下角', x: arenaX + arenaWidth - cornerWidth, y: arenaY + arenaHeight - cornerHeight }
                      ];
                      
                      let inCorner = false;
                      for (const corner of corners) {
                        if (lastTrackPoint.x >= corner.x && 
                            lastTrackPoint.x <= corner.x + cornerWidth &&
                            lastTrackPoint.y >= corner.y && 
                            lastTrackPoint.y <= corner.y + cornerHeight) {
                          location = corner.name;
                          inCorner = true;
                          break;
                        }
                      }
                      
                      if (!inCorner) {
                        location = '边缘区';
                      }
                    } else {
                      location = '边缘区';
                    }
                  }
                } else {
                  for (const roi of rois) {
                    if (roi.type === 'rectangle') {
                      if (
                        lastTrackPoint.x >= roi.x &&
                        lastTrackPoint.x <= roi.x + roi.width &&
                        lastTrackPoint.y >= roi.y &&
                        lastTrackPoint.y <= roi.y + roi.height
                      ) {
                        location = roi.name;
                        break;
                      }
                    } else if (roi.type === 'circle' && roi.center) {
                      const dist = Math.sqrt(
                        Math.pow(lastTrackPoint.x - roi.center.x, 2) +
                        Math.pow(lastTrackPoint.y - roi.center.y, 2)
                      );
                      if (dist <= roi.radius) {
                        location = roi.name;
                        break;
                      }
                    } else if (roi.type === 'polygon' && Array.isArray(roi.points) && roi.points.length >= 3) {
                      let inside = false;
                      for (let i = 0, j = roi.points.length - 1; i < roi.points.length; j = i++) {
                        const xi = roi.points[i].x;
                        const yi = roi.points[i].y;
                        const xj = roi.points[j].x;
                        const yj = roi.points[j].y;
                        if (((yi > lastTrackPoint.y) !== (yj > lastTrackPoint.y)) &&
                          (lastTrackPoint.x < (xj - xi) * (lastTrackPoint.y - yi) / (yj - yi + Number.EPSILON) + xi)) {
                          inside = !inside;
                        }
                      }
                      if (inside) {
                        location = roi.name;
                        break;
                      }
                    }
                  }
                }
              }

              let movementState = '等待追踪';
              if (lastTrackPoint) {
                if (prevTrackPoint) {
                  const dx = lastTrackPoint.x - prevTrackPoint.x;
                  const dy = lastTrackPoint.y - prevTrackPoint.y;
                  movementState = Math.sqrt(dx * dx + dy * dy) < 2 ? '静止中' : '运动中';
                } else {
                  movementState = '运动中';
                }
              }

              const hasDetection = Boolean(data.centroid);

              return {
                ...(prev || {}),
                trajectory: nextTrajectory,
                isTracking: true,
                currentZone: location,
                currentLocation: location,
                currentState: movementState,
                status: movementState,
                latestFrame: frameNumber,
                latestTimestamp: frameNumber / fps,
                hasDetection,
                metrics: data.metrics || prev?.metrics || {}
              };
            });

            if (data.centroid) {
              const scaleX = canvasSize.width / videoInfo.width;
              const scaleY = canvasSize.height / videoInfo.height;
              const scaledCentroid = {
                x: data.centroid.x * scaleX,
                y: data.centroid.y * scaleY
              };
              setCentroidPosition(scaledCentroid);

              setTrajectoryHistory(prev => {
                const now = Date.now();
                const newHistory = [...prev, { ...scaledCentroid, timestamp: now }];
                const filtered = newHistory.filter(p => now - p.timestamp <= TRAJECTORY_DURATION_MS);
                return filtered.slice(-TRAJECTORY_MAX_POINTS);
              });
            }
            if (data.contour_points && data.contour_points.length > 0) {
              const scaleX = canvasSize.width / videoInfo.width;
              const scaleY = canvasSize.height / videoInfo.height;
              const scaledPoints = data.contour_points.map(p => ({
                x: p[0] * scaleX,
                y: p[1] * scaleY
              }));
              setContourData(scaledPoints);
            } else {
              setContourData(null);
            }
            if (data.binary_frame) {
              setBinaryFrame(`data:image/jpeg;base64,${data.binary_frame}`);
            }
          }
        })
        .catch(err => {
          trackingRequestInFlightRef.current = false;
          console.error('Frame processing error:', err);
        });
      }, 16);

      return () => clearInterval(interval);
    }
  }, [isPlaying, trackingEnabled, videoReady, canvasSize, videoInfo, rois, trackingFPS, timeRange, stopTracking]);

  useEffect(() => {
    const originalOnBackgroundCaptured = window.onBackgroundCaptured;
    
    window.onBackgroundCaptured = (path) => {
      setBackgroundPath(path);
      console.log('MainWorkspace received background path:', path);
      if (originalOnBackgroundCaptured) {
        originalOnBackgroundCaptured(path);
      }
    };
    
    window.captureBackgroundFromVideo = () => {
      if (!videoRef.current || !videoReady) {
        alert('请先导入视频文件');
        return;
      }
      
      const video = videoRef.current;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0);
      
      canvas.toBlob((blob) => {
        if (!blob) {
          alert('背景采集失败：无法从当前帧生成图像');
          return;
        }

        const formData = new FormData();
        formData.append('image', blob, 'background.jpg');
        
        fetch('http://localhost:5000/api/background/capture', {
          method: 'POST',
          body: formData
        })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            alert('背景图像已保存！');
            setBackgroundPath(data.background_path);
            if (window.onBackgroundCaptured) {
              window.onBackgroundCaptured(data.background_path);
            }
            console.log('Background captured:', data.background_path);
          } else {
            alert('保存失败: ' + data.error);
          }
        })
        .catch(err => {
          console.error('Failed to capture background:', err);
          alert('保存失败: ' + err.message);
        });
      }, 'image/jpeg', 0.95);
    };
    
    return () => {
      window.onBackgroundCaptured = originalOnBackgroundCaptured;
      window.captureBackgroundFromVideo = null;
    };
  }, [videoReady]);

  const startTracking = async () => {
    if (!videoFile || !backgroundPath) {
      alert('请先导入视频并采集背景图像');
      return;
    }

    try {
      setIsAnalyzing(true);
      
      const formData = new FormData();
      formData.append('video', videoFile);
      
      const uploadRes = await fetch('http://localhost:5000/api/video/upload', {
        method: 'POST',
        body: formData
      });
      const uploadData = await uploadRes.json();
      
      if (!uploadData.success) {
        throw new Error(uploadData.error);
      }

      const startRes = await fetch('http://localhost:5000/api/tracking/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoPath: uploadData.filepath,
          backgroundPath: backgroundPath,
          threshold: algorithmParams.threshold || 50,
          minArea: algorithmParams.minArea || 100,
          maxArea: algorithmParams.maxArea || 10000
        })
      });
      const startData = await startRes.json();
      
      if (startData.success) {
        trackingRequestInFlightRef.current = false;
        latestTrackingFrameRef.current = -1;
        const fps = normalizeFPS(startData.video_info?.fps || videoInfo?.fps);
        const startTime = Math.max(0, Number(timeRange?.start || 0));

        setTrackingFPS(fps);
        if (videoRef.current) {
          videoRef.current.currentTime = startTime;
        }
        setCurrentTime(startTime);
        setCurrentFrame(Math.floor(startTime * fps));

        setTrackingData({ trajectory: [], isTracking: true });
        trackingIdRef.current = startData.tracking_id;
        setTrackingId(startData.tracking_id);
        setTrackingEnabled(true);
        setIsTracking(true);
        setIsPlaying(true);
        console.log('Tracking started:', startData.tracking_id);
      } else {
        setIsAnalyzing(false);
        alert('启动追踪失败: ' + startData.error);
      }
    } catch (error) {
      console.error('Failed to start tracking:', error);
      setIsAnalyzing(false);
      alert('启动追踪失败: ' + error.message);
    }
  };

  useEffect(() => {
    if (selectedArena && transformerRef.current && stageRef.current) {
      const selectedNode = stageRef.current.findOne(`[name="arena-main"]`);
      if (selectedNode) {
        transformerRef.current.nodes([selectedNode]);
        transformerRef.current.getLayer().batchDraw();
      }
    } else if (selectedROI !== null && transformerRef.current && stageRef.current) {
      const selectedNode = stageRef.current.findOne(`#roi-${rois[selectedROI]?.id}`);
      if (selectedNode) {
        transformerRef.current.nodes([selectedNode]);
        transformerRef.current.getLayer().batchDraw();
      }
    } else if (transformerRef.current) {
      transformerRef.current.nodes([]);
      transformerRef.current.getLayer().batchDraw();
    }
  }, [selectedROI, selectedArena, rois]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current && videoInfo) {
        const containerWidth = containerRef.current.offsetWidth - 40;
        const containerHeight = containerRef.current.offsetHeight - 120;
        const aspectRatio = videoInfo.width / videoInfo.height;
        
        let width = containerWidth;
        let height = width / aspectRatio;
        
        if (height > containerHeight) {
          height = containerHeight;
          width = height * aspectRatio;
        }
        
        setCanvasSize({ width, height });
      }
    };
    
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, [videoInfo]);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !videoReady) return;

    const updateFrame = () => {
      const fps = normalizeFPS(trackingFPS || videoInfo?.fps);
      if (video.paused) return;

      const endTime = Number(timeRange?.end ?? 0);
      if (trackingEnabled && Number.isFinite(endTime) && endTime > 0 && video.currentTime >= endTime) {
        stopTracking();
        return;
      }

      setCurrentTime(video.currentTime);
      setCurrentFrame(Math.floor(video.currentTime * fps));
      
      if (trackingData?.trajectory) {
        const fps = videoInfo?.fps || 30;
        const currentPoint = trackingData.trajectory.find(
          p => Math.abs((p.timestamp ?? p.time ?? (p.frame / fps)) - video.currentTime) < (1 / fps)
        );
        if (currentPoint) {
          setMousePosition(currentPoint);
          setTrajectoryPoints(prev => {
            const newPoints = [...prev, currentPoint];
            return newPoints.slice(-100);
          });
        }
      }
      
      animationRef.current = requestAnimationFrame(updateFrame);
    };

    let playPromise = null;
    
    if (isPlaying) {
      console.log('Starting video playback, isPlaying:', isPlaying);
      playPromise = video.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            console.log('Video playback started successfully');
            animationRef.current = requestAnimationFrame(updateFrame);
          })
          .catch(error => {
            console.error('Video play error:', error);
            setIsPlaying(false);
          });
      }
    } else {
      console.log('Pausing video, isPlaying:', isPlaying);
      video.pause();
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (playPromise !== undefined) {
        video.pause();
      }
    };
  }, [isPlaying, trackingData, videoReady, trackingFPS, videoInfo, timeRange, trackingEnabled, stopTracking]);

  const handleVideoLoad = () => {
    if (videoRef.current) {
      setCurrentTime(0);
      setCurrentFrame(0);
      setIsPlaying(false);
      setVideoReady(true);
    }
  };

  const handleVideoEnded = () => {
    setIsPlaying(false);
  };

  const handlePlayPause = () => {
    console.log('handlePlayPause called, videoReady:', videoReady, 'isPlaying:', isPlaying);
    if (!videoReady || !videoRef.current) {
      console.log('Cannot toggle play: video not ready');
      return;
    }
    setIsPlaying(!isPlaying);
  };

  const handleSeek = (time) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
      const fps = normalizeFPS(trackingFPS || videoInfo?.fps);
      setCurrentFrame(Math.floor(time * fps));
    }
  };

  const handleRateChange = (rate) => {
    setPlaybackRate(rate);
  };

  const saveToHistory = () => {
    setHistory([...history, rois]);
  };

  const handleUndo = () => {
    if (history.length > 0) {
      const newHistory = [...history];
      const previousState = newHistory.pop();
      setHistory(newHistory);
      setROIs(previousState);
    }
  };

  const handleClear = () => {
    saveToHistory();
    setROIs([]);
    setSelectedROI(null);
  };

  const getRelativePointerPosition = () => {
    const stage = stageRef.current;
    const pos = stage.getPointerPosition();
    return {
      x: pos.x,
      y: pos.y
    };
  };

  const transformToVideoCoords = (pos) => {
    if (!videoInfo) return pos;
    const scaleX = videoInfo.width / canvasSize.width;
    const scaleY = videoInfo.height / canvasSize.height;
    return {
      x: pos.x * scaleX,
      y: pos.y * scaleY
    };
  };

  const handleStageClick = (e) => {
    if (calibrationMode) {
      const pos = getRelativePointerPosition();
      const videoPos = transformToVideoCoords(pos);
      onCalibrationClick(videoPos);
      return;
    }

    if (arenaConfig?.arena) {
      const clickedOnArena = e.target.name() === 'arena-main';
      const clickedOnEmpty = e.target === e.target.getStage();
      
      if (clickedOnArena) {
        setSelectedArena(true);
        setSelectedROI(null);
      } else if (clickedOnEmpty) {
        setSelectedArena(false);
        setSelectedROI(null);
      }
      return;
    }

    if (activeTool === TOOL_TYPES.SELECT) {
      const clickedOnEmpty = e.target === e.target.getStage();
      if (clickedOnEmpty) {
        setSelectedROI(null);
      }
      return;
    }

    if (activeTool === TOOL_TYPES.POLYGON) {
      const pos = getRelativePointerPosition();
      const videoPos = transformToVideoCoords(pos);
      
      if (!isDrawing) {
        setIsDrawing(true);
        setDrawingPoints([videoPos]);
      } else {
        setDrawingPoints([...drawingPoints, videoPos]);
      }
    }
  };

  const handleStageDblClick = () => {
    if (arenaConfig?.arena) return;
    if (activeTool === TOOL_TYPES.POLYGON && isDrawing && drawingPoints.length >= 3) {
      completePolygon();
    }
  };

  const handleMouseDown = (e) => {
    if (arenaConfig?.arena && activeTool !== TOOL_TYPES.SELECT) return;
    
    if (activeTool === TOOL_TYPES.RECTANGLE) {
      const pos = getRelativePointerPosition();
      const videoPos = transformToVideoCoords(pos);
      setIsDrawing(true);
      setDrawingPoints([videoPos, videoPos]);
    } else if (activeTool === TOOL_TYPES.CIRCLE) {
      const pos = getRelativePointerPosition();
      const videoPos = transformToVideoCoords(pos);
      setIsDrawing(true);
      setDrawingPoints([videoPos, { ...videoPos, radius: 0 }]);
    }
  };

  const handleMouseMove = () => {
    if (!isDrawing) return;
    if (arenaConfig?.arena && activeTool !== TOOL_TYPES.SELECT) return;

    const pos = getRelativePointerPosition();
    const videoPos = transformToVideoCoords(pos);

    if (activeTool === TOOL_TYPES.RECTANGLE && drawingPoints.length === 2) {
      setDrawingPoints([drawingPoints[0], videoPos]);
    } else if (activeTool === TOOL_TYPES.CIRCLE && drawingPoints.length === 2) {
      const center = drawingPoints[0];
      const radius = Math.sqrt(
        Math.pow(videoPos.x - center.x, 2) + Math.pow(videoPos.y - center.y, 2)
      );
      setDrawingPoints([center, { ...videoPos, radius }]);
    }
  };

  const handleMouseUp = () => {
    if (arenaConfig?.arena && activeTool !== TOOL_TYPES.SELECT) return;
    if (activeTool === TOOL_TYPES.RECTANGLE && drawingPoints.length === 2) {
      completeRectangle();
    } else if (activeTool === TOOL_TYPES.CIRCLE && drawingPoints.length === 2) {
      completeCircle();
    }
  };

  const completeRectangle = () => {
    if (drawingPoints.length === 2) {
      const [start, end] = drawingPoints;
      const newROI = {
        id: Date.now(),
        name: `矩形区域_${rois.length + 1}`,
        type: 'rectangle',
        points: drawingPoints,
        color: `hsl(${Math.random() * 360}, 70%, 50%)`,
        x: Math.min(start.x, end.x),
        y: Math.min(start.y, end.y),
        width: Math.abs(end.x - start.x),
        height: Math.abs(end.y - start.y)
      };

      if (arenaConfig?.enabled && !arenaConfig.arena) {
        const videoWidth = videoInfo?.width || canvasSize.width;
        const videoHeight = videoInfo?.height || canvasSize.height;
        const arenaROI = {
          id: 'arena-main',
          name: '全场区',
          type: 'rectangle',
          // newROI is in VIDEO coordinates, so normalize with VIDEO dimensions
          x: newROI.x / videoWidth,
          y: newROI.y / videoHeight,
          width: newROI.width / videoWidth,
          height: newROI.height / videoHeight,
          color: 'hsl(0, 70%, 50%)',
          isArena: true
        };
        console.log('Created arena ROI:', arenaROI, 'canvasSize:', canvasSize, 'videoInfo:', videoInfo);
        onArenaChange({
          ...arenaConfig,
          arena: arenaROI
        });
        setIsDrawing(false);
        setDrawingPoints([]);
        setSelectedArena(true);
        onToolChange(TOOL_TYPES.SELECT);
        return;
      }

      saveToHistory();
      setROIs([...rois, newROI]);
    }
    setIsDrawing(false);
    setDrawingPoints([]);
  };

  const completePolygon = () => {
    if (arenaConfig?.arena) return;
    if (drawingPoints.length >= 3) {
      saveToHistory();
      const newROI = {
        id: Date.now(),
        name: `多边形区域_${rois.length + 1}`,
        type: 'polygon',
        points: drawingPoints,
        color: `hsl(${Math.random() * 360}, 70%, 50%)`
      };
      setROIs([...rois, newROI]);
    }
    setIsDrawing(false);
    setDrawingPoints([]);
  };

  const completeCircle = () => {
    if (arenaConfig?.arena) return;
    if (drawingPoints.length === 2 && drawingPoints[1].radius > 5) {
      saveToHistory();
      const newROI = {
        id: Date.now(),
        name: `圆形区域_${rois.length + 1}`,
        type: 'circle',
        center: drawingPoints[0],
        radius: drawingPoints[1].radius,
        color: `hsl(${Math.random() * 360}, 70%, 50%)`
      };
      setROIs([...rois, newROI]);
    }
    setIsDrawing(false);
    setDrawingPoints([]);
  };

  const transformFromVideoCoords = (points) => {
    if (!videoInfo) return points;
    const scaleX = canvasSize.width / videoInfo.width;
    const scaleY = canvasSize.height / videoInfo.height;
    return points.map(p => ({
      x: p.x * scaleX,
      y: p.y * scaleY
    }));
  };

  const isPointInROI = (point, roi) => {
    if (roi.type === 'rectangle') {
      return point.x >= roi.x && 
             point.x <= roi.x + roi.width && 
             point.y >= roi.y && 
             point.y <= roi.y + roi.height;
    } else if (roi.type === 'circle') {
      const dist = Math.sqrt(
        Math.pow(point.x - roi.center.x, 2) + 
        Math.pow(point.y - roi.center.y, 2)
      );
      return dist <= roi.radius;
    } else if (roi.type === 'polygon' && roi.points.length >= 3) {
      let inside = false;
      const points = roi.points;
      for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
        const xi = points[i].x, yi = points[i].y;
        const xj = points[j].x, yj = points[j].y;
        if (((yi > point.y) !== (yj > point.y)) &&
            (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi)) {
          inside = !inside;
        }
      }
      return inside;
    }
    return false;
  };

  const isROIInsideParent = (childROI, parentROI) => {
    if (childROI.id === parentROI.id) return false;
    
    if (childROI.type === 'rectangle') {
      const corners = [
        { x: childROI.x, y: childROI.y },
        { x: childROI.x + childROI.width, y: childROI.y },
        { x: childROI.x, y: childROI.y + childROI.height },
        { x: childROI.x + childROI.width, y: childROI.y + childROI.height }
      ];
      return corners.every(corner => isPointInROI(corner, parentROI));
    } else if (childROI.type === 'circle') {
      return isPointInROI(childROI.center, parentROI);
    } else if (childROI.type === 'polygon') {
      return childROI.points.every(point => isPointInROI(point, parentROI));
    }
    return false;
  };

  const handleROIDragEnd = (e, draggedROI, index) => {
    const scaleX = videoInfo.width / canvasSize.width;
    const scaleY = videoInfo.height / canvasSize.height;
    
    const newX = e.target.x() * scaleX;
    const newY = e.target.y() * scaleY;
    
    let dx, dy;
    
    if (draggedROI.type === 'rectangle') {
      dx = newX - draggedROI.x;
      dy = newY - draggedROI.y;
    } else if (draggedROI.type === 'circle') {
      dx = newX - draggedROI.center.x;
      dy = newY - draggedROI.center.y;
    } else if (draggedROI.type === 'polygon') {
      const oldCenterX = draggedROI.points.reduce((sum, p) => sum + p.x, 0) / draggedROI.points.length;
      const oldCenterY = draggedROI.points.reduce((sum, p) => sum + p.y, 0) / draggedROI.points.length;
      dx = newX - oldCenterX;
      dy = newY - oldCenterY;
    }
    
    const childROIs = rois.filter(roi => isROIInsideParent(roi, draggedROI));
    
    saveToHistory();
    
    const newROIs = [...rois];
    
    if (draggedROI.type === 'rectangle') {
      newROIs[index] = { ...draggedROI, x: newX, y: newY };
    } else if (draggedROI.type === 'circle') {
      newROIs[index] = { ...draggedROI, center: { x: newX, y: newY } };
    } else if (draggedROI.type === 'polygon') {
      newROIs[index] = {
        ...draggedROI,
        points: draggedROI.points.map(p => ({ x: p.x + dx, y: p.y + dy }))
      };
    }
    
    childROIs.forEach(childROI => {
      const childIndex = rois.findIndex(r => r.id === childROI.id);
      if (childIndex !== -1) {
        if (childROI.type === 'rectangle') {
          newROIs[childIndex] = { 
            ...childROI, 
            x: childROI.x + dx, 
            y: childROI.y + dy 
          };
        } else if (childROI.type === 'circle') {
          newROIs[childIndex] = { 
            ...childROI, 
            center: { x: childROI.center.x + dx, y: childROI.center.y + dy } 
          };
        } else if (childROI.type === 'polygon') {
          newROIs[childIndex] = { 
            ...childROI, 
            points: childROI.points.map(p => ({ x: p.x + dx, y: p.y + dy })) 
          };
        }
      }
    });
    
    setROIs(newROIs);
  };

  const handleTransformEnd = (roi, index, newProps) => {
    saveToHistory();
    const newROIs = [...rois];
    newROIs[index] = { 
      ...roi, 
      x: Math.max(0, newProps.x),
      y: Math.max(0, newProps.y),
      width: Math.max(10, newProps.width),
      height: Math.max(10, newProps.height)
    };
    setROIs(newROIs);
  };

  const [arenaTempX, setArenaTempX] = useState(null);
  const [arenaTempY, setArenaTempY] = useState(null);

  const handleArenaDragMove = (e) => {
    if (!arenaConfig.arena) return;
    setArenaTempX(e.target.x());
    setArenaTempY(e.target.y());
  };

  const handleArenaDragEnd = (e) => {
    if (!arenaConfig.arena) return;
    
    const newX = e.target.x() / canvasSize.width;
    const newY = e.target.y() / canvasSize.height;
    
    setArenaTempX(null);
    setArenaTempY(null);
    
    onArenaChange({
      ...arenaConfig,
      arena: {
        ...arenaConfig.arena,
        x: newX,
        y: newY
      }
    });
  };

  const handleArenaTransformEnd = (e) => {
    if (!arenaConfig.arena) return;
    
    const node = e.target;
    const newWidth = node.width() * node.scaleX();
    const newHeight = node.height() * node.scaleY();
    const newX = node.x();
    const newY = node.y();
    
    node.scaleX(1);
    node.scaleY(1);
    
    onArenaChange({
      ...arenaConfig,
      arena: {
        ...arenaConfig.arena,
        x: newX / canvasSize.width,
        y: newY / canvasSize.height,
        width: newWidth / canvasSize.width,
        height: newHeight / canvasSize.height
      }
    });
  };

  const renderArena = () => {
    if (!arenaConfig?.arena || !videoInfo) return null;
    
    const arena = arenaConfig.arena;
    
    const displayX = arenaTempX !== null ? arenaTempX : arena.x * canvasSize.width;
    const displayY = arenaTempY !== null ? arenaTempY : arena.y * canvasSize.height;
    const arenaWidth = arena.width * canvasSize.width;
    const arenaHeight = arena.height * canvasSize.height;
    
    const elements = [];
    
    elements.push(
      <Rect
        key="arena-main"
        name="arena-main"
        x={displayX}
        y={displayY}
        width={arenaWidth}
        height={arenaHeight}
        stroke={selectedArena ? '#ffffff' : '#ef4444'}
        strokeWidth={selectedArena ? 4 : 3}
        fill="rgba(239, 68, 68, 0.1)"
        draggable={true}
        onDragMove={handleArenaDragMove}
        onDragEnd={handleArenaDragEnd}
        onTransformEnd={handleArenaTransformEnd}
      />
    );
    
    return elements;
  };

  const renderCentroid = () => {
    if (!centroidPosition || viewMode !== 'realtime') return null;
    
    return (
      <>
        <Circle
          x={centroidPosition.x}
          y={centroidPosition.y}
          radius={8}
          fill="#ff0000"
          stroke="#ffffff"
          strokeWidth={3}
        />
        <Circle
          x={centroidPosition.x}
          y={centroidPosition.y}
          radius={3}
          fill="#ffffff"
        />
      </>
    );
  };

  const renderContour = () => {
    if (!contourData || viewMode !== 'realtime') return null;
    
    const points = [];
    contourData.forEach(p => {
      points.push(p.x, p.y);
    });
    
    return (
      <Line
        points={points}
        stroke="#ffff00"
        strokeWidth={3}
        closed={true}
        fill="rgba(255, 255, 0, 0.1)"
        tension={0.5}
        lineCap="round"
        lineJoin="round"
      />
    );
  };

  const renderTrajectory = () => {
    if (trajectoryHistory.length < 2 || viewMode !== 'realtime') return null;
    
    const points = [];
    trajectoryHistory.forEach((point, index) => {
      points.push(point.x, point.y);
    });
    
    return (
      <Line
        points={points}
        stroke="#00ff00"
        strokeWidth={2}
        tension={0.5}
        lineCap="round"
        lineJoin="round"
      />
    );
  };

  const renderROIs = () => {
    return rois.map((roi, index) => {
      const isSelected = selectedROI === index;
      const strokeColor = isSelected ? '#fff' : roi.color;
      const strokeWidth = isSelected ? 3 : 2;

      if (roi.type === 'rectangle') {
        const scaleX = canvasSize.width / videoInfo.width;
        const scaleY = canvasSize.height / videoInfo.height;
        return (
          <Rect
            key={roi.id}
            id={`roi-${roi.id}`}
            x={roi.x * scaleX}
            y={roi.y * scaleY}
            width={roi.width * scaleX}
            height={roi.height * scaleY}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            fill={hslToRgba(roi.color, 0.2)}
            draggable={activeTool === TOOL_TYPES.SELECT}
            onClick={() => setSelectedROI(index)}
            onTap={() => setSelectedROI(index)}
            onDragEnd={(e) => handleROIDragEnd(e, roi, index)}
            onTransformEnd={(e) => {
              const node = e.target;
              const newWidth = node.width() * node.scaleX();
              const newHeight = node.height() * node.scaleY();
              const newX = node.x();
              const newY = node.y();
              
              node.scaleX(1);
              node.scaleY(1);
              
              handleTransformEnd(roi, index, {
                x: newX / scaleX,
                y: newY / scaleY,
                width: newWidth / scaleX,
                height: newHeight / scaleY
              });
            }}
          />
        );
      } else if (roi.type === 'polygon') {
        const displayPoints = transformFromVideoCoords(roi.points);
        const flatPoints = displayPoints.reduce((acc, p) => [...acc, p.x, p.y], []);
        return (
          <Line
            key={roi.id}
            points={flatPoints}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            fill={hslToRgba(roi.color, 0.2)}
            closed
            draggable={activeTool === TOOL_TYPES.SELECT}
            onClick={() => setSelectedROI(index)}
            onTap={() => setSelectedROI(index)}
            onDragEnd={(e) => handleROIDragEnd(e, roi, index)}
          />
        );
      } else if (roi.type === 'circle') {
        const scaleX = canvasSize.width / videoInfo.width;
        const scaleY = canvasSize.height / videoInfo.height;
        return (
          <Circle
            key={roi.id}
            x={roi.center.x * scaleX}
            y={roi.center.y * scaleY}
            radius={roi.radius * Math.min(scaleX, scaleY)}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            fill={hslToRgba(roi.color, 0.2)}
            draggable={activeTool === TOOL_TYPES.SELECT}
            onClick={() => setSelectedROI(index)}
            onTap={() => setSelectedROI(index)}
            onDragEnd={(e) => handleROIDragEnd(e, roi, index)}
          />
        );
      }
      return null;
    });
  };

  const renderDrawingPreview = () => {
    if (!isDrawing || drawingPoints.length === 0) return null;

    const scaleX = canvasSize.width / videoInfo.width;
    const scaleY = canvasSize.height / videoInfo.height;

    if (activeTool === TOOL_TYPES.RECTANGLE && drawingPoints.length === 2) {
      const [start, end] = drawingPoints;
      return (
        <Rect
          x={Math.min(start.x, end.x) * scaleX}
          y={Math.min(start.y, end.y) * scaleY}
          width={Math.abs(end.x - start.x) * scaleX}
          height={Math.abs(end.y - start.y) * scaleY}
          stroke="#00ff00"
          strokeWidth={2}
          dash={[5, 5]}
        />
      );
    } else if (activeTool === TOOL_TYPES.POLYGON) {
      const displayPoints = transformFromVideoCoords(drawingPoints);
      const flatPoints = displayPoints.reduce((acc, p) => [...acc, p.x, p.y], []);
      return (
        <Line
          points={flatPoints}
          stroke="#00ff00"
          strokeWidth={2}
          dash={[5, 5]}
        />
      );
    } else if (activeTool === TOOL_TYPES.CIRCLE && drawingPoints.length === 2) {
      const center = drawingPoints[0];
      return (
        <Circle
          x={center.x * scaleX}
          y={center.y * scaleY}
          radius={drawingPoints[1].radius * Math.min(scaleX, scaleY)}
          stroke="#00ff00"
          strokeWidth={2}
          dash={[5, 5]}
        />
      );
    }
    return null;
  };

  const renderMousePosition = () => {
    if (!mousePosition || !videoInfo) return null;
    
    const scaleX = canvasSize.width / videoInfo.width;
    const scaleY = canvasSize.height / videoInfo.height;
    
    return (
      <Circle
        x={mousePosition.x * scaleX}
        y={mousePosition.y * scaleY}
        radius={5}
        fill="#00ff00"
        stroke="#fff"
        strokeWidth={2}
      />
    );
  };

  const renderCalibrationLine = () => {
    if (!calibrationMode || calibrationPoints.length === 0 || !videoInfo) return null;
    
    const scaleX = canvasSize.width / videoInfo.width;
    const scaleY = canvasSize.height / videoInfo.height;
    
    const elements = [];
    
    calibrationPoints.forEach((point, index) => {
      elements.push(
        <Circle
          key={`cal-point-${index}`}
          x={point.x * scaleX}
          y={point.y * scaleY}
          radius={8}
          fill="#ff6b6b"
          stroke="#fff"
          strokeWidth={2}
        />
      );
    });
    
    if (calibrationPoints.length === 2) {
      elements.push(
        <Line
          key="cal-line"
          points={[
            calibrationPoints[0].x * scaleX,
            calibrationPoints[0].y * scaleY,
            calibrationPoints[1].x * scaleX,
            calibrationPoints[1].y * scaleY
          ]}
          stroke="#ff6b6b"
          strokeWidth={3}
          dash={[10, 5]}
        />
      );
    }
    
    return elements;
  };

  return (
    <div className="main-workspace" ref={containerRef}>
      <div className="view-control-panel">
        <div className="view-mode-toggle">
          <button 
            className={`view-mode-btn ${viewMode === 'realtime' ? 'active' : ''}`}
            onClick={() => setViewMode('realtime')}
          >
            <span className="btn-icon">📹</span>
            <span className="btn-text">实时视图</span>
          </button>
          <button 
            className={`view-mode-btn ${viewMode === 'binary' ? 'active' : ''}`}
            onClick={() => setViewMode('binary')}
          >
            <span className="btn-icon">⚪</span>
            <span className="btn-text">二值化视图</span>
          </button>
        </div>
        <div className="analysis-control">
          <button 
            className={`analysis-btn ${trackingEnabled ? 'analyzing' : ''}`}
            onClick={trackingEnabled ? stopTracking : startTracking}
            disabled={!videoFile || !backgroundPath}
            style={{ opacity: (!videoFile || !backgroundPath) ? 0.5 : 1 }}
          >
            <span className="btn-icon">{trackingEnabled ? '⏹️' : '▶️'}</span>
            <span className="btn-text">{trackingEnabled ? '停止分析' : '开始分析'}</span>
          </button>
        </div>
      </div>
      <div className="video-canvas-container">
        {videoSrc ? (
          <>
            <video
              ref={videoRef}
              src={videoSrc}
              className="video-element"
              onLoadedMetadata={handleVideoLoad}
              onEnded={handleVideoEnded}
              muted
              playsInline
              style={{
                width: canvasSize.width,
                height: canvasSize.height,
                display: viewMode === 'realtime' ? 'block' : 'none'
              }}
            />
            {viewMode === 'binary' && (
              <>
                {previewBinaryFrame ? (
                  <img
                    src={previewBinaryFrame}
                    alt="Binary View"
                    className="binary-frame"
                    style={{
                      width: canvasSize.width,
                      height: canvasSize.height,
                      objectFit: 'fill',
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: 'translate(-50%, -50%)'
                    }}
                  />
                ) : binaryFrame && trackingEnabled ? (
                  <img
                    src={binaryFrame}
                    alt="Binary View"
                    className="binary-frame"
                    style={{
                      width: canvasSize.width,
                      height: canvasSize.height,
                      objectFit: 'fill',
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: 'translate(-50%, -50%)'
                    }}
                  />
                ) : (
                  <div 
                    className="binary-placeholder"
                    style={{
                      width: canvasSize.width,
                      height: canvasSize.height,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: '#1a1a1a',
                      color: '#888',
                      fontSize: '16px',
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: 'translate(-50%, -50%)'
                    }}
                  >
                    <p>正在生成二值化预览...</p>
                  </div>
                )}
              </>
            )}
            <Stage
              ref={stageRef}
              width={canvasSize.width}
              height={canvasSize.height}
              className="canvas-overlay"
              onClick={handleStageClick}
              onDblClick={handleStageDblClick}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
            >
              <Layer>
                {renderArena()}
                {renderROIs()}
                {renderDrawingPreview()}
                {renderTrajectory()}
                {renderMousePosition()}
                {renderContour()}
                {renderCentroid()}
                {renderCalibrationLine()}
                <Transformer
                  ref={transformerRef}
                  boundBoxFunc={(oldBox, newBox) => {
                    if (newBox.width < 10 || newBox.height < 10) {
                      return oldBox;
                    }
                    return newBox;
                  }}
                  enabledAnchors={[
                    'top-left',
                    'top-right',
                    'bottom-left',
                    'bottom-right',
                    'middle-left',
                    'middle-right',
                    'top-center',
                    'bottom-center'
                  ]}
                  rotateEnabled={false}
                />
              </Layer>
            </Stage>
          </>
        ) : (
          <div className="video-placeholder">
            <div className="placeholder-content">
              <span className="placeholder-icon">🎬</span>
              <p className="placeholder-text">请先导入视频文件</p>
              <p className="placeholder-hint">在左侧配置面板中上传视频</p>
            </div>
          </div>
        )}
      </div>

      <PlaybackControls
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        currentTime={currentTime}
        duration={videoInfo?.duration || 0}
        onSeek={handleSeek}
        playbackRate={playbackRate}
        onRateChange={handleRateChange}
        currentFrame={currentFrame}
        totalFrames={videoInfo ? Math.floor((videoInfo.duration || 0) * normalizeFPS(trackingFPS || videoInfo?.fps)) : 0}
        fps={normalizeFPS(trackingFPS || videoInfo?.fps)}
      />
    </div>
  );
};

export default MainWorkspace;
