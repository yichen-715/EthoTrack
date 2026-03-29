import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const StatusIndicator = ({ label, value, icon, color }) => (
  <div className="status-indicator" style={{ borderColor: color }}>
    <div className="status-header">
      <span className="status-icon">{icon}</span>
      <span className="status-label">{label}</span>
    </div>
    <div className="status-value" style={{ color }}>
      {value}
    </div>
  </div>
);

const MetricCard = ({ label, value, unit, trend, icon }) => (
  <div className="metric-card">
    <div className="metric-header">
      <span className="metric-icon">{icon}</span>
      <span className="metric-label">{label}</span>
    </div>
    <div className="metric-body">
      <span className="metric-value">{value}</span>
      <span className="metric-unit">{unit}</span>
    </div>
    {trend !== undefined && (
      <div className={`metric-trend ${trend >= 0 ? 'positive' : 'negative'}`}>
        {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
      </div>
    )}
  </div>
);

const TrajectoryMap = ({ trajectory, arenaConfig, videoInfo, isTracking, showZones }) => {
  const canvasRef = useRef(null);
  
  const canvasSize = useMemo(() => {
    const size = 210;
    return { width: size, height: size };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const { width, height } = canvasSize;
    
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, width, height);
    
    if (!arenaConfig?.arena) {
      ctx.fillStyle = '#666';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('请先设置实验区域', width / 2, height / 2);
      return;
    }
    
    const arena = arenaConfig.arena;
    
    if (showZones) {
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.strokeRect(0, 0, width, height);
      
      const centerRatio = (arenaConfig.centerRatio || 30) / 100;
      const centerWidth = width * centerRatio;
      const centerHeight = height * centerRatio;
      const centerX = (width - centerWidth) / 2;
      const centerY = (height - centerHeight) / 2;
      
      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 1;
      ctx.strokeRect(centerX, centerY, centerWidth, centerHeight);
      
      const showCorners = arenaConfig.showCorners || arenaConfig.hasCorners;
      if (showCorners) {
        const cornerRatio = (arenaConfig.cornerRatio || 20) / 100;
        const cornerWidth = width * cornerRatio;
        const cornerHeight = height * cornerRatio;
        
        const corners = [
          { x: 0, y: 0 },
          { x: width - cornerWidth, y: 0 },
          { x: 0, y: height - cornerHeight },
          { x: width - cornerWidth, y: height - cornerHeight }
        ];
        
        ctx.strokeStyle = '#22c55e';
        ctx.lineWidth = 1;
        corners.forEach(corner => {
          ctx.strokeRect(corner.x, corner.y, cornerWidth, cornerHeight);
        });
      }
    }
    
    if (isTracking && (!trajectory || trajectory.length === 0)) {
      ctx.fillStyle = '#fbbf24';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('采集中...', width / 2, height / 2);
      return;
    }
    
    if (!trajectory || trajectory.length < 2) {
      ctx.fillStyle = '#666';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('暂无轨迹数据', width / 2, height / 2);
      return;
    }
    
    const videoWidth = videoInfo?.width || 1;
    const videoHeight = videoInfo?.height || 1;
    
    const toCanvasX = (x) => {
      const normalizedX = x / videoWidth;
      const arenaNormalizedX = (normalizedX - arena.x) / arena.width;
      return Math.max(0, Math.min(width, arenaNormalizedX * width));
    };
    const toCanvasY = (y) => {
      const normalizedY = y / videoHeight;
      const arenaNormalizedY = (normalizedY - arena.y) / arena.height;
      return Math.max(0, Math.min(height, arenaNormalizedY * height));
    };
    
    ctx.beginPath();
    ctx.strokeStyle = '#4facfe';
    ctx.lineWidth = 1.5;
    
    const firstPoint = trajectory[0];
    ctx.moveTo(toCanvasX(firstPoint.x), toCanvasY(firstPoint.y));
    
    for (let i = 1; i < trajectory.length; i++) {
      const point = trajectory[i];
      ctx.lineTo(toCanvasX(point.x), toCanvasY(point.y));
    }
    ctx.stroke();
    
    ctx.beginPath();
    ctx.arc(toCanvasX(firstPoint.x), toCanvasY(firstPoint.y), 4, 0, Math.PI * 2);
    ctx.fillStyle = '#22c55e';
    ctx.fill();
    
    const lastPoint = trajectory[trajectory.length - 1];
    ctx.beginPath();
    ctx.arc(toCanvasX(lastPoint.x), toCanvasY(lastPoint.y), 4, 0, Math.PI * 2);
    ctx.fillStyle = '#ef4444';
    ctx.fill();
    
  }, [trajectory, arenaConfig, videoInfo, isTracking, showZones, canvasSize]);

  return (
    <canvas 
      ref={canvasRef} 
      width={canvasSize.width} 
      height={canvasSize.height}
      style={{ 
        width: canvasSize.width, 
        height: canvasSize.height,
        borderRadius: '4px',
        border: '1px solid #333'
      }}
    />
  );
};

