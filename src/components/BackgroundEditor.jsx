import React, { useState, useRef, useEffect, useCallback } from 'react';

const BackgroundEditor = ({ isOpen, onClose, backgroundPath, onBackgroundUpdated }) => {
  const canvasRef = useRef(null);
  const [brushSize, setBrushSize] = useState(30);
  const [brushHardness, setBrushHardness] = useState(80);
  const [isCloning, setIsCloning] = useState(false);
  const [cloneSource, setCloneSource] = useState(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [backgroundImage, setBackgroundImage] = useState(null);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });

  useEffect(() => {
    if (isOpen && backgroundPath) {
      loadBackgroundImage(backgroundPath);
    }
  }, [isOpen, backgroundPath]);

  const loadBackgroundImage = async (path) => {
    console.log('Loading background image:', path);
    
    if (!path) {
      console.error('No background path provided');
      alert('没有背景图像路径');
      return;
    }
    
    let imageUrl;
    if (path.startsWith('http')) {
      imageUrl = path;
    } else if (path.startsWith('/')) {
      imageUrl = `http://localhost:5000${path}`;
    } else {
      imageUrl = `http://localhost:5000/${path}`;
    }
    
    console.log('Image URL:', imageUrl);
    
    try {
      const response = await fetch(imageUrl, { method: 'HEAD' });
      console.log('Image fetch status:', response.status, response.statusText);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (fetchError) {
      console.error('Failed to fetch image:', fetchError);
      alert(`无法访问背景图像\nURL: ${imageUrl}\n错误: ${fetchError.message}`);
      return;
    }
    
    const img = new Image();
    img.crossOrigin = 'anonymous';
    
    img.onload = () => {
      console.log('Image loaded successfully:', img.width, 'x', img.height);
      const maxWidth = 800;
      const maxHeight = 600;
      let width = img.width;
      let height = img.height;
      
      if (width > maxWidth) {
        height = (maxWidth / width) * height;
        width = maxWidth;
      }
      if (height > maxHeight) {
        width = (maxHeight / height) * width;
        height = maxHeight;
      }
      
      setCanvasSize({ width, height });
      setBackgroundImage(img);
      
      setTimeout(() => {
        const canvas = canvasRef.current;
        if (canvas) {
          const ctx = canvas.getContext('2d');
          canvas.width = width;
          canvas.height = height;
          ctx.drawImage(img, 0, 0, width, height);
          console.log('Image drawn to canvas successfully');
        } else {
          console.error('Canvas ref is null');
        }
      }, 50);
    };
    
    img.onerror = (e) => {
      console.error('Failed to load background image:', path, e);
      console.error('Attempted URL:', imageUrl);
      alert(`背景图像加载失败\nURL: ${imageUrl}\n请检查后端服务是否启动`);
    };
    
    img.src = imageUrl;
  };

  const getCanvasCoords = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  };

  const handleCanvasClick = (e) => {
    if (!isCloning) {
      const coords = getCanvasCoords(e);
      setCloneSource(coords);
      setIsCloning(true);
    }
  };

  const handleMouseDown = (e) => {
    if (isCloning && cloneSource) {
      setIsDrawing(true);
      applyClone(e);
    }
  };

  const handleMouseMove = (e) => {
    if (isDrawing && isCloning) {
      applyClone(e);
    }
  };

  const handleMouseUp = () => {
    setIsDrawing(false);
  };

  const applyClone = (e) => {
    const canvas = canvasRef.current;
    if (!canvas || !cloneSource) return;
    
    const ctx = canvas.getContext('2d');
    const coords = getCanvasCoords(e);
    
    const offsetX = cloneSource.x - coords.x;
    const offsetY = cloneSource.y - coords.y;
    
    const sourceX = coords.x + offsetX;
    const sourceY = coords.y + offsetY;
    
    const hardness = brushHardness / 100;
    const opacity = 0.3 + (hardness * 0.7);
    
    ctx.save();
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = opacity;
    
    ctx.beginPath();
    ctx.arc(coords.x, coords.y, brushSize / 2, 0, Math.PI * 2);
    ctx.clip();
    
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvas.width;
    tempCanvas.height = canvas.height;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(canvas, 0, 0);
    
    ctx.drawImage(
      tempCanvas,
      sourceX - brushSize / 2,
      sourceY - brushSize / 2,
      brushSize,
      brushSize,
      coords.x - brushSize / 2,
      coords.y - brushSize / 2,
      brushSize,
      brushSize
    );
    
    ctx.restore();
  };

  const handleSave = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    canvas.toBlob(async (blob) => {
      const formData = new FormData();
      formData.append('image', blob, 'background_edited.jpg');
      
      try {
        const res = await fetch('http://localhost:5000/api/background/capture', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        
        if (data.success) {
          onBackgroundUpdated(data.background_path);
          onClose();
          alert('背景已更新！');
        }
      } catch (err) {
        console.error('Failed to save background:', err);
        alert('保存失败');
      }
    }, 'image/jpeg', 0.95);
  };

  const handleReset = () => {
    if (backgroundPath) {
      loadBackgroundImage(backgroundPath);
      setCloneSource(null);
      setIsCloning(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="background-editor-overlay" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div className="background-editor-modal" style={{
        backgroundColor: '#1a1a1a',
        borderRadius: '12px',
        padding: '20px',
        maxWidth: '900px',
        maxHeight: '90vh',
        overflow: 'auto'
      }}>
        <div className="editor-header" style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px'
        }}>
          <h3 style={{ color: '#fff', margin: 0 }}>🎨 背景编辑器 - 仿制图章工具</h3>
          <button 
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#fff',
              fontSize: '24px',
              cursor: 'pointer'
            }}
          >
            ×
          </button>
        </div>

        <div className="editor-toolbar" style={{
          display: 'flex',
          gap: '20px',
          marginBottom: '20px',
          padding: '15px',
          backgroundColor: '#2a2a2a',
          borderRadius: '8px'
        }}>
          <div className="tool-group">
            <label style={{ color: '#fff', display: 'block', marginBottom: '5px' }}>
              画笔大小: {brushSize}px
            </label>
            <input
              type="range"
              min="5"
              max="100"
              value={brushSize}
              onChange={(e) => setBrushSize(parseInt(e.target.value))}
              style={{ width: '150px' }}
            />
          </div>

          <div className="tool-group">
            <label style={{ color: '#fff', display: 'block', marginBottom: '5px' }}>
              硬度: {brushHardness}%
            </label>
            <input
              type="range"
              min="10"
              max="100"
              value={brushHardness}
              onChange={(e) => setBrushHardness(parseInt(e.target.value))}
              style={{ width: '150px' }}
            />
          </div>

          <div className="tool-status" style={{ color: '#fff' }}>
            <p style={{ margin: 0 }}>
              状态: {isCloning ? (
                <span style={{ color: '#4ade80' }}>涂抹模式 - 按住鼠标拖动消除小鼠</span>
              ) : (
                <span style={{ color: '#fbbf24' }}>取样模式 - 点击设置采样点</span>
              )}
            </p>
            {cloneSource && (
              <p style={{ margin: '5px 0 0', fontSize: '12px', color: '#888' }}>
                采样点: ({Math.round(cloneSource.x)}, {Math.round(cloneSource.y)})
              </p>
            )}
          </div>
        </div>

        <div className="editor-instructions" style={{
          marginBottom: '15px',
          padding: '10px',
          backgroundColor: '#333',
          borderRadius: '6px',
          color: '#aaa',
          fontSize: '13px'
        }}>
          <strong style={{ color: '#fff' }}>使用说明：</strong>
          <ol style={{ margin: '5px 0 0', paddingLeft: '20px' }}>
            <li>首先在干净区域<strong>点击</strong>设置采样点</li>
            <li>然后在小鼠区域<strong>按住拖动</strong>进行涂抹消除</li>
            <li>调整画笔大小和硬度获得最佳效果</li>
          </ol>
        </div>

        <div className="editor-canvas-container" style={{
          display: 'flex',
          justifyContent: 'center',
          marginBottom: '20px'
        }}>
          <canvas
            ref={canvasRef}
            onClick={handleCanvasClick}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{
              border: '2px solid #444',
              borderRadius: '4px',
              cursor: isCloning ? 'crosshair' : 'pointer',
              maxWidth: '100%'
            }}
          />
        </div>

        <div className="editor-actions" style={{
          display: 'flex',
          gap: '10px',
          justifyContent: 'flex-end'
        }}>
          <button
            onClick={handleReset}
            style={{
              padding: '10px 20px',
              backgroundColor: '#444',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            重置
          </button>
          <button
            onClick={() => { setCloneSource(null); setIsCloning(false); }}
            style={{
              padding: '10px 20px',
              backgroundColor: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            重新取样
          </button>
          <button
            onClick={handleSave}
            style={{
              padding: '10px 20px',
              backgroundColor: '#10b981',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            保存背景
          </button>
        </div>
      </div>
    </div>
  );
};

export default BackgroundEditor;
