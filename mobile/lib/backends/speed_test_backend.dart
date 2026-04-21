import '../models/connection_info.dart';
import '../models/latency_result.dart';
import '../models/speed_result.dart';
import 'progress_event.dart';

typedef ProgressCallback = void Function(ProgressEvent event);

abstract class SpeedTestBackend {
  String get name;
  String get displayName;

  bool get isAvailable => true;

  Future<ConnectionInfo> connectionInfo();

  Future<LatencyResult> testLatency({
    int samples = 10,
    ProgressCallback? onProgress,
  });

  Future<SpeedResult> testDownload({ProgressCallback? onProgress});

  Future<SpeedResult> testUpload({ProgressCallback? onProgress});

  void cancel();
}