const TrajectoryChart = ({ trajectory, videoInfo }) => {
  const data = useMemo(() => {
    if (!trajectory || trajectory.length === 0) {
      return {
        labels: [],
        datasets: []
      };
    }

    return {
      labels: trajectory.map((_, i) => i),
      datasets: [
        {
          label: 'X 坐标',
          data: trajectory.map(p => p.x),
          borderColor: 'rgb(255, 99, 132)',
          backgroundColor: 'rgba(255, 99, 132, 0.1)',
          tension: 0.3,
          fill: false
        },
        {
          label: 'Y 坐标',
          data: trajectory.map(p => p.y),
          borderColor: 'rgb(54, 162, 235)',
          backgroundColor: 'rgba(54, 162, 235, 0.1)',
          tension: 0.3,
          fill: false
        }
      ]
    };
  }, [trajectory]);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#fff',
          font: { size: 10 }
        }
      }
    },
    scales: {
      x: {
        display: false
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)'
        },
        ticks: {
          color: '#888',
          font: { size: 10 }
        }
      }
    }
  };

  return (
    <div className="trajectory-chart">
      <Line data={data} options={options} />
    </div>
  );
};

const HeatmapDisplay = ({ trackingData, videoInfo, arenaConfig, trackingId, isTracking }) => {
  const [heatmapImage, setHeatmapImage] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const lastGeneratedIdRef = useRef(null);

  useEffect(() => {
    console.log('[HeatmapDisplay] Props changed:', {
      trackingId,
      trajectoryLength: trackingData?.trajectory?.length,
      isTracking
    });
  }, [trackingId, trackingData?.trajectory?.length, isTracking]);

  useEffect(() => {
    if (isTracking) {
      setHeatmapImage(null);
      lastGeneratedIdRef.current = null;
    }
  }, [isTracking]);

  const generateHeatmap = useCallback(async () => {
    if (!trackingId || !trackingData?.trajectory?.length) {
      console.log('[Heatmap] Missing data:', { trackingId, trajectoryLength: trackingData?.trajectory?.length });
      return;
    }
    if (lastGeneratedIdRef.current === trackingId) {
      console.log('[Heatmap] Already generated for this trackingId');
      return;
    }
    
    console.log('[Heatmap] Starting generation for trackingId:', trackingId);
    setIsGenerating(true);
    lastGeneratedIdRef.current = trackingId;
    try {
      const res = await fetch('http://localhost:5000/api/analysis/heatmap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trackingId,
          bandwidth: 15,
          scaleMode: 'auto',
          maxValue: 10,
          arenaConfig
        })
      });
      const data = await res.json();
      
      console.log('[Heatmap] Response:', data);
      
      if (data.success) {
        setHeatmapImage(data.heatmap);
      }
    } catch (error) {
      console.error('Failed to generate heatmap:', error);
      lastGeneratedIdRef.current = null;
    } finally {
      setIsGenerating(false);
    }
  }, [trackingId, trackingData?.trajectory, arenaConfig]);

  useEffect(() => {
    console.log('[HeatmapDisplay] Auto-generate check:', {
      trackingId,
      trajectoryLength: trackingData?.trajectory?.length,
      isTracking,
      shouldGenerate: trackingId && trackingData?.trajectory?.length > 10 && !isTracking
    });
    if (trackingId && trackingData?.trajectory?.length > 10 && !isTracking) {
      console.log('[HeatmapDisplay] Triggering auto-generate');
      generateHeatmap();
    }
  }, [trackingId, trackingData?.trajectory?.length, isTracking, generateHeatmap]);

  return (
    <div className="heatmap-container">
      <div className="heatmap-display">
        {heatmapImage ? (
          <img 
            src={`data:image/png;base64,${heatmapImage}`} 
            alt="KDE Heatmap"
            className="heatmap-image"
          />
        ) : (
          <div className="heatmap-empty">
            <p>{isGenerating ? '正在生成热力图...' : '暂无热力图数据'}</p>
            <p className="hint">
              {isTracking ? '追踪中...' : 
               !trackingId ? '无追踪ID' : 
               !trackingData?.trajectory?.length ? '无轨迹数据' : 
               `轨迹点: ${trackingData?.trajectory?.length || 0}`}
            </p>
          </div>
        )}
      </div>
      
      <style>{`
        .heatmap-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .heatmap-display {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 200px;
          background: #1a1a2e;
          border-radius: 8px;
          overflow: hidden;
        }
        .heatmap-image {
          max-width: 100%;
          max-height: 300px;
          object-fit: contain;
        }
        .heatmap-empty {
          text-align: center;
          color: #666;
          padding: 40px;
        }
        .heatmap-empty p {
          margin: 4px 0;
        }
        .heatmap-empty .hint {
          font-size: 11px;
          color: #555;
        }
      `}</style>
    </div>
  );
};

