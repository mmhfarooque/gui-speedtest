import Cocoa
import FlutterMacOS

class MainFlutterWindow: NSWindow {
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    self.contentViewController = flutterViewController
    self.title = "Speed Test"
    self.setContentSize(NSSize(width: 800, height: 600))
    self.contentMinSize = NSSize(width: 600, height: 500)
    self.center()

    RegisterGeneratedPlugins(registry: flutterViewController)

    super.awakeFromNib()
  }
}
