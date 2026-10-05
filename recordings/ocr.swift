// OCR every image in a folder with Apple's Vision text recognizer; prints one JSON line per image:
// {"file": ..., "lines": [[text, x, y, w, h], ...]} with coordinates normalized (origin top-left).
// usage: swift ocr.swift <folder> > out.jsonl
import Foundation
import Vision
import AppKit

let dir = CommandLine.arguments[1]
let files = (try FileManager.default.contentsOfDirectory(atPath: dir)).filter { $0.hasSuffix(".jpg") || $0.hasSuffix(".png") }.sorted()
for f in files {
    let url = URL(fileURLWithPath: dir).appendingPathComponent(f)
    guard let img = NSImage(contentsOf: url), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    try? h.perform([req])
    var lines: [[Any]] = []
    for o in (req.results ?? []) {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        lines.append([c.string, Double(b.minX), Double(1 - b.maxY), Double(b.width), Double(b.height)])
    }
    let obj: [String: Any] = ["file": f, "lines": lines]
    if let d = try? JSONSerialization.data(withJSONObject: obj), let s = String(data: d, encoding: .utf8) { print(s); fflush(stdout) }
}
