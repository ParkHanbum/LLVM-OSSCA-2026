import Foundation
import Vision
import ImageIO

struct Job: Decodable { let id: String; let path: String }
struct Line: Encodable { let text: String; let confidence: Float; let x: Double; let y: Double; let w: Double; let h: Double }
struct Result: Encodable { let id: String; let width: Int; let height: Int; let lines: [Line]; let error: String? }
let jobs = try JSONDecoder().decode([Job].self, from: FileHandle.standardInput.readDataToEndOfFile())
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys]
for job in jobs {
  let result: Result = autoreleasepool {
    do {
      guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: job.path) as CFURL, nil),
            let img = CGImageSourceCreateImageAtIndex(source, 0, nil) else { throw NSError(domain:"image",code:1) }
      let request = VNRecognizeTextRequest()
      request.recognitionLevel = .accurate
      request.usesCPUOnly = true
      request.recognitionLanguages = ["ko-KR", "en-US"]
      request.usesLanguageCorrection = false
      request.minimumTextHeight = 0.003
      try VNImageRequestHandler(cgImage: img, options: [:]).perform([request])
      let lines = (request.results ?? []).compactMap { observation -> Line? in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return Line(text:candidate.string,confidence:candidate.confidence,x:box.minX,y:1-box.maxY,w:box.width,h:box.height)
      }
      return Result(id:job.id,width:img.width,height:img.height,lines:lines,error:nil)
    } catch { return Result(id:job.id,width:0,height:0,lines:[],error:String(reflecting:error)) }
  }
  let data = try encoder.encode(result)
  FileHandle.standardOutput.write(data)
  FileHandle.standardOutput.write(Data([10]))
}
