# LeRobot Camera Streaming Test Guide 🎥

## 🔧 **System Overview**

We've implemented a complete camera streaming system that:

1. **Frontend (Vue.js)**:
   - Socket.IO client connects to backend
   - Receives base64-encoded camera frames via Socket.IO
   - Displays frames in real-time in 2x2 grid
   - Automatically starts/stops streams with teleoperation

2. **Backend (Flask + Socket.IO)**:
   - Captures frames from robot cameras or generates test patterns
   - Converts frames to base64 for transmission
   - Streams frames via Socket.IO at configurable FPS
   - Integrates with teleoperation lifecycle

## 🧪 **Testing Steps**

### **1. Start the System**
```bash
# Terminal 1 - Start Backend
cd /home/jannick/PycharmProjects/lerobot/web/backend
python app.py --host 0.0.0.0 --port 5000

# Terminal 2 - Start Frontend  
cd /home/jannick/PycharmProjects/lerobot/web/frontend
npm run dev
```

### **2. Basic Connection Test**
1. Open browser to `http://localhost:5173`
2. Navigate to "Control" tab
3. Look for "Camera Debug Info" section (only visible in development)
4. Check "Socket Connected" status should be `true`

### **3. Manual Camera Stream Test**
1. In the debug section, click "Test Camera Streams" button
2. You should see test pattern frames appear in the camera grid
3. Each camera should show:
   - Camera name in the frame
   - Timestamp updating in real-time
   - Colored rectangles (test pattern)
4. Click "Stop Test Streams" to stop

### **4. Integration Test with Teleoperation**
1. Connect robot with "Demo Default with Cameras" configuration
2. Start teleoperation (should automatically start camera streams)
3. Camera feeds should appear automatically
4. Stop teleoperation (should automatically stop camera streams)

### **5. Error Handling Test**
1. Disconnect backend while streams are running
2. Frontend should show "Offline" status
3. Reconnect backend - streams should resume

## 🐛 **Troubleshooting**

### **Socket Connection Issues**
```javascript
// Check browser console for:
"Socket connected to backend" ✅
"Socket connection error:" ❌

// If connection fails:
1. Verify backend is running on port 5000
2. Check proxy configuration in vite.config.js
3. Verify no firewall blocking connections
```

### **No Camera Frames**
```javascript
// Check browser console for:
"Received camera frame for cam_high" ✅
"Starting camera stream for cam_high" ✅

// If no frames:
1. Check backend logs for camera errors
2. Verify robot.cameras exists and has data
3. Test with manual "Test Camera Streams" button
```

### **Camera Display Issues**
```javascript
// Common fixes:
1. Image load errors → Check base64 format
2. Frame not updating → Check Socket.IO events
3. Wrong camera names → Check backend camera IDs
```

## 📋 **Expected Behavior**

### **With Real Robot + Cameras**
- 4 camera feeds showing real robot view
- Live updating at configured FPS
- "Live" status badges on active cameras

### **Without Cameras (Fallback)**
- Test pattern frames with camera ID and timestamp
- Colored rectangles and text overlay
- Simulated "Live" feed for testing

### **No Robot Connected**
- "No cameras available" message
- Debug info shows empty camera array
- Camera grid shows placeholder cards

## 🔍 **Debug Information**

In development mode, you'll see:
```json
{
  "Available Cameras": ["cam_high", "cam_right_wrist", "cam_left_wrist", "cam_low"],
  "Camera Streams": ["cam_high", "cam_right_wrist"],
  "Socket Connected": true
}
```

## 🚀 **Next Steps After Testing**

1. **Remove debug UI** for production
2. **Add camera quality controls** (resolution, FPS settings)
3. **Implement camera recording** during teleoperation
4. **Add camera calibration tools**
5. **Multi-robot camera support**

## ✅ **Success Criteria**

- [ ] Socket connects automatically when page loads
- [ ] Test streams work with "Test Camera Streams" button
- [ ] Camera feeds start automatically with teleoperation
- [ ] Frame rate is smooth and responsive (no stuttering)
- [ ] Error states are handled gracefully
- [ ] Camera feeds stop cleanly when teleoperation stops

If all criteria pass, the camera streaming system is ready for real robot integration! 🎉