const DataPanel = ({
  experimentType,
  trackingData,
  rois,
  currentTime,
  currentFrame,
  isTracking,
  subjectInfo,
  scaleCalibration,
  arenaConfig,
  videoInfo,
  trackingId
}) => {
  const [activeTab, setActiveTab] = useState('trajectory');
  const [isExporting, setIsExporting] = useState(false);
  const [showZones, setShowZones] = useState(true);
  const scrollContainerRef = useRef(null);
  const scrollPositionRef = useRef(0);

  useEffect(() => {
    console.log('[DataPanel] Props:', {
      trackingId,
      trajectoryLength: trackingData?.trajectory?.length,
      isTracking
    });
  }, [trackingId, trackingData?.trajectory?.length, isTracking]);

  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollPositionRef.current;
    }
  }, []);

  const handleScroll = useCallback((e) => {
    scrollPositionRef.current = e.target.scrollTop;
  }, []);

  const metrics = useMemo(() => {
    if (!trackingData) {
      return {
        totalDistance: 0,
        avgSpeed: 0,
        centerTime: 0,
        entries: 0,
        immobilityTime: 0,
        maxSpeed: 0
      };
    }

    const trajectory = trackingData.trajectory || [];
    let totalDistance = 0;
    let speeds = [];
    let immobilityTime = 0;
    let centerTime = 0;
    let centerEntries = 0;
    let wasInCenter = false;

    const isInCenter = (point) => {
      if (!arenaConfig?.arena || !videoInfo) return false;
      
      const arena = arenaConfig.arena;
      const centerRatio = (arenaConfig.centerRatio || 30) / 100;
      
      const videoWidth = videoInfo?.width || 1;
      const videoHeight = videoInfo?.height || 1;
      
      const arenaX = arena.x * videoWidth;
      const arenaY = arena.y * videoHeight;
      const arenaWidth = arena.width * videoWidth;
      const arenaHeight = arena.height * videoHeight;
      
      const centerWidth = arenaWidth * centerRatio;
      const centerHeight = arenaHeight * centerRatio;
      const centerX = arenaX + (arenaWidth - centerWidth) / 2;
      const centerY = arenaY + (arenaHeight - centerHeight) / 2;
      
      return point.x >= centerX && 
             point.x <= centerX + centerWidth &&
             point.y >= centerY && 
             point.y <= centerY + centerHeight;
    };

    for (let i = 1; i < trajectory.length; i++) {
      const prev = trajectory[i - 1];
      const curr = trajectory[i];
      
      const dx = curr.x - prev.x;
      const dy = curr.y - prev.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (scaleCalibration) {
        totalDistance += distance / scaleCalibration.pixelsPerCm;
      } else {
        totalDistance += distance;
      }
      
      const dt = curr.timestamp && prev.timestamp 
        ? (curr.timestamp - prev.timestamp) 
        : (1 / 30);
      
      const speed = distance / dt;
      speeds.push(speed);
      
      if (distance < 1) {
        immobilityTime += dt;
      }
      
      const inCenter = isInCenter(curr);
      if (inCenter) {
        centerTime += dt;
      }
      if (inCenter && !wasInCenter) {
        centerEntries++;
      }
      wasInCenter = inCenter;
    }

    const avgSpeed = speeds.length > 0 
      ? speeds.reduce((a, b) => a + b, 0) / speeds.length 
      : 0;
    const maxSpeed = speeds.length > 0 
      ? Math.max(...speeds) 
      : 0;

    return {
      totalDistance: totalDistance.toFixed(1),
      avgSpeed: avgSpeed.toFixed(1),
      centerTime: centerTime.toFixed(1),
      entries: centerEntries,
      immobilityTime: immobilityTime.toFixed(1),
      maxSpeed: maxSpeed.toFixed(1)
    };
  }, [trackingData, scaleCalibration, arenaConfig, videoInfo]);

  const currentStatus = useMemo(() => {
    if (trackingData?.currentLocation || trackingData?.currentZone || trackingData?.status || trackingData?.currentState) {
      return {
        location: trackingData.currentLocation || trackingData.currentZone || '未知区域',
        state: trackingData.status || trackingData.currentState || '等待追踪'
      };
    }

    if (!trackingData?.trajectory || trackingData.trajectory.length === 0) {
      return {
        location: '未知区域',
        state: '等待追踪'
      };
    }

    const lastPoint = trackingData.trajectory[trackingData.trajectory.length - 1];
    let location = '未知区域';
    
    if (arenaConfig?.arena && videoInfo) {
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
      
      const inArena = lastPoint.x >= arenaX && 
                      lastPoint.x <= arenaX + arenaWidth &&
                      lastPoint.y >= arenaY && 
                      lastPoint.y <= arenaY + arenaHeight;
      
      if (inArena) {
        const centerWidth = arenaWidth * centerRatio;
        const centerHeight = arenaHeight * centerRatio;
        const centerX = arenaX + (arenaWidth - centerWidth) / 2;
        const centerY = arenaY + (arenaHeight - centerHeight) / 2;
        
        const inCenter = lastPoint.x >= centerX && 
                         lastPoint.x <= centerX + centerWidth &&
                         lastPoint.y >= centerY && 
                         lastPoint.y <= centerY + centerHeight;
        
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
            if (lastPoint.x >= corner.x && 
                lastPoint.x <= corner.x + cornerWidth &&
                lastPoint.y >= corner.y && 
                lastPoint.y <= corner.y + cornerHeight) {
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
        if (isPointInROI(lastPoint, roi)) {
          location = roi.name;
          break;
        }
      }
    }

    const prevPoint = trackingData.trajectory[trackingData.trajectory.length - 2];
    const dx = lastPoint.x - (prevPoint?.x || lastPoint.x);
    const dy = lastPoint.y - (prevPoint?.y || lastPoint.y);
    const movement = Math.sqrt(dx * dx + dy * dy);
    
    const state = movement < 2 ? '静止中' : '运动中';

    return { location, state };
  }, [trackingData, rois, arenaConfig, videoInfo]);

  function isPointInROI(point, roi) {
    if (roi.type === 'rectangle') {
      return point.x >= roi.x && 
             point.x <= roi.x + roi.width &&
             point.y >= roi.y && 
             point.y <= roi.y + roi.height;
    } else if (roi.type === 'circle') {
      const distance = Math.sqrt(
        Math.pow(point.x - roi.center.x, 2) + 
        Math.pow(point.y - roi.center.y, 2)
      );
      return distance <= roi.radius;
    }
    return false;
  }

  const handleExport = async () => {
    setIsExporting(true);
    
    try {
      const exportData = {
        experimentType: experimentType?.name,
        subjectInfo,
        rois,
        metrics,
        trackingData,
        scaleCalibration,
        exportTime: new Date().toISOString()
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analysis_report_${subjectInfo.id || 'unknown'}_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="data-panel">
      <div className="panel-header">
        <h3>数据看板</h3>
        <span className={`tracking-status ${isTracking ? 'active' : ''}`}>
          {isTracking ? '追踪中' : '待机'}
        </span>
      </div>

      <div 
        className="scrollable-content" 
        ref={scrollContainerRef}
        onScroll={handleScroll}
      >
        <div className="status-section">
          <StatusIndicator
            label="所在区域"
            value={currentStatus.location}
            icon="📍"
            color="#4facfe"
          />
          <StatusIndicator
            label="当前状态"
            value={currentStatus.state}
            icon="⚡"
            color="#00f260"
          />
        </div>

        <div className="metrics-section">
          <h4 className="section-title">核心指标</h4>
          <div className="metrics-grid">
            <MetricCard
              label="总运动距离"
              value={metrics.totalDistance}
              unit={scaleCalibration ? 'cm' : 'px'}
              icon="📏"
            />
            <MetricCard
              label="平均速度"
              value={metrics.avgSpeed}
              unit={scaleCalibration ? 'cm/s' : 'px/s'}
              icon="⚡"
            />
            <MetricCard
              label="中心区时间"
              value={metrics.centerTime}
              unit="s"
              icon="🎯"
            />
            <MetricCard
              label="穿越次数"
              value={metrics.entries}
              unit="次"
              icon="🔄"
            />
          </div>
        </div>

        <div className="visualization-section">
          <div className="tab-header">
            <button
              className={`tab-btn ${activeTab === 'trajectory' ? 'active' : ''}`}
              onClick={() => setActiveTab('trajectory')}
            >
              轨迹图
            </button>
            <button
              className={`tab-btn ${activeTab === 'heatmap' ? 'active' : ''}`}
              onClick={() => setActiveTab('heatmap')}
            >
              热力图
            </button>
          </div>
          
          <div className="tab-content">
            {activeTab === 'trajectory' ? (
              <div className="trajectory-map-container">
                <div className="trajectory-controls">
                  <label className="zone-toggle">
                    <input 
                      type="checkbox" 
                      checked={showZones} 
                      onChange={(e) => setShowZones(e.target.checked)}
                    />
                    <span>显示区域框</span>
                  </label>
                </div>
                <TrajectoryMap 
                  trajectory={trackingData?.trajectory}
                  arenaConfig={arenaConfig}
                  videoInfo={videoInfo}
                  isTracking={isTracking}
                  showZones={showZones}
                />
              </div>
            ) : (
              <HeatmapDisplay 
                trackingData={trackingData}
                videoInfo={videoInfo}
                arenaConfig={arenaConfig}
                trackingId={trackingId}
                isTracking={isTracking}
              />
            )}
          </div>
        </div>
      </div>

      <style>{`
        .data-panel {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }
        .panel-header {
          flex-shrink: 0;
        }
        .scrollable-content {
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
          scroll-behavior: smooth;
        }
        .scrollable-content::-webkit-scrollbar {
          width: 8px;
        }
        .scrollable-content::-webkit-scrollbar-track {
          background: #1a1a2e;
          border-radius: 4px;
        }
        .scrollable-content::-webkit-scrollbar-thumb {
          background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
          border-radius: 4px;
          min-height: 40px;
        }
        .scrollable-content::-webkit-scrollbar-thumb:hover {
          background: linear-gradient(180deg, #7b8fed 0%, #8a5db3 100%);
        }
        .scrollable-content::-webkit-scrollbar-thumb:active {
          background: linear-gradient(180deg, #8a9ff0 0%, #9a6fc0 100%);
        }
        .trajectory-map-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
        }
        .trajectory-controls {
          display: flex;
          justify-content: flex-end;
          width: 100%;
        }
        .zone-toggle {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #888;
          cursor: pointer;
        }
        .zone-toggle input {
          cursor: pointer;
        }
        .zone-toggle:hover {
          color: #fff;
        }
      `}</style>
    </div>
  );
};

export default DataPanel;
