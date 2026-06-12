import Photos
import AVFoundation

enum PermissionStatus {
  case notDetermined
  case authorized
  case limited
  case denied
  case restricted
}

struct PhotoPermissionManager {
  static var currentStatus: PermissionStatus {
    switch PHPhotoLibrary.authorizationStatus(for: .readWrite) {
    case .notDetermined: return .notDetermined
    case .authorized: return .authorized
    case .limited: return .limited
    case .denied: return .denied
    case .restricted: return .restricted
    @unknown default: return .denied
    }
  }

  static func request() async -> PermissionStatus {
    let status = await PHPhotoLibrary.requestAuthorization(for: .readWrite)
    switch status {
    case .authorized: return .authorized
    case .limited: return .limited
    case .denied: return .denied
    case .restricted: return .restricted
    default: return .denied
    }
  }
}

struct CameraPermissionManager {
  static var currentStatus: PermissionStatus {
    switch AVCaptureDevice.authorizationStatus(for: .video) {
    case .notDetermined: return .notDetermined
    case .authorized: return .authorized
    case .denied: return .denied
    case .restricted: return .restricted
    @unknown default: return .denied
    }
  }

  static func request() async -> Bool {
    await AVCaptureDevice.requestAccess(for: .video)
  }
}
