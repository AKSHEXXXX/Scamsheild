//
//  ShareViewController.swift
//  ScamShieldShareExtension
//
//  Created by akshat saxena on 15/06/26.
//

import UIKit
import Social
import UniformTypeIdentifiers

class ShareViewController: UIViewController {

    override func viewDidLoad() {
        super.viewDidLoad()
        
        guard let item = extensionContext?.inputItems.first as? NSExtensionItem,
              let attachment = item.attachments?.first else {
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
            return
        }

        if attachment.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
            attachment.loadItem(forTypeIdentifier: UTType.url.identifier) { [weak self] data, _ in
                if let url = data as? URL {
                    self?.openApp(with: "url", value: url.absoluteString)
                } else {
                    self?.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                }
            }
        } else if attachment.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
            attachment.loadItem(forTypeIdentifier: UTType.plainText.identifier) { [weak self] data, _ in
                if let text = data as? String {
                    self?.openApp(with: "text", value: text)
                } else {
                    self?.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                }
            }
        } else if attachment.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
            attachment.loadItem(forTypeIdentifier: UTType.image.identifier) { [weak self] data, _ in
                var image: UIImage?
                
                if let url = data as? URL {
                    image = UIImage(contentsOfFile: url.path)
                } else if let imgData = data as? Data {
                    image = UIImage(data: imgData)
                } else if let img = data as? UIImage {
                    image = img
                }
                
                if let image = image {
                    self?.saveImageAndOpenApp(image)
                } else {
                    self?.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                }
            }
        } else {
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
        }
    }

    private func saveImageAndOpenApp(_ image: UIImage) {
        guard let data = image.jpegData(compressionQuality: 0.8),
              let groupURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: "group.com.binaryz.scamshield") else {
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
            return
        }
        
        let filename = "shared_scan_\(UUID().uuidString).jpg"
        let fileURL = groupURL.appendingPathComponent(filename)
        
        do {
            try data.write(to: fileURL)
            self.openApp(with: "file", value: filename)
        } catch {
            print("Failed to write to app group: \(error)")
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
        }
    }

    private func openApp(with key: String, value: String) {
        let encoded = value.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        guard let url = URL(string: "scamshield://scan?\(key)=\(encoded)") else {
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
            return
        }
        _ = self.openURL(url)
        self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
    }

    @discardableResult
    @objc func openURL(_ url: URL) -> Bool {
        var responder: UIResponder? = self
        let selectorOpenURL = sel_registerName("openURL:")

        while responder != nil {
            if responder?.responds(to: selectorOpenURL) == true {
                responder?.perform(selectorOpenURL, with: url)
                return true
            }
            responder = responder?.next
        }
        self.extensionContext?.perform(sel_registerName("openURL:completionHandler:"), with: url, with: nil)
        return true
    }
}
