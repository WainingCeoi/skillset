// Apple Vision OCR -> JSON with pixel bounding boxes (top-left origin).
// Usage: swift ocr_vision.swift <image.png> <lang1,lang2,...>
//        swift ocr_vision.swift --list-langs
//
// Pass the languages explicitly and check --list-langs first: for a script
// Vision does NOT support (e.g. Hebrew) it exits 0 and emits confident-looking
// garbage while silently dropping regions — there is no error signal.
import Foundation
import Vision
import AppKit

let args = CommandLine.arguments

if args.count >= 2 && args[1] == "--list-langs" {
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    print(try req.supportedRecognitionLanguages())
    exit(0)
}

guard args.count >= 3 else {
    FileHandle.standardError.write(
        "usage: ocr_vision.swift <image> <lang1,lang2,...>   (or --list-langs)\n".data(using: .utf8)!)
    exit(2)
}
let path = args[1]
let langs = args[2].split(separator: ",").map(String.init)

guard let img = NSImage(contentsOfFile: path),
      let tiff = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: tiff),
      let cg = rep.cgImage
else { FileHandle.standardError.write("cannot load image\n".data(using: .utf8)!); exit(1) }

let W = CGFloat(cg.width), H = CGFloat(cg.height)
var results: [[String: Any]] = []

let req = VNRecognizeTextRequest { r, _ in
    guard let obs = r.results as? [VNRecognizedTextObservation] else { return }
    for o in obs {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox  // normalized, bottom-left origin
        results.append([
            "text": c.string,
            "conf": Double(c.confidence),
            "x": Double(b.origin.x * W),
            "y": Double((1 - b.origin.y - b.size.height) * H),
            "w": Double(b.size.width * W),
            "h": Double(b.size.height * H),
        ])
    }
}
req.recognitionLevel = .accurate
req.recognitionLanguages = langs
req.usesLanguageCorrection = false

try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
let data = try JSONSerialization.data(withJSONObject: results, options: [.prettyPrinted, .sortedKeys])
print(String(data: data, encoding: .utf8)!)
