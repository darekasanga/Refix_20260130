import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  PanResponder,
  TouchableOpacity,
  ScrollView,
  Alert,
  Dimensions,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

const { width, height } = Dimensions.get('window');

export default function App() {
  const [drawings, setDrawings] = useState([]);
  const [currentDrawing, setCurrentDrawing] = useState([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [selectedDrawing, setSelectedDrawing] = useState(null);

  // PanResponder for drawing
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (evt) => {
        const { locationX, locationY } = evt.nativeEvent;
        setIsDrawing(true);
        setCurrentDrawing([{ x: locationX, y: locationY, timestamp: Date.now() }]);
      },
      onPanResponderMove: (evt) => {
        if (!isDrawing) return;
        const { locationX, locationY } = evt.nativeEvent;
        setCurrentDrawing(prev => [
          ...prev,
          { x: locationX, y: locationY, timestamp: Date.now() }
        ]);
      },
      onPanResponderRelease: () => {
        if (currentDrawing.length > 0) {
          const newDrawing = {
            id: Date.now().toString(),
            path: currentDrawing,
            timestamp: new Date(),
            title: `Drawing ${drawings.length + 1}`,
          };
          setDrawings(prev => [newDrawing, ...prev]);
          saveDrawing(newDrawing);
        }
        setCurrentDrawing([]);
        setIsDrawing(false);
      },
    })
  );

  // Load drawings on app start
  useEffect(() => {
    loadDrawings();
  }, []);

  const saveDrawing = async (drawing) => {
    try {
      const filename = `drawing_${drawing.id}.json`;
      const fileUri = FileSystem.documentDirectory + filename;
      await FileSystem.writeAsStringAsync(fileUri, JSON.stringify(drawing));
    } catch (error) {
      console.error('Save error:', error);
    }
  };

  const loadDrawings = async () => {
    try {
      const files = await FileSystem.readDirectoryAsync(FileSystem.documentDirectory);
      const drawingFiles = files.filter(file => file.startsWith('drawing_'));

      const loadedDrawings = [];
      for (const file of drawingFiles) {
        try {
          const fileUri = FileSystem.documentDirectory + file;
          const content = await FileSystem.readAsStringAsync(fileUri);
          const drawing = JSON.parse(content);
          loadedDrawings.push(drawing);
        } catch (error) {
          console.error('Load error for', file, error);
        }
      }

      // Sort by timestamp (newest first)
      loadedDrawings.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setDrawings(loadedDrawings);
    } catch (error) {
      console.error('Load drawings error:', error);
    }
  };

  const deleteDrawing = async (drawingId) => {
    try {
      const filename = `drawing_${drawingId}.json`;
      const fileUri = FileSystem.documentDirectory + filename;
      await FileSystem.deleteAsync(fileUri);
      setDrawings(prev => prev.filter(d => d.id !== drawingId));
      if (selectedDrawing?.id === drawingId) {
        setSelectedDrawing(null);
      }
    } catch (error) {
      console.error('Delete error:', error);
    }
  };

  const exportDrawing = async (drawing) => {
    try {
      const svgContent = generateSVG(drawing);
      const filename = `drawing_${drawing.id}.svg`;
      const fileUri = FileSystem.documentDirectory + filename;

      await FileSystem.writeAsStringAsync(fileUri, svgContent);

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(fileUri, {
          mimeType: 'image/svg+xml',
          dialogTitle: 'Export Drawing',
        });
      }
    } catch (error) {
      Alert.alert('Export Error', 'Failed to export drawing');
    }
  };

  const generateSVG = (drawing) => {
    const paths = drawing.path;
    if (paths.length < 2) return '';

    let pathData = `M ${paths[0].x} ${paths[0].y}`;
    for (let i = 1; i < paths.length; i++) {
      pathData += ` L ${paths[i].x} ${paths[i].y}`;
    }

    return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <path d="${pathData}" stroke="#007AFF" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
  };

  const clearAllDrawings = () => {
    Alert.alert(
      'Clear All Drawings',
      'Are you sure you want to delete all drawings?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear All',
          style: 'destructive',
          onPress: async () => {
            try {
              const files = await FileSystem.readDirectoryAsync(FileSystem.documentDirectory);
              const drawingFiles = files.filter(file => file.startsWith('drawing_'));

              for (const file of drawingFiles) {
                await FileSystem.deleteAsync(FileSystem.documentDirectory + file);
              }

              setDrawings([]);
              setSelectedDrawing(null);
            } catch (error) {
              console.error('Clear all error:', error);
            }
          }
        }
      ]
    );
  };

  return (
    <View style={styles.container}>
      <StatusBar style="auto" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>🎨 Calcu</Text>
        <TouchableOpacity
          style={styles.clearButton}
          onPress={clearAllDrawings}
        >
          <Text style={styles.clearButtonText}>🗑️ Clear All</Text>
        </TouchableOpacity>
      </View>

      {/* Main Content */}
      <View style={styles.mainContent}>
        {/* Sidebar */}
        <View style={styles.sidebar}>
          <TouchableOpacity
            style={styles.newDrawingButton}
            onPress={() => setSelectedDrawing(null)}
          >
            <Text style={styles.newDrawingText}>✏️ New Drawing</Text>
          </TouchableOpacity>

          <ScrollView style={styles.drawingsList}>
            {drawings.map((drawing) => (
              <TouchableOpacity
                key={drawing.id}
                style={[
                  styles.drawingItem,
                  selectedDrawing?.id === drawing.id && styles.selectedDrawingItem
                ]}
                onPress={() => setSelectedDrawing(drawing)}
              >
                <View style={styles.drawingPreview}>
                  <View style={styles.miniCanvas}>
                    {drawing.path.slice(0, 20).map((point, index) => (
                      <View
                        key={index}
                        style={[
                          styles.miniPoint,
                          { left: (point.x / width) * 60, top: (point.y / height) * 40 }
                        ]}
                      />
                    ))}
                  </View>
                </View>
                <View style={styles.drawingInfo}>
                  <Text style={styles.drawingTitle} numberOfLines={1}>
                    {drawing.title}
                  </Text>
                  <Text style={styles.drawingDate}>
                    {new Date(drawing.timestamp).toLocaleDateString()}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.deleteButton}
                  onPress={() => deleteDrawing(drawing.id)}
                >
                  <Text style={styles.deleteButtonText}>🗑️</Text>
                </TouchableOpacity>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* Canvas Area */}
        <View style={styles.canvasArea}>
          {selectedDrawing ? (
            // View Mode
            <View style={styles.viewMode}>
              <View style={styles.viewHeader}>
                <Text style={styles.viewTitle}>{selectedDrawing.title}</Text>
                <TouchableOpacity
                  style={styles.exportButton}
                  onPress={() => exportDrawing(selectedDrawing)}
                >
                  <Text style={styles.exportButtonText}>📤 Export</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.drawingDisplay}>
                <View style={styles.displayCanvas}>
                  {selectedDrawing.path.map((point, index) => {
                    if (index === 0) return null;
                    const prevPoint = selectedDrawing.path[index - 1];
                    const distance = Math.sqrt(
                      Math.pow(point.x - prevPoint.x, 2) + Math.pow(point.y - prevPoint.y, 2)
                    );

                    return (
                      <View
                        key={index}
                        style={[
                          styles.displayPoint,
                          {
                            left: point.x - 1.5,
                            top: point.y - 1.5,
                            width: Math.max(3, distance * 0.1),
                            height: Math.max(3, distance * 0.1),
                          }
                        ]}
                      />
                    );
                  })}
                </View>
              </View>
            </View>
          ) : (
            // Draw Mode
            <View style={styles.drawMode}>
              <Text style={styles.drawInstruction}>
                {isDrawing ? '描画中...' : '画面をタッチして描画を開始'}
              </Text>

              <View
                style={styles.canvas}
                {...panResponder.current.panHandlers}
              >
                {/* Saved drawings (dimmed) */}
                {drawings.slice(0, 3).map((drawing) => (
                  <View key={`bg-${drawing.id}`} style={styles.backgroundDrawing}>
                    {drawing.path.map((point, index) => {
                      if (index === 0) return null;
                      const prevPoint = drawing.path[index - 1];
                      return (
                        <View
                          key={index}
                          style={[
                            styles.backgroundPoint,
                            { left: point.x - 1, top: point.y - 1 }
                          ]}
                        />
                      );
                    })}
                  </View>
                ))}

                {/* Current drawing */}
                {currentDrawing.map((point, index) => {
                  if (index === 0) return null;
                  const prevPoint = currentDrawing[index - 1];
                  return (
                    <View
                      key={`current-${index}`}
                      style={[
                        styles.currentPoint,
                        { left: point.x - 2, top: point.y - 2 }
                      ]}
                    />
                  );
                })}
              </View>

              <View style={styles.stats}>
                <Text style={styles.statsText}>
                  描画数: {drawings.length} | 最新: {drawings.length > 0 ? new Date(drawings[0].timestamp).toLocaleTimeString() : 'なし'}
                </Text>
              </View>
            </View>
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 50,
    paddingBottom: 10,
    backgroundColor: '#007AFF',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: 'white',
  },
  clearButton: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 20,
  },
  clearButtonText: {
    color: 'white',
    fontWeight: '600',
  },
  mainContent: {
    flex: 1,
    flexDirection: 'row',
  },
  sidebar: {
    width: 280,
    backgroundColor: 'white',
    borderRightWidth: 1,
    borderRightColor: '#e0e0e0',
  },
  newDrawingButton: {
    backgroundColor: '#007AFF',
    margin: 15,
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  newDrawingText: {
    color: 'white',
    fontWeight: 'bold',
    fontSize: 16,
  },
  drawingsList: {
    flex: 1,
  },
  drawingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  selectedDrawingItem: {
    backgroundColor: '#e3f2fd',
  },
  drawingPreview: {
    width: 70,
    height: 50,
    backgroundColor: '#f8f9fa',
    borderRadius: 5,
    justifyContent: 'center',
    alignItems: 'center',
  },
  miniCanvas: {
    width: 60,
    height: 40,
    backgroundColor: 'white',
    borderRadius: 3,
  },
  miniPoint: {
    position: 'absolute',
    width: 1,
    height: 1,
    backgroundColor: '#007AFF',
    borderRadius: 0.5,
  },
  drawingInfo: {
    flex: 1,
    marginLeft: 10,
  },
  drawingTitle: {
    fontWeight: '600',
    fontSize: 14,
  },
  drawingDate: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
  deleteButton: {
    padding: 5,
  },
  deleteButtonText: {
    fontSize: 16,
  },
  canvasArea: {
    flex: 1,
    backgroundColor: '#ffffff',
  },
  drawMode: {
    flex: 1,
  },
  drawInstruction: {
    textAlign: 'center',
    fontSize: 18,
    color: '#666',
    marginTop: 20,
    marginBottom: 10,
  },
  canvas: {
    flex: 1,
    backgroundColor: '#fafafa',
    margin: 10,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#e0e0e0',
    borderStyle: 'dashed',
  },
  backgroundDrawing: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  backgroundPoint: {
    position: 'absolute',
    width: 2,
    height: 2,
    backgroundColor: '#cccccc',
    borderRadius: 1,
  },
  currentPoint: {
    position: 'absolute',
    width: 4,
    height: 4,
    backgroundColor: '#007AFF',
    borderRadius: 2,
  },
  stats: {
    padding: 10,
    alignItems: 'center',
  },
  statsText: {
    fontSize: 12,
    color: '#666',
  },
  viewMode: {
    flex: 1,
  },
  viewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  viewTitle: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  exportButton: {
    backgroundColor: '#28a745',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 20,
  },
  exportButtonText: {
    color: 'white',
    fontWeight: '600',
  },
  drawingDisplay: {
    flex: 1,
    padding: 20,
  },
  displayCanvas: {
    flex: 1,
    backgroundColor: '#fafafa',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  displayPoint: {
    position: 'absolute',
    backgroundColor: '#007AFF',
    borderRadius: 1.5,
  },
});