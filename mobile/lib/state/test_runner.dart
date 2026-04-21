import 'package:flutter/foundation.dart';
import 'package:logging/logging.dart';

import '../backends/backend_error.dart';
import '../backends/cloudflare.dart';
import '../backends/progress_event.dart';
import '../backends/speed_test_backend.dart';
import '../models/connection_info.dart';
import '../models/latency_result.dart';
import '../models/speed_result.dart';

final _log = Logger('TestRunner');

enum TestPhase { idle, connecting, latency, download, upload, done, error }

class TestRunner extends ChangeNotifier {
  TestRunner({SpeedTestBackend? backend})
      : _backend = backend ?? CloudflareBackend();

  final SpeedTestBackend _backend;

  TestPhase _phase = TestPhase.idle;
  ConnectionInfo? _connectionInfo;
  LatencyResult? _latency;
  SpeedResult? _download;
  SpeedResult? _upload;
  double? _liveDownloadMbps;
  double? _liveUploadMbps;
  String? _errorText;

  TestPhase get phase => _phase;
  ConnectionInfo? get connectionInfo => _connectionInfo;
  LatencyResult? get latency => _latency;
  SpeedResult? get download => _download;
  SpeedResult? get upload => _upload;
  double? get liveDownloadMbps => _liveDownloadMbps;
  double? get liveUploadMbps => _liveUploadMbps;
  String? get errorText => _errorText;
  bool get isRunning =>
      _phase != TestPhase.idle &&
      _phase != TestPhase.done &&
      _phase != TestPhase.error;

  Future<void> start() async {
    if (isRunning) return;
    _log.info('Starting test with backend=${_backend.name}');
    _connectionInfo = null;
    _latency = null;
    _download = null;
    _upload = null;
    _liveDownloadMbps = null;
    _liveUploadMbps = null;
    _errorText = null;
    _setPhase(TestPhase.connecting);

    try {
      _connectionInfo = await _backend.connectionInfo();
      _log.info('Connection: ${_connectionInfo!.server} '
          'IP=${_connectionInfo!.ip} ISP=${_connectionInfo!.isp} '
          'Loc=${_connectionInfo!.location}');
      notifyListeners();

      _setPhase(TestPhase.latency);
      _latency = await _backend.testLatency(onProgress: _onProgress);
      _log.info('Latency: avg=${_latency!.avg.toStringAsFixed(1)}ms '
          'jitter=${_latency!.jitter.toStringAsFixed(1)}ms '
          'samples=${_latency!.samples} failed=${_latency!.failed}');
      notifyListeners();

      _setPhase(TestPhase.download);
      _download = await _backend.testDownload(onProgress: _onProgress);
      _liveDownloadMbps = _download!.speedMbps;
      _log.info('Download: ${_download!.speedMbps.toStringAsFixed(2)} Mbps '
          '(${_download!.samples.length} samples)');
      notifyListeners();

      _setPhase(TestPhase.upload);
      _upload = await _backend.testUpload(onProgress: _onProgress);
      _liveUploadMbps = _upload!.speedMbps;
      _log.info('Upload: ${_upload!.speedMbps.toStringAsFixed(2)} Mbps '
          '(${_upload!.samples.length} samples)');
      notifyListeners();

      _setPhase(TestPhase.done);
      _log.info('Test complete');
    } on BackendError catch (e) {
      _log.warning('Backend error: ${e.message}');
      _errorText = e.message;
      _setPhase(TestPhase.error);
    } catch (e) {
      _log.severe('Unexpected error: $e');
      _errorText = e.toString();
      _setPhase(TestPhase.error);
    }
  }

  void cancel() {
    if (!isRunning) return;
    _log.info('Cancel requested');
    _backend.cancel();
  }

  void _onProgress(ProgressEvent event) {
    switch (event) {
      case DownloadProgress(:final speedMbps) ||
            DownloadChunk(:final speedMbps):
        _liveDownloadMbps = speedMbps;
        notifyListeners();
      case UploadProgress(:final speedMbps) || UploadChunk(:final speedMbps):
        _liveUploadMbps = speedMbps;
        notifyListeners();
      case LatencySample():
        notifyListeners();
      case ChunkError():
        // Per-chunk failures are non-fatal; we rely on the final SpeedResult.
        break;
    }
  }

  void _setPhase(TestPhase next) {
    _phase = next;
    notifyListeners();
  }
}
