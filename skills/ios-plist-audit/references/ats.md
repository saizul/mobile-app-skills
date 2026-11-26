# App Transport Security (ATS)

ATS requires HTTPS with TLS 1.2+ and forward secrecy for connections made with
URLSession (and therefore Flutter's `http`/`dio` on iOS and React Native `fetch`).

## Keys and severity

| Key | Severity | Notes |
| --- | --- | --- |
| `NSAllowsArbitraryLoads = true` | high | Turns ATS off. App Review asks for a justification. Ignored on iOS 10+ when `NSAllowsArbitraryLoadsInWebContent` or `...ForMedia` is also set (the script reports low then). |
| `NSAllowsArbitraryLoadsInWebContent` | medium | Only for apps that browse arbitrary web pages in WKWebView. |
| `NSAllowsArbitraryLoadsForMedia` | medium | AVFoundation media from arbitrary hosts. |
| `NSAllowsLocalNetworking` | info | Loads to `.local` hosts and IP addresses; fine for LAN devices. |
| `NSExceptionDomains/<host>/NSExceptionAllowsInsecureHTTPLoads` | medium (info for localhost) | Plain HTTP for that host; with `NSIncludesSubdomains` for all subdomains. |
| `NSExceptionMinimumTLSVersion = TLSv1.0/1.1` | medium | Old TLS; fix the server. |
| `NSExceptionRequiresForwardSecrecy = false` | low | Server lacks ECDHE ciphers. |

## Preferred fixes

1. Move the endpoint to HTTPS (Let's Encrypt, a CDN, or a TLS-terminating proxy).
2. If a third-party host is HTTP-only and outside your control, scope an exception to that
   exact domain, without `NSIncludesSubdomains`, and write the reason down for review.
3. Debug-only exceptions (a local dev server): keep them in a Debug-only Info.plist or
   use `NSAllowsLocalNetworking`; never ship `NSAllowsArbitraryLoads` for development
   convenience.

## Minimal scoped exception

```xml
<key>NSAppTransportSecurity</key>
<dict>
  <key>NSExceptionDomains</key>
  <dict>
    <key>legacy-partner.example.com</key>
    <dict>
      <key>NSExceptionAllowsInsecureHTTPLoads</key>
      <true/>
    </dict>
  </dict>
</dict>
```
