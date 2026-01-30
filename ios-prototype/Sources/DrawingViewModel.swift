import SwiftUI

struct DrawingItem: Identifiable, Codable {
    let id: UUID
    let imageData: Data
    let timestamp: Date
    let title: String

    var image: UIImage? {
        UIImage(data: imageData)
    }

    init(image: UIImage, title: String = "Drawing") {
        self.id = UUID()
        self.imageData = image.pngData() ?? Data()
        self.timestamp = Date()
        self.title = title
    }
}

class DrawingViewModel: ObservableObject {
    @Published var drawings: [DrawingItem] = []

    private let drawingsKey = "savedDrawings"

    init() {
        loadDrawings()
    }

    func addDrawing(from image: UIImage, title: String = "Drawing") {
        let drawing = DrawingItem(image: image, title: title)
        drawings.insert(drawing, at: 0)
        saveDrawings()
    }

    func deleteDrawing(_ drawing: DrawingItem) {
        drawings.removeAll { $0.id == drawing.id }
        saveDrawings()
    }

    func clearAllDrawings() {
        drawings.removeAll()
        saveDrawings()
    }

    private func saveDrawings() {
        do {
            let data = try JSONEncoder().encode(drawings)
            UserDefaults.standard.set(data, forKey: drawingsKey)
        } catch {
            print("Failed to save drawings: \(error)")
        }
    }

    private func loadDrawings() {
        guard let data = UserDefaults.standard.data(forKey: drawingsKey) else { return }
        do {
            drawings = try JSONDecoder().decode([DrawingItem].self, from: data)
        } catch {
            print("Failed to load drawings: \(error)")
        }
    }
}

struct ContentView: View {
    @StateObject private var viewModel = DrawingViewModel()

    var body: some View {
        NavigationView {
            List {
                ForEach(viewModel.drawings) { drawing in
                    if let uiImage = drawing.image {
                        NavigationLink(destination: DetailView(image: uiImage, title: drawing.title)) {
                            HStack {
                                Image(uiImage: uiImage)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(height: 100)
                                    .cornerRadius(10)
                                VStack(alignment: .leading) {
                                    Text(drawing.title)
                                        .font(.headline)
                                    Text("\(drawing.timestamp, formatter: itemFormatter)")
                                        .font(.subheadline)
                                        .foregroundColor(.gray)
                                }
                            }
                        }
                    }
                }
                .onDelete(perform: deleteDrawing)
            }
            .navigationTitle("Drawings")
            .navigationBarItems(trailing: Button(action: {
                // Action to add a new drawing
            }) {
                Image(systemName: "plus")
            })
        }
    }

    private func deleteDrawing(at offsets: IndexSet) {
        offsets.map { viewModel.drawings[$0] }.forEach(viewModel.deleteDrawing)
    }
}

struct DetailView: View {
    let image: UIImage
    let title: String

    var body: some View {
        ScrollView {
            VStack {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .cornerRadius(10)
                    .padding()

                Text(title)
                    .font(.title)
                    .padding()

                Spacer()
            }
        }
        .navigationTitle("Drawing Detail")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private let itemFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.dateStyle = .short
    formatter.timeStyle = .short
    return formatter
}()