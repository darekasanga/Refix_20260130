import SwiftUI
import PencilKit

struct DrawingOverlay: View {
    @Environment(\.presentationMode) var presentation
    @StateObject private var canvasVM = CanvasViewModel()

    var onDone: (UIImage) -> Void
    var onCancel: () -> Void

    var body: some View {
        ZStack(alignment: .topTrailing) {
            CanvasView(canvas: canvasVM.canvas)
                .background(.ultraThinMaterial)
                .edgesIgnoringSafeArea(.all)

            HStack(spacing: 12) {
                Button(action: { canvasVM.clear() }) {
                    Label("Clear", systemImage: "trash")
                }
                .buttonStyle(.borderedProminent)

                Button(action: {
                    if let img = canvasVM.exportImage() {
                        onDone(img)
                    }
                }) {
                    Label("Done", systemImage: "checkmark")
                }
                .buttonStyle(.borderedProminent)

                Button(action: {
                    onCancel()
                }) {
                    Label("Cancel", systemImage: "xmark")
                }
                .buttonStyle(.bordered)
            }
            .padding()
        }
    }
}

// MARK: - Canvas UIViewRepresentable
struct CanvasView: UIViewRepresentable {
    let canvas: PKCanvasView

    func makeUIView(context: Context) -> PKCanvasView {
        canvas.isOpaque = false
        canvas.backgroundColor = .clear
        canvas.alwaysBounceVertical = false

        // Tool picker
        if let window = UIApplication.shared.windows.first {
            let toolPicker = PKToolPicker.shared(for: window)
            toolPicker?.setVisible(true, forFirstResponder: canvas)
            toolPicker?.addObserver(canvas)
            canvas.becomeFirstResponder()
        }
        return canvas
    }

    func updateUIView(_ uiView: PKCanvasView, context: Context) {
        // nothing
    }
}

// MARK: - ViewModel
final class CanvasViewModel: ObservableObject {
    let canvas = PKCanvasView()

    func clear() {
        canvas.drawing = PKDrawing()
    }

    func exportImage() -> UIImage? {
        let drawing = canvas.drawing
        guard !drawing.bounds.isEmpty else { return nil }
        let scale = UIScreen.main.scale
        let img = drawing.image(from: drawing.bounds, scale: scale)
        return img
    }
}
