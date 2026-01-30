import SwiftUI

struct DrawingRow: View {
    let drawing: DrawingItem

    var body: some View {
        HStack {
            if let image = drawing.image {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 60, height: 60)
                    .cornerRadius(8)
            }

            VStack(alignment: .leading) {
                Text(drawing.title)
                    .font(.headline)
                Text(drawing.timestamp, style: .date)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

struct DrawingCanvas: View {
    let drawing: DrawingItem
    @ObservedObject var viewModel: DrawingViewModel

    @State private var scale: CGFloat = 1.0
    @State private var offset: CGSize = .zero

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Color.gray.opacity(0.1)

                if let image = drawing.image {
                    Image(uiImage: image)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .scaleEffect(scale)
                        .offset(offset)
                        .gesture(
                            MagnificationGesture()
                                .onChanged { value in
                                    scale = value
                                }
                        )
                        .gesture(
                            DragGesture()
                                .onChanged { value in
                                    offset = value.translation
                                }
                        )
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationTitle(drawing.title)
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button(action: shareDrawing) {
                    Label("Share", systemImage: "square.and.arrow.up")
                }

                Button(action: deleteDrawing) {
                    Label("Delete", systemImage: "trash")
                }
                .foregroundColor(.red)
            }
        }
    }

    private func shareDrawing() {
        guard let image = drawing.image else { return }
        let av = UIActivityViewController(activityItems: [image], applicationActivities: nil)
        UIApplication.shared.windows.first?.rootViewController?.present(av, animated: true)
    }

    private func deleteDrawing() {
        viewModel.deleteDrawing(drawing)
    }
}