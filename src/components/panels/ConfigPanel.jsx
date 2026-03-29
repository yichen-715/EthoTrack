import React, { useState, useRef } from 'react';
import BackgroundEditor from '../BackgroundEditor';

const TOOL_TYPES = {
  SELECT: 'select',
  RECTANGLE: 'rectangle',
  POLYGON: 'polygon',
  CIRCLE: 'circle'
};

const AccordionSection = ({ title, icon, children, defaultOpen = false }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="accordion-section">
      <button 
        className={`accordion-header ${isOpen ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="accordion-icon">{icon}</span>
        <span className="accordion-title">{title}</span>
        <span className="accordion-arrow">{isOpen ? '▼' : '▶'}</span>
      </button>
      {isOpen && (
        <div className="accordion-content">
          {children}
        </div>
      )}
    </div>
  );
};

const ConfigPanel = ({
  experimentType,
  subjectInfo,
  setSubjectInfo,
  videoFile,
  setVideoFile,
  videoInfo,
  setVideoInfo,
  timeRange,
  setTimeRange,
  scaleCalibration,
  setScaleCalibration,
  rois,
  setROIs,
  algorithmParams,
  setAlgorithmParams,
  activeTool,
  onToolChange,
  onUndo,
  onClear,
  canUndo,
  calibrationMode,
  setCalibrationMode,
  calibrationPoints,
  setCalibrationPoints,
  onCalibrationComplete,
  arenaConfig,
  onArenaChange
}) => {
  const fileInputRef = useRef(null);
  const [calibrationLength, setCalibrationLength] = useState('');
  const [showBackgroundEditor, setShowBackgroundEditor] = useState(false);
  const [currentBackgroundPath, setCurrentBackgroundPath] = useState(null);

  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (file) {
      setVideoFile(file);
      const url = URL.createObjectURL(file);
      const video = document.createElement('video');
      video.src = url;
      video.onloadedmetadata = async () => {
        const videoWidth = video.videoWidth;
        const videoHeight = video.videoHeight;
        const duration = video.duration;
        let fps = 30;
        
        const formData = new FormData();
        formData.append('video', file);
        
        try {
          const res = await fetch('http://localhost:5000/api/video/upload', {
            method: 'POST',
            body: formData
          });
          const data = await res.json();
          if (data.success && data.video_info) {
            fps = data.video_info.fps || 30;
          }
        } catch (err) {
          console.warn('Failed to get video FPS from backend, using default 30:', err);
        }
        
        setVideoInfo({
          width: videoWidth,
          height: videoHeight,
          duration: duration,
          fps: fps
        });
        setTimeRange({ start: 0, end: duration });
      };
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      setVideoFile(file);
      const url = URL.createObjectURL(file);
      const video = document.createElement('video');
      video.src = url;
      video.onloadedmetadata = async () => {
        const videoWidth = video.videoWidth;
        const videoHeight = video.videoHeight;
        const duration = video.duration;
        let fps = 30;
        
        const formData = new FormData();
        formData.append('video', file);
        
        try {
          const res = await fetch('http://localhost:5000/api/video/upload', {
            method: 'POST',
            body: formData
          });
          const data = await res.json();
          if (data.success && data.video_info) {
            fps = data.video_info.fps || 30;
          }
        } catch (err) {
          console.warn('Failed to get video FPS from backend, using default 30:', err);
        }
        
        setVideoInfo({
          width: videoWidth,
          height: videoHeight,
          duration: duration,
          fps: fps
        });
        setTimeRange({ start: 0, end: duration });
      };
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const removeROI = (id) => {
    setROIs(rois.filter(roi => roi.id !== id));
  };

  const handleCalibrationConfirm = () => {
    if (calibrationPoints.length === 2 && calibrationLength) {
      onCalibrationComplete(calibrationLength);
      setCalibrationLength('');
    }
  };

  return (
    <div className="config-panel">
      <div className="panel-header">
        <h3>配置面板</h3>
        <span className="experiment-badge">{experimentType?.name}</span>
      </div>

      <div className="accordion-container">
        <AccordionSection title="受试体信息" icon="🐭">
          <div className="form-group">
            <label>小鼠编号</label>
            <input
              type="text"
              placeholder="请输入编号，如：M001"
              value={subjectInfo.id}
              onChange={(e) => setSubjectInfo({ ...subjectInfo, id: e.target.value })}
            />
          </div>
        </AccordionSection>

        <AccordionSection title="导入视频" icon="📹">
          <div 
            className="video-drop-zone"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => fileInputRef.current?.click()}
          >
            {videoFile ? (
              <div className="video-info-card">
                <span className="video-icon">🎬</span>
                <div className="video-details">
                  <p className="video-name">{videoFile.name}</p>
                  <p className="video-meta">
                    {videoInfo && `${videoInfo.width}×${videoInfo.height} | ${(videoInfo.duration).toFixed(1)}s`}
                  </p>
                </div>
                <button 
                  className="btn-remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    setVideoFile(null);
                    setVideoInfo(null);
                  }}
                >
                  ✕
                </button>
              </div>
            ) : (
              <div className="drop-hint">
                <span className="drop-icon">📁</span>
                <p>拖拽视频文件到这里</p>
                <p className="drop-sub">或点击选择文件</p>
                <p className="drop-formats">支持 MP4, AVI, MOV 格式</p>
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </AccordionSection>

        <AccordionSection title="时间截取" icon="⏱️">
          <div className="time-range-container">
            <div className="form-group">
              <label>开始时间</label>
              <div className="time-input-group">
                <input
                  type="number"
                  min="0"
                  max={videoInfo?.duration || 0}
                  step="0.1"
                  value={timeRange.start}
                  onChange={(e) => setTimeRange({ ...timeRange, start: parseFloat(e.target.value) })}
                />
                <span className="time-unit">秒</span>
              </div>
            </div>
            <div className="form-group">
              <label>结束时间</label>
              <div className="time-input-group">
                <input
                  type="number"
                  min="0"
                  max={videoInfo?.duration || 0}
                  step="0.1"
                  value={timeRange.end}
                  onChange={(e) => setTimeRange({ ...timeRange, end: parseFloat(e.target.value) })}
                />
                <span className="time-unit">秒</span>
              </div>
            </div>
            <div className="time-preview">
              分析时长：<strong>{(timeRange.end - timeRange.start).toFixed(1)}</strong> 秒
            </div>
            <p className="time-hint">
              💡 提示：建议跳过放入小鼠的前几秒，从行为稳定时开始分析
            </p>
          </div>
        </AccordionSection>

        <AccordionSection title="标尺校对" icon="📏">
          <div className="calibration-container">
            {scaleCalibration ? (
              <div className="calibration-result">
                <div className="calibration-success">
                  <span className="success-icon">✅</span>
                  <p>校对完成</p>
                </div>
                <p className="calibration-value">
                  <strong>{scaleCalibration.pixelsPerCm.toFixed(2)}</strong> 像素/厘米
                </p>
                <button 
                  className="btn btn-secondary btn-small"
                  onClick={() => setScaleCalibration(null)}
                >
                  重新校对
                </button>
              </div>
            ) : (
              <div className="calibration-setup">
                <p className="calibration-hint">
                  在视频画面中画一条已知长度的线段，输入实际长度完成校对
                </p>
                {calibrationMode ? (
                  <div className="calibration-active">
                    <p className="calibration-status">
                      {calibrationPoints.length === 0 ? '点击设置起点' : 
                       calibrationPoints.length === 1 ? '点击设置终点' : 
                       '设置完成'}
                    </p>
                    {calibrationPoints.length === 2 && (
                      <div className="form-group">
                        <label>实际长度 (cm)</label>
                        <input
                          type="number"
                          placeholder="如：50"
                          value={calibrationLength}
                          onChange={(e) => setCalibrationLength(e.target.value)}
                        />
                      </div>
                    )}
                    <div className="calibration-actions">
                      <button 
                        className="btn btn-secondary btn-small"
                        onClick={() => {
                          setCalibrationMode(false);
                          setCalibrationPoints([]);
                        }}
                      >
                        取消
                      </button>
                      {calibrationPoints.length === 2 && calibrationLength && (
                        <button 
                          className="btn btn-primary btn-small"
                          onClick={handleCalibrationConfirm}
                        >
                          确认
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <button 
                    className="btn btn-primary btn-block"
                    onClick={() => setCalibrationMode(true)}
                    disabled={!videoFile}
                  >
                    开始校对
                  </button>
                )}
              </div>
            )}
          </div>
        </AccordionSection>

        <AccordionSection title="旷场区域标定" icon="📐">
          <div className="arena-config">
            {!arenaConfig?.enabled ? (
              <div className="arena-setup">
                <p className="arena-hint">
                  标定实验箱边界后，系统将自动计算中心区和边缘区
                </p>
                <button 
                  className="btn btn-primary btn-block"
                  onClick={() => {
                    onArenaChange({
                      ...arenaConfig,
                      enabled: true,
                      arena: null
                    });
                    onToolChange(TOOL_TYPES.RECTANGLE);
                  }}
                  disabled={!videoFile}
                >
                  开始标定全场区
                </button>
              </div>
            ) : !arenaConfig.arena ? (
              <div className="arena-drawing">
                <div className="arena-status">
                  <span className="status-icon">🎯</span>
                  <p>请在视频画面中绘制全场区边界</p>
                  <p className="status-hint">拖拽绘制一个矩形，贴合实验箱内壁</p>
                </div>
                <button 
                  className="btn btn-secondary btn-small"
                  onClick={() => onArenaChange({ ...arenaConfig, enabled: false })}
                >
                  取消标定
                </button>
              </div>
            ) : (
              <div className="arena-complete">
                <div className="arena-info">
                  <div className="arena-item">
                    <span className="arena-icon">📦</span>
                    <span className="arena-name">全场区</span>
                    <span className="arena-size">
                      {(() => {
                        const videoWidth = videoInfo?.width || 1;
                        const videoHeight = videoInfo?.height || 1;
                        const arenaWidthPx = arenaConfig.arena.width * videoWidth;
                        const arenaHeightPx = arenaConfig.arena.height * videoHeight;

                        if (scaleCalibration) {
                          return `${(arenaWidthPx / scaleCalibration.pixelsPerCm).toFixed(1)} × ${(arenaHeightPx / scaleCalibration.pixelsPerCm).toFixed(1)} cm`;
                        }

                        return `${Math.round(arenaWidthPx)} × ${Math.round(arenaHeightPx)} px`;
                      })()}
                    </span>
                  </div>
                </div>

                <div className="form-group">
                  <label>
                    中心区边长比例
                    <span className="param-value">{arenaConfig.centerRatio}%</span>
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="80"
                    value={arenaConfig.centerRatio}
                    onChange={(e) => onArenaChange({ ...arenaConfig, centerRatio: parseInt(e.target.value) })}
                  />
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={arenaConfig.showCorners}
                      onChange={(e) => onArenaChange({ ...arenaConfig, showCorners: e.target.checked })}
                    />
                    <span>显示角落区</span>
                  </label>
                </div>

                {arenaConfig.showCorners && (
                  <div className="form-group">
                    <label>
                      角落区边长比例
                      <span className="param-value">{arenaConfig.cornerRatio}%</span>
                    </label>
                    <input
                      type="range"
                      min="5"
                      max="50"
                      value={arenaConfig.cornerRatio}
                      onChange={(e) => onArenaChange({ ...arenaConfig, cornerRatio: parseInt(e.target.value) })}
                    />
                  </div>
                )}

                <div className="arena-actions">
                  <button 
                    className="btn btn-secondary btn-small"
                    onClick={() => {
                      onArenaChange({
                        enabled: false,
                        arena: null,
                        centerRatio: 30,
                        showCorners: false,
                        cornerRatio: 10
                      });
                      setROIs(rois.filter(roi => !roi.isAutoGenerated));
                    }}
                  >
                    重新标定
                  </button>
                </div>
              </div>
            )}
          </div>
        </AccordionSection>

        <AccordionSection title="检测设置" icon="⚙️">
          <div className="detection-settings">
            <div className="background-capture-section" style={{ marginBottom: '20px', paddingBottom: '15px', borderBottom: '1px solid #333' }}>
              <h4 style={{ color: '#fff', marginBottom: '10px' }}>📷 背景采集</h4>
              <p className="background-hint" style={{ fontSize: '13px', color: '#aaa', marginBottom: '12px' }}>
                播放视频至没有小鼠的帧，点击拍摄作为背景图像
              </p>
              <div className="button-group" style={{ 
                display: 'flex', 
                flexDirection: 'row', 
                alignItems: 'center', 
                gap: '6px',
                flexWrap: 'nowrap',
                overflow: 'visible'
              }}>
                <button 
                  className="btn btn-primary"
                  onClick={() => {
                    if (window.captureBackgroundFromVideo) {
                      window.onBackgroundCaptured = (path) => {
                        setCurrentBackgroundPath(path);
                        console.log('ConfigPanel received background path:', path);
                      };
                      window.captureBackgroundFromVideo();
                    } else {
                      alert('请先导入视频文件');
                    }
                  }}
                  style={{ 
                    flexShrink: 0,
                    whiteSpace: 'nowrap',
                    padding: '6px 10px',
                    fontSize: '12px'
                  }}
                >
                  <span className="btn-icon">📷</span>
                  拍摄背景
                </button>
                {currentBackgroundPath && (
                  <button 
                    className="btn btn-secondary"
                    onClick={() => setShowBackgroundEditor(true)}
                    style={{
                      backgroundColor: '#3b82f6',
                      color: '#fff',
                      flexShrink: 0,
                      whiteSpace: 'nowrap',
                      padding: '6px 10px',
                      fontSize: '12px'
                    }}
                  >
                    <span className="btn-icon">🎨</span>
                    编辑背景
                  </button>
                )}
              </div>
            </div>

            <div className="threshold-controls">
              <h4 style={{ color: '#fff', marginBottom: '15px' }}>🎯 检测参数</h4>
              
              <div className="form-group">
                <label>
                  二值化阈值
                  <span className="param-value">{algorithmParams.threshold || 50}</span>
                </label>
                <input
                  type="range"
                  min="10"
                  max="150"
                  value={algorithmParams.threshold || 50}
                  onChange={(e) => setAlgorithmParams({
                    ...algorithmParams,
                    threshold: parseInt(e.target.value)
                  })}
                />
                <p className="param-hint">调整背景差分阈值，值越小检测越灵敏</p>
              </div>

              <div className="form-group">
                <label>
                  最小检测面积
                  <span className="param-value">{algorithmParams.minArea || 100}</span>
                </label>
                <input
                  type="range"
                  min="50"
                  max="500"
                  value={algorithmParams.minArea || 100}
                  onChange={(e) => setAlgorithmParams({
                    ...algorithmParams,
                    minArea: parseInt(e.target.value)
                  })}
                />
                <p className="param-hint">过滤小于此面积的噪点</p>
              </div>

              <div className="form-group">
                <label>
                  最大检测面积
                  <span className="param-value">{algorithmParams.maxArea || 10000}</span>
                </label>
                <input
                  type="range"
                  min="1000"
                  max="50000"
                  value={algorithmParams.maxArea || 10000}
                  onChange={(e) => setAlgorithmParams({
                    ...algorithmParams,
                    maxArea: parseInt(e.target.value)
                  })}
                />
                <p className="param-hint">过滤大于此面积的异常检测</p>
              </div>
            </div>
          </div>
        </AccordionSection>
      </div>

      <BackgroundEditor
        isOpen={showBackgroundEditor}
        onClose={() => setShowBackgroundEditor(false)}
        backgroundPath={currentBackgroundPath}
        onBackgroundUpdated={(path) => {
          setCurrentBackgroundPath(path);
          if (window.onBackgroundCaptured) {
            window.onBackgroundCaptured(path);
          }
        }}
      />
    </div>
  );
};

export default ConfigPanel;
