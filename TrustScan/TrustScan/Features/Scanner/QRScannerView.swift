import SwiftUI
import AVFoundation
import Vision

struct QRScannerView: UIViewControllerRepresentable {
  let onScan: (String) -> Void

  func makeUIViewController(context: Context) -> QRScannerViewController {
    let vc = QRScannerViewController()
    vc.onScan = onScan
    return vc
  }

  func updateUIViewController(_ uiViewController: QRScannerViewController, context: Context) {}
}

class QRScannerViewController: UIViewController, AVCaptureVideoDataOutputSampleBufferDelegate {
  var onScan: ((String) -> Void)?
  
  private var captureSession = AVCaptureSession()
  private var hasScanned = false

  override func viewDidLoad() {
    super.viewDidLoad()
    setupCamera()
  }

  override func viewWillAppear(_ animated: Bool) {
    super.viewWillAppear(animated)
    if !captureSession.isRunning {
      DispatchQueue.global(qos: .userInitiated).async {
        self.captureSession.startRunning()
      }
    }
  }

  override func viewWillDisappear(_ animated: Bool) {
    super.viewWillDisappear(animated)
    if captureSession.isRunning {
      captureSession.stopRunning()
    }
  }

  private func setupCamera() {
    guard let device = AVCaptureDevice.default(for: .video),
          let input = try? AVCaptureDeviceInput(device: device) else { return }
    if captureSession.canAddInput(input) {
      captureSession.addInput(input)
    }

    let output = AVCaptureVideoDataOutput()
    output.setSampleBufferDelegate(self, queue: DispatchQueue(label: "qr.scan"))
    if captureSession.canAddOutput(output) {
      captureSession.addOutput(output)
    }

    let preview = AVCaptureVideoPreviewLayer(session: captureSession)
    preview.frame = view.layer.bounds
    preview.videoGravity = .resizeAspectFill
    view.layer.addSublayer(preview)

    DispatchQueue.global(qos: .userInitiated).async {
      self.captureSession.startRunning()
    }
  }

  func captureOutput(_ output: AVCaptureOutput,
                     didOutput sampleBuffer: CMSampleBuffer,
                     from connection: AVCaptureConnection) {
    guard !hasScanned,
          let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

    let request = VNDetectBarcodesRequest { [weak self] request, _ in
      guard let results = request.results as? [VNBarcodeObservation],
            let barcode = results.first,
            let payload = barcode.payloadStringValue else { return }
      
      self?.hasScanned = true
      self?.captureSession.stopRunning()
      DispatchQueue.main.async {
        self?.onScan?(payload)
      }
    }

    try? VNImageRequestHandler(cvPixelBuffer: pixelBuffer).perform([request])
  }
}
