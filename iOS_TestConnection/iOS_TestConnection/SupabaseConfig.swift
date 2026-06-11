import Foundation
import Supabase

struct SupabaseConfig {
    static let supabaseURL = URL(string: "https://woudapmpknaqkebfxeck.supabase.co")!
    static let supabaseAnonKey = "sb_publishable_35kZfTKdcUopu1PPXnw21w_7XA3RWZz"
    static let functionURL = URL(string: "https://woudapmpknaqkebfxeck.supabase.co/functions/v1/smart-processor")!

    static let client = SupabaseClient(
        supabaseURL: supabaseURL,
        supabaseKey: supabaseAnonKey
    )

    static func invokeSmartProcessor(payload: [String: Any]) async throws -> Any {
        let response = try await client.functions.invoke(
            functionName: "smart-processor",
            options: FunctionInvokeOptions(body: payload)
        )
        return response
    }
}
