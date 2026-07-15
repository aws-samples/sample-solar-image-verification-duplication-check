// Save clipboard image (PNG/TIFF) to file — macOS
// Usage: swift temp/save_clipboard.swift <output.png>
import AppKit

let args = CommandLine.arguments
guard args.count > 1 else { print("usage: save_clipboard.swift <out.png>"); exit(1) }
let pb = NSPasteboard.general
guard let data = pb.data(forType: .png) ?? pb.data(forType: .tiff) else {
    print("no image on clipboard"); exit(1)
}
var pngData = data
if pb.data(forType: .png) == nil, let rep = NSBitmapImageRep(data: data),
   let converted = rep.representation(using: .png, properties: [:]) {
    pngData = converted
}
try! pngData.write(to: URL(fileURLWithPath: args[1]))
print("saved \(args[1]) (\(pngData.count) bytes)")
